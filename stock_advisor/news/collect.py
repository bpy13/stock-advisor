"""Collector CLI: pull news from every source into the SQLite store.

    python -m stock_advisor.news.collect --recent
    python -m stock_advisor.news.collect --backfill --source guardian --start 2020-01-01

`--recent` calls every source's `fetch_recent`. `--backfill` calls one source's `fetch_range`
and resumes from the newest date that backfill reached (a cursor kept in the store). A source that fails is
logged and skipped; the others carry on. Sources with a daily call cap (Guardian, NYT) stop
cleanly when the cap is reached and continue from the last stored date on the next run.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional, Sequence

import requests

from stock_advisor.news.models import NewsItem, SourceLimitReached, ensure_utc
from stock_advisor.news.store import NewsStore

logger = logging.getLogger(__name__)

# Both APIs allow 500 calls a day; 480 leaves room for manual calls.
DAILY_CALL_BUDGETS: Dict[str, int] = {"guardian": 480, "nyt": 480}
BATCH_SIZE = 200  # items written to the store at a time during a backfill


@dataclass
class SourceResult:
    """What one source did in one run."""

    name: str
    fetched: int = 0
    new: int = 0
    status: str = "ok"  # "ok", "limit" (stopped at a cap) or "failed"
    error: str = ""


def holdings_symbols() -> List[str]:
    """Symbols in the user's portfolio, or [] when none can be read. Never printed."""
    try:
        from stock_advisor.report import resolve_symbols_and_portfolio

        symbols, portfolio = resolve_symbols_and_portfolio()
    except Exception as exc:  # no portfolio file must not stop news collection
        logger.warning("Could not read holdings (%s)", type(exc).__name__)
        return []
    return list(symbols) if portfolio is not None else []


def build_sources(holdings: Iterable[str] = ()) -> list:
    """One instance of every working adapter. `holdings` widen the Yahoo symbol list and the
    EDGAR allowlist."""
    from stock_advisor.news.sources.edgar import DEFAULT_TICKERS, EdgarSource
    from stock_advisor.news.sources.gdelt import GdeltSource
    from stock_advisor.news.sources.guardian import GuardianSource
    from stock_advisor.news.sources.nyt import NytSource
    from stock_advisor.news.sources.rss_feeds import RssFeedsSource
    from stock_advisor.news.sources.wikipedia_events import WikipediaEventsSource
    from stock_advisor.news.sources.yahoo import DEFAULT_SYMBOLS, YahooNewsSource

    holdings = list(holdings)
    # EDGAR lists US companies only: skip index symbols and exchange-suffixed tickers (0700.HK).
    us_holdings = [s for s in holdings if "." not in s and not s.startswith("^")]
    return [
        WikipediaEventsSource(),
        GdeltSource(),
        GuardianSource(),
        NytSource(),
        YahooNewsSource(symbols=list(dict.fromkeys(DEFAULT_SYMBOLS + holdings))),
        EdgarSource(tickers=list(dict.fromkeys([*DEFAULT_TICKERS, *us_holdings]))),
        RssFeedsSource(),
    ]


def attach_budget(source, store: NewsStore, budgets: Dict[str, int]) -> None:
    """Give a capped source a hook that counts each API call in the store."""
    cap = budgets.get(source.name)
    if cap is not None and hasattr(source, "budget"):
        source.budget = lambda: store.spend_call(source.name, cap)


def _is_rate_limit(exc: BaseException) -> bool:
    response = getattr(exc, "response", None)
    return (
        isinstance(exc, requests.HTTPError)
        and response is not None
        and response.status_code in (403, 429)
    )


def collect_recent(
    store: NewsStore, sources: Sequence, budgets: Optional[Dict[str, int]] = None
) -> List[SourceResult]:
    """Store `fetch_recent()` of every source. One failing source does not stop the rest."""
    budgets = DAILY_CALL_BUDGETS if budgets is None else budgets
    results: List[SourceResult] = []
    for source in sources:
        result = SourceResult(source.name)
        attach_budget(source, store, budgets)
        try:
            items = source.fetch_recent()
            result.fetched = len(items)
            result.new = store.add_items(items)
        except SourceLimitReached as exc:
            result.status, result.error = "limit", str(exc)
            logger.warning("%s stopped: %s", source.name, exc)
        except Exception as exc:
            status = "limit" if _is_rate_limit(exc) else "failed"
            result.status, result.error = status, f"{type(exc).__name__}: {exc}"
            logger.warning("%s %s: %s", source.name, status, result.error)
        results.append(result)
    return results


