"""Walk-forward backtest of the news model: python -m stock_advisor.news_backtest_cli

For every target and horizon it fits the analog + ridge model (`news.model`) on earlier years
only and predicts each later year (expanding window by calendar year). It prints, per target
and horizon: n (out-of-sample events), hit rate, mean return when following the predicted
sign, Welch t-stat and `proven` (n >= 30, |t| >= 2, hit rate > 0.5; see
`model.score_predictions`). A per-category summary shows which event categories move which
targets (input for the high-impact `market_moving` hook).

Side effects (all under data/cache/news/model/):
* reactions.parquet: cache of the reaction table. New events (and recent ones whose later
  horizons may still have been missing) are added on each run; old rows are reused.
* results.json: the results, read back by `load_results` (Tasks 5.1 to 5.3 use
  `load_results().is_proven(target, horizon)`).

The news store is opened read-only (SQLite URI mode=ro), so a running backfill is never
blocked or changed.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from stock_advisor.news.model import (
    PROVEN_MIN_ABS_T,
    PROVEN_MIN_N,
    EvalResult,
    EventLibrary,
    EventRecord,
    NewsModel,
    load_event_records,
    return_kind,
)
from stock_advisor.news.reactions import HORIZONS, PriceLoader, build_reaction_table
from stock_advisor.news.settings import DEFAULT_DB_PATH, NEWS_CACHE_DIR
from stock_advisor.news.window import HOLD_HORIZON, evaluate_window_rule, window_cases

MODEL_CACHE_DIR = NEWS_CACHE_DIR / "model"
REACTIONS_FILE = "reactions.parquet"
RESULTS_FILE = "results.json"
RESULTS_PATH = MODEL_CACHE_DIR / RESULTS_FILE
RESULTS_VERSION = 1

# Cached reactions for events newer than this are rebuilt on every run, because their later
# horizons (up to the 10th close, about two weeks) may not have had prices yet.
REFRESH_DAYS = 21
# Indices whose moves define a "market-moving" category (the high-impact hook in events.py).
MARKET_INDICES = ("^HSI", "^GSPC")

ReactionBuilder = Callable[[Iterable[object], Sequence[str], PriceLoader], pd.DataFrame]


# ---- read-only store --------------------------------------------------------------------------


class ReadOnlyStore:
    """Read-only view of the news SQLite file.

    `NewsStore` creates tables on open, which writes; this opens with mode=ro instead, so the
    backfill writing the same file is never blocked. `load_event_records` only needs `_conn`.
    """

    def __init__(self, path: Path) -> None:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"news store not found: {path}")
        self.path = path
        self._conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        self._conn.row_factory = sqlite3.Row

    def event_precisions(self) -> Dict[str, str]:
        """{event id: "exact" | "day"}: "exact" when any member has an exact time
        (the rule of `events.event_time_precision`)."""
        rows = self._conn.execute(
            "SELECT s.event_id AS event_id, "
            "MAX(CASE WHEN i.time_precision = 'day' THEN 0 ELSE 1 END) AS any_exact "
            "FROM scores s JOIN items i ON i.id = s.item_id "
            "WHERE s.event_id IS NOT NULL GROUP BY s.event_id"
        )
        return {r["event_id"]: ("exact" if r["any_exact"] else "day") for r in rows}

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "ReadOnlyStore":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


# ---- reaction cache ---------------------------------------------------------------------------


@dataclass
class _ReactionEvent:
    """What `build_reaction_table` reads from an event."""

    id: str
    started_at: datetime
    time_precision: str = "exact"


def load_or_build_reactions(
    events: Sequence[EventRecord],
    targets: Sequence[str],
    cache_path: Path,
    price_loader: Optional[PriceLoader] = None,
    precisions: Optional[Dict[str, str]] = None,
    builder: ReactionBuilder = build_reaction_table,
    rebuild: bool = False,
    now: Optional[datetime] = None,
) -> pd.DataFrame:
    """Reaction rows for `events` x `targets`, reusing the parquet cache at `cache_path`.

    Only (event, target) pairs missing from the cache, or whose event started within
    REFRESH_DAYS of `now`, are built. Cached rows for other events are kept in the file
    (a run limited by --start/--end must not wipe them) but left out of the result.
    """
    precisions = precisions or {}
    now = now or datetime.now(timezone.utc)
    cached = None
    if cache_path.exists() and not rebuild:
        cached = pd.read_parquet(cache_path)
    fresh_cutoff = now - timedelta(days=REFRESH_DAYS)
    stale_ids = {e.id for e in events if e.started_at >= fresh_cutoff}

    built = []
    for target in targets:
        have = set()
        if cached is not None:
            have = set(cached.loc[cached["target"] == target, "event_id"])
        todo = [
            _ReactionEvent(e.id, e.started_at, precisions.get(e.id, "exact"))
            for e in events if e.id not in have or e.id in stale_ids
        ]
        if todo:
            kwargs = {} if price_loader is None else {"price_loader": price_loader}
            built.append(builder(todo, [target], **kwargs))

    if built:
        new_rows = pd.concat(built, ignore_index=True)
        if cached is not None:
            replaced = cached.set_index(["event_id", "target"]).index.isin(
                new_rows.set_index(["event_id", "target"]).index)
            merged = pd.concat([cached[~replaced], new_rows], ignore_index=True)
        else:
            merged = new_rows
        merged["start_ts"] = pd.to_datetime(merged["start_ts"], utc=True)
        merged["start_source"] = merged["start_source"].astype(object)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        merged.to_parquet(cache_path, index=False)
    else:
        merged = cached if cached is not None else pd.DataFrame(
            columns=["event_id", "target", "horizon", "raw", "adjusted", "start_ts",
                     "start_source"])

    ids = {e.id for e in events}
    keep = merged["event_id"].isin(ids) & merged["target"].isin(list(targets))
    return merged[keep].reset_index(drop=True)


# ---- category summary -------------------------------------------------------------------------


def _one_sample_t(values: np.ndarray) -> float:
    if len(values) < 2:
        return float("nan")
    sd = values.std(ddof=1)
    return float(values.mean() / (sd / math.sqrt(len(values)))) if sd > 0 else float("nan")


def _welch_t(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    denom = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float((a.mean() - b.mean()) / denom) if denom > 0 else float("nan")


def category_summary(events: Sequence[EventRecord], reactions: pd.DataFrame,
                     targets: Sequence[str], horizons: Sequence[str],
                     min_events: int = PROVEN_MIN_N) -> pd.DataFrame:
    """Which event categories move which targets (descriptive, uses all events).

    Per category, target and horizon: n, mean return, mean absolute return, abs_ratio (mean
    absolute return / that of all other events), t_mean (one-sample t of the mean return) and
    t_abs (Welch t of absolute returns, this category vs all others). `moves` = n >= min_events
    and t_abs >= 2 (bigger moves than usual, either direction) or |t_mean| >= 2 (a consistent
    direction). The return column follows `model.return_kind` (raw for indices).
    """
    columns = ["target", "horizon", "category", "n", "mean_return", "mean_abs_return",
               "abs_ratio", "t_mean", "t_abs", "moves"]
    category_of = pd.Series({e.id: (e.category or "other") for e in events}, dtype=object)
    rows = []
    for target in targets:
        kind = return_kind(target)
        for horizon in horizons:
            sub = reactions[(reactions["target"] == target) & (reactions["horizon"] == horizon)]
            if sub.empty:
                continue
            values = sub[kind].to_numpy(float)
            cats = category_of.reindex(sub["event_id"]).to_numpy()
            ok = ~np.isnan(values) & pd.notna(cats)
            values, cats = values[ok], cats[ok]
            for category in sorted(set(cats)):
                mine = values[cats == category]
                rest = values[cats != category]
                abs_mine, abs_rest = np.abs(mine), np.abs(rest)
                rest_abs_mean = abs_rest.mean() if len(rest) else float("nan")
                t_mean = _one_sample_t(mine)
                t_abs = _welch_t(abs_mine, abs_rest)
                moves = bool(len(mine) >= min_events and (
                    (t_abs == t_abs and t_abs >= PROVEN_MIN_ABS_T)
                    or (t_mean == t_mean and abs(t_mean) >= PROVEN_MIN_ABS_T)))
                rows.append((target, horizon, category, len(mine), float(mine.mean()),
                             float(abs_mine.mean()),
                             float(abs_mine.mean() / rest_abs_mean)
                             if rest_abs_mean and rest_abs_mean == rest_abs_mean else float("nan"),
                             t_mean, t_abs, moves))
    return pd.DataFrame(rows, columns=columns)


# ---- the backtest ----------------------------------------------------------------------------


@dataclass
class BacktestRun:
    """Everything one backtest run produced; passed to `window_section` (Task 4.5)."""

    events: List[EventRecord]
    reactions: pd.DataFrame
    model: NewsModel
    targets: List[str]
    horizons: List[str]
    min_events: int
    results: List[EvalResult] = field(default_factory=list)
    skipped: List[tuple] = field(default_factory=list)  # (target, horizon, known reactions)
    categories: pd.DataFrame = field(default_factory=pd.DataFrame)


def known_reaction_counts(model: NewsModel, targets: Sequence[str],
                          horizons: Sequence[str]) -> Dict[tuple, int]:
    """Events with a usable reaction per (target, horizon), as the model sees them."""
    return {(t, h): int(np.count_nonzero(~np.isnan(model.outcomes(t, h).values)))
            for t in targets for h in horizons}


def run_backtest(events: Sequence[EventRecord], reactions: pd.DataFrame,
                 targets: Sequence[str], horizons: Sequence[str],
                 min_events: int = PROVEN_MIN_N,
                 price_loader: Optional[PriceLoader] = None) -> BacktestRun:
    """Walk-forward test every target and horizon with at least `min_events` known
    reactions; the rest are listed in `skipped`."""
    library = EventLibrary(events)
    model = NewsModel(library, reactions, price_loader=price_loader)
    run = BacktestRun(list(library.events), reactions, model, list(targets), list(horizons),
                      min_events)
    counts = known_reaction_counts(model, targets, horizons)
    for target in targets:
        for horizon in horizons:
            if counts[(target, horizon)] < min_events:
                run.skipped.append((target, horizon, counts[(target, horizon)]))
                continue
            run.results.append(model.walk_forward(target, horizon))
    run.categories = category_summary(run.events, reactions, targets, horizons, min_events)
    return run


# ---- Task 4.5 slot: profitable-window section --------------------------------------------------


@dataclass
class WindowSection:
    """Extra output from Task 4.5: printable text and a JSON-ready payload."""

    text: str
    data: object


WINDOW_DIRECTION_HORIZON = "1d"  # the headline prediction whose sign sets the direction


def window_section(run: BacktestRun) -> Optional[WindowSection]:
    """Profitable-window check (Task 4.5): per target, exiting at each held-out event's window
    (its median peak horizon) versus holding to day 10, both signed by the 1d prediction.

    Windows use only analogs whose whole path had finished before each event (no look-ahead).
    Printed after the category summary and saved under "window" in results.json. None when no
    target has a 1d walk-forward result.
    """
    by_target = {r.target: r for r in run.results
                 if r.horizon == WINDOW_DIRECTION_HORIZON and r.predictions is not None}
    if not by_target:
        return None
    rows = []
    for target in run.targets:
        result = by_target.get(target)
        if result is None:
            continue
        cases = window_cases(run.model, target, result.predictions, HORIZONS)
        ev = evaluate_window_rule(cases, HOLD_HORIZON)
        rows.append({
            "target": target, "events": len(cases),
            "windows": sum(1 for c in cases if c.window.usable), "n": ev.n,
            "mean_window": ev.mean_window, "mean_hold": ev.mean_hold,
            "mean_diff": ev.mean_diff, "t_stat": ev.t_stat, "beat_rate": ev.beat_rate,
        })
    table = pd.DataFrame([{
        "target": r["target"], "events": r["events"], "windows": r["windows"], "n": r["n"],
        "follow_window": _pct(r["mean_window"], 3), f"hold_{HOLD_HORIZON}": _pct(r["mean_hold"], 3),
        "mean_diff": _pct(r["mean_diff"], 3),
        "t_stat": "" if r["t_stat"] != r["t_stat"] else f"{r['t_stat']:+.2f}",
        "beat_rate": "" if r["beat_rate"] != r["beat_rate"] else f"{r['beat_rate']:.3f}",
    } for r in rows])
    text = (
        f"Profitable window (direction = sign of the {WINDOW_DIRECTION_HORIZON} prediction; "
        f"out-of-sample events only)\n"
        f"Exit at the window's median peak vs hold to {HOLD_HORIZON}; returns signed by the "
        "direction. events = held-out events, windows = events with enough finished analogs,\n"
        f"n = events with both returns known, t_stat = paired t of (window - hold), "
        f"beat_rate = share where the window beat holding.\n"
        + table.to_string(index=False)
    )
    return WindowSection(text, [{k: _clean(v) for k, v in r.items()} for r in rows])


# ---- results file ------------------------------------------------------------------------------


def _clean(value):
    """JSON-safe value: NaN/inf become null, numpy scalars become Python numbers."""
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        value = float(value)
        return value if math.isfinite(value) else None
    return value


def results_payload(run: BacktestRun, store_path: Optional[Path] = None,
                    window: Optional[WindowSection] = None) -> dict:
    """The results.json document (version RESULTS_VERSION)."""
    started = [e.started_at for e in run.events]
    results = [{
        "target": r.target, "horizon": r.horizon, "return_kind": return_kind(r.target),
        "n": int(r.n), "hit_rate": _clean(r.hit_rate),
        "mean_signed_return": _clean(r.mean_signed_return), "t_stat": _clean(r.t_stat),
        "proven": bool(r.proven), "years": [int(y) for y in r.years],
    } for r in run.results]
    categories = [{k: _clean(v) for k, v in row.items()}
                  for row in run.categories.to_dict(orient="records")]
    return {
        "version": RESULTS_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "store": str(store_path) if store_path else None,
        "n_events": len(run.events),
        "first_event": min(started).isoformat() if started else None,
        "last_event": max(started).isoformat() if started else None,
        "targets": run.targets,
        "horizons": run.horizons,
        "min_events": run.min_events,
        "proven_rule": {"min_n": PROVEN_MIN_N, "min_abs_t": PROVEN_MIN_ABS_T,
                        "min_hit_rate": 0.5},
        "results": results,
        "skipped": [{"target": t, "horizon": h, "n_reactions": int(n)}
                    for t, h, n in run.skipped],
        "categories": categories,
        "market_moving": market_moving_from_rows(categories),
        "window": window.data if window is not None else None,  # Task 4.5
    }


def save_results(payload: dict, path: Path = RESULTS_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)  # readers never see a half-written file
    return path


def market_moving_from_rows(categories: Iterable[dict],
                            indices: Sequence[str] = MARKET_INDICES,
                            horizon: str = "1d") -> List[str]:
    """Categories that move at least one main index at `horizon` (for events.py's hook)."""
    return sorted({row["category"] for row in categories
                   if row.get("moves") and row.get("target") in indices
                   and row.get("horizon") == horizon and row.get("category") != "other"})


@dataclass
class BacktestResults:
    """results.json as read back by the live monitor, report and dashboard."""

    data: dict = field(default_factory=dict)

    def result(self, target: str, horizon: str) -> Optional[dict]:
        symbol = target.strip().upper()
        for row in self.data.get("results", []):
            if row["target"].upper() == symbol and row["horizon"] == horizon:
                return row
        return None

    def is_proven(self, target: str, horizon: str) -> bool:
        """True only when the backtest proved this target and horizon; unknown -> False."""
        row = self.result(target, horizon)
        return bool(row and row.get("proven"))

    def market_moving(self) -> List[str]:
        return list(self.data.get("market_moving", []))

    @property
    def window(self):
        return self.data.get("window")


def load_results(path: Path = RESULTS_PATH) -> BacktestResults:
    """Read results.json; a missing or unreadable file means nothing is proven."""
    try:
        return BacktestResults(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return BacktestResults({})


# ---- printing ---------------------------------------------------------------------------------


def _pct(value: float, digits: int = 2) -> str:
    return "" if value != value else f"{value * 100:+.{digits}f}%"


def _years(years: Sequence[int]) -> str:
    return f"{min(years)}-{max(years)}" if years else ""


def results_table(run: BacktestRun) -> pd.DataFrame:
    order = {h: i for i, h in enumerate(HORIZONS)}
    rows = [{
        "target": r.target, "horizon": r.horizon, "kind": return_kind(r.target), "n": r.n,
        "hit_rate": "" if r.hit_rate != r.hit_rate else f"{r.hit_rate:.3f}",
        "mean_signed": _pct(r.mean_signed_return, 3),
        "t_stat": "" if r.t_stat != r.t_stat else f"{r.t_stat:+.2f}",
        "proven": "yes" if r.proven else "no", "test_years": _years(r.years),
    } for r in sorted(run.results, key=lambda r: (r.target, order.get(r.horizon, 99)))]
    return pd.DataFrame(rows)


def category_table(categories: pd.DataFrame, horizon: str) -> pd.DataFrame:
    """Category x target grid of mean return at one horizon; '*' marks `moves`."""
    sub = categories[categories["horizon"] == horizon]
    if sub.empty:
        return pd.DataFrame()
    cells = sub.assign(cell=[
        f"{_pct(m, 2)}{'*' if mv else ''} ({n})"
        for m, mv, n in zip(sub["mean_return"], sub["moves"], sub["n"])])
    return cells.pivot(index="category", columns="target", values="cell").fillna("")


def print_report(run: BacktestRun, category_horizon: str, window: Optional[WindowSection]) -> None:
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 50)
    pd.set_option("display.max_rows", 500)
    if run.events:
        first = min(e.started_at for e in run.events).date()
        last = max(e.started_at for e in run.events).date()
        print(f"Events: {len(run.events)} ({first} to {last})")
    else:
        print("Events: 0")
    print("\nWalk-forward results (expanding window by year; out-of-sample only)")
    table = results_table(run)
    print(table.to_string(index=False) if not table.empty else "  no target/horizon had "
          f"at least {run.min_events} events with a known reaction")
    if run.skipped:
        print(f"\nSkipped {len(run.skipped)} target/horizon pairs with fewer than "
              f"{run.min_events} known reactions (see results.json 'skipped').")
    print(f"\nCategory summary at {category_horizon}: mean return (events); "
          "* = moves the target (|t| >= 2 on the mean, or bigger moves than other events)")
    grid = category_table(run.categories, category_horizon)
    print(grid.to_string() if not grid.empty else "  no reactions at this horizon")
    moving = market_moving_from_rows(run.categories.to_dict(orient="records"),
                                     horizon=category_horizon)
    print(f"Market-moving categories (move ^HSI or ^GSPC at {category_horizon}): "
          f"{', '.join(moving) if moving else 'none yet'}")
    if window is not None:  # Task 4.5 section
        print()
        print(window.text)


# ---- CLI -------------------------------------------------------------------------------------


def _date(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _holdings(portfolio_path: Optional[str]) -> List[str]:
    """Symbols held in the user's portfolio, or [] when there is none."""
    from stock_advisor.portfolio import load_portfolio, resolve_portfolio_path
    from stock_advisor.transactions import build_portfolio_from_transactions

    path = resolve_portfolio_path(portfolio_path)
    if path is None:
        return []
    if path.suffix.lower() == ".csv":
        portfolio = build_portfolio_from_transactions(path)
    else:
        portfolio = load_portfolio(path)
    return list(portfolio.positions.keys()) if portfolio else []


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Walk-forward backtest of the news model: per target and horizon, out-of-sample "
            "hit rate, mean signed return, Welch t-stat and whether it is proven."
        )
    )
    parser.add_argument("--targets", nargs="+", default=None,
                        help="Targets to test (default: index, sector and HK proxies plus holdings).")
    parser.add_argument("--portfolio", default=None,
                        help="Portfolio JSON/CSV for the default holdings.")
    parser.add_argument("--horizons", nargs="+", default=list(HORIZONS), choices=HORIZONS,
                        metavar="H", help="Horizons to test (default: all: %(default)s).")
    parser.add_argument("--start", type=_date, default=None,
                        help="First event date, YYYY-MM-DD (default: earliest).")
    parser.add_argument("--end", type=_date, default=None,
                        help="End date (exclusive), YYYY-MM-DD (default: latest).")
    parser.add_argument("--min-events", type=int, default=PROVEN_MIN_N,
                        help="Skip a target/horizon with fewer known reactions (default: %(default)s).")
    parser.add_argument("--category-horizon", default="1d", choices=HORIZONS,
                        help="Horizon printed in the category summary (default: %(default)s).")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH,
                        help="News store (opened read-only; default: %(default)s).")
    parser.add_argument("--cache-dir", type=Path, default=MODEL_CACHE_DIR,
                        help="Where reactions.parquet and results.json go (default: %(default)s).")
    parser.add_argument("--rebuild-reactions", action="store_true",
                        help="Ignore the cached reaction table and rebuild it.")
    return parser


