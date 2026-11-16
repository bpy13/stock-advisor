"""Fill and inspect the price store: ``python -m stock_advisor.prices_cli refresh|status``."""
from __future__ import annotations

import argparse
import logging
import time
from datetime import date
from pathlib import Path

import pandas as pd

from stock_advisor import price_compare, price_store
from stock_advisor.price_sources import SOURCES
from stock_advisor.price_sources.futu import QuotaExhausted
from stock_advisor.watchlist import load_watchlist

PAUSE_SECONDS = 0.5
HOURLY_OVERLAP_DAYS = 7  # refetch this much before the last stored hourly bar
log = logging.getLogger(__name__)
# Holdings first, then index funds: Futu's history quota covers a limited number of symbols.
_KIND_ORDER = {"holding": 0, "index_fund": 1}


def _serves(module, item) -> bool:
    """False for symbols a one-market source cannot serve (they are skipped, not failures)."""
    market = getattr(module, "MARKET", None)
    kinds = getattr(module, "ELIGIBLE_KINDS", None)
    return (market is None or item.market == market) and (kinds is None or item.kind in kinds)


def refresh(source: str, intervals: list[str], limit: int | None = None) -> tuple[int, int, int]:
    """Fetch every watchlist symbol into the store. Returns (done, failed, bars added).

    Symbols the source does not serve are skipped and not counted. When Futu's history quota
    runs out the walk stops, and every symbol not yet fetched counts as failed."""
    items = load_watchlist()
    if limit is not None:
        items = items[:limit]
    module = SOURCES[source]
    items = sorted((i for i in items if _serves(module, i)), key=lambda i: _KIND_ORDER.get(i.kind, 2))
    done = failed = added = 0
    jobs = [(interval, item) for interval in intervals for item in items
            if not (interval == "60m" and item.market == "OTHER")]
    for n, (interval, item) in enumerate(jobs):
        stored = price_store.read_bars(item.symbol, interval, adjusted=False, source=source)
        before = len(stored)
        # Hourly bars have no adjusted form, so only recent bars need fetching; a full
        # re-download since 2016 took Alpaca 8 hours a night. Daily stays whole, because
        # the adjusted history changes after every dividend.
        start = None
        if interval == "60m" and before:
            start = stored.index.max() - pd.Timedelta(days=HOURLY_OVERLAP_DAYS)
        try:
            raw, adjusted = module.fetch(item.symbol, interval, start, None)
            if raw.empty:
                raise ValueError("no bars returned")
            price_store.write_bars(source, interval, item.symbol, raw, adjusted)
        except QuotaExhausted:
            waiting = len(jobs) - n
            failed += waiting
            log.warning("%s: history quota used up; %d symbol fetches wait", source, waiting)
            break
        except Exception as exc:  # one bad symbol must not stop the walk
            failed += 1
            # Never log a holding's symbol: the console and logs are not private.
            name = "a holding" if item.kind == "holding" else item.symbol
            log.warning("%s %s failed: %s", name, interval, exc)
        else:
            done += 1
            after = len(price_store.read_bars(item.symbol, interval, adjusted=False, source=source))
            added += after - before
        time.sleep(PAUSE_SECONDS)
    return done, failed, added


def compare(report_dir: Path | None = None) -> Path:
    """Write the per-symbol report, print the per-market totals and the suggested order."""
    symbols = [i.symbol for i in load_watchlist()]
    detail = price_compare.compare_all(symbols)
    if detail.empty:
        raise SystemExit("no symbol is held by two sources yet")
    summary = price_compare.totals(detail)
    today = date.today().isoformat()
    folder = report_dir or Path(__file__).resolve().parent.parent / "data" / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"price-comparison-{today}.md"
    path.write_text(price_compare.report_markdown(detail, summary, today), encoding="utf-8")
    print(summary.to_string(index=False))
    print("suggested order:", price_compare.preferred_order(summary))
    print("report:", path)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prices_cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("refresh", help="fetch the watchlist into the price store")
    r.add_argument("--source", default="yahoo", choices=sorted(SOURCES))
    r.add_argument("--interval", choices=list(price_store.INTERVALS), help="default: both")
    r.add_argument("--limit", type=int, help="only the first N watchlist rows")
    sub.add_parser("status", help="what the store holds, by market (no symbols)")
    sub.add_parser("compare", help="compare Yahoo with Futu (HK) and Alpaca (US)")
    args = parser.parse_args(argv)
    if args.cmd == "compare":
        compare()
    elif args.cmd == "refresh":
        intervals = [args.interval] if args.interval else list(price_store.INTERVALS)
        done, failed, added = refresh(args.source, intervals, args.limit)
        print(f"refresh {args.source}: {done} symbols done, {failed} failed, {added} bars added")
    else:
        table = price_store.status()
        print(table.to_string(index=False) if not table.empty else "store is empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
