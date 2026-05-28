import logging
import os
import threading
import time

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.support.ui import WebDriverWait

INJECT_JS = open(os.path.join(os.path.dirname(__file__), "log script.js")).read()

# JS that returns True once all objects the injected script depends on are ready
_READY_CHECK = """
return typeof biddingsignalr !== 'undefined'
    && typeof biddingsignalr.turnersconnection !== 'undefined'
    && typeof biddingui !== 'undefined'
    && typeof biddingui.serverResponses !== 'undefined'
    && typeof biddingui.goodNumber !== 'undefined'
    && typeof common !== 'undefined'
    && typeof $ === 'function';
"""

# TODO: tune these selectors/regexes after observing a real ended auction
_END_CHECK = """
return !!document.querySelector('.auction-ended, .no-more-lots, .auction-complete')
    || /auction\\s*(ended|complete|finished|closed)/i.test(
           document.body.innerText.slice(0, 8000));
"""

PROBE_INTERVAL = 15        # seconds between liveness probes
IDLE_BAIL_SECONDS = 90 * 60  # quit if no lot change seen for 90 minutes


class AuctionWorker(threading.Thread):
    def __init__(self, auction):
        super().__init__(daemon=True, name=f"AuctionWorker-{auction.id}")
        self.auction = auction
        self.driver = None
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        try:
            self._open_browser()
            self._wait_for_bidding_objects(timeout=120)
            self._inject_logger()
            self._main_loop()
        except Exception:
            logging.exception("worker %s crashed", self.auction.id)
        finally:
            self._cleanup()

    # ------------------------------------------------------------------

    def _open_browser(self):
        opts = webdriver.ChromeOptions()
        # Separate profile per auction so concurrent Chromes don't share a lock.
        # If Turners requires login, log in once manually in this dir; cookies persist.
        profile_dir = f"/tmp/turners-profile-{self.auction.id}"
        opts.add_argument(f"--user-data-dir={profile_dir}")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--window-size=1280,900")
        # Disable CORS so the injected script can POST to http://localhost:5000
        # from the https://www.turners.co.nz origin without being blocked.
        opts.add_argument("--disable-web-security")
        opts.add_argument("--allow-running-insecure-content")
        # Not headless — Turners may block headless agents and bidding JS can
        # need a visible window to fully initialise.
        self.driver = webdriver.Chrome(options=opts)
        logging.info("opened browser for auction %s → %s", self.auction.id, self.auction.url)
        self.driver.get(self.auction.url)

    def _wait_for_bidding_objects(self, timeout):
        logging.info("waiting for bidding objects on %s (up to %ss)", self.auction.id, timeout)
        WebDriverWait(self.driver, timeout, poll_frequency=1.0).until(
            lambda d: d.execute_script(_READY_CHECK) is True
        )
        logging.info("bidding objects ready for %s", self.auction.id)

    def _inject_logger(self):
        for attempt in range(2):
            try:
                result = self.driver.execute_script(INJECT_JS)
                logging.info("injected logger into %s: %s", self.auction.id, result)
                return
            except WebDriverException:
                if attempt == 0:
                    logging.warning("inject failed on %s, retrying in 5s", self.auction.id)
                    time.sleep(5)
                else:
                    raise

    def _main_loop(self):
        last_lot_seen = time.time()
        last_good = None

        while not self._stop.is_set():
            try:
                installed = self.driver.execute_script(
                    "return window.__turnersLoggerInstalled === true;"
                )
                if not installed:
                    # Page reloaded or navigated — re-attach
                    logging.info("logger gone on %s (page reload?), re-injecting", self.auction.id)
                    self._wait_for_bidding_objects(timeout=60)
                    self._inject_logger()
                    last_lot_seen = time.time()
                    last_good = None
                    self._stop.wait(PROBE_INTERVAL)
                    continue

                state = self.driver.execute_script(
                    "return {good: biddingui.goodNumber, ended: (%s)};" % _END_CHECK.strip()
                )

                if state.get("ended"):
                    logging.info("auction %s detected as ended", self.auction.id)
                    break

                if state.get("good") and state["good"] != last_good:
                    last_good = state["good"]
                    last_lot_seen = time.time()

                if time.time() - last_lot_seen > IDLE_BAIL_SECONDS:
                    logging.warning(
                        "auction %s idle for >90 min with no lot change, exiting",
                        self.auction.id,
                    )
                    break

            except WebDriverException:
                logging.exception("driver error in worker %s — exiting", self.auction.id)
                break

            self._stop.wait(PROBE_INTERVAL)

    def _cleanup(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
        logging.info("worker %s finished", self.auction.id)
