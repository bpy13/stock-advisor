"""Profitable window: how long a suggested action usually stays profitable (plan Task 4.5).

Decision 2026-10-27 (Brian): each suggested action also estimates how long it stays
profitable, from when similar past events' price paths usually peaked and reversed.

How a window is estimated, for one event, target and predicted direction
------------------------------------------------------------------------
1. Analog paths: the cumulative reaction paths (return at 1m, 5m, ... 10d) of the most similar
   earlier events whose whole path had finished by the event's time (the model's purge rule,
   applied to the longest horizon). See `analog_paths`.
2. Each path is signed by the predicted direction (+1 up, -1 down), so "profit" is positive.
   The peak time is the horizon with the highest signed return (ties: the earliest). A path
   whose highest signed return is <= 0 was never profitable.
3. Among the profitable analogs, the similarity-weighted 25th, 50th and 75th percentiles of the
   peak times give the window, e.g. peaks mostly between 1 and 3 days -> "exit within 1–3 days".
   When most peaks sit at the last horizon the move had not reversed: "no reversal within
   10 days".

`evaluate_window_rule` is the out-of-sample check: across held-out events, exiting at the
window's median peak horizon versus holding to day 10.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, List, Mapping, Optional, Sequence, Union

import numpy as np
import pandas as pd

from stock_advisor.news.reactions import HORIZONS

MIN_ANALOGS = 8  # fewer usable analogs than this gives "not enough similar events"
NO_REVERSAL_SHARE = 0.5  # weighted share of peaks at the last horizon that means "no reversal"
HOLD_HORIZON = "10d"

# Display form of each horizon: (number, unit). Units: "min", "h", "day".
_LABELS = {
    "1m": (1, "min"), "5m": (5, "min"), "15m": (15, "min"), "1h": (1, "h"), "4h": (4, "h"),
    "1d": (1, "day"), "2d": (2, "day"), "3d": (3, "day"), "5d": (5, "day"), "10d": (10, "day"),
}

# Window.status values
OK = "ok"
NO_REVERSAL = "no_reversal"
TOO_FEW = "too_few"
NEVER_PROFITABLE = "never_profitable"
NO_DIRECTION = "no_direction"


@dataclass
class AnalogPath:
    """One similar past event's cumulative returns by horizon, with its similarity (weight)."""

    returns: Mapping[str, float]
    similarity: float = 1.0
    event_id: str = ""


@dataclass
class Window:
    """Estimated profitable window for one suggested action."""

    status: str  # OK, NO_REVERSAL, TOO_FEW, NEVER_PROFITABLE or NO_DIRECTION
    text: str  # e.g. "exit within 1–3 days"
    start: Optional[str] = None  # p25 peak horizon
    peak: Optional[str] = None  # median peak horizon (the exit used by evaluate_window_rule)
    end: Optional[str] = None  # p75 peak horizon
    share_profitable: float = float("nan")  # similarity-weighted share of analogs ever profitable
    median_gain: float = float("nan")  # weighted median signed peak return of profitable analogs
    n_analogs: int = 0  # usable analogs (at least one known horizon)
    n_profitable: int = 0

    @property
    def usable(self) -> bool:
        """True when the window gives an exit horizon (OK or NO_REVERSAL)."""
        return self.status in (OK, NO_REVERSAL)


def _label(horizon: str) -> str:
    n, unit = _LABELS.get(horizon, (None, None))
    if n is None:
        return horizon
    return f"{n} {unit}s" if unit == "day" and n != 1 else f"{n} {unit}"


def window_text(start: str, end: str) -> str:
    """"exit within 1–3 days", "exit within 15 min–1 h", "exit within 4 h–2 days"."""
    if start == end:
        return f"exit within {_label(end)}"
    (a, ua), (_, ub) = _LABELS.get(start, (start, "")), _LABELS.get(end, (end, ""))
    if ua == ub and ua:
        return f"exit within {a}–{_label(end)}"
    return f"exit within {_label(start)}–{_label(end)}"


