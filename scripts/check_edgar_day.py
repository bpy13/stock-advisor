"""Live check for Task 6.1: fetch one past day of 8-Ks for the whole US watchlist.

Needs SEC_CONTACT_EMAIL in .env. Usage: python scripts/check_edgar_day.py 2026-11-12
Prints the ticker count, the tickers without a CIK (in the log), filings found, items seen,
and the request count (the SEC limit is 10 a second; the adapter keeps under 7).
"""
from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone

from stock_advisor.news.collect import build_sources


def main(day: str) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    edgar = {s.name: s for s in build_sources([])}["edgar"]
    moment = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    started = time.time()
    items = list(edgar.fetch_range(moment, moment))
    seconds = time.time() - started
    print(f"tickers {len(edgar._tickers)}, CIKs {len(edgar.allowlist())}, filings {len(items)}")
    print(f"companies {len({tuple(i.symbols) for i in items})}, with items {sum(bool(i.event_items) for i in items)}")
    for item in items[:5]:
        print(item.symbols, item.event_items, item.title[:70])
    print(f"{seconds:.1f} s")
    return 0 if items else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
