"""Combines valuation, correlation, and portfolio context into a final call."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .config import DEFAULT_CONFIG, AnalysisConfig
from .correlation import PeerCorrelation
from .portfolio import Portfolio
from .price_analysis import ValuationMetrics


@dataclass(frozen=True)
class Recommendation:
    """Final actionable call for a single symbol."""

    symbol: str
    action: str  # "BUY" | "SELL" | "HOLD"
    raw_signal: str  # the un-adjusted valuation signal, before portfolio context
    rationale: str
    shares_held: float
    position_weight: float


def _peer_note(peers: List[PeerCorrelation]) -> str:
    if not peers:
        return ""
    parts = [f"{peer.symbol} ({peer.correlation:+.2f})" for peer in peers]
    return f" Correlated peers: {', '.join(parts)}."


def build_recommendation(
    valuation: ValuationMetrics,
    peers: List[PeerCorrelation],
    portfolio: Optional[Portfolio],
    current_prices: Dict[str, float],
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> Recommendation:
    """Adjust a raw valuation signal using the user's existing portfolio exposure."""
    symbol = valuation.symbol
    signal = valuation.signal

    shares_held = 0.0
    position_weight = 0.0
    if portfolio is not None:
        position = portfolio.positions.get(symbol)
        shares_held = position.shares if position else 0.0
        position_weight = portfolio.position_weight(symbol, current_prices)

    action = signal
    rationale = (
        f"{symbol} is trading at a z-score of {valuation.zscore:+.2f} and the "
        f"{valuation.percentile_rank:.0f}th percentile of its trailing history."
    )

    if signal == "BUY" and position_weight >= config.max_position_weight:
        action = "HOLD"
        rationale += (
            f" Signal downgraded from BUY: position already {position_weight:.0%} of "
            f"portfolio (limit {config.max_position_weight:.0%})."
        )
    elif signal == "SELL" and portfolio is not None and shares_held <= 0:
        action = "HOLD"
        rationale += " Signal downgraded from SELL: no existing position to reduce."

    rationale += _peer_note(peers)

    return Recommendation(
        symbol=symbol,
        action=action,
        raw_signal=signal,
        rationale=rationale,
        shares_held=shares_held,
        position_weight=position_weight,
    )
