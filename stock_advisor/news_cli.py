"""News events, similar past events, predicted moves and suggested actions.

    python -m stock_advisor.news_cli                 # events of the last 24 h from the store
    python -m stock_advisor.news_cli --collect       # fetch every source first, then show
    python -m stock_advisor.news_cli --watch         # keep polling; print new high-impact events

For each event: time, category, headline and link, outlets, the 5 most similar past events with
their 1-day reaction, the predicted move per target for 1 minute, 1 hour and 1 day with an 80%
range, the action (reduce / add / hold) and the profitable window. A prediction is marked
"unproven" unless the walk-forward backtest (results.json) proved that target and horizon.
With too little history the predictions read "n/a" and the report says so.

Watch mode polls EDGAR, RSS (without CISA) and yfinance news every 60 s; CISA, Guardian, NYT and
GDELT every 15 min (GDELT is skipped while a backfill is running it). Ctrl+C stops it cleanly.
`watch(..., on_new_events=callback)` calls `callback(analyses)` with the new high-impact events;
the Telegram notifier (Task 5.4) plugs in there. All numbers come from `news.analysis`.
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence

from stock_advisor.config import normalize_target
from stock_advisor.news import analysis as A
from stock_advisor.news.analysis import EventAnalysis, NewsAnalyzer
from stock_advisor.news.settings import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)

FAST_INTERVAL = 60.0  # seconds between polls of EDGAR, RSS and yfinance
SLOW_INTERVAL = 15 * 60.0  # Guardian, NYT, GDELT, CISA
MODEL_REFRESH = timedelta(hours=6)  # rebuild the model so it sees newly saved reactions
PROCESS_LOOKBACK = timedelta(days=3)  # score only items this recent in a live run
DEFAULT_HOURS = 24
DEFAULT_LIMIT = 10  # events printed in full

NewEventsHook = Callable[[List[EventAnalysis]], None]


# ---- formatting ---------------------------------------------------------------------------------


def fmt_pct(value: float, signed: bool = True) -> str:
    if value is None or math.isnan(value):
        return "n/a"
    return f"{value * 100:+.2f}%" if signed else f"{value * 100:.2f}%"


def fmt_time(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def format_forecast(forecast: A.HorizonForecast) -> str:
    if not forecast.available:
        return f"{forecast.horizon} n/a"
    text = (f"{forecast.horizon} {fmt_pct(forecast.predicted)} "
            f"(80% range {fmt_pct(forecast.low)} to {fmt_pct(forecast.high)})")
    return text if forecast.proven else f"{text} ⚠ unproven"


def format_outlook(outlook: A.TargetOutlook) -> List[str]:
    cells = " | ".join(format_forecast(f) for f in outlook.forecasts.values())
    if outlook.has_prediction:
        flag = "" if outlook.action_proven else " ⚠ unproven"
        action = f"action: {outlook.action}{flag}"
    else:
        action = "action: hold (no prediction yet)"
    return [f"    {outlook.target}: {cells}", f"        {action}; window: {outlook.window_text}"]


def format_analysis(analysis: EventAnalysis, targets: Optional[Sequence[str]] = None) -> str:
    """The text block for one event. Guardian items show the headline and link only."""
    tag = "HIGH IMPACT" if analysis.high_impact else "event"
    lines = [
        f"[{fmt_time(analysis.started_at)}] {analysis.category or 'uncategorized'} "
        f"({tag}; {analysis.n_items} headlines, {analysis.n_sources} sources)",
        f"  {analysis.title}",
    ]
    if analysis.link:
        lines.append(f"  {analysis.link}")
    others = [h for h in analysis.headlines if h.title != analysis.title][:2]
    for h in others:
        lines.append(f"  also: {h.title}" + (f" - {h.url}" if h.url else ""))
    if analysis.sources:
        lines.append(f"  sources: {', '.join(analysis.sources)}")
    shown = list(targets) if targets is not None else list(analysis.outlooks)
    lines.append("  similar past events (1-day reaction):")
    if analysis.similar:
        for s in analysis.similar:
            moves = "  ".join(f"{t} {fmt_pct(s.reactions.get(t, math.nan))}"
                              for t in shown if t in s.reactions)
            lines.append(f"    {s.started_at.date()}  {s.title}  [{moves}]  sim {s.similarity:.2f}")
    else:
        lines.append("    none yet (not enough history in the store)")
    lines.append("  predicted move:")
    for target in shown:
        outlook = analysis.outlooks.get(target)
        if outlook is not None:
            lines.extend(format_outlook(outlook))
    for warning in analysis.warnings:
        lines.append(f"  note: {warning}")
    return "\n".join(lines)


def history_note(analyzer: NewsAnalyzer) -> str:
    n = analyzer.history_events
    fitted = 0 if analyzer.model is None else len(analyzer.model.models)
    if fitted == 0:
        return (f"Note: {n} past events in the store and no fitted model yet, so predictions "
                "show n/a. Run news_backtest_cli once enough events have prices.")
    return f"History: {n} past events, {fitted} fitted target/horizon pairs."


def print_report(analyses: Sequence[EventAnalysis], total: int, hours: float,
                 analyzer: NewsAnalyzer, targets: Sequence[str], out=print) -> None:
    out(f"News events, last {hours:g} h: {total} found, showing {len(analyses)} "
        f"(targets: {', '.join(targets)})")
    out(history_note(analyzer))
    for analysis in analyses:
        out("")
        out(format_analysis(analysis, targets))
    if total > len(analyses):
        out(f"\n{total - len(analyses)} more events not shown (raise --limit).")
    if total == 0:
        out("No events in this period. Run with --collect to fetch the latest headlines.")


# ---- one shot -----------------------------------------------------------------------------------


def process(store, analyzer: NewsAnalyzer, finbert=None, embedder=None) -> A.ProcessResult:
    return A.process_new(
        store, since=analyzer.clock() - PROCESS_LOOKBACK, finbert=finbert, embedder=embedder,
        market_moving=analyzer.results.market_moving())


def collect_all(store, sources: A.WatchSources, out=print) -> None:
    results = A.collect_group(store, sources.fast + sources.slow, skip_gdelt=A.gdelt_busy())
    new = sum(r.new for r in results)
    failed = [r.name for r in results if r.status == "failed"]
    out(f"Collected {new} new headlines from {len(results)} sources"
        + (f" (failed: {', '.join(failed)})" if failed else "") + ".")


def run_once(store, analyzer: NewsAnalyzer, hours: float, limit: int, targets: Sequence[str],
             out=print) -> List[EventAnalysis]:
    events = analyzer.recent_events(hours)
    analyzer.refresh()
    analyses = analyzer.analyze_recent(hours, limit=limit)
    print_report(analyses, len(events), hours, analyzer, targets, out)
    return analyses


# ---- watch mode ---------------------------------------------------------------------------------


class SlowPoller:
    """Runs the 15-minute sources (Guardian, NYT, GDELT, CISA) on a side thread.

    GDELT can answer 429 for ten minutes or more; on the main thread that would stall the
    60-second polls. The thread uses its own store connection (SQLite connections are not shared
    between threads) and only stores new items; the main cycle scores and clusters them. A new
    run is skipped while the previous one is still going. The thread is a daemon, so Ctrl+C never
    waits for it. `background=False` runs the job at once (tests).
    """

    def __init__(self, store_path, background: bool = True) -> None:
        self.store_path = store_path
        self.background = background
        self._thread: Optional[threading.Thread] = None

    def start(self, sources: Sequence) -> bool:
        if not sources or (self._thread is not None and self._thread.is_alive()):
            return False
        if not self.background:
            self._job(sources)
            return True
        self._thread = threading.Thread(target=self._job, args=(sources,), daemon=True,
                                        name="news-slow-poll")
        self._thread.start()
        return True

    def _job(self, sources: Sequence) -> None:
        try:
            with A.open_store(self.store_path) as store:
                results = A.collect_group(store, sources, skip_gdelt=A.gdelt_busy())
            for r in results:
                if r.status != "ok":
                    logger.warning("%s %s: %s", r.name, r.status, r.error)
            logger.info("slow poll: %d new", sum(r.new for r in results))
        except Exception as exc:
            logger.warning("slow poll failed (%s: %s)", type(exc).__name__, exc)


def watch(
    store,
    analyzer: NewsAnalyzer,
    sources: A.WatchSources,
    on_new_events: Optional[NewEventsHook] = None,
    hours: float = DEFAULT_HOURS,
    finbert=None,
    embedder=None,
    out=print,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    max_cycles: Optional[int] = None,
    fast_interval: float = FAST_INTERVAL,
    slow_interval: float = SLOW_INTERVAL,
    background_slow: bool = True,
) -> int:
    """Poll until Ctrl+C (or `max_cycles`). Prints only high-impact events not seen before.

    Events already stored when the watch starts count as seen. Each new high-impact event is
    analyzed, printed and passed to `on_new_events(analyses)` (errors in the hook are logged).
    """
    seen = {e.id for e in analyzer.recent_events(hours, high_impact_only=True)}
    out(f"Watching (Ctrl+C to stop). {len(seen)} high-impact events already known; "
        "printing only new ones.")
    next_slow = clock()  # the slow group runs on the first cycle
    slow = SlowPoller(store.path, background_slow)
    cycles = 0
    try:
        while max_cycles is None or cycles < max_cycles:
            began = clock()
            if began >= next_slow:
                slow.start(sources.slow)
                next_slow = began + slow_interval
            try:
                _cycle(store, analyzer, list(sources.fast), seen, on_new_events, hours, finbert,
                       embedder, out)
            except Exception as exc:  # a failed cycle (locked file, network) must not end the watcher
                logger.warning("watch cycle failed (%s: %s); trying again next cycle",
                               type(exc).__name__, exc)
            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                break
            sleep(max(1.0, fast_interval - (clock() - began)))
    except KeyboardInterrupt:
        out("\nStopped.")
    return 0


def _cycle(store, analyzer, group, seen, on_new_events, hours, finbert, embedder, out) -> None:
    results = A.collect_group(store, group, skip_gdelt=A.gdelt_busy())
    for r in results:
        if r.status != "ok":
            logger.warning("%s %s: %s", r.name, r.status, r.error)
    done = process(store, analyzer, finbert, embedder)
    logger.info("cycle: %d new, scored %d, clustered %d", sum(r.new for r in results),
                done.scored, done.clustered)
    new = [e for e in analyzer.recent_events(hours, high_impact_only=True) if e.id not in seen]
    if not new:
        return
    stale = (analyzer.refreshed_at is None
             or analyzer.clock() - analyzer.refreshed_at > MODEL_REFRESH)
    if stale:
        analyzer.refresh()
    analyses = analyzer.analyze_events(sorted(new, key=lambda e: (e.started_at, e.id)))
    seen.update(e.id for e in new)
    for analysis in analyses:
        out("")
        out(format_analysis(analysis, analyzer.targets))
    if analyses and on_new_events is not None:
        try:
            on_new_events(analyses)
        except Exception as exc:
            logger.warning("on_new_events failed (%s: %s)", type(exc).__name__, exc)


# ---- command line -------------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Current news events with similar past events, predicted moves and actions.")
    parser.add_argument("--watch", action="store_true",
                        help="keep polling the sources and print new high-impact events")
    parser.add_argument("--no-alerts", action="store_true",
                        help="with --watch: do not send Telegram alerts")
    parser.add_argument("--collect", action="store_true",
                        help="fetch every source and score new items before showing events")
    parser.add_argument("--hours", type=float, default=DEFAULT_HOURS,
                        help="how far back to look (default: %(default)s)")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help="events shown in full (default: %(default)s)")
    parser.add_argument("--targets", nargs="+", default=None,
                        help="targets to predict (default: ^HSI, ^GSPC and your holdings)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH,
                        help="news store (default: %(default)s)")
    parser.add_argument("-v", "--verbose", action="store_true", help="log each watch cycle")
    return parser


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    sources: Optional[A.WatchSources] = None,
    price_loader=None,
    results=None,
    reactions=None,
    fitted=None,
    finbert=None,
    embedder=None,
    on_new_events: Optional[NewEventsHook] = None,
    out=print,
    **watch_options,
) -> int:
    """Run the CLI. Everything after `argv` can be injected for tests; `watch_options` go to
    `watch` (clock, sleep, max_cycles, intervals)."""
    args = build_arg_parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # headlines hold characters a Windows console lacks
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO if args.verbose or args.watch else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    holdings: Iterable[str] = ()
    if args.targets:
        targets = [normalize_target(t) for t in args.targets]
    else:
        from stock_advisor.news.collect import holdings_symbols

        holdings = holdings_symbols()
        targets = A.alert_targets(holdings)
    if price_loader is None:
        from stock_advisor.news.reactions import default_price_loader

        price_loader = default_price_loader

    store = A.open_store(args.db)
    try:
        analyzer = NewsAnalyzer(store, targets, results=results, reactions=reactions,
                                fitted=fitted, price_loader=price_loader)
        if args.watch or args.collect:
            if sources is None:
                sources = A.build_watch_sources(holdings)
        if args.watch:
            if on_new_events is None and not args.no_alerts:
                from stock_advisor.news.notify import build_notifier

                on_new_events = build_notifier(store)  # inert (one warning) without a token
            return watch(store, analyzer, sources, on_new_events, hours=args.hours,
                         finbert=finbert, embedder=embedder, out=out, **watch_options)
        if args.collect:
            collect_all(store, sources, out)
            done = process(store, analyzer, finbert, embedder)
            out(f"Scored {done.scored} items, categorized {done.categorized}, "
                f"placed {done.clustered} in events.")
        run_once(store, analyzer, args.hours, args.limit, targets, out)
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