def _weighted_quantile(positions: np.ndarray, weights: np.ndarray, q: float) -> int:
    """Lower weighted quantile of discrete positions: the first whose cumulative weight >= q."""
    order = np.argsort(positions, kind="stable")
    cum = np.cumsum(weights[order]) / weights.sum()
    return int(positions[order][int(np.searchsorted(cum, q - 1e-12, side="left"))])


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    order = np.argsort(values, kind="stable")
    cum = np.cumsum(weights[order]) / weights.sum()
    return float(values[order][int(np.searchsorted(cum, 0.5 - 1e-12, side="left"))])


def _as_path(item: Union[AnalogPath, Mapping[str, float]]) -> AnalogPath:
    return item if isinstance(item, AnalogPath) else AnalogPath(returns=item)


def estimate_window(analog_paths: Sequence[Union[AnalogPath, Mapping[str, float]]],
                    direction: float, horizons: Sequence[str] = HORIZONS,
                    min_analogs: int = MIN_ANALOGS) -> Window:
    """Profitable window from the analogs' cumulative paths, signed by `direction`.

    `analog_paths` holds only analogs whose path had finished by the event time (see
    `analog_paths`); a plain mapping counts with similarity 1. `horizons` is in time order;
    NaN or missing horizons are skipped, and a path with none known is not counted.
    Similarities below 0 count as 0; if every weight is 0, all analogs weigh the same.
    """
    sign = 0.0 if direction is None or direction != direction else float(np.sign(direction))
    if sign == 0:
        return Window(NO_DIRECTION, "no predicted direction")
    horizons = tuple(horizons)
    peaks, gains, weights = [], [], []
    for item in analog_paths:
        path = _as_path(item)
        signed = np.array([sign * float(path.returns.get(h, np.nan)) for h in horizons])
        if np.all(np.isnan(signed)):
            continue
        best = int(np.nanargmax(signed))  # first maximum = earliest on ties
        peaks.append(best)
        gains.append(float(signed[best]))
        sim = path.similarity
        weights.append(max(float(sim), 0.0) if sim == sim else 0.0)
    n = len(peaks)
    if n < min_analogs:
        return Window(TOO_FEW, "not enough similar events", n_analogs=n)
    peaks_a, gains_a, w = np.array(peaks), np.array(gains), np.array(weights)
    if w.sum() <= 0:
        w = np.ones(n)
    profitable = gains_a > 0
    share = float(w[profitable].sum() / w.sum())
    n_prof = int(profitable.sum())
    if n_prof == 0:
        return Window(NEVER_PROFITABLE, "similar events were never profitable",
                      share_profitable=share, n_analogs=n)
    p_peaks, p_gains, p_w = peaks_a[profitable], gains_a[profitable], w[profitable]
    if p_w.sum() <= 0:  # every profitable analog had zero similarity
        p_w = np.ones(n_prof)
    lo, mid, hi = (_weighted_quantile(p_peaks, p_w, q) for q in (0.25, 0.5, 0.75))
    start, peak, end = horizons[lo], horizons[mid], horizons[hi]
    last = len(horizons) - 1
    at_last = float(p_w[p_peaks == last].sum() / p_w.sum())
    if at_last >= NO_REVERSAL_SHARE:
        status, text = NO_REVERSAL, f"no reversal within {_label(horizons[last])}"
    else:
        status, text = OK, window_text(start, end)
    return Window(status, text, start, peak, end, share, _weighted_median(p_gains, p_w),
                  n, n_prof)


# ---- analogs from the model (no look-ahead) ------------------------------------------------


def analog_paths(model, event, target: str, horizons: Sequence[str] = HORIZONS,
                 k: Optional[int] = None) -> List[AnalogPath]:
    """The k most similar earlier events whose whole path had finished by `event`'s time.

    `model` is a `news.model.NewsModel`. "Finished" is the model's purge rule applied to the
    longest horizon (its start plus `_realized_lag`, e.g. 17 days for "10d"), so a recent
    analog never contributes a path cut short. Analogs without a known longest-horizon return
    are skipped (a reversal cannot be judged without it).
    """
    horizons = tuple(horizons)
    k = model.library.k if k is None else k
    idx, sim, t = model.library.candidates_for(event)
    outcomes = {h: model.outcomes(target, h) for h in horizons}
    last = outcomes[horizons[-1]]
    out: List[AnalogPath] = []
    for j, s in zip(idx, sim):
        if len(out) >= k:
            break
        j = int(j)
        if j < 0 or np.isnan(last.values[j]) or last.realized_ns[j] > t:
            continue
        returns = {h: float(outcomes[h].values[j]) for h in horizons}
        out.append(AnalogPath(returns, float(s), model.library.events[j].id))
    return out


