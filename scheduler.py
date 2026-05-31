import logging
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from scraper import fetch_upcoming_auctions
from auction_worker import AuctionWorker

NZ_TZ = ZoneInfo("Pacific/Auckland")
TICK_INTERVAL = 60          # seconds between discovery scrapes
OPEN_BEFORE = timedelta(minutes=2)  # how early to open the browser

active_auctions: dict[str, AuctionWorker] = {}
_lock = threading.Lock()


def run_scheduler():
    logging.info("scheduler started")
    while True:
        try:
            _tick()
        except Exception:
            logging.exception("scheduler tick failed")
        time.sleep(TICK_INTERVAL)


def _tick():
    upcoming = fetch_upcoming_auctions()
    now = datetime.now(NZ_TZ)

    with _lock:
        # Spawn workers for auctions that are starting soon.
        # Upper bound (+3h) prevents opening Chrome for past-dated placeholder entries.
        for auction in upcoming:
            if auction.id in active_auctions:
                continue
            if auction.start - OPEN_BEFORE <= now <= auction.start + timedelta(hours=6):
                logging.info(
                    "spawning worker for auction %s (%s) start=%s",
                    auction.id, auction.title, auction.start,
                )
                worker = AuctionWorker(auction)
                worker.start()
                active_auctions[auction.id] = worker

        # Reap workers whose threads have exited
        finished = [aid for aid, w in active_auctions.items() if not w.is_alive()]
        for aid in finished:
            logging.info("reaping finished worker %s", aid)
            del active_auctions[aid]
