"""Backtests candidate valuation metrics against realized forward returns.

The core question: does a metric's BUY/SELL signal actually predict future
price movement, or does it just look plausible? For each metric this measures
the average forward return realized after a historical BUY signal vs. after a
SELL signal (pooled across symbols), and flags which ones show a real,
statistically-meaningful edge rather than noise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Tuple

import pandas as pd

from . import indicators as ind


@dataclass(frozen=True)
class MetricDefinition:
    """One candidate metric: how to compute it, and what counts as BUY/SELL."""

    name: str
    compute: Callable[[pd.Series], pd.Series]
    buy_threshold: float
    sell_threshold: float
    # False (default): low values are bullish, e.g. z-score / RSI mean reversion.
    # True: high values are bullish, e.g. momentum/trend-following.
    higher_is_bullish: bool = False


DEFAULT_METRICS: Tuple[MetricDefinition, ...] = (
    MetricDefinition("zscore_252d", lambda c: ind.rolling_zscore(c, 252), -1.0, 1.0),
    MetricDefinition("percentile_rank_252d", lambda c: ind.rolling_percentile_rank(c, 252), 20.0, 80.0),
    MetricDefinition("pct_from_ma_200d", lambda c: ind.pct_from_moving_average(c, 200), -10.0, 10.0),
    MetricDefinition("rsi_14d", lambda c: ind.rsi(c, 14), 30.0, 70.0),
    MetricDefinition("bollinger_percent_b_20d", lambda c: ind.bollinger_percent_b(c, 20), 0.0, 1.0),
    MetricDefinition("momentum_60d", lambda c: ind.momentum(c, 60), 0.05, -0.05, higher_is_bullish=True),
    MetricDefinition("distance_from_52w_high", lambda c: ind.distance_from_high(c, 252), -20.0, -2.0),
)


def classify_series(values: pd.Series, definition: MetricDefinition) -> pd.Series:
    """Classify each historical value into BUY/SELL/HOLD using the metric's thresholds."""
    if definition.higher_is_bullish:
        buy_mask = values >= definition.buy_threshold
        sell_mask = values <= definition.sell_threshold
    else:
        buy_mask = values <= definition.buy_threshold
        sell_mask = values >= definition.sell_threshold

    signal = pd.Series("HOLD", index=values.index, dtype=object)
    signal[sell_mask.fillna(False)] = "SELL"
    signal[buy_mask.fillna(False)] = "BUY"  # BUY wins on the (rare) overlap
    signal[values.isna()] = None
    return signal


@dataclass(frozen=True)
class SignalStats:
    """Forward-return distribution observed after one signal class historically."""

    label: str
    count: int
    mean_forward_return: float
    hit_rate: float  # fraction of occurrences where the return matched the expected direction


def _summarize(forward_returns: pd.Series, label: str, expect_positive: Optional[bool]) -> SignalStats:
    values = forward_returns.dropna()
    if values.empty:
        return SignalStats(label, 0, float("nan"), float("nan"))
    mean_return = float(values.mean())
    if expect_positive is None:
        hit_rate = float("nan")
    elif expect_positive:
        hit_rate = float((values > 0).mean())
    else:
        hit_rate = float((values < 0).mean())
    return SignalStats(label, len(values), mean_return, hit_rate)


def _welch_t_stat(a: pd.Series, b: pd.Series) -> float:
    """Welch's t-statistic for a difference in means; |t| >= ~2 is a common
    rule-of-thumb threshold for "probably not just noise"."""
    a, b = a.dropna(), b.dropna()
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    var_a, var_b = a.var(ddof=1), b.var(ddof=1)
    denom = math.sqrt(var_a / len(a) + var_b / len(b))
    if denom == 0:
        return float("nan")
    return float((a.mean() - b.mean()) / denom)


def evaluate_metrics(
    close_prices: pd.DataFrame,
    metrics: Iterable[MetricDefinition] = DEFAULT_METRICS,
    forward_window: int = 20,
    min_history: int = 60,
) -> pd.DataFrame:
    """Backtest every metric, pooling signal/forward-return pairs across all
    symbols (columns) in `close_prices` for statistical power.

    Returns one row per metric with sample counts, mean forward return after
    each signal class, the BUY-vs-SELL spread, and a Welch's t-stat for that
    spread.
    """
    rows = []
    for definition in metrics:
        pooled_buy, pooled_sell, pooled_hold = [], [], []
        for symbol in close_prices.columns:
            closes = close_prices[symbol].dropna()
            if len(closes) < min_history:
                continue
            values = definition.compute(closes)
            signal = classify_series(values, definition)
            forward_return = closes.shift(-forward_window) / closes - 1.0
            pooled_buy.append(forward_return[signal == "BUY"])
            pooled_sell.append(forward_return[signal == "SELL"])
            pooled_hold.append(forward_return[signal == "HOLD"])

        buy_returns = pd.concat(pooled_buy) if pooled_buy else pd.Series(dtype=float)
        sell_returns = pd.concat(pooled_sell) if pooled_sell else pd.Series(dtype=float)
        hold_returns = pd.concat(pooled_hold) if pooled_hold else pd.Series(dtype=float)

        buy_stats = _summarize(buy_returns, "BUY", expect_positive=True)
        sell_stats = _summarize(sell_returns, "SELL", expect_positive=False)
        hold_stats = _summarize(hold_returns, "HOLD", expect_positive=None)
        spread = buy_stats.mean_forward_return - sell_stats.mean_forward_return
        t_stat = _welch_t_stat(buy_returns.dropna(), sell_returns.dropna())

        rows.append(
            {
                "metric": definition.name,
                "n_buy": buy_stats.count,
                "avg_return_after_buy": buy_stats.mean_forward_return,
                "buy_hit_rate": buy_stats.hit_rate,
                "n_sell": sell_stats.count,
                "avg_return_after_sell": sell_stats.mean_forward_return,
                "sell_hit_rate": sell_stats.hit_rate,
                "n_hold": hold_stats.count,
                "avg_return_after_hold": hold_stats.mean_forward_return,
                "spread": spread,
                "t_stat": t_stat,
            }
        )

    result = pd.DataFrame(rows).set_index("metric")
    return result.sort_values("t_stat", ascending=False)


def rank_metrics(
    summary: pd.DataFrame, min_samples: int = 30, min_abs_t_stat: float = 2.0
) -> pd.DataFrame:
    """Flag metrics with enough samples, a correctly-signed spread (BUY really
    did outperform SELL going forward), and a large-enough |t-stat| to look
    like a genuine edge rather than noise.
    """
    qualifies = (
        (summary["n_buy"] >= min_samples)
        & (summary["n_sell"] >= min_samples)
        & (summary["spread"] > 0)
        & (summary["t_stat"].abs() >= min_abs_t_stat)
    )
    return summary.assign(good_indicator=qualifies).sort_values("t_stat", ascending=False)