def main(argv: Optional[Sequence[str]] = None, price_loader: Optional[PriceLoader] = None,
         reaction_builder: ReactionBuilder = build_reaction_table) -> int:
    """Run the backtest. `price_loader` and `reaction_builder` are injectable for tests;
    None uses `reactions.default_price_loader` (price cache, fetching daily data if stale)."""
    args = build_arg_parser().parse_args(argv)
    if price_loader is None:
        from stock_advisor.news.reactions import default_price_loader
        price_loader = default_price_loader
    if args.targets:
        targets = [t.strip().upper() for t in args.targets]
    else:
        from stock_advisor.config import news_targets
        targets = news_targets(_holdings(args.portfolio))

    with ReadOnlyStore(args.db) as store:
        events = load_event_records(store, args.start, args.end)
        precisions = store.event_precisions()
    print(f"Loaded {len(events)} events from {args.db} (read-only).")
    if not events:
        # Not an error (e.g. the backfill has not scored anything yet); results.json is left
        # as it was so a narrow --start/--end never wipes earlier results.
        print("No scored events in this range; nothing to backtest. results.json unchanged.")
        return 0

    reactions = load_or_build_reactions(
        events, targets, args.cache_dir / REACTIONS_FILE, price_loader, precisions,
        builder=reaction_builder, rebuild=args.rebuild_reactions)
    run = run_backtest(events, reactions, targets, args.horizons, args.min_events, price_loader)
    window = window_section(run)
    print_report(run, args.category_horizon, window)
    path = save_results(results_payload(run, args.db, window), args.cache_dir / RESULTS_FILE)
    print(f"\nSaved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
