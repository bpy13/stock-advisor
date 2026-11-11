"""Dashboard Portfolio tab, run with Streamlit's AppTest. Synthetic data, no network."""
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from stock_advisor import analyzer

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _fake_report(cash_set: bool) -> analyzer.PortfolioReport:
    idx = pd.bdate_range("2025-01-01", periods=5)
    summary = analyzer.PortfolioSummary(
        value_today=1000.0, holdings_value=1000.0, cash=0.0, return_without_timing=0.1,
        return_with_timing=0.08, deepest_fall=-0.05, fall_start=idx[1], fall_end=idx[2],
        yearly_swing=0.2, weights={"AAA": 1.0}, top3_weight=1.0, effective_holdings=1.0,
        value_series=pd.Series([1, 2, 1.5, 2, 3.0], index=idx))
    table = pd.DataFrame({"weight": [1.0], "risk_share": [1.0], "group": [1],
                          "market_beta": [1.0], "drivers": [""]}, index=["AAA"])
    return analyzer.PortfolioReport(summary=summary, table=table, groups=[["AAA", "BBB"]],
                                    too_short=[], cash_set=cash_set)


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """The Report and News tabs fail or come back empty without touching the network."""
    def boom(*a, **k):
        raise RuntimeError("offline")
    monkeypatch.setattr("stock_advisor.report.generate_report", boom)
    monkeypatch.setattr("stock_advisor.news.collect.holdings_symbols", lambda *a, **k: [])
    monkeypatch.setattr("stock_advisor.news.analysis.alert_targets", lambda *a, **k: [])
    monkeypatch.setattr("stock_advisor.news.analysis.open_store", boom)  # News tab shows its own error
    st.cache_data.clear()
    monkeypatch.setattr("stock_advisor.analyze_cli.cost_report", lambda s, a, p=None: f"cost {s} {a}")


def _run() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    return at


def test_tab_renders_and_shows_cash_note(monkeypatch):
    monkeypatch.setattr(analyzer, "build_portfolio_report", lambda *a, **k: _fake_report(False))
    at = _run()
    assert [t.label for t in at.tabs][:3] == ["Report", "Portfolio", "News"]
    assert any(m.label == "Value today" and m.value == "1,000" for m in at.metric)
    assert any("Cash is not set" in i.value for i in at.info)
    assert any("AAA, BBB" in m.value for m in at.markdown)


def test_cash_note_absent_when_cash_set(monkeypatch):
    monkeypatch.setattr(analyzer, "build_portfolio_report", lambda *a, **k: _fake_report(True))
    at = _run()
    assert not any("Cash is not set" in i.value for i in at.info)


def test_failure_shows_error_and_news_tab_still_renders(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("store missing")
    monkeypatch.setattr(analyzer, "build_portfolio_report", boom)
    at = _run()
    assert any("Could not build the portfolio analysis" in e.value for e in at.error)
    assert any(s.value == "Recent news events" for s in at.subheader)
