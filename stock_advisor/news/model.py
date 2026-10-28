"""Analog and regression model: predict an event's market reaction from similar past events.

How a prediction is made, for one event, target and horizon
-----------------------------------------------------------
1. Analogs: the k=20 earlier events most similar in meaning (cosine similarity of the event
   embeddings) whose reaction for that target and horizon was already known at the event's
   time. "Known" means the analog's reaction had finished: its start time plus the horizon
   (daily horizons use a calendar allowance, `_realized_lag`) is at or before the event time.
   Their similarity-weighted mean reaction is the analog prediction.
2. Features: category one-hot, tone, log(1 + source count), high_impact, the analog prediction
   and the target's 20-day volatility before the event day.
3. Ridge regression per (target, horizon). Alpha (the penalty strength) is chosen by
   time-ordered cross-validation inside the training rows only. The uncertainty band comes from
   the out-of-fold residuals (prediction errors on held-back blocks).

The predicted return is the market-adjusted return for stocks and sector funds, and the raw
return for indices (see `return_kind`). Intraday horizons use only reactions measured from
intraday bars (start_source other than "1d").

Scaling: events sit in one time-sorted, unit-length embedding matrix. Analog search for many
events runs as chunked matrix products over the earlier rows only; each event keeps a short
candidate list (5k most similar earlier events) that is shared by every target and horizon.
New, later events append without recomputing older ones (`EventLibrary.extend`).

`walk_forward` is the out-of-sample check (expanding window by calendar year) that decides
whether a target and horizon is `proven` (decision 2026-10-27: unproven predictions only warn).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from stock_advisor.news.categories import CATEGORIES
from stock_advisor.news.reactions import HORIZONS
from stock_advisor.news.scoring import embedding_from_bytes

DEFAULT_K = 20
CANDIDATE_FACTOR = 5  # candidates kept per event = factor * k, filtered per target/horizon
DEFAULT_ALPHAS: Tuple[float, ...] = (0.01, 0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0)
DEFAULT_FOLDS = 5
MIN_TRAIN_ROWS = 30
VOL_WINDOW = 20
BAND_LEVEL = 0.8  # the uncertainty band covers the middle 80% of out-of-fold errors

# `proven` bar, matching validation.rank_metrics and plan Task 4.4.
PROVEN_MIN_N = 30
PROVEN_MIN_ABS_T = 2.0

INTRADAY_HORIZONS = ("1m", "5m", "15m", "1h", "4h")
_INTRADAY_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}
_DAILY_CLOSES = {"1d": 1, "2d": 2, "3d": 3, "5d": 5, "10d": 10}
_NS = 1_000_000_000
_DAY_NS = 86_400 * _NS
_SEARCH_BUDGET = 32_000_000  # similarity cells per chunk (~128 MB of float32)

FEATURE_NAMES: Tuple[str, ...] = tuple(f"cat_{c}" for c in CATEGORIES) + (
    "tone", "log_sources", "high_impact", "analog_mean", "vol_20d",
)
_CAT_INDEX = {c: i for i, c in enumerate(CATEGORIES)}

DailyLoader = Callable[[str, str], Optional[pd.DataFrame]]


def _realized_lag(horizon: str) -> int:
    """Nanoseconds after a reaction's start by which its horizon has surely finished.

    Intraday: the horizon itself. Daily: N closes take at most ceil(N * 7/5) + 3 calendar days
    (weekends plus a holiday allowance), e.g. "1d" -> 5 days, "10d" -> 17 days.
    """
    if horizon in _INTRADAY_SECONDS:
        return _INTRADAY_SECONDS[horizon] * _NS
    n = _DAILY_CLOSES[horizon]
    return (math.ceil(n * 7 / 5) + 3) * _DAY_NS


def is_index(target: str) -> bool:
    """True for indices and index trackers, which are predicted on raw returns."""
    from stock_advisor.config import MARKET_INDEX_FOR, NEWS_TARGETS

    symbol = target.strip().upper()
    if symbol.startswith("^") or MARKET_INDEX_FOR(symbol) == symbol:
        return True
    return NEWS_TARGETS.get(symbol, {}).get("kind") == "index"


def return_kind(target: str) -> str:
    """Reaction column predicted for a target: "raw" for indices, "adjusted" otherwise."""
    return "raw" if is_index(target) else "adjusted"


def _to_ns(moment) -> int:
    t = pd.Timestamp(moment)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return int(t.as_unit("ns").value)


# ---- events ---------------------------------------------------------------------------------


@dataclass
class EventRecord:
    """What the model needs about one event. `embedding` need not be unit length."""

    id: str
    started_at: datetime
    embedding: np.ndarray
    category: Optional[str] = None
    tone: float = 0.0
    n_sources: int = 1
    high_impact: bool = False
    title: str = ""


def load_event_records(store, start: Optional[datetime] = None,
                       end: Optional[datetime] = None) -> List[EventRecord]:
    """Read events with their mean member embedding and mean member tone from the store.

    One streaming pass over the members (rows arrive grouped by event), so it works for
    millions of items. Events without any embedded member are skipped.
    (Lives here because the store has no such query yet; see the Task 4.3 report.)
    """
    from stock_advisor.news.store import _from_text, _to_text

    clauses, params = ["s.embedding IS NOT NULL"], []
    if start is not None:
        clauses.append("e.started_at >= ?")
        params.append(_to_text(start))
    if end is not None:
        clauses.append("e.started_at < ?")
        params.append(_to_text(end))
    rows = store._conn.execute(
        "SELECT e.id, e.started_at, e.category, e.title, e.n_sources, e.high_impact, "
        "s.embedding, s.tone FROM events e JOIN scores s ON s.event_id = e.id "
        f"WHERE {' AND '.join(clauses)} ORDER BY e.started_at, e.id",
        params,
    )
    out: List[EventRecord] = []
    current = None
    vec_sum, tones = None, []

    def flush() -> None:
        if current is None:
            return
        out.append(EventRecord(
            id=current["id"], started_at=_from_text(current["started_at"]),
            embedding=vec_sum.astype(np.float32), category=current["category"],
            tone=float(np.mean(tones)) if tones else 0.0,
            n_sources=int(current["n_sources"] or 1), high_impact=bool(current["high_impact"]),
            title=current["title"] or "",
        ))

    for row in rows:
        if current is None or row["id"] != current["id"]:
            flush()
            current, vec_sum, tones = row, None, []
        vec = embedding_from_bytes(row["embedding"]).astype(np.float64)
        vec_sum = vec if vec_sum is None else vec_sum + vec
        if row["tone"] is not None:
            tones.append(float(row["tone"]))
    flush()
    return out


class EventLibrary:
    """Events in time order with a unit-length embedding matrix, for analog search.

    `extend` appends later events cheaply; an event older than the newest one triggers a full
    re-sort. Each event's candidate list (most similar strictly-earlier events, by descending
    similarity) is computed lazily in chunks and kept.
    """

    def __init__(self, events: Iterable[EventRecord] = (), k: int = DEFAULT_K,
                 candidate_factor: int = CANDIDATE_FACTOR) -> None:
        self.k = k
        self.n_candidates = max(k, k * candidate_factor)
        self.version = 0
        self.events: List[EventRecord] = []
        self.position: Dict[str, int] = {}
        self._matrix = np.zeros((0, 0), dtype=np.float32)
        self._times = np.zeros(0, dtype=np.int64)
        self._cand_idx = np.zeros((0, self.n_candidates), dtype=np.int32)
        self._cand_sim = np.zeros((0, self.n_candidates), dtype=np.float32)
        self.extend(events)

    def __len__(self) -> int:
        return len(self.events)

    @property
    def matrix(self) -> np.ndarray:
        return self._matrix[: len(self.events)]

    @property
    def times(self) -> np.ndarray:
        return self._times[: len(self.events)]

    def extend(self, events: Iterable[EventRecord]) -> None:
        new = [e for e in events if e.id not in self.position]
        if not new:
            return
        new.sort(key=lambda e: (_to_ns(e.started_at), e.id))
        if self.events and _to_ns(new[0].started_at) < int(self._times[len(self.events) - 1]):
            self._rebuild(self.events + new)
        else:
            self._append(new)
        self.version += 1

    def _rebuild(self, events: List[EventRecord]) -> None:
        self.events, self.position = [], {}
        self._matrix = np.zeros((0, 0), dtype=np.float32)
        self._times = np.zeros(0, dtype=np.int64)
        self._cand_idx = self._cand_idx[:0]
        self._cand_sim = self._cand_sim[:0]
        events.sort(key=lambda e: (_to_ns(e.started_at), e.id))
        self._append(events)

    def _append(self, new: List[EventRecord]) -> None:
        n_old, n_new = len(self.events), len(new)
        vectors = np.vstack([np.asarray(e.embedding, dtype=np.float32) for e in new])
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = vectors / np.maximum(norms, 1e-12)
        dim = vectors.shape[1]
        if self._matrix.shape[1] not in (0, dim):
            raise ValueError(f"embedding size {dim} != library size {self._matrix.shape[1]}")
        needed = n_old + n_new
        if self._matrix.shape[0] < needed:  # grow by doubling, like EventClusterer
            capacity = max(needed, 2 * self._matrix.shape[0], 64)
            grown = np.zeros((capacity, dim), dtype=np.float32)
            if n_old:
                grown[:n_old] = self._matrix[:n_old]
            self._matrix = grown
            times = np.zeros(capacity, dtype=np.int64)
            times[:n_old] = self._times[:n_old]
            self._times = times
        self._matrix[n_old:needed] = vectors
        self._times[n_old:needed] = [_to_ns(e.started_at) for e in new]
        for offset, event in enumerate(new):
            self.position[event.id] = n_old + offset
        self.events.extend(new)

    # -- analog search ---------------------------------------------------------------------

    def search(self, queries: np.ndarray, cutoffs: np.ndarray,
               n_candidates: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray]:
        """Most similar events among the first `cutoffs[i]` library rows, for each query row.

        `queries` must be unit length. Returns (indices, similarities), each (m, K), sorted by
        descending similarity; -1 / NaN pad rows with fewer than K earlier events. Rows are
        processed in chunks so memory stays near `_SEARCH_BUDGET` cells; the product only
        spans the columns the chunk can see, so time-sorted queries cost about half of n^2.
        """
        k_cand = n_candidates or self.n_candidates
        m = len(queries)
        out_idx = np.full((m, k_cand), -1, dtype=np.int32)
        out_sim = np.full((m, k_cand), np.nan, dtype=np.float32)
        if m == 0 or len(self.events) == 0:
            return out_idx, out_sim
        matrix = self.matrix
        cutoffs = np.asarray(cutoffs, dtype=np.int64)
        start = 0
        while start < m:
            # Shrink the chunk until rows * visible columns fits the budget.
            rows = max(1, _SEARCH_BUDGET // int(max(cutoffs[start], 1)))
            while True:
                span = int(cutoffs[start:start + rows].max())
                if rows == 1 or rows * span <= _SEARCH_BUDGET:
                    break
                rows = max(1, _SEARCH_BUDGET // span)
            stop = min(m, start + rows)
            cut = cutoffs[start:stop]
            if span > 0:
                sims = queries[start:stop] @ matrix[:span].T
                low = int(cut.min())  # columns before `low` are earlier for every row
                if low < span:
                    tail = sims[:, low:]
                    tail[np.arange(low, span)[None, :] >= cut[:, None]] = -np.inf
                kk = min(k_cand, span)
                if span > kk:
                    part = np.argpartition(sims, span - kk, axis=1)[:, span - kk:]
                else:
                    part = np.broadcast_to(np.arange(span), (len(cut), span)).copy()
                part_sims = np.take_along_axis(sims, part, axis=1)
                order = np.argsort(-part_sims, axis=1, kind="stable")
                part = np.take_along_axis(part, order, axis=1)
                part_sims = np.take_along_axis(part_sims, order, axis=1)
                ok = np.isfinite(part_sims)
                out_idx[start:stop, :kk] = np.where(ok, part, -1)
                out_sim[start:stop, :kk] = np.where(ok, part_sims, np.nan)
            start = stop
        return out_idx, out_sim

    def id_index(self) -> pd.Index:
        """Event ids in library order (cached per version), for aligning reaction rows."""
        if getattr(self, "_id_index_version", None) != self.version:
            self._id_index = pd.Index([e.id for e in self.events])
            self._id_index_version = self.version
        return self._id_index

    def earlier_count(self, time_ns) -> np.ndarray:
        """Number of library events strictly earlier than each given time."""
        return np.searchsorted(self.times, np.asarray(time_ns, dtype=np.int64), side="left")

    def candidates(self) -> Tuple[np.ndarray, np.ndarray]:
        """Candidate analogs for every library event; computes only rows not yet done."""
        n, done = len(self.events), len(self._cand_idx)
        if done < n:
            idx, sim = self.search(self.matrix[done:n], self.earlier_count(self.times[done:n]))
            self._cand_idx = np.vstack([self._cand_idx, idx])
            self._cand_sim = np.vstack([self._cand_sim, sim])
        return self._cand_idx, self._cand_sim

    def candidates_for(self, event: EventRecord) -> Tuple[np.ndarray, np.ndarray, int]:
        """(indices, similarities, time ns) for one event, in the library or not."""
        pos = self.position.get(event.id)
        if pos is not None:
            t = int(self.times[pos])
            if pos < len(self._cand_idx):
                return self._cand_idx[pos], self._cand_sim[pos], t
            # Search this one row only: the full table compares every pair of events, which
            # takes hours on the live store (450k events) when only a few events are analyzed.
            idx, sim = self.search(self.matrix[pos:pos + 1], self.earlier_count([t]))
            return idx[0], sim[0], t
        vec = np.asarray(event.embedding, dtype=np.float32)
        vec = vec / max(float(np.linalg.norm(vec)), 1e-12)
        t = _to_ns(event.started_at)
        idx, sim = self.search(vec[None, :], self.earlier_count([t]))
        return idx[0], sim[0], t


# ---- reactions, analogs, volatility ---------------------------------------------------------


@dataclass
class _Outcomes:
    """One target and horizon's reactions aligned to library order."""

    values: np.ndarray  # NaN where unknown
    realized_ns: np.ndarray  # when the reaction was surely finished; int64 max where unknown


