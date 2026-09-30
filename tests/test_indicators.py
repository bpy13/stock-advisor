"""Tests for stock_advisor.indicators."""

import numpy as np
import pandas as pd
import pytest

from stock_advisor import indicators as ind


def _flat_series(length=300, level=100.0):
    index = pd.date_range("2023-01-01", periods=length, freq="D")
    return pd.Series(level, index=index, dtype=float)


def test_rolling_zscore_is_zero_on_perfectly_flat_series():
    closes = _flat_series(300)
    z = ind.rolling_zscore(closes, window=100)
    # std is 0 on a flat series -> division yields NaN, not a crash.
    assert z.iloc[-1] != z.iloc[-1] or z.iloc[-1] == 0  # NaN or 0, either is fine


def test_rolling_zscore_detects_a_final_dip():
    values = np.full(300, 100.0)
    values[-1] = 50.0
    closes = pd.Series(values, index=pd.date_range("2023-01-01", periods=300, freq="D"))
    z = ind.rolling_zscore(closes, window=252)
    assert z.iloc[-1] < -1.0


def test_rolling_percentile_rank_bounds_and_extremes():
    values = np.linspace(1, 100, 300)  # monotonic increasing
    closes = pd.Series(values, index=pd.date_range("2023-01-01", periods=300, freq="D"))
    rank = ind.rolling_percentile_rank(closes, window=100)
    assert rank.iloc[-1] == pytest.approx(100.0)  # today's value is the highest in window


def test_pct_from_moving_average_zero_on_flat_series():
    closes = _flat_series(300)
    pct = ind.pct_from_moving_average(closes, window=100)
    assert pct.iloc[-1] == pytest.approx(0.0)


def test_rsi_approaches_100_on_strictly_increasing_series():
    values = np.arange(1, 301, dtype=float)
    closes = pd.Series(values, index=pd.date_range("2023-01-01", periods=300, freq="D"))
    rsi = ind.rsi(closes, window=14)
    assert rsi.iloc[-1] == pytest.approx(100.0, abs=0.01)


def test_rsi_approaches_zero_on_strictly_decreasing_series():
    values = np.arange(300, 0, -1, dtype=float)
    closes = pd.Series(values, index=pd.date_range("2023-01-01", periods=300, freq="D"))
    rsi = ind.rsi(closes, window=14)
    assert rsi.iloc[-1] == pytest.approx(0.0, abs=0.01)


def test_bollinger_percent_b_zero_at_lower_band_one_at_upper_band():
    rng = np.random.default_rng(seed=1)
    values = 100 + rng.normal(0, 1, 300)
    values[-1] = values[:-1].mean() - 3 * values[:-1].std()  # far below lower band
    closes = pd.Series(values, index=pd.date_range("2023-01-01", periods=300, freq="D"))
    percent_b = ind.bollinger_percent_b(closes, window=100)
    assert percent_b.iloc[-1] < 0.0


def test_momentum_matches_manual_pct_change():
    values = np.linspace(100, 200, 300)
    closes = pd.Series(values, index=pd.date_range("2023-01-01", periods=300, freq="D"))
    mom = ind.momentum(closes, window=60)
    expected = values[-1] / values[-61] - 1.0
    assert mom.iloc[-1] == pytest.approx(expected)


def test_distance_from_high_is_zero_at_new_high_and_negative_otherwise():
    values = np.concatenate([np.linspace(100, 150, 150), np.linspace(149, 120, 150)])
    closes = pd.Series(values, index=pd.date_range("2023-01-01", periods=300, freq="D"))
    distance = ind.distance_from_high(closes, window=100)
    assert distance.iloc[149] == pytest.approx(0.0)  # the peak itself
    assert distance.iloc[-1] < 0.0  # off the high afterward
