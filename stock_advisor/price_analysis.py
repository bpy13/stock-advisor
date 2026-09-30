"""Relative-valuation analysis: is a stock cheap or expensive vs. its own history?"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .config import DEFAULT_CONFIG, AnalysisConfig


@dataclass(frozen=True)
class ValuationMetrics:
    """Point-in-time valuation snapshot for a single symbol."""

    symbol: str
    current_price: float
    ma_short: Optional[float]
    ma_medium: Optional[float]
    ma_long: Optional[float]
    pct_from_ma_long: Optional[float]
    zscore: float
    percentile_rank: float
    signal: str  # "BUY" | "SELL" | "HOLD"


def _moving_average(closes: pd.Series, window: int) -> Optional[float]:
    if len(closes) < window:
        return None
    return float(closes.tail(window).mean())


def _percentile_rank(value: float, history: pd.Series) -> float:
    """Percentage of historical observations at or below `value`."""
    if history.empty:
        return 50.0
    return float((history <= value).mean() * 100.0)


def classify_signal(
    zscore: float,
    percentile_rank: float,
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> str:
    """Classify a valuation as BUY (cheap), SELL (expensive), or HOLD (fair)."""
    is_cheap = zscore <= config.buy_zscore or percentile_rank <= config.buy_percentile
    is_expensive = zscore >= config.sell_zscore or percentile_rank >= config.sell_percentile
    if is_cheap and not is_expensive:
        return "BUY"
    if is_expensive and not is_cheap:
        return "SELL"
    return "HOLD"


def analyze_valuation(
    symbol: str,
    closes: pd.Series,
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> ValuationMetrics:
    """Compute how a stock's current price compares to its own trading history."""
    closes = closes.dropna()
    if closes.empty:
        raise ValueError(f"No close-price history available for {symbol!r}.")

    current_price = float(closes.iloc[-1])
    lookback = closes.tail(config.valuation_lookback)

    mean = float(lookback.mean())
    std = float(lookback.std(ddof=0))
    zscore = 0.0 if std == 0 or np.isnan(std) else (current_price - mean) / std

    percentile_rank = _percentile_rank(current_price, lookback)

    ma_short = _moving_average(closes, config.short_ma_window)
    ma_medium = _moving_average(closes, config.medium_ma_window)
    ma_long = _moving_average(closes, config.long_ma_window)
    pct_from_ma_long = (
        (current_price - ma_long) / ma_long * 100.0 if ma_long else None
    )

    signal = classify_signal(zscore, percentile_rank, config)

    return ValuationMetrics(
        symbol=symbol,
        current_price=current_price,
        ma_short=ma_short,
        ma_medium=ma_medium,
        ma_long=ma_long,
        pct_from_ma_long=pct_from_ma_long,
        zscore=zscore,
        percentile_rank=percentile_rank,
        signal=signal,
    )


def analyze_valuations(
    close_prices: pd.DataFrame,
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> dict[str, ValuationMetrics]:
    """Run `analyze_valuation` for every symbol/column in a close-price DataFrame."""
    return {
        symbol: analyze_valuation(symbol, close_prices[symbol], config)
        for symbol in close_prices.columns
    }