def _outcomes(library: EventLibrary, reactions: pd.DataFrame, target: str,
              horizon: str) -> _Outcomes:
    n = len(library)
    values = np.full(n, np.nan)
    realized = np.full(n, np.iinfo(np.int64).max, dtype=np.int64)
    rows = reactions[(reactions["target"] == target) & (reactions["horizon"] == horizon)]
    if horizon in INTRADAY_HORIZONS and "start_source" in rows:
        rows = rows[rows["start_source"].astype(object) != "1d"]
    if rows.empty or n == 0:
        return _Outcomes(values, realized)
    pos = library.id_index().get_indexer(rows["event_id"])
    keep = pos >= 0
    pos = pos[keep]
    vals = rows[return_kind(target)].to_numpy(float)[keep]
    starts = library.times[pos].copy()
    if "start_ts" in rows:
        start_ts = pd.DatetimeIndex(pd.to_datetime(rows["start_ts"], utc=True)).as_unit("ns")
        has = ~np.asarray(start_ts.isna())[keep]
        starts[has] = start_ts.asi8[keep][has]
    values[pos] = vals
    known = ~np.isnan(vals)
    realized[pos[known]] = starts[known] + _realized_lag(horizon)
    return _Outcomes(values, realized)


def _select_analogs(cand_idx: np.ndarray, cand_sim: np.ndarray, query_ns: np.ndarray,
                    outcomes: _Outcomes, k: int) -> Tuple[np.ndarray, np.ndarray]:
    """For candidate rows (m, K): mask of the first k usable analogs and their weighted mean.

    Usable = has a reaction for this target/horizon that had finished by the query time.
    """
    safe = np.where(cand_idx >= 0, cand_idx, 0)
    values = outcomes.values[safe]
    usable = (
        (cand_idx >= 0)
        & ~np.isnan(values)
        & (outcomes.realized_ns[safe] <= np.asarray(query_ns)[:, None])
    )
    take = usable & (np.cumsum(usable, axis=1) <= k)
    weights = np.where(take, np.clip(np.nan_to_num(cand_sim), 0.0, None), 0.0)
    total = weights.sum(axis=1)
    weighted = (weights * np.where(take, values, 0.0)).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(total > 0, weighted / np.where(total > 0, total, 1.0), np.nan)
    return take, mean