def resume_start(store: NewsStore, source_name: str, start: datetime) -> datetime:
    """`start`, or the source's backfill cursor (newest time a backfill reached) if later.

    The cursor is separate from the newest stored item, because `--recent` runs store
    items from today and would otherwise make a backfill skip all of history."""
    start = ensure_utc(start)
    cursor = store.get_backfill_cursor(source_name)
    return max(start, cursor) if cursor else start


def backfill_source(
    store: NewsStore,
    source,
    start: datetime,
    end: Optional[datetime] = None,
    budgets: Optional[Dict[str, int]] = None,
    batch_size: int = BATCH_SIZE,
) -> SourceResult:
    """Store `source.fetch_range(start, end)`, resuming from the latest stored date.

    Items are written in batches, so a stop (daily cap, rate limit, crash) keeps what has
    been fetched and the next run continues from there."""
    budgets = DAILY_CALL_BUDGETS if budgets is None else budgets
    result = SourceResult(source.name)
    if not hasattr(source, "fetch_range"):
        result.status, result.error = "failed", "source has no history (no fetch_range)"
        return result
    attach_budget(source, store, budgets)
    end = ensure_utc(end) if end else datetime.now(timezone.utc)
    first = resume_start(store, source.name, start)
    pending: List[NewsItem] = []

    def flush() -> None:
        if pending:
            result.fetched += len(pending)
            result.new += store.add_items(pending)
            store.advance_backfill_cursor(source.name, min(max(i.published_at for i in pending), end))
            pending.clear()

    try:
        try:
            for item in source.fetch_range(first, end):
                pending.append(item)
                if len(pending) >= batch_size:
                    flush()
        finally:
            flush()  # keep what was fetched even when the source stops with an error
        if first < end:
            store.advance_backfill_cursor(source.name, end)  # finished the whole range
    except SourceLimitReached as exc:
        result.status, result.error = "limit", str(exc)
        logger.warning("%s backfill paused: %s. Run again to resume.", source.name, exc)
    except Exception as exc:
        status = "limit" if _is_rate_limit(exc) else "failed"
        result.status, result.error = status, f"{type(exc).__name__}: {exc}"
        logger.warning("%s backfill %s: %s", source.name, status, result.error)
    return result


def format_results(results: Sequence[SourceResult]) -> str:
    lines = [f"{'source':<18}{'fetched':>8}{'new':>8}  status"]
    for r in results:
        note = "" if r.status == "ok" else f" ({r.error})"
        lines.append(f"{r.name:<18}{r.fetched:>8}{r.new:>8}  {r.status}{note}")
    lines.append(f"{'total':<18}{sum(r.fetched for r in results):>8}"
                 f"{sum(r.new for r in results):>8}")
    return "\n".join(lines)


def _parse_day(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def main(argv: Optional[Sequence[str]] = None, sources: Optional[list] = None,
         clock: Callable[[], float] = time.monotonic) -> int:
    parser = argparse.ArgumentParser(prog="python -m stock_advisor.news.collect",
                                     description="Collect news into the local store.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--recent", action="store_true", help="fetch the latest items of every source")
    mode.add_argument("--backfill", action="store_true", help="fetch history for one source")
    parser.add_argument("--source", help="source name (required with --backfill)")
    parser.add_argument("--start", type=_parse_day, help="YYYY-MM-DD (required with --backfill)")
    parser.add_argument("--end", type=_parse_day, help="YYYY-MM-DD (default: now)")
    parser.add_argument("--db", help="path of the SQLite store (default: data/cache/news/news.db)")
    args = parser.parse_args(argv)
    if args.backfill and (not args.source or not args.start):
        parser.error("--backfill needs --source and --start")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    began = clock()
    with NewsStore(args.db) as store:
        if sources is None:
            sources = build_sources(holdings_symbols())
        if args.recent:
            results = collect_recent(store, sources)
        else:
            chosen = [s for s in sources if s.name == args.source]
            if not chosen:
                parser.error(f"unknown source {args.source!r}; choose from "
                             f"{', '.join(s.name for s in sources)}")
            results = [backfill_source(store, chosen[0], args.start, args.end)]
    print(format_results(results))
    print(f"elapsed {clock() - began:.0f} s")
    return 1 if any(r.status == "failed" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
