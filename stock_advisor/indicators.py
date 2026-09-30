"""Vectorized time-series technical/statistical indicators for backtesting.

Unlike `price_analysis.py` (which reports a single current-day snapshot), each
function here returns a full `pd.Series` aligned to the input's index, with
each value computed only from data available up to that point in time (no
look-ahead). This is what `validation.py` needs to backtest a metric's signal
quality across history.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_zscore(closes: pd.Series, window: int = 252) -> pd.Series:
    """How many rolling std-devs the price is from its own rolling mean."""
    mean = closes.rolling(window).mean()
    std = closes.rolling(window).std(ddof=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return (closes - mean) / std


def rolling_percentile_rank(closes: pd.Series, window: int = 252) -> pd.Series:
    """Percentage of the trailing `window` observations at or below today's price."""
    return closes.rolling(window).apply(lambda x: (x <= x[-1]).mean() * 100.0, raw=True)


def pct_from_moving_average(closes: pd.Series, window: int = 200) -> pd.Series:
    """Percent the price sits above (+) or below (-) its rolling moving average."""
    ma = closes.rolling(window).mean()
    with np.errstate(divide="ignore", invalid="ignore"):
        return (closes - ma) / ma * 100.0


def rsi(closes: pd.Series, window: int = 14) -> pd.Series:
    """Wilder's Relative Strength Index, 0-100 (<30 oversold, >70 overbought)."""
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    with np.errstate(divide="ignore", invalid="ignore"):
        relative_strength = avg_gain / avg_loss
        return 100 - (100 / (1 + relative_strength))


def bollinger_percent_b(closes: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.Series:
    """Position within the Bollinger Bands: 0 = at the lower band, 1 = at the upper band."""
    ma = closes.rolling(window).mean()
    std = closes.rolling(window).std(ddof=0)
    upper = ma + num_std * std
    lower = ma - num_std * std
    with np.errstate(divide="ignore", invalid="ignore"):
        return (closes - lower) / (upper - lower)


def momentum(closes: pd.Series, window: int = 60) -> pd.Series:
    """Trailing percent change over the `window`-day lookback (trend/continuation)."""
    return closes / closes.shift(window) - 1.0


def distance_from_high(closes: pd.Series, window: int = 252) -> pd.Series:
    """Percent below (always <= 0) the trailing `window`-day rolling high."""
    rolling_high = closes.rolling(window).max()
    with np.errstate(divide="ignore", invalid="ignore"):
        return (closes - rolling_high) / rolling_high * 100.0