def pre_event_volatility(daily: Optional[pd.DataFrame], times_ns: np.ndarray,
                         window: int = VOL_WINDOW) -> np.ndarray:
    """Std of daily log returns over the `window` sessions before each event's local date.

    The event day's own close is never used (it may come after the event). NaN when the
    history is too short or missing.
    """
    times_ns = np.asarray(times_ns, dtype=np.int64)
    out = np.full(len(times_ns), np.nan)
    if daily is None or len(daily) == 0 or "Close" not in daily:
        return out
    closes = daily["Close"].dropna().sort_index()
    if len(closes) <= window:
        return out
    index = pd.DatetimeIndex(closes.index)
    tz = index.tz if index.tz is not None else timezone.utc
    dates = index.tz_localize(None).normalize().to_numpy().astype("datetime64[D]")
    vol = np.log(closes.to_numpy(float)).astype(float)
    vol = pd.Series(np.diff(vol, prepend=np.nan)).rolling(window).std().to_numpy()
    event_dates = (
        pd.DatetimeIndex(times_ns.astype("datetime64[ns]")).tz_localize("UTC").tz_convert(tz)
        .tz_localize(None).normalize().to_numpy().astype("datetime64[D]")
    )
    last = np.searchsorted(dates, event_dates, side="left") - 1  # last session before the date
    ok = last >= 0
    out[ok] = vol[last[ok]]
    return out


