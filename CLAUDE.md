# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a two-part Turners Auctions live bid tracker. A JavaScript snippet is pasted into the browser console on a Turners auction page; it intercepts WebSocket events and lot data, then POSTs them to a local Flask server that stores everything in SQLite and serves a simple HTML dashboard.

## Running

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py          # starts Flask + scheduler; Ctrl-C to stop
```

The Flask dashboard runs on `http://localhost:5000`. The SQLite database (`main.db`) is created automatically on first run.

To test the scraper standalone:

```bash
python scraper.py
```

## Architecture

The system is three cooperating layers:

**`main.py`** — entry point. Starts the Flask app in a daemon thread, waits 1 s for it to bind, then runs the scheduler loop (blocks until Ctrl-C).

**`scraper.py`** — fetches the auctions listing page with `requests`+`BeautifulSoup` (no browser needed) and returns a list of `Auction(id, url, start, title)`. Run standalone to verify selectors against the live page. The CSS selectors and date-parsing regex have `# TODO` markers that may need tuning when first run against the real site.

**`scheduler.py`** — loops every 60 s. Opens a Chrome worker 2 minutes before each auction's scheduled start. Reaps finished workers on each tick. Uses a `threading.Lock`-guarded `active_auctions` dict.

**`auction_worker.py`** — one `threading.Thread` per live auction, each owning its own `WebDriver`. Lifecycle:
1. Open Chrome with a per-auction `--user-data-dir` (persistent cookies — log in manually once if Turners requires it).
2. Poll every 1 s (up to 120 s) until `biddingsignalr`, `biddingui`, `common`, and `$` are all defined.
3. Inject `log script.js` via `driver.execute_script()`.
4. Probe every 15 s: re-inject if the guard flag is gone (page reload), detect auction end via DOM/text check, bail out after 90 min of no lot changes.

**`log script.js`** — wrapped in an IIFE with a `window.__turnersLoggerInstalled` guard so it's safe to inject more than once. Returns `"ok"` or `"already-installed"` to the Python caller. Hooks `biddingsignalr.turnersconnection` for live WS events and overrides `biddingui.serverResponses.receiveGood` for lot transitions.

**`logger.py`** — Flask + SQLAlchemy backend (unchanged logic):
- `POST /` — receives `{logtype, data, id}` payloads and routes to `ws()` or `lot()`.
- `GET /` — renders an HTML table of all tracked cars; append `?photos` to show thumbnail images.
- `GET /heartbeat` — liveness probe used by workers before injecting.
- `GET /dbtest` — sanity-checks the DB connection.

**WebSocket message types handled** (from `packageType` constants in the JS file):
- Type 7 (`AskingBid`) — updates `cars.price` with the asking bid.
- Type 8 (`Bid`) — scans all bids in `data.obj`, finds the highest `cbid`, and updates `cars.price`.
- Type 9 (`ReserveMet`) — sets `cars.sold = 1`.

**`Car` model fields:** `id`, `name`, `desc`, `json` (image array as JSON string), `sold` (0/1), `price` (integer cents, split on `.`), `uuid` (the auction lot number / `biddingui.goodNumber`).

## Notes

- Chrome is **not** run headless — Turners may block headless user-agents and the bidding JS can require a visible window to initialise.
- Selenium 4's built-in Selenium Manager auto-downloads a matching `chromedriver`; no manual install needed.
- If chromedriver processes leak after a hard kill: `pkill -f chromedriver`.

## Finding upcoming auctions

Upcoming damaged-vehicle auctions are listed at `https://www.turners.co.nz/Damaged-Vehicles/Auctions/` as an HTML page.
