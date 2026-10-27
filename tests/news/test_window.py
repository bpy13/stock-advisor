"""Tests for the profitable-window estimate (synthetic paths only)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from stock_advisor.news.model import EventLibrary, EventRecord, NewsModel
from stock_advisor.news.reactions import HORIZONS
from stock_advisor.news.window import (
    NEVER_PROFITABLE,
    NO_DIRECTION,
    NO_REVERSAL,
    OK,
    TOO_FEW,
    AnalogPath,
    Window,
    WindowCase,
    analog_paths,
    estimate_window,
    evaluate_window_rule,
    window_cases,
    window_text,
)

# A rough time axis (days) for building smooth synthetic paths.
_DAYS = {"1m": 1 / 1440, "5m": 5 / 1440, "15m": 15 / 1440, "1h": 1 / 24, "4h": 4 / 24,
         "1d": 1, "2d": 2, "3d": 3, "5d": 5, "10d": 10}


def peaked_path(peak: str, height: float = 0.03, sign: float = 1.0, noise: float = 0.0,
                rng=None) -> dict:
    """Cumulative path that rises to `height` at `peak`, then falls back below zero."""
    p = _DAYS[peak]
    out = {}
    for h in HORIZONS:
        t = _DAYS[h]
        value = height * t / p if t <= p else height - 2 * height * (t - p) / max(10 - p, 1)
        if rng is not None:
            value += rng.normal(0, noise)
        out[h] = sign * value
    return out


def rising_path(sign: float = 1.0) -> dict:
    return {h: sign * 0.01 * (1 + _DAYS[h]) for h in HORIZONS}


def test_planted_peak_at_two_days():
    rng = np.random.default_rng(0)
    peaks = ["1d", "2d", "2d", "2d", "2d", "2d", "3d", "2d", "2d", "3d", "1d", "2d"]
    paths = [AnalogPath(peaked_path(p, noise=0.0005, rng=rng), 0.8) for p in peaks]
    w = estimate_window(paths, direction=+1)
    assert w.status == OK
    assert w.peak == "2d"
    assert w.start in ("1d", "2d") and w.end in ("2d", "3d")
    assert w.text.startswith("exit within") and "days" in w.text
    assert w.share_profitable == 1.0
    assert abs(w.median_gain - 0.03) < 0.005
    assert w.n_analogs == len(peaks) and w.n_profitable == len(peaks)


def test_spread_window_text():
    paths = [peaked_path(p) for p in ["1d"] * 3 + ["2d"] * 4 + ["3d"] * 3]
    w = estimate_window(paths, +1)
    assert (w.start, w.peak, w.end) == ("1d", "2d", "3d")
    assert w.text == "exit within 1–3 days"


def test_intraday_window_text():
    paths = [peaked_path(p) for p in ["15m"] * 4 + ["1h"] * 5]
    w = estimate_window(paths, +1)
    assert w.text == "exit within 15 min–1 h"
    assert window_text("4h", "2d") == "exit within 4 h–2 days"
    assert window_text("1d", "1d") == "exit within 1 day"


def test_never_reversing_path():
    w = estimate_window([rising_path() for _ in range(10)], +1)
    assert w.status == NO_REVERSAL
    assert w.text == "no reversal within 10 days"
    assert w.peak == "10d"
    assert w.usable


def test_direction_flips_the_sign():
    # Paths falling to a trough at 1d: profitable for a predicted fall, never for a rise.
    paths = [peaked_path("1d", sign=-1.0) for _ in range(10)]
    down = estimate_window(paths, direction=-0.02)
    assert down.status == OK and down.peak == "1d" and down.median_gain > 0
    up = estimate_window(paths, direction=+0.02)
    # Signed upward the path is negative to 1d, then rises above zero by day 10.
    assert up.peak == "10d"


def test_mixed_directions_count_share_profitable():
    good = [peaked_path("2d") for _ in range(6)]
    bad = [{h: -0.01 - 0.001 * i for i, h in enumerate(HORIZONS)} for _ in range(4)]
    w = estimate_window(good + bad, +1)
    assert w.status == OK
    assert w.n_analogs == 10 and w.n_profitable == 6
    assert abs(w.share_profitable - 0.6) < 1e-9
    assert w.peak == "2d"  # the window uses profitable analogs only


def test_all_unprofitable():
    bad = [{h: -0.01 for h in HORIZONS} for _ in range(10)]
    w = estimate_window(bad, +1)
    assert w.status == NEVER_PROFITABLE and w.share_profitable == 0.0
    assert not w.usable


def test_too_few_analogs():
    w = estimate_window([peaked_path("2d")] * 7, +1)
    assert w.status == TOO_FEW and w.text == "not enough similar events"
    assert w.n_analogs == 7
    assert estimate_window([peaked_path("2d")] * 7, +1, min_analogs=5).status == OK


def test_all_nan_paths_are_not_counted():
    empty = [{h: float("nan") for h in HORIZONS}] * 5
    w = estimate_window(empty + [peaked_path("2d")] * 7, +1)
    assert w.status == TOO_FEW and w.n_analogs == 7


def test_nan_horizons_are_skipped():
    path = peaked_path("2d")
    for h in ("1m", "5m", "15m", "1h", "4h"):
        path[h] = float("nan")
    w = estimate_window([path] * 8, +1)
    assert w.peak == "2d"


def test_no_direction():
    assert estimate_window([peaked_path("2d")] * 10, 0.0).status == NO_DIRECTION
    assert estimate_window([peaked_path("2d")] * 10, float("nan")).status == NO_DIRECTION


def test_ties_pick_the_earliest_horizon():
    flat = {h: 0.02 for h in HORIZONS}
    w = estimate_window([flat] * 8, +1)
    assert w.peak == "1m"


def test_similarity_weighting():
    near = [AnalogPath(peaked_path("1d"), 0.9) for _ in range(4)]
    far = [AnalogPath(peaked_path("5d"), 0.1) for _ in range(6)]
    weighted = estimate_window(near + far, +1)
    assert weighted.peak == "1d"  # 3.6 of 4.2 total weight peaks at 1d
    equal = estimate_window([AnalogPath(p.returns) for p in near + far], +1)
    assert equal.peak == "5d"  # unweighted, 6 of 10 peak at 5d
    # Negative similarity counts as zero weight; all-zero falls back to equal weights.
    neg = [AnalogPath(p.returns, -0.5) for p in far]
    assert estimate_window(near + neg, +1).peak == "1d"
    zero = [AnalogPath(p.returns, 0.0) for p in near + far]
    assert estimate_window(zero, +1).peak == "5d"


# ---- evaluate_window_rule -------------------------------------------------------------------


def _window(peak: str, status: str = OK) -> Window:
    return Window(status, "x", peak, peak, peak)


def test_evaluate_window_rule_window_beats_hold():
    rng = np.random.default_rng(1)
    cases = []
    for i in range(40):
        sign = 1.0 if i % 2 else -1.0
        actual = peaked_path("2d", sign=sign, noise=0.002, rng=rng)
        cases.append(WindowCase(sign * 0.01, _window("2d"), actual, f"e{i}"))
    result = evaluate_window_rule(cases)
    assert result.n == 40
    assert result.mean_window > 0.02 and result.mean_hold < 0
    assert result.mean_diff > 0 and result.t_stat > 2 and result.beat_rate > 0.9
    assert list(result.details.columns) == ["event_id", "exit_horizon", "window_return",
                                            "hold_return"]


def test_evaluate_window_rule_skips_unusable_cases():
    good = WindowCase(1.0, _window("1d"), {"1d": 0.01, "10d": 0.02})
    cases = [
        good,
        WindowCase(1.0, Window(TOO_FEW, "not enough similar events"), {"1d": 0.5, "10d": 0.0}),
        WindowCase(0.0, _window("1d"), {"1d": 0.5, "10d": 0.0}),
        WindowCase(1.0, _window("1d"), {"1d": float("nan"), "10d": 0.0}),
        WindowCase(-1.0, _window("10d", NO_REVERSAL), {"10d": -0.03}),
    ]
    result = evaluate_window_rule(cases)
    assert result.n == 2
    assert abs(result.mean_window - (0.01 + 0.03) / 2) < 1e-12
    assert abs(result.mean_hold - (0.02 + 0.03) / 2) < 1e-12
    assert result.beat_rate == 0.0
    empty = evaluate_window_rule([])
    assert empty.n == 0 and np.isnan(empty.t_stat)


# ---- analogs from the model -----------------------------------------------------------------


def _model_with_paths(n: int = 30):
    """n identical-meaning events 30 days apart, each with a path peaking at 2d."""
    t0 = datetime(2020, 1, 6, 15, tzinfo=timezone.utc)
    vec = np.ones(8, dtype=np.float32)
    events = [EventRecord(f"e{i}", t0 + timedelta(days=30 * i), vec) for i in range(n)]
    rows = []
    for e in events:
        for h, v in peaked_path("2d").items():
            rows.append((e.id, "^GSPC", h, v, v, pd.Timestamp(e.started_at), "1m"))
    reactions = pd.DataFrame(rows, columns=["event_id", "target", "horizon", "raw", "adjusted",
                                            "start_ts", "start_source"])
    return NewsModel(EventLibrary(events), reactions), events


def test_analog_paths_use_only_finished_paths():
    model, events = _model_with_paths(15)  # fewer than k, so every finished event is used
    # A live event 10 days after e14: e14's 10d path is not finished (needs 17 days).
    live = EventRecord("live", events[-1].started_at + timedelta(days=10), events[0].embedding)
    paths = analog_paths(model, live, "^GSPC")
    assert {p.event_id for p in paths} == {f"e{i}" for i in range(14)}
    assert all(not np.isnan(p.returns["10d"]) for p in paths)
    # 20 days later it is finished and usable.
    later = EventRecord("live2", events[-1].started_at + timedelta(days=20), events[0].embedding)
    assert "e14" in {p.event_id for p in analog_paths(model, later, "^GSPC")}
    assert len(analog_paths(model, later, "^GSPC", k=5)) == 5


def test_window_cases_feed_evaluate_window_rule():
    model, events = _model_with_paths()
    predictions = pd.DataFrame({"event_id": [e.id for e in events],
                                "predicted": [0.01] * len(events)})
    cases = window_cases(model, "^GSPC", predictions)
    assert len(cases) == len(events)
    assert cases[0].window.status == TOO_FEW  # no earlier events
    late = cases[-1]
    assert late.window.status == OK and late.window.peak == "2d"
    result = evaluate_window_rule(cases)
    assert result.n > 0 and result.mean_diff > 0
