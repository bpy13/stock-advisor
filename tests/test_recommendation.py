"""Tests for stock_advisor.recommendation."""

from stock_advisor.config import AnalysisConfig
from stock_advisor.correlation import PeerCorrelation
from stock_advisor.portfolio import Portfolio, Position
from stock_advisor.price_analysis import ValuationMetrics
from stock_advisor.recommendation import build_recommendation


def _valuation(signal: str, symbol: str = "AAPL") -> ValuationMetrics:
    return ValuationMetrics(
        symbol=symbol,
        current_price=100.0,
        ma_short=100.0,
        ma_medium=100.0,
        ma_long=100.0,
        pct_from_ma_long=0.0,
        zscore=-1.5 if signal == "BUY" else (1.5 if signal == "SELL" else 0.0),
        percentile_rank=10.0 if signal == "BUY" else (90.0 if signal == "SELL" else 50.0),
        signal=signal,
    )


def test_buy_signal_passes_through_when_no_existing_position():
    valuation = _valuation("BUY")
    recommendation = build_recommendation(
        valuation=valuation,
        peers=[],
        portfolio=None,
        current_prices={"AAPL": 100.0},
    )
    assert recommendation.action == "BUY"


def test_buy_signal_downgraded_when_overconcentrated():
    config = AnalysisConfig(max_position_weight=0.1)
    portfolio = Portfolio(positions={"AAPL": Position("AAPL", 100, 90.0)}, cash=0.0)
    valuation = _valuation("BUY")

    recommendation = build_recommendation(
        valuation=valuation,
        peers=[],
        portfolio=portfolio,
        current_prices={"AAPL": 100.0},
        config=config,
    )

    assert recommendation.action == "HOLD"
    assert recommendation.raw_signal == "BUY"
    assert "downgraded" in recommendation.rationale


def test_sell_signal_downgraded_when_no_shares_held():
    valuation = _valuation("SELL")
    portfolio = Portfolio(positions={}, cash=0.0)

    recommendation = build_recommendation(
        valuation=valuation,
        peers=[],
        portfolio=portfolio,
        current_prices={"AAPL": 100.0},
    )

    assert recommendation.action == "HOLD"
    assert recommendation.raw_signal == "SELL"


def test_sell_signal_passes_through_when_shares_held():
    valuation = _valuation("SELL")
    portfolio = Portfolio(positions={"AAPL": Position("AAPL", 10, 90.0)}, cash=0.0)

    recommendation = build_recommendation(
        valuation=valuation,
        peers=[],
        portfolio=portfolio,
        current_prices={"AAPL": 100.0},
    )

    assert recommendation.action == "SELL"
    assert recommendation.shares_held == 10


def test_rationale_includes_peer_note():
    valuation = _valuation("HOLD")
    peers = [PeerCorrelation(symbol="MSFT", correlation=0.85)]

    recommendation = build_recommendation(
        valuation=valuation,
        peers=peers,
        portfolio=None,
        current_prices={"AAPL": 100.0},
    )

    assert "MSFT" in recommendation.rationale
