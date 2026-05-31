import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

LISTING_URL = "https://www.turners.co.nz/Damaged-Vehicles/Auctions/"
# Live bidding page URL — apid comes from data-pageid on the listing button
LIVE_URL_TEMPLATE = "https://www.turners.co.nz/Turners-Live/Turners-Live/?apid={apid}&div=Damaged"
NZ_TZ = ZoneInfo("Pacific/Auckland")
BASE_URL = "https://www.turners.co.nz"


@dataclass
class Auction:
    id: str        # catalogue slug, e.g. "1002-79918"
    apid: str      # page id used for the live bidding URL, e.g. "671401"
    url: str       # live bidding URL
    catalogue_url: str  # catalogue listing URL
    start: datetime
    title: str


def fetch_upcoming_auctions() -> list[Auction]:
    try:
        resp = requests.get(
            LISTING_URL,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException:
        logging.exception("failed to fetch auction listing")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    auctions = []

    for row in soup.select("div.event-row"):
        link_tag = row.select_one(".event-title a")
        btn = row.select_one(".view-live-button")
        if not link_tag or not btn:
            continue

        apid = btn.get("data-pageid", "").strip()
        if not apid:
            continue

        href = link_tag["href"]
        catalogue_url = BASE_URL + href if not href.startswith("http") else href
        live_url = LIVE_URL_TEMPLATE.format(apid=apid)

        slug_match = re.search(r"/Auctions/([^/]+)/?$", href, re.I)
        auction_id = slug_match.group(1) if slug_match else apid

        # Date: "01 Jun", Time: "08:30am" — strip icon spans
        date_cell = row.select_one(".event-date")
        time_cell = row.select_one(".event-time")
        if not date_cell or not time_cell:
            logging.warning("no date/time cells for auction %s, skipping", auction_id)
            continue

        date_str = _cell_text(date_cell)
        time_str = _cell_text(time_cell)

        if not date_str:
            logging.warning("empty date for auction %s, skipping", auction_id)
            continue

        # "Today" / "Tomorrow" — replace with an unambiguous date string
        now_nz = datetime.now(NZ_TZ)
        dl = date_str.strip().lower()
        if dl == "today":
            date_str = now_nz.strftime("%d %b")
        elif dl == "tomorrow":
            date_str = (now_nz + timedelta(days=1)).strftime("%d %b")

        # "-" means time not published yet; default to midnight so the auction
        # is still discovered and the scheduler can open the browser on time.
        if not time_str or time_str.strip() == "-":
            time_str = "12:00am"

        try:
            start = dateparser.parse(
                f"{date_str} {time_str} {now_nz.year}",
                dayfirst=True,
            ).replace(tzinfo=NZ_TZ)
        except Exception:
            logging.warning("could not parse date '%s %s' for auction %s", date_str, time_str, auction_id)
            continue

        title = link_tag.get_text(strip=True)
        auctions.append(Auction(
            id=auction_id,
            apid=apid,
            url=live_url,
            catalogue_url=catalogue_url,
            start=start,
            title=title,
        ))
        logging.info("found auction %s (apid=%s): %s @ %s", auction_id, apid, title, start)

    return auctions


def _cell_text(cell) -> str:
    for span in cell.find_all("span"):
        span.decompose()
    return cell.get_text(strip=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    results = fetch_upcoming_auctions()
    print(f"\n{len(results)} auctions found:\n")
    for a in results:
        print(f"  {a.start.strftime('%a %d %b %H:%M')}  {a.title}")
        print(f"    id={a.id}  apid={a.apid}")
        print(f"    live: {a.url}")
