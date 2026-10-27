"""Tests for stock_advisor.report, mocking out the Yahoo Finance fetch layer."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import stock_advisor.report as report_module


@pytest.fixture(autouse=True)
def _no_real_news_store(monkeypatch):
    """Keep every test off the real news.db; news tests pass a fake analyzer instead."""
    import stock_advisor.news.settings as news_settings

    monkeypatch.setattr(news_settings, "DEFAULT_DB_PATH", Path("does-not-exist") / "news.db")


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


# ---- news column --------------------------------------------------------------------------------


def _outlook(move, action, proven):
    return SimpleNamespace(predicted_action_move=move, action=action, action_proven=proven)


class _FakeAnalyzer:
    def __init__(self, outlooks=None, error=None):
        self.outlooks = outlooks or {}
        self.error = error

    def analyze_recent(self, hours=24):
        if self.error:
            raise self.error
        if not self.outlooks:
            return []
        return [SimpleNamespace(category="war_conflict", outlooks=self.outlooks)]


def _report(monkeypatch, **kwargs):
    prices = _synthetic_close_prices()
    monkeypatch.setattr(
        report_module, "fetch_close_prices", lambda symbols, period, interval: prices
    )
    monkeypatch.setattr(report_module, "resolve_portfolio_path", lambda explicit_path: None)
    return report_module.generate_report(["AAPL", "MSFT"], **kwargs)


def test_unproven_news_warns_and_never_changes_action(monkeypatch):
    analyzer = _FakeAnalyzer({"AAPL": _outlook(-0.021, "reduce", False)})
    result = _report(monkeypatch, news_analyzer=analyzer)

    assert result.loc["AAPL", "news"] == "\u26a0 war_conflict: \u22122.1% 1d (unproven)"
    assert result.loc["AAPL", "recommendation"] == "BUY"
    assert result.loc["MSFT", "news"] == report_module.NO_NEWS
    assert "war_conflict" in report_module.format_report(result)


def test_proven_news_can_change_action(monkeypatch):
    analyzer = _FakeAnalyzer({"AAPL": _outlook(-0.021, "reduce", True)})
    result = _report(monkeypatch, news_analyzer=analyzer)

    assert result.loc["AAPL", "news"] == "war_conflict: \u22122.1% 1d (proven: reduce)"
    assert result.loc["AAPL", "recommendation"] == "HOLD"  # BUY stepped down
    assert "News: proven reduce" in result.loc["AAPL", "rationale"]


def test_no_events_leaves_report_unchanged(monkeypatch):
    with_news = _report(monkeypatch, news_analyzer=_FakeAnalyzer())
    without = _report(monkeypatch, include_news=False)

    assert (with_news["news"] == report_module.NO_NEWS).all()
    assert "news" not in without.columns
    pd.testing.assert_frame_equal(with_news.drop(columns="news"), without)


def test_news_failure_never_breaks_report(monkeypatch, capsys):
    result = _report(monkeypatch, news_analyzer=_FakeAnalyzer(error=RuntimeError("boom")))

    assert (result["news"] == report_module.NO_NEWS).all()
    assert result.loc["AAPL", "recommendation"] == "BUY"
    assert "news column unavailable" in capsys.readouterr().out


def test_missing_news_store_gives_empty_column(monkeypatch):
    result = _report(monkeypatch)  # fixture points the store path at a missing file

    assert (result["news"] == report_module.NO_NEWS).all()
    assert not Path("does-not-exist").exists()  # the report did not create a store


def test_cli_no_news_flag(monkeypatch):
    import stock_advisor.cli as cli

    seen = {}

    def fake_generate(symbols, portfolio_path, config, include_news):
        seen["include_news"] = include_news
        return pd.DataFrame()

    monkeypatch.setattr(cli, "generate_report", fake_generate)
    monkeypatch.setattr(cli, "format_report", lambda report: "")
    monkeypatch.setattr("sys.argv", ["cli", "--no-news"])
    cli.main()
    assert seen["include_news"] is False