"""Cross-stock correlation analysis using daily returns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd

from .config import DEFAULT_CONFIG, AnalysisConfig


@dataclass(frozen=True)
class PeerCorrelation:
    """A single correlated peer and its correlation coefficient."""

    symbol: str
    correlation: float


def compute_returns(close_prices: pd.DataFrame) -> pd.DataFrame:
    """Daily percentage returns for each symbol."""
    return close_prices.pct_change().dropna(how="all")


def compute_correlation_matrix(
    close_prices: pd.DataFrame,
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """Pairwise correlation of returns over the configured rolling window."""
    returns = compute_returns(close_prices)
    window = min(config.correlation_window, len(returns)) or len(returns)
    recent_returns = returns.tail(window)
    return recent_returns.corr()


def get_correlated_peers(
    symbol: str,
    correlation_matrix: pd.DataFrame,
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> List[PeerCorrelation]:
    """Return the strongest-correlated peers for `symbol`, above the threshold."""
    if symbol not in correlation_matrix.columns:
        return []

    peer_scores = correlation_matrix[symbol].drop(index=symbol, errors="ignore").dropna()
    strong = peer_scores[peer_scores.abs() >= config.correlation_threshold]
    ranked = strong.reindex(strong.abs().sort_values(ascending=False).index)

    peers = [
        PeerCorrelation(symbol=peer, correlation=float(value))
        for peer, value in ranked.items()
    ]
    return peers[: config.max_peers_reported]


def build_peer_map(
    close_prices: pd.DataFrame,
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> Dict[str, List[PeerCorrelation]]:
    """Compute the correlated-peer list for every symbol in `close_prices`."""
    matrix = compute_correlation_matrix(close_prices, config)
    return {
        symbol: get_correlated_peers(symbol, matrix, config)
        for symbol in close_prices.columns
    }