# ---- ridge regression -----------------------------------------------------------------------


@dataclass
class _Ridge:
    mean: np.ndarray
    scale: np.ndarray
    coef: np.ndarray  # on standardized features
    intercept: float

    def predict(self, x: np.ndarray) -> np.ndarray:
        return ((x - self.mean) / self.scale) @ self.coef + self.intercept


def _fit_ridge(x: np.ndarray, y: np.ndarray, alpha: float) -> _Ridge:
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale = np.where(scale > 1e-12, scale, 1.0)
    z = (x - mean) / scale
    y_mean = float(y.mean())
    coef = np.linalg.solve(z.T @ z + alpha * np.eye(z.shape[1]), z.T @ (y - y_mean))
    return _Ridge(mean, scale, coef, y_mean)


def _time_folds(times: np.ndarray, realized: np.ndarray, n_folds: int,
                min_train: int) -> List[Tuple[np.ndarray, np.ndarray]]:
    """Expanding-window folds over time-sorted rows: train on earlier blocks, validate on the
    next. Training rows whose reaction finished after the block starts are purged."""
    n = len(times)
    edges = np.linspace(0, n, n_folds + 2).astype(int)
    folds = []
    for i in range(1, n_folds + 1):
        val = np.arange(edges[i], edges[i + 1])
        if len(val) == 0:
            continue
        train = np.arange(edges[i])
        train = train[realized[train] <= times[val[0]]]
        if len(train) >= min_train:
            folds.append((train, val))
    return folds


