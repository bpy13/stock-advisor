"""Tests for stock_advisor.report, mocking out the Yahoo Finance fetch layer."""

import numpy as np
import pandas as pd

import stock_advisor.report as report_module


def _synthetic_close_prices(length: int = 300) -> pd.DataFrame:
    index = pd.date_range("2023-01-01", periods=length, freq="D")
    rng = np.random.default_rng(seed=7)

    aapl = 150 + rng.normal(0, 1, length).cumsum() * 0.1
    aapl[-1] = aapl[:-1].mean() * 0.5  # force a cheap final price -> BUY

    msft = 300 + rng.normal(0, 1, length).cumsum() * 0.1
    msft[-1] = msft[:-1].mean() * 2.0  # force an expensive final price -> SELL

    return pd.DataFrame({"AAPL": aapl, "MSFT": msft}, index=index)


def test_generate_report_produces_expected_columns_and_signals(monkeypatch, tmp_path):
    prices = _synthetic_close_prices()
    monkeypatch.setattr(
        report_module, "fetch_close_prices", lambda symbols, period, interval: prices
    )
    monkeypatch.setattr(report_module, "resolve_portfolio_path", lambda explicit_path: None)

    result = report_module.generate_report(["AAPL", "MSFT"])

    assert set(result.index) == {"AAPL", "MSFT"}
    assert "recommendation" in result.columns
    assert result.loc["AAPL", "recommendation"] == "BUY"
    assert result.loc["MSFT", "recommendation"] == "SELL"


def test_generate_report_applies_portfolio_adjustment(monkeypatch, tmp_path):
    prices = _synthetic_close_prices()
    monkeypatch.setattr(
        report_module, "fetch_close_prices", lambda symbols, period, interval: prices
    )

    portfolio_path = tmp_path / "portfolio.json"
    portfolio_path.write_text(
        '{"cash": 0.0, "positions": [{"symbol": "MSFT", "shares": 5, "cost_basis": 300.0}]}',
        encoding="utf-8",
    )

    result = report_module.generate_report(["AAPL", "MSFT"], portfolio_path=portfolio_path)

    # AAPL has no existing position and is cheap -> BUY should pass through.
    assert result.loc["AAPL", "recommendation"] == "BUY"
    # MSFT is expensive and held -> SELL should pass through.
    assert result.loc["MSFT", "recommendation"] == "SELL"
    assert result.loc["MSFT", "shares_held"] == 5


def test_format_report_includes_rationale_section(monkeypatch):
    prices = _synthetic_close_prices()
    monkeypatch.setattr(
        report_module, "fetch_close_prices", lambda symbols, period, interval: prices
    )
    monkeypatch.setattr(report_module, "resolve_portfolio_path", lambda explicit_path: None)

    result = report_module.generate_report(["AAPL", "MSFT"])
    text = report_module.format_report(result)

    assert "Rationale:" in text
    assert "AAPL" in text and "MSFT" in text


def test_generate_report_defaults_to_portfolio_holdings_when_symbols_omitted(
    monkeypatch, tmp_path
):
    prices = _synthetic_close_prices()
    captured_requests = []

    def fake_fetch(symbols, period, interval):
        captured_requests.append(list(symbols))
        return prices

    monkeypatch.setattr(report_module, "fetch_close_prices", fake_fetch)

    portfolio_path = tmp_path / "portfolio.json"
    portfolio_path.write_text(
        '{"cash": 0.0, "positions": [{"symbol": "MSFT", "shares": 5, "cost_basis": 300.0}]}',
        encoding="utf-8",
    )

    report_module.generate_report(symbols=None, portfolio_path=portfolio_path)

    assert captured_requests == [["MSFT"]]


def test_generate_report_defaults_to_hk_universe_when_no_symbols_and_no_portfolio(
    monkeypatch,
):
    prices = _synthetic_close_prices().rename(columns={"AAPL": "0700.HK", "MSFT": "9988.HK"})
    captured_requests = []

    def fake_fetch(symbols, period, interval):
        captured_requests.append(list(symbols))
        return prices

    monkeypatch.setattr(report_module, "fetch_close_prices", fake_fetch)
    monkeypatch.setattr(report_module, "resolve_portfolio_path", lambda explicit_path: None)

    report_module.generate_report(symbols=None, portfolio_path=None)

    assert captured_requests == [list(report_module.DEFAULT_HK_UNIVERSE)]