def window_for(model, event, target: str, direction: float,
               horizons: Sequence[str] = HORIZONS, min_analogs: int = MIN_ANALOGS) -> Window:
    """`estimate_window` over `analog_paths` for one event and target."""
    return estimate_window(analog_paths(model, event, target, horizons), direction, horizons,
                           min_analogs)


# ---- out-of-sample check -------------------------------------------------------------------


@dataclass
class WindowCase:
    """One held-out event: predicted direction, its window and the actual path."""

    direction: float
    window: Window
    actual: Mapping[str, float]
    event_id: str = ""


@dataclass
class WindowEvalResult:
    """Following the window (exit at its median peak) versus holding to `hold_horizon`."""

    n: int
    mean_window: float  # mean signed return when exiting at the window's median peak
    mean_hold: float  # mean signed return when holding to hold_horizon
    mean_diff: float  # mean of (window - hold)
    t_stat: float  # paired t of the differences
    beat_rate: float  # share of events where the window return beat holding
    hold_horizon: str = HOLD_HORIZON
    details: Optional[pd.DataFrame] = field(default=None, repr=False)


def _paired_t(diff: np.ndarray) -> float:
    if len(diff) < 2:
        return float("nan")
    sd = float(diff.std(ddof=1))
    return float(diff.mean() / (sd / math.sqrt(len(diff)))) if sd > 0 else float("nan")


def evaluate_window_rule(cases: Iterable[WindowCase],
                         hold_horizon: str = HOLD_HORIZON) -> WindowEvalResult:
    """Compare exiting at each window's median peak horizon with holding to `hold_horizon`.

    Only cases with a direction, a usable window (OK or NO_REVERSAL) and both actual returns
    known are counted. Returns are signed by the predicted direction (profit is positive).
    """
    rows = []
    for case in cases:
        d = case.direction
        if d is None or d != d or np.sign(d) == 0 or not case.window.usable:
            continue
        sign = float(np.sign(d))
        win = float(case.actual.get(case.window.peak, np.nan))
        hold = float(case.actual.get(hold_horizon, np.nan))
        if np.isnan(win) or np.isnan(hold):
            continue
        rows.append((case.event_id, case.window.peak, sign * win, sign * hold))
    details = pd.DataFrame(rows, columns=["event_id", "exit_horizon", "window_return",
                                          "hold_return"])
    n = len(details)
    if n == 0:
        nan = float("nan")
        return WindowEvalResult(0, nan, nan, nan, nan, nan, hold_horizon, details)
    win_r = details["window_return"].to_numpy(float)
    hold_r = details["hold_return"].to_numpy(float)
    diff = win_r - hold_r
    return WindowEvalResult(n, float(win_r.mean()), float(hold_r.mean()), float(diff.mean()),
                            _paired_t(diff), float((diff > 0).mean()), hold_horizon, details)


def window_cases(model, target: str, predictions: pd.DataFrame,
                 horizons: Sequence[str] = HORIZONS,
                 min_analogs: int = MIN_ANALOGS) -> List[WindowCase]:
    """Build `WindowCase`s from walk-forward predictions (`EvalResult.predictions`).

    Direction = sign of each held-out event's predicted return; the window uses only analogs
    finished before that event (no look-ahead); the actual path is the event's own reactions.
    """
    lib = model.library
    outcomes = {h: model.outcomes(target, h) for h in horizons}
    cases: List[WindowCase] = []
    for event_id, predicted in zip(predictions["event_id"], predictions["predicted"]):
        pos = lib.position.get(event_id)
        if pos is None:
            continue
        event = lib.events[pos]
        window = window_for(model, event, target, predicted, horizons, min_analogs)
        actual = {h: float(outcomes[h].values[pos]) for h in horizons}
        cases.append(WindowCase(float(predicted), window, actual, event_id))
    return cases