@dataclass
class _Fitted:
    ridge: _Ridge
    alpha: float
    residuals: np.ndarray  # out-of-fold (or in-sample when no fold was possible)
    vol_fill: float
    n_train: int


def _fit_with_cv(x: np.ndarray, y: np.ndarray, times: np.ndarray, realized: np.ndarray,
                 alphas: Sequence[float], n_folds: int) -> _Fitted:
    """Ridge with alpha chosen by time-ordered CV inside these rows (already time-sorted)."""
    folds = _time_folds(times, realized, n_folds, min_train=max(10, x.shape[1] // 2))
    best_alpha, best_err, best_resid = float(np.median(alphas)), np.inf, None
    if folds:
        for alpha in alphas:
            resid = []
            for train, val in folds:
                model = _fit_ridge(x[train], y[train], alpha)
                resid.append(y[val] - model.predict(x[val]))
            resid = np.concatenate(resid)
            err = float(np.mean(resid ** 2))
            if err < best_err:
                best_alpha, best_err, best_resid = alpha, err, resid
    ridge = _fit_ridge(x, y, best_alpha)
    if best_resid is None:
        best_resid = y - ridge.predict(x)
    return _Fitted(ridge, best_alpha, best_resid, float("nan"), len(y))


# ---- public results -------------------------------------------------------------------------


@dataclass
class Analog:
    """One similar past event and how the target reacted to it."""

    event_id: str
    started_at: datetime
    title: str
    category: Optional[str]
    similarity: float
    reaction: float


@dataclass
class Prediction:
    target: str
    horizon: str
    return_kind: str  # "raw" or "adjusted"
    predicted: float  # NaN when no model could be fitted for this target and horizon
    low: float  # uncertainty band (BAND_LEVEL of out-of-fold errors)
    high: float
    analog_mean: float  # similarity-weighted mean reaction of the analogs (NaN if none)
    analogs: List[Analog] = field(default_factory=list)
    n_train: int = 0
    alpha: float = float("nan")


@dataclass
class EvalResult:
    """Out-of-sample result of `walk_forward` for one target and horizon."""

    target: str
    horizon: str
    n: int
    hit_rate: float
    mean_signed_return: float  # mean return when following the predicted sign
    t_stat: float  # Welch t: actual return after predicted-up vs predicted-down events
    proven: bool
    years: List[int] = field(default_factory=list)
    predictions: Optional[pd.DataFrame] = None  # event_id, started_at, predicted, actual


def _welch_t(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    denom = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float((a.mean() - b.mean()) / denom) if denom > 0 else float("nan")


def score_predictions(predicted: np.ndarray, actual: np.ndarray) -> Tuple[int, float, float,
                                                                          float, bool]:
    """(n, hit rate, mean signed return, Welch t, proven) for out-of-sample predictions.

    proven = n >= 30, |t| >= 2 with the up-minus-down spread positive, and hit rate > 0.5
    (the bar of plan Task 4.4 and validation.rank_metrics).
    """
    predicted, actual = np.asarray(predicted, float), np.asarray(actual, float)
    ok = ~np.isnan(predicted) & ~np.isnan(actual)
    predicted, actual = predicted[ok], actual[ok]
    n = len(actual)
    if n == 0:
        return 0, float("nan"), float("nan"), float("nan"), False
    sign = np.sign(predicted)
    decided = (sign != 0) & (actual != 0)
    hit = float((np.sign(actual[decided]) == sign[decided]).mean()) if decided.any() else float("nan")
    signed = float((sign * actual).mean())
    up, down = actual[predicted > 0], actual[predicted < 0]
    t = _welch_t(up, down)
    spread = (up.mean() - down.mean()) if len(up) and len(down) else float("nan")
    proven = bool(
        n >= PROVEN_MIN_N and t == t and abs(t) >= PROVEN_MIN_ABS_T and spread > 0
        and hit == hit and hit > 0.5
    )
    return n, hit, signed, t, proven


# ---- the model ------------------------------------------------------------------------------


@dataclass
class FeatureSet:
    """Features for every library event, for one target and horizon (library order)."""

    target: str
    horizon: str
    x: np.ndarray  # (n, len(FEATURE_NAMES)); NaN vol left for the fit to fill
    y: np.ndarray  # reaction, NaN when unknown
    times: np.ndarray  # event start, ns
    realized: np.ndarray  # when y was surely known, ns


class NewsModel:
    """Analog + ridge model over an `EventLibrary` and a long reaction table.

    `reactions` has the columns of `reactions.build_reaction_table`. `price_loader(symbol,
    "1d")` returns daily OHLC frames for the volatility feature (None disables it).
    """

    def __init__(self, library: EventLibrary, reactions: pd.DataFrame,
                 price_loader: Optional[DailyLoader] = None,
                 alphas: Sequence[float] = DEFAULT_ALPHAS, n_folds: int = DEFAULT_FOLDS,
                 band_level: float = BAND_LEVEL) -> None:
        self.library = library
        self.reactions = reactions
        self.price_loader = price_loader
        self.alphas = tuple(alphas)
        self.n_folds = n_folds
        self.band_level = band_level
        self.models: Dict[Tuple[str, str], _Fitted] = {}
        self._features: Dict[Tuple[str, str], Tuple[int, FeatureSet]] = {}
        self._outcomes_cache: Dict[Tuple[str, str], Tuple[int, _Outcomes]] = {}
        self._daily: Dict[str, Optional[pd.DataFrame]] = {}

    # -- features --------------------------------------------------------------------------

    def _daily_prices(self, target: str) -> Optional[pd.DataFrame]:
        if self.price_loader is None:
            return None
        if target not in self._daily:
            self._daily[target] = self.price_loader(target, "1d")
        return self._daily[target]

    def outcomes(self, target: str, horizon: str) -> _Outcomes:
        key = (target, horizon)
        cached = self._outcomes_cache.get(key)
        if cached is None or cached[0] != self.library.version:
            cached = (self.library.version, _outcomes(self.library, self.reactions, target, horizon))
            self._outcomes_cache[key] = cached
        return cached[1]

    @staticmethod
    def _static_features(events: Sequence[EventRecord]) -> np.ndarray:
        n = len(events)
        x = np.zeros((n, len(FEATURE_NAMES)))
        cats = [_CAT_INDEX.get(e.category or "other", _CAT_INDEX["other"]) for e in events]
        x[np.arange(n), cats] = 1.0
        base = len(CATEGORIES)
        x[:, base] = [float(e.tone or 0.0) for e in events]
        x[:, base + 1] = np.log1p([max(int(e.n_sources or 0), 0) for e in events])
        x[:, base + 2] = [1.0 if e.high_impact else 0.0 for e in events]
        return x

    def features(self, target: str, horizon: str) -> FeatureSet:
        """Features for every library event (cached until the library changes)."""
        key = (target, horizon)
        cached = self._features.get(key)
        if cached is not None and cached[0] == self.library.version:
            return cached[1]
        lib = self.library
        outcomes = self.outcomes(target, horizon)
        cand_idx, cand_sim = lib.candidates()
        times = lib.times.copy()
        x = self._static_features(lib.events)
        _, analog_mean = _select_analogs(cand_idx, cand_sim, times, outcomes, lib.k)
        x[:, FEATURE_NAMES.index("analog_mean")] = analog_mean
        x[:, FEATURE_NAMES.index("vol_20d")] = pre_event_volatility(
            self._daily_prices(target), times)
        fs = FeatureSet(target, horizon, x, outcomes.values.copy(), times, outcomes.realized_ns)
        self._features[key] = (lib.version, fs)
        return fs

    def analogs(self, event: EventRecord, target: str, horizon: str) -> Tuple[List[Analog], float]:
        """The k analogs used for `event` (most similar first) and their weighted mean."""
        idx, sim, t = self.library.candidates_for(event)
        outcomes = self.outcomes(target, horizon)
        take, mean = _select_analogs(idx[None, :], sim[None, :], np.array([t]), outcomes,
                                     self.library.k)
        result = []
        for j in np.flatnonzero(take[0]):
            past = self.library.events[int(idx[j])]
            result.append(Analog(past.id, past.started_at, past.title, past.category,
                                 float(sim[j]), float(outcomes.values[int(idx[j])])))
        return result, float(mean[0])

    @staticmethod
    def _prepare(x: np.ndarray, vol_fill: float) -> np.ndarray:
        x = x.copy()
        a, v = FEATURE_NAMES.index("analog_mean"), FEATURE_NAMES.index("vol_20d")
        x[:, a] = np.nan_to_num(x[:, a], nan=0.0)
        x[:, v] = np.where(np.isnan(x[:, v]), vol_fill, x[:, v])
        return x

    # -- fitting ---------------------------------------------------------------------------

    def _fit_rows(self, fs: FeatureSet, rows: np.ndarray) -> Optional[_Fitted]:
        rows = rows[~np.isnan(fs.y[rows])]
        if len(rows) < MIN_TRAIN_ROWS:
            return None
        vol = fs.x[rows, FEATURE_NAMES.index("vol_20d")]
        vol_fill = float(np.nanmedian(vol)) if np.any(~np.isnan(vol)) else 0.0
        x = self._prepare(fs.x[rows], vol_fill)
        fitted = _fit_with_cv(x, fs.y[rows], fs.times[rows], fs.realized[rows],
                              self.alphas, self.n_folds)
        fitted.vol_fill = vol_fill
        return fitted

    def fit(self, targets: Optional[Iterable[str]] = None,
            horizons: Iterable[str] = HORIZONS,
            train_end: Optional[datetime] = None) -> "NewsModel":
        """Fit one ridge per target and horizon on events whose reaction was known by
        `train_end` (all events when None). Pairs with < 30 rows get no model."""
        if targets is None:
            targets = sorted(self.reactions["target"].unique())
        cutoff = None if train_end is None else _to_ns(train_end)
        for target in targets:
            for horizon in horizons:
                # Too few known reactions can never fit: skip before `features`, whose
                # candidate table costs hours on the full live store.
                known = np.count_nonzero(~np.isnan(self.outcomes(target, horizon).values))
                if known < MIN_TRAIN_ROWS:
                    self.models.pop((target, horizon), None)
                    continue
                fs = self.features(target, horizon)
                rows = np.arange(len(fs.y))
                if cutoff is not None:
                    rows = rows[fs.realized <= cutoff]
                fitted = self._fit_rows(fs, rows)
                if fitted is None:
                    self.models.pop((target, horizon), None)
                else:
                    self.models[(target, horizon)] = fitted
        return self

    def coefficients(self, target: str, horizon: str) -> Dict[str, float]:
        """Standardized coefficients (effect of a 1-std change in each feature)."""
        fitted = self.models[(target, horizon)]
        return dict(zip(FEATURE_NAMES, map(float, fitted.ridge.coef)))

    # -- prediction ------------------------------------------------------------------------

    def _band(self, fitted: _Fitted, predicted: float) -> Tuple[float, float]:
        tail = (1.0 - self.band_level) / 2
        lo, hi = np.quantile(fitted.residuals, [tail, 1.0 - tail])
        return predicted + float(lo), predicted + float(hi)

    def predict(self, event: EventRecord, target: str, horizon: str) -> Prediction:
        """Predicted return, uncertainty band and analogs for one event (in the library or a
        new one). Uses only events strictly earlier than the event whose reaction had finished."""
        analogs, analog_mean = self.analogs(event, target, horizon)
        kind = return_kind(target)
        fitted = self.models.get((target, horizon))
        if fitted is None:
            return Prediction(target, horizon, kind, float("nan"), float("nan"), float("nan"),
                              analog_mean, analogs)
        x = self._static_features([event])
        x[0, FEATURE_NAMES.index("analog_mean")] = analog_mean
        x[0, FEATURE_NAMES.index("vol_20d")] = pre_event_volatility(
            self._daily_prices(target), np.array([_to_ns(event.started_at)]))[0]
        predicted = float(fitted.ridge.predict(self._prepare(x, fitted.vol_fill))[0])
        low, high = self._band(fitted, predicted)
        return Prediction(target, horizon, kind, predicted, low, high, analog_mean, analogs,
                          fitted.n_train, fitted.alpha)

    # -- out-of-sample check ---------------------------------------------------------------

    def walk_forward(self, target: str, horizon: str, min_train_years: int = 1) -> EvalResult:
        """Expanding window by calendar year: for each year, fit on events whose reaction was
        known by 1 January and predict that year's events. Features are as-of each event, so
        nothing from the future leaks in."""
        fs = self.features(target, horizon)
        rows_all = np.arange(len(fs.y))
        years = pd.DatetimeIndex(fs.times.astype("datetime64[ns]")).year.to_numpy()
        preds, actual, ids, used_years = [], [], [], []
        if len(years) == 0:
            return EvalResult(target, horizon, 0, float("nan"), float("nan"), float("nan"), False)
        for year in range(int(years.min()) + min_train_years, int(years.max()) + 1):
            test = rows_all[(years == year) & ~np.isnan(fs.y)]
            if len(test) == 0:
                continue
            cutoff = _to_ns(datetime(year, 1, 1, tzinfo=timezone.utc))
            fitted = self._fit_rows(fs, rows_all[fs.realized <= cutoff])
            if fitted is None:
                continue
            p = fitted.ridge.predict(self._prepare(fs.x[test], fitted.vol_fill))
            preds.append(p)
            actual.append(fs.y[test])
            ids.extend(test.tolist())
            used_years.append(year)
        if not preds:
            return EvalResult(target, horizon, 0, float("nan"), float("nan"), float("nan"), False)
        p, a = np.concatenate(preds), np.concatenate(actual)
        n, hit, signed, t, proven = score_predictions(p, a)
        frame = pd.DataFrame({
            "event_id": [self.library.events[i].id for i in ids],
            "started_at": pd.to_datetime(fs.times[ids], utc=True),
            "predicted": p, "actual": a,
        })
        return EvalResult(target, horizon, n, hit, signed, t, proven, used_years, frame)
