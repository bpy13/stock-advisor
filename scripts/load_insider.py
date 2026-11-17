"""Load US insider trades (Form 4) for the US watchlist into the news database.

  python scripts/load_insider.py --history [--from-year 2006]   # quarterly SEC data sets
  python scripts/load_insider.py --day 2026-11-14                # one day's live filings

The history run is long (about 80 zips): queue it with jobq.ps1 in the cpu lane. It is
resumable: a quarter already loaded is skipped by the unique (accession, line) key, and zips
stay in data/cache/news/insider/. The log ends with rows per year.
Needs SEC_CONTACT_EMAIL in .env (the SEC's fair-access rule).
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, datetime
from pathlib import Path

from stock_advisor.news.settings import DEFAULT_DB_PATH, NEWS_CACHE_DIR, sec_contact_email
from stock_advisor.news.sources import PoliteSession
from stock_advisor.news.sources.edgar import EdgarSource
from stock_advisor.news.sources.insider import (
    DATASET_URL,
    FIRST_YEAR,
    InsiderTrades,
    fetch_day,
    parse_dataset_zip,
)
from stock_advisor.watchlist import load_watchlist

log = logging.getLogger("load_insider")


def us_symbols() -> list[str]:
    return [i.symbol for i in load_watchlist() if i.market == "US" and i.kind in ("stock", "holding")]


def download(http: PoliteSession, url: str, target: Path) -> bool:
    """Fetch one zip to `target` (kept for reruns). False when the SEC has no such file yet."""
    if target.exists():
        return True
    try:
        response = http.get(url, stream=True)
    except Exception as exc:  # the current quarter is not published until it ends
        log.warning("no data set at %s: %s", url, exc)
        return False
    partial = target.with_suffix(".part")
    with partial.open("wb") as out:
        for chunk in response.iter_content(1 << 20):
            out.write(chunk)
    partial.replace(target)
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--history", action="store_true")
    ap.add_argument("--from-year", type=int, default=FIRST_YEAR)
    ap.add_argument("--day", help="YYYY-MM-DD: load that day's live filings")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    ap.add_argument("--cache", type=Path, default=NEWS_CACHE_DIR / "insider")
    args = ap.parse_args()
    if not (args.history or args.day):
        ap.error("give --history or --day")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    email = sec_contact_email()
    if not email:
        log.error("SEC_CONTACT_EMAIL is not set; the SEC requires a contact in the User-Agent")
        return 2
    http = PoliteSession(user_agent=f"stock_advisor {email}", min_delay=0.15)
    symbols = us_symbols()
    args.cache.mkdir(parents=True, exist_ok=True)
    with InsiderTrades(args.db) as table:
        if args.history:
            today = date.today()
            for year in range(args.from_year, today.year + 1):
                for quarter in range(1, 5):
                    if (year, quarter) > (today.year, (today.month - 1) // 3 + 1):
                        break
                    zip_path = args.cache / f"{year}q{quarter}_form345.zip"
                    if download(http, DATASET_URL.format(year=year, quarter=quarter), zip_path):
                        added = table.add(parse_dataset_zip(zip_path, symbols))
                        log.info("%dq%d: %d new rows", year, quarter, added)
        if args.day:
            day = datetime.strptime(args.day, "%Y-%m-%d").date()
            allow = EdgarSource(tickers=symbols, email=email, session=http).allowlist()
            log.info("%s: %d new rows", day, table.add(fetch_day(http, day, allow)))
        log.info("rows per trade year: %s", table.rows_per_year())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
