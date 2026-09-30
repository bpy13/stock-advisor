"""Tests for stock_advisor.price_analysis using synthetic price series."""

import numpy as np
import pandas as pd
import pytest

from stock_advisor.config import AnalysisConfig
from stock_advisor.price_analysis import analyze_valuation, classify_signal


def _flat_series_with_dip(length: int = 300, base: float = 100.0) -> pd.Series:
    """A mostly flat price series that dips sharply on the last observation."""
    values = np.full(length, base, dtype=float)
    values[:-1] += np.tile([1.0, -1.0], length // 2)[: length - 1]  # small noise
    values[-1] = base * 0.5  # sharp final dip -> should register as cheap
    index = pd.date_range("2023-01-01", periods=length, freq="D")
    return pd.Series(values, index=index)


def _flat_series_with_spike(length: int = 300, base: float = 100.0) -> pd.Series:
    values = np.full(length, base, dtype=float)
    values[:-1] += np.tile([1.0, -1.0], length // 2)[: length - 1]
    values[-1] = base * 2.0  # sharp final spike -> should register as expensive
    index = pd.date_range("2023-01-01", periods=length, freq="D")
    return pd.Series(values, index=index)


def test_analyze_valuation_flags_cheap_price_as_buy():
    closes = _flat_series_with_dip()
    metrics = analyze_valuation("TEST", closes)

    assert metrics.signal == "BUY"
    assert metrics.zscore < 0
    assert metrics.percentile_rank < 50


def test_analyze_valuation_flags_expensive_price_as_sell():
    closes = _flat_series_with_spike()
    metrics = analyze_valuation("TEST", closes)

    assert metrics.signal == "SELL"
    assert metrics.zscore > 0
    assert metrics.percentile_rank > 50


def test_analyze_valuation_moving_averages_present_with_enough_history():
    closes = _flat_series_with_dip(length=300)
    metrics = analyze_valuation("TEST", closes)

    assert metrics.ma_short is not None
    assert metrics.ma_medium is not None
    assert metrics.ma_long is not None
    assert metrics.pct_from_ma_long is not None


def test_analyze_valuation_moving_averages_none_with_short_history():
    index = pd.date_range("2023-01-01", periods=10, freq="D")
    closes = pd.Series(np.linspace(100, 110, 10), index=index)
    metrics = analyze_valuation("TEST", closes)

    assert metrics.ma_short is None
    assert metrics.ma_medium is None
    assert metrics.ma_long is None
    assert metrics.pct_from_ma_long is None


def test_analyze_valuation_raises_on_empty_series():
    with pytest.raises(ValueError):
        analyze_valuation("TEST", pd.Series(dtype=float))


def test_classify_signal_hold_when_within_thresholds():
    config = AnalysisConfig()
    assert classify_signal(0.0, 50.0, config) == "HOLD"


def test_classify_signal_buy_and_sell_boundaries():
    config = AnalysisConfig()
    assert classify_signal(config.buy_zscore, 50.0, config) == "BUY"
    assert classify_signal(config.sell_zscore, 50.0, config) == "SELL"
