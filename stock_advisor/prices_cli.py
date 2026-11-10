"""Fill and inspect the price store: ``python -m stock_advisor.prices_cli refresh|status``."""
from __future__ import annotations

import argparse
import logging
import time

from stock_advisor import price_store
from stock_advisor.price_sources import SOURCES
from stock_advisor.watchlist import load_watchlist

PAUSE_SECONDS = 0.5
log = logging.getLogger(__name__)


def refresh(source: str, intervals: list[str], limit: int | None = None) -> tuple[int, int, int]:
    """Fetch every watchlist symbol into the store. Returns (done, failed, bars added)."""
    items = load_watchlist()
    if limit is not None:
        items = items[:limit]
    module = SOURCES[source]
    done = failed = added = 0
    for interval in intervals:
        for item in items:
            if interval == "60m" and item.market == "OTHER":
                continue
            before = len(price_store.read_bars(item.symbol, interval, adjusted=False, source=source))
            try:
                raw, adjusted = module.fetch(item.symbol, interval, None, None)
                if raw.empty:
                    raise ValueError("no bars returned")
                price_store.write_bars(source, interval, item.symbol, raw, adjusted)
            except Exception as exc:  # one bad symbol must not stop the walk
                failed += 1
                log.warning("%s %s failed: %s", item.symbol, interval, exc)
            else:
                done += 1
                after = len(price_store.read_bars(item.symbol, interval, adjusted=False, source=source))
                added += after - before
            time.sleep(PAUSE_SECONDS)
    return done, failed, added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prices_cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("refresh", help="fetch the watchlist into the price store")
    r.add_argument("--source", default="yahoo", choices=sorted(SOURCES))
    r.add_argument("--interval", choices=list(price_store.INTERVALS), help="default: both")
    r.add_argument("--limit", type=int, help="only the first N watchlist rows")
    sub.add_parser("status", help="what the store holds, by market (no symbols)")
    args = parser.parse_args(argv)
    if args.cmd == "refresh":
        intervals = [args.interval] if args.interval else list(price_store.INTERVALS)
        done, failed, added = refresh(args.source, intervals, args.limit)
        print(f"refresh {args.source}: {done} symbols done, {failed} failed, {added} bars added")
    else:
        table = price_store.status()
        print(table.to_string(index=False) if not table.empty else "store is empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
