"""Default configuration values for stock-advisor analysis."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisConfig:
    """Tunable thresholds and windows used across the analysis pipeline."""

    # History window fetched from Yahoo Finance.
    period: str = "2y"
    interval: str = "1d"

    # Moving-average windows (trading days) reported alongside valuation metrics.
    short_ma_window: int = 20
    medium_ma_window: int = 50
    long_ma_window: int = 200

    # Lookback window used for z-score / percentile-rank valuation.
    valuation_lookback: int = 252

    # Z-score thresholds: price this many std-devs from its historical mean.
    buy_zscore: float = -1.0
    sell_zscore: float = 1.0

    # Percentile-rank thresholds (0-100) of current price within lookback history.
    buy_percentile: float = 20.0
    sell_percentile: float = 80.0

    # Rolling window (trading days) used to compute return correlations.
    correlation_window: int = 90

    # Absolute correlation above which two symbols are considered "correlated peers".
    correlation_threshold: float = 0.6

    # Max number of correlated peers to surface per symbol in the report.
    max_peers_reported: int = 3

    # Portfolio concentration guardrail: fraction of portfolio value a single
    # position may represent before BUY signals are downgraded to HOLD.
    max_position_weight: float = 0.25


DEFAULT_CONFIG = AnalysisConfig()
