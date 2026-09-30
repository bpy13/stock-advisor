"""Tests for stock_advisor.validation (metric backtesting)."""

import numpy as np
import pandas as pd
import pytest

from stock_advisor.validation import (
    MetricDefinition,
    classify_series,
    evaluate_metrics,
    rank_metrics,
)


def test_classify_series_low_is_bullish():
    values = pd.Series([-2.0, -1.0, 0.0, 1.0, 2.0, float("nan")])
    definition = MetricDefinition("test", lambda c: c, buy_threshold=-1.0, sell_threshold=1.0)

    signal = classify_series(values, definition)

    assert list(signal[:5]) == ["BUY", "BUY", "HOLD", "SELL", "SELL"]
    assert signal.iloc[5] is None


def test_classify_series_higher_is_bullish():
    values = pd.Series([-2.0, -1.0, 0.0, 1.0, 2.0])
    definition = MetricDefinition(
        "test", lambda c: c, buy_threshold=1.0, sell_threshold=-1.0, higher_is_bullish=True
    )

    signal = classify_series(values, definition)

    assert list(signal) == ["SELL", "SELL", "HOLD", "BUY", "BUY"]


def _mean_reverting_series(length=1500, level=100.0, phi=0.97, noise_std=1.0, seed=0):
    """A strongly mean-reverting AR(1) price series around `level`."""
    rng = np.random.default_rng(seed)
    values = np.empty(length)
    values[0] = level
    for t in range(1, length):
        values[t] = level + phi * (values[t - 1] - level) + rng.normal(0, noise_std)
    index = pd.date_range("2018-01-01", periods=length, freq="B")
    return pd.Series(values, index=index)


def test_evaluate_metrics_finds_genuine_edge_on_mean_reverting_series():
    closes = _mean_reverting_series()
    close_prices = pd.DataFrame({"SYN": closes})
    zscore_metric = MetricDefinition("zscore_252d", lambda c: c.rolling(252).apply(
        lambda w: (w[-1] - w.mean()) / w.std(), raw=True
    ), -1.0, 1.0)

    summary = evaluate_metrics(close_prices, metrics=(zscore_metric,), forward_window=20)

    row = summary.loc["zscore_252d"]
    # On genuinely mean-reverting data, buying when cheap should outperform
    # selling when expensive, and by a statistically meaningful margin.
    assert row["spread"] > 0
    assert abs(row["t_stat"]) >= 2.0
    assert row["n_buy"] > 30
    assert row["n_sell"] > 30


def test_rank_metrics_flags_good_indicator_when_criteria_met():
    summary = pd.DataFrame(
        {
            "n_buy": [50, 50],
            "avg_return_after_buy": [0.05, 0.01],
            "buy_hit_rate": [0.6, 0.5],
            "n_sell": [50, 50],
            "avg_return_after_sell": [-0.03, 0.0],
            "sell_hit_rate": [0.6, 0.5],
            "n_hold": [100, 100],
            "avg_return_after_hold": [0.0, 0.0],
            "spread": [0.08, 0.01],
            "t_stat": [3.5, 0.2],
        },
        index=pd.Index(["good_metric", "weak_metric"], name="metric"),
    )

    ranked = rank_metrics(summary, min_samples=30, min_abs_t_stat=2.0)

    assert ranked.loc["good_metric", "good_indicator"] == True  # noqa: E712
    assert ranked.loc["weak_metric", "good_indicator"] == False  # noqa: E712


def test_rank_metrics_requires_minimum_sample_size():
    summary = pd.DataFrame(
        {
            "n_buy": [5],
            "avg_return_after_buy": [0.05],
            "buy_hit_rate": [0.6],
            "n_sell": [5],
            "avg_return_after_sell": [-0.05],
            "sell_hit_rate": [0.6],
            "n_hold": [10],
            "avg_return_after_hold": [0.0],
            "spread": [0.1],
            "t_stat": [5.0],
        },
        index=pd.Index(["tiny_sample_metric"], name="metric"),
    )

    ranked = rank_metrics(summary, min_samples=30, min_abs_t_stat=2.0)

    assert ranked.loc["tiny_sample_metric", "good_indicator"] == False  # noqa: E712
