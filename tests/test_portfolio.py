"""Tests for stock_advisor.portfolio."""

import json

import pytest

import stock_advisor.portfolio as portfolio_module
from stock_advisor.portfolio import Portfolio, Position, load_portfolio, resolve_portfolio_path


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


def test_resolve_portfolio_path_explicit_wins(monkeypatch, tmp_path):
    data_path = tmp_path / "data_portfolio.json"
    sample_path = tmp_path / "sample_portfolio.json"
    data_path.write_text("{}", encoding="utf-8")
    sample_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(portfolio_module, "DATA_TRANSACTIONS_PATH", tmp_path / "nope.csv")
    monkeypatch.setattr(portfolio_module, "DATA_PORTFOLIO_PATH", data_path)
    monkeypatch.setattr(portfolio_module, "SAMPLE_PORTFOLIO_PATH", sample_path)

    explicit_path = tmp_path / "explicit.json"
    assert resolve_portfolio_path(explicit_path) == explicit_path


def test_resolve_portfolio_path_prefers_transactions_csv(monkeypatch, tmp_path):
    transactions_path = tmp_path / "transaction.csv"
    data_path = tmp_path / "data_portfolio.json"
    transactions_path.write_text("#date,name,ticker,currency,price,quantity\n", encoding="utf-8")
    data_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(portfolio_module, "DATA_TRANSACTIONS_PATH", transactions_path)
    monkeypatch.setattr(portfolio_module, "DATA_PORTFOLIO_PATH", data_path)
    monkeypatch.setattr(portfolio_module, "SAMPLE_PORTFOLIO_PATH", tmp_path / "nope.json")

    assert resolve_portfolio_path(None) == transactions_path


def test_resolve_portfolio_path_prefers_data_over_sample(monkeypatch, tmp_path):
    data_path = tmp_path / "data_portfolio.json"
    sample_path = tmp_path / "sample_portfolio.json"
    data_path.write_text("{}", encoding="utf-8")
    sample_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(portfolio_module, "DATA_TRANSACTIONS_PATH", tmp_path / "nope.csv")
    monkeypatch.setattr(portfolio_module, "DATA_PORTFOLIO_PATH", data_path)
    monkeypatch.setattr(portfolio_module, "SAMPLE_PORTFOLIO_PATH", sample_path)

    assert resolve_portfolio_path(None) == data_path


def test_resolve_portfolio_path_falls_back_to_sample_when_no_data(monkeypatch, tmp_path):
    data_path = tmp_path / "missing_data_portfolio.json"
    sample_path = tmp_path / "sample_portfolio.json"
    sample_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(portfolio_module, "DATA_TRANSACTIONS_PATH", tmp_path / "nope.csv")
    monkeypatch.setattr(portfolio_module, "DATA_PORTFOLIO_PATH", data_path)
    monkeypatch.setattr(portfolio_module, "SAMPLE_PORTFOLIO_PATH", sample_path)

    assert resolve_portfolio_path(None) == sample_path


def test_resolve_portfolio_path_none_when_nothing_available(monkeypatch, tmp_path):
    monkeypatch.setattr(portfolio_module, "DATA_TRANSACTIONS_PATH", tmp_path / "nope0.csv")
    monkeypatch.setattr(portfolio_module, "DATA_PORTFOLIO_PATH", tmp_path / "nope1.json")
    monkeypatch.setattr(portfolio_module, "SAMPLE_PORTFOLIO_PATH", tmp_path / "nope2.json")

    assert resolve_portfolio_path(None) is None
