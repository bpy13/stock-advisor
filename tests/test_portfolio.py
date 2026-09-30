"""Tests for stock_advisor.portfolio."""

import json

import pytest

from stock_advisor.portfolio import Portfolio, Position, load_portfolio


@pytest.fixture
def portfolio_path(tmp_path):
    data = {
        "cash": 1000.0,
        "positions": [
            {"symbol": "aapl", "shares": 10, "cost_basis": 150.0},
            {"symbol": "MSFT", "shares": 5, "cost_basis": 280.0},
        ],
    }
    path = tmp_path / "portfolio.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_portfolio_parses_positions_and_normalizes_symbols(portfolio_path):
    portfolio = load_portfolio(portfolio_path)

    assert portfolio.cash == 1000.0
    assert set(portfolio.positions.keys()) == {"AAPL", "MSFT"}
    assert portfolio.positions["AAPL"].shares == 10
    assert portfolio.positions["AAPL"].cost_basis == 150.0


def test_market_value_uses_current_prices_when_available(portfolio_path):
    portfolio = load_portfolio(portfolio_path)
    current_prices = {"AAPL": 200.0, "MSFT": 300.0}

    expected = 10 * 200.0 + 5 * 300.0 + 1000.0
    assert portfolio.market_value(current_prices) == pytest.approx(expected)


def test_market_value_falls_back_to_cost_basis_when_price_missing(portfolio_path):
    portfolio = load_portfolio(portfolio_path)

    expected = 10 * 150.0 + 5 * 280.0 + 1000.0
    assert portfolio.market_value({}) == pytest.approx(expected)


def test_position_weight_for_held_and_unheld_symbol(portfolio_path):
    portfolio = load_portfolio(portfolio_path)
    current_prices = {"AAPL": 200.0, "MSFT": 300.0}
    total = portfolio.market_value(current_prices)

    assert portfolio.position_weight("AAPL", current_prices) == pytest.approx(
        (10 * 200.0) / total
    )
    assert portfolio.position_weight("GOOG", current_prices) == 0.0


def test_position_weight_zero_when_total_value_zero():
    portfolio = Portfolio(positions={"AAPL": Position("AAPL", 0, 0.0)}, cash=0.0)
    assert portfolio.position_weight("AAPL", {}) == 0.0
