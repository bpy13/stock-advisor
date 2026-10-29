"""Reusable analysis layer for current news events (plan Task 5.1; used by 5.2 to 5.4 too).

Everything here returns data and prints nothing. `news_cli` prints it; the CLI report column
(5.2), the dashboard News tab (5.3) and the Telegram notifier (5.4) read the same objects.

    analyzer = NewsAnalyzer(store, targets=["^HSI", "^GSPC"])
    for analysis in analyzer.analyze_recent(hours=24):
        analysis.headlines, analysis.similar, analysis.outlooks["^GSPC"].action, ...

Also here: `process_new` (score, categorize and cluster new items), `build_watch_sources`
(the fast and slow polling groups) and `gdelt_busy` (a backfill is using GDELT).

Rules this layer keeps:
* Predictions are shown, but `proven` is False unless results.json says the target and horizon
  passed the walk-forward test (decision 2026-10-27: unproven predictions only warn).
* Guardian items carry the headline and link only. Item summaries are read for outlet names
  (`source_key`) and never copied into the results.
* Nothing here fits a model: `refresh` loads the models the backtest saved (fitted.pkl). With
  no such file predictions are NaN, while similar events and windows still work.
* With too little history, predictions are NaN and the window says "not enough similar events";
  nothing raises.
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from stock_advisor.config import NEWS_ACTION_THRESHOLD_PCT, NEWS_ALERT_TARGETS, normalize_target
from stock_advisor.news.models import Event, ItemScore, NewsItem, ensure_utc
from stock_advisor.news.settings import NEWS_CACHE_DIR
from stock_advisor.news.store import NewsStore

logger = logging.getLogger(__name__)

HEADLINE_HORIZONS = ("1m", "1h", "1d")  # horizons shown per target
ACTION_HORIZON = "1d"  # the horizon that sets the action and the window direction
TOP_SIMILAR = 5
MAX_HEADLINES = 5
BUSY_TIMEOUT_MS = 30_000
REACTIONS_PATH = NEWS_CACHE_DIR / "model" / "reactions.parquet"
FITTED_PATH = NEWS_CACHE_DIR / "model" / "fitted.pkl"  # same file as news_backtest_cli.FITTED_PATH
BACKFILL_STATUS_PATH = NEWS_CACHE_DIR / "backfill_status.json"
REACTION_COLUMNS = ["event_id", "target", "horizon", "raw", "adjusted", "start_ts",
                    "start_source"]

REDUCE, ADD, HOLD = "reduce", "add", "hold"

NAN = float("nan")


# ---- result objects -----------------------------------------------------------------------------


@dataclass
class Headline:
    """One headline of an event. Never carries a summary (Guardian terms)."""

    title: str
    url: str
    source: str  # outlet name, e.g. "guardian", "rss:BBC World"


@dataclass
class SimilarEvent:
    """A similar past event and how each target reacted over the action horizon (1d)."""

    event_id: str
    started_at: datetime
    title: str
    category: Optional[str]
    similarity: float
    reactions: Dict[str, float] = field(default_factory=dict)  # target -> 1d return (NaN unknown)


@dataclass
class HorizonForecast:
    """Predicted return for one target and horizon, with the 80% range."""

    horizon: str
    predicted: float = NAN  # a fraction (0.01 = +1%); NaN when no model could be fitted
    low: float = NAN
    high: float = NAN
    proven: bool = False
    n_train: int = 0

    @property
    def available(self) -> bool:
        return not math.isnan(self.predicted)


@dataclass
class TargetOutlook:
    """Forecasts, suggested action and profitable window for one target."""

    target: str
    forecasts: Dict[str, HorizonForecast] = field(default_factory=dict)
    action: str = HOLD
    action_proven: bool = False
    has_prediction: bool = False  # False: "hold" only because nothing could be predicted
    window_text: str = "no predicted direction"
    window_status: str = "no_direction"

    @property
    def predicted_action_move(self) -> float:
        """Predicted 1-day return (NaN when unavailable)."""
        f = self.forecasts.get(ACTION_HORIZON)
        return f.predicted if f else NAN


@dataclass
class EventAnalysis:
    """Everything the CLI, report, dashboard and notifier show about one current event."""

    event_id: str
    started_at: datetime
    category: Optional[str]
    title: str
    link: str
    high_impact: bool
    n_items: int
    n_sources: int
    sources: List[str] = field(default_factory=list)
    headlines: List[Headline] = field(default_factory=list)
    similar: List[SimilarEvent] = field(default_factory=list)
    outlooks: Dict[str, TargetOutlook] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


# ---- store connection ---------------------------------------------------------------------------


def open_store(path=None) -> NewsStore:
    """Open the news store for a process that shares the file with the backfill.

    SQLite allows one writer. `NewsStore` already waits 30 s on a lock; the PRAGMA repeats it
    for any connection made before that change. Rollback-journal mode is kept (switching the
    live file to WAL is the backfill owner's call); keep every transaction short.
    """
    store = NewsStore(path)
    store._conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    return store


# ---- action and targets -------------------------------------------------------------------------


def decide_action(predicted_1d: float, threshold_pct: float = NEWS_ACTION_THRESHOLD_PCT) -> str:
    """"reduce" at or below -threshold %, "add" at or above +threshold %, else "hold"."""
    if predicted_1d is None or math.isnan(predicted_1d):
        return HOLD
    pct = predicted_1d * 100.0
    if pct <= -threshold_pct:
        return REDUCE
    if pct >= threshold_pct:
        return ADD
    return HOLD


def alert_targets(holdings: Iterable[str] = ()) -> List[str]:
    """The always-reported targets (^HSI, ^GSPC) followed by the holdings, de-duplicated."""
    out: List[str] = []
    for symbol in [*NEWS_ALERT_TARGETS, *holdings]:
        symbol = symbol.strip().upper()
        if symbol and symbol not in out:
            out.append(symbol)
    return out


def strong_targets(analysis: EventAnalysis,
                   threshold_pct: float = NEWS_ACTION_THRESHOLD_PCT) -> List[str]:
    """Targets whose predicted 1-day move is at least the threshold in size (alert rule, 5.4)."""
    out = []
    for target, outlook in analysis.outlooks.items():
        move = outlook.predicted_action_move
        if not math.isnan(move) and abs(move) * 100.0 >= threshold_pct:
            out.append(target)
    return out


# ---- reactions file -----------------------------------------------------------------------------


_TEXT_REACTION_COLUMNS = ["event_id", "target", "horizon", "start_source"]


def read_reactions(path: Optional[Path] = None,
                   targets: Optional[Sequence[str]] = None) -> pd.DataFrame:
    """The cached reaction table written by news_backtest_cli, or an empty table.

    Only the rows of `targets` (all when None) with a known return are kept. On 2026-10-29
    the file held 119M rows, almost all without a return (114k known for the 24 live
    targets). Read whole, it took 15+ GB in the dashboard; even a filtered `read_table`
    peaked at 8 GB. So the file is streamed one batch at a time and only matching rows are
    kept, with the text columns as categories.
    """
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.dataset as ds

    path = Path(path) if path is not None else REACTIONS_PATH
    try:
        if path.exists():
            known = ((pc.is_valid(pc.field("raw")) & ~pc.is_nan(pc.field("raw")))
                     | (pc.is_valid(pc.field("adjusted")) & ~pc.is_nan(pc.field("adjusted"))))
            if targets is not None:
                known = known & pc.field("target").isin(list(targets))
            dataset = ds.dataset(path, format="parquet")
            batches = [b for b in dataset.to_batches(filter=known, batch_size=65_536)
                       if b.num_rows]
            if not batches:
                return pd.DataFrame(columns=REACTION_COLUMNS)
            frame = pa.Table.from_batches(batches).to_pandas()
            del batches
            pa.default_memory_pool().release_unused()  # give the decode buffers back
            return frame.astype({c: "category" for c in _TEXT_REACTION_COLUMNS if c in frame})
    except Exception as exc:  # a half-written or unreadable file must not stop the monitor
        logger.warning("Could not read %s (%s); predictions need the backtest first", path,
                       type(exc).__name__)
    return pd.DataFrame(columns=REACTION_COLUMNS)


# ---- the analyzer -------------------------------------------------------------------------------


class NewsAnalyzer:
    """Builds the prediction model once (`refresh`) and analyzes events against it.

    The model loads the fitted models saved by news_backtest_cli (fitted.pkl) and never fits.
    `reactions` overrides the cached reaction file and `fitted` (a `model.FittedFile`) the
    fitted file (tests); `reactions_path` and `fitted_path` point at other files. `results` is
    a `news_backtest_cli.BacktestResults` (default: results.json). `price_loader` feeds the
    volatility feature (None: skipped).
    """

    def __init__(
        self,
        store,
        targets: Sequence[str],
        results=None,
        reactions: Optional[pd.DataFrame] = None,
        reactions_path: Optional[Path] = None,
        fitted=None,
        fitted_path: Optional[Path] = None,
        price_loader=None,
        threshold_pct: float = NEWS_ACTION_THRESHOLD_PCT,
        top_similar: int = TOP_SIMILAR,
        horizons: Sequence[str] = HEADLINE_HORIZONS,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        from stock_advisor.news_backtest_cli import load_results

        self.store = store
        self.targets = [normalize_target(t) for t in targets]
        self.results = results if results is not None else load_results()
        self._fixed_reactions = reactions
        self.reactions_path = reactions_path
        self._fixed_fitted = fitted
        self.fitted_path = fitted_path
        self.price_loader = price_loader
        self.threshold_pct = threshold_pct
        self.top_similar = top_similar
        self.horizons = tuple(horizons)
        self.clock = clock
        self.model = None
        self.refreshed_at: Optional[datetime] = None

    # -- model ---------------------------------------------------------------------------------

    def refresh(self) -> None:
        """(Re)build the event library from the store and load the backtest's fitted models.

        Never fits: fitting builds the all-pairs analog table, which takes 30-60 minutes on the
        live store. With no fitted file, `model.models` stays empty and predictions are NaN.
        """
        from stock_advisor.news.model import (
            EventLibrary,
            NewsModel,
            load_event_records,
            load_fitted,
        )

        # Drop the old model first: holding it while the new library loads doubled the peak
        # (6.7 GB instead of 3.3 GB on the live store, 2026-10-29).
        self.model = None
        records = load_event_records(self.store)
        reactions = (self._fixed_reactions if self._fixed_reactions is not None
                     else read_reactions(self.reactions_path, self.targets))
        model = NewsModel(EventLibrary(records), reactions, price_loader=self.price_loader)
        fitted = (self._fixed_fitted if self._fixed_fitted is not None
                  else load_fitted(self.fitted_path if self.fitted_path is not None
                                   else FITTED_PATH))
        if fitted is not None:
            wanted = {(t, h) for t in self.targets for h in self.horizons}
            model.models = {k: v for k, v in fitted.models.items() if k in wanted}
            logger.info("Fitted models generated %s on %d events", fitted.generated_at,
                        fitted.library_size)
        self.model = model
        self.refreshed_at = self.clock()
        logger.info("Model ready: %d events, %d fitted target/horizon pairs",
                    len(records), len(model.models))

    @property
    def history_events(self) -> int:
        return 0 if self.model is None else len(self.model.library)

    # -- events ----------------------------------------------------------------------------------

    def recent_events(self, hours: float = 24, high_impact_only: bool = False) -> List[Event]:
        """Stored events that started in the last `hours`, newest first."""
        start = ensure_utc(self.clock()) - timedelta(hours=hours)
        events = self.store.query_events(start=start, high_impact_only=high_impact_only)
        return sorted(events, key=lambda e: (e.started_at, e.id), reverse=True)

    def analyze_recent(self, hours: float = 24, high_impact_only: bool = False,
                       limit: Optional[int] = None) -> List[EventAnalysis]:
        """Analyses of recent events: high-impact first, then by number of sources, then newest."""
        events = self.recent_events(hours, high_impact_only)
        events.sort(key=lambda e: (e.high_impact, e.n_sources, e.started_at), reverse=True)
        if limit is not None:
            events = events[:limit]
        return self.analyze_events(events)

    def analyze_events(self, events: Sequence[Event]) -> List[EventAnalysis]:
        from stock_advisor.news.model import load_event_records

        if not events:
            return []
        if self.model is None:
            self.refresh()
        first = min(e.started_at for e in events)
        last = max(e.started_at for e in events)
        records = {r.id: r for r in load_event_records(
            self.store, first, last + timedelta(seconds=1))}
        out = []
        for event in events:
            record = records.get(event.id)
            if record is None:  # no embedded member yet
                continue
            out.append(self._analyze(event, record))
        return out

    def _analyze(self, event: Event, record) -> EventAnalysis:
        from stock_advisor.news.events import source_key

        items = self.store.items_for_event(event.id)
        headlines = _headlines(items, event.title)
        lead_link = next((h.url for h in headlines if h.url), "")
        sources = sorted({source_key(i.source, i.url, i.summary) for i in items})
        analysis = EventAnalysis(
            event_id=event.id, started_at=event.started_at, category=event.category,
            title=event.title, link=lead_link, high_impact=event.high_impact,
            n_items=event.n_items, n_sources=event.n_sources, sources=sources,
            headlines=headlines,
        )
        try:
            analysis.similar = self._similar(record)
        except Exception as exc:
            analysis.warnings.append(f"similar events unavailable ({type(exc).__name__})")
            logger.warning("similar events failed for %s: %s", event.id, exc)
        for target in self.targets:
            analysis.outlooks[target] = self._outlook(record, target, analysis.warnings)
        return analysis

    def _similar(self, record) -> List[SimilarEvent]:
        lib = self.model.library
        idx, sim, _ = lib.candidates_for(record)
        one_day = {t: self.model.outcomes(t, ACTION_HORIZON).values for t in self.targets}
        out: List[SimilarEvent] = []
        for j, s in zip(idx, sim):
            if len(out) >= self.top_similar:
                break
            if int(j) < 0 or math.isnan(float(s)):
                continue
            past = lib.events[int(j)]
            out.append(SimilarEvent(
                past.id, past.started_at, past.title, past.category, float(s),
                {t: float(v[int(j)]) for t, v in one_day.items()},
            ))
        return out

    def _outlook(self, record, target: str, warnings: List[str]) -> TargetOutlook:
        from stock_advisor.news.window import window_for

        outlook = TargetOutlook(target)
        for horizon in self.horizons:
            forecast = HorizonForecast(horizon, proven=self.results.is_proven(target, horizon))
            try:
                p = self.model.predict(record, target, horizon)
                forecast.predicted, forecast.low, forecast.high = p.predicted, p.low, p.high
                forecast.n_train = p.n_train
            except Exception as exc:
                warnings.append(f"{target} {horizon} prediction failed ({type(exc).__name__})")
                logger.warning("prediction failed for %s %s: %s", target, horizon, exc)
            outlook.forecasts[horizon] = forecast
        move = outlook.predicted_action_move
        outlook.has_prediction = not math.isnan(move)
        outlook.action = decide_action(move, self.threshold_pct)
        outlook.action_proven = self.results.is_proven(target, ACTION_HORIZON)
        try:
            window = window_for(self.model, record, target, move)
            outlook.window_text, outlook.window_status = window.text, window.status
        except Exception as exc:
            warnings.append(f"{target} window failed ({type(exc).__name__})")
            logger.warning("window failed for %s: %s", target, exc)
        return outlook


def _headlines(items: Sequence[NewsItem], lead_title: str) -> List[Headline]:
    """Distinct headlines, the event's lead headline first. Title, link and outlet only."""
    from stock_advisor.news.events import source_key

    ordered = sorted(items, key=lambda i: (i.title != lead_title, i.published_at, i.id))
    seen, out = set(), []
    for item in ordered:
        key = item.title.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(Headline(item.title, item.url, source_key(item.source, item.url, item.summary)))
        if len(out) >= MAX_HEADLINES:
            break
    return out


# ---- processing new items -----------------------------------------------------------------------


@dataclass
class ProcessResult:
    scored: int = 0
    categorized: int = 0
    clustered: int = 0


def _recent_unscored(store, since: datetime, limit: int) -> List[NewsItem]:
    from stock_advisor.news.store import _row_to_item, _to_text

    rows = store._conn.execute(
        "SELECT i.* FROM items i LEFT JOIN scores s ON s.item_id = i.id "
        "WHERE i.published_at >= ? AND (s.item_id IS NULL OR s.tone IS NULL) "
        "ORDER BY i.published_at, i.id LIMIT ?",
        (_to_text(since), limit),
    ).fetchall()
    return [_row_to_item(r) for r in rows]


def process_new(store, since: datetime, finbert=None, embedder=None,
                market_moving: Iterable[str] = (), batch_size: int = 64,
                limit: int = 2000) -> ProcessResult:
    """Score the unscored items since `since`, categorize, then cluster into events.

    Scoring, categorizing and clustering are all limited to items published since `since`, so
    a live run never takes over the backfill's backlog (the backfill does all three for its own
    items; loading that backlog every cycle made the watcher grow to ~12 GB). Each store write is
    a short transaction, so the backfill can write between them.
    """
    from stock_advisor.news.categories import categorize_pending
    from stock_advisor.news.events import cluster_pending
    from stock_advisor.news.scoring import (
        embed,
        embedding_to_bytes,
        score_tone,
    )

    result = ProcessResult()
    since = ensure_utc(since)
    items = _recent_unscored(store, since, limit)
    for start in range(0, len(items), batch_size):
        chunk = items[start:start + batch_size]
        titles = [i.title for i in chunk]
        tones = score_tone(titles, model=finbert)
        vectors = embed(titles, model=embedder)
        for item, (pos, neg, neu, tone), vector in zip(chunk, tones, vectors):
            store.update_scores(ItemScore(
                item_id=item.id, tone_pos=pos, tone_neg=neg, tone_neu=neu, tone=tone,
                embedding=embedding_to_bytes(np.asarray(vector)),
            ))
        result.scored += len(chunk)
    result.categorized = categorize_pending(store, since=since)
    result.clustered = cluster_pending(store, market_moving=tuple(market_moving), since=since)
    return result


# ---- sources for the watcher --------------------------------------------------------------------

@dataclass
class WatchSources:
    """Sources by polling group. `fast`: every 60 s. `slow`: every 15 min."""

    fast: list = field(default_factory=list)
    slow: list = field(default_factory=list)


def build_watch_sources(holdings: Iterable[str] = ()) -> WatchSources:
    """Live sources split by plan Task 5.1: EDGAR, RSS (without CISA) and yfinance news every
    minute; CISA, Guardian, NYT and GDELT every 15 minutes. Wikipedia (daily events) is left
    to the backfill."""
    from stock_advisor.news.collect import build_sources
    from stock_advisor.news.sources.rss_feeds import FEEDS, RssFeedsSource

    by_name = {s.name: s for s in build_sources(holdings)}
    cisa = [f for f in FEEDS if "CISA" in f.name]
    rest = [f for f in FEEDS if "CISA" not in f.name]
    fast = [by_name[n] for n in ("edgar", "yahoo") if n in by_name]
    fast.append(RssFeedsSource(feeds=rest))
    slow = [by_name[n] for n in ("guardian", "nyt", "gdelt") if n in by_name]
    slow.append(RssFeedsSource(feeds=cisa))
    return WatchSources(fast, slow)


def gdelt_busy(status_path: Optional[Path] = None, now: Optional[datetime] = None,
               max_age: timedelta = timedelta(minutes=15)) -> bool:
    """True when the backfill status file says a GDELT backfill is running (and the file is
    fresh). GDELT locks out for a minute or more after bursts, so never run two callers.
    Reads the status file only; never takes the backfill's lock."""
    path = Path(status_path) if status_path is not None else BACKFILL_STATUS_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        running = data.get("sources", {}).get("gdelt", {}).get("run_status") == "running"
        updated = datetime.fromisoformat(data["updated"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
    now = ensure_utc(now or datetime.now(timezone.utc))
    return running and now - ensure_utc(updated) <= max_age


def collect_group(store, sources: Sequence, skip_gdelt: bool = False) -> list:
    """Fetch the given sources into the store (one failing source never stops the rest)."""
    from stock_advisor.news.collect import collect_recent

    chosen = [s for s in sources if not (skip_gdelt and s.name == "gdelt")]
    return collect_recent(store, chosen)


def is_locked_error(exc: BaseException) -> bool:
    return isinstance(exc, sqlite3.OperationalError) and "locked" in str(exc).lower()
