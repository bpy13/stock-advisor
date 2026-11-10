"""analyze_cli with the store and accounts faked (synthetic data, no network)."""
import numpy as np
import pandas as pd
import pytest

from stock_advisor import analyze_cli, analyzer, price_store
from stock_advisor.transactions import Transaction


def _bars(prices):
    idx = pd.bdate_range("2022-01-03", periods=len(prices))
    return pd.DataFrame({"open": prices, "high": prices, "low": prices, "close": prices,
                         "volume": 1.0, "no_trade": False, "big_move": False, "gap_before": 0}, index=idx)


def _fake_store(monkeypatch):
    rng = np.random.default_rng(0)
    n = 400
    mkt = rng.normal(0, 0.01, n)
    data = {
        "AAA.HK": 100 * np.cumprod(1 + mkt + rng.normal(0, 0.002, n)),
        "BBB.HK": 50 * np.cumprod(1 + mkt + rng.normal(0, 0.002, n)),
        "CCC.HK": 20 * np.cumprod(1 + rng.normal(0, 0.01, n)),
        "^HSI": 1000 * np.cumprod(1 + mkt),
    }
    monkeypatch.setattr(price_store, "read_bars",
                        lambda symbol, interval="1d", adjusted=True, **kw:
                        _bars(data[symbol]) if symbol in data else _bars([]))


def _trades():
    d = pd.Timestamp("2022-01-03").date()
    return [Transaction(trade_date=d, name=s, ticker=s, currency="HKD", price=p, quantity=100)
            for s, p in [("AAA.HK", 100), ("BBB.HK", 50), ("CCC.HK", 20)]]


def test_report_has_table_groups_and_caveat(monkeypatch):
    _fake_store(monkeypatch)
    monkeypatch.setattr(analyzer, "load_transactions", lambda p: _trades())
    rep = analyzer.build_portfolio_report()
    assert rep.table["risk_share"].astype(float).sum() == pytest.approx(1.0)
    assert rep.table["weight"].astype(float).sum() == pytest.approx(1.0)
    assert any({"AAA.HK", "BBB.HK"} <= set(g) for g in rep.groups)
    text = analyze_cli.format_report(rep)
    assert "Per holding" in text and rep.caveat in text and "AAA.HK" in text


def test_cost_command_example_matches_fee_tables(monkeypatch):
    monkeypatch.setattr(price_store, "read_bars", lambda *a, **k: _bars([]))
    out = analyze_cli.cost_report("0005.HK", 20000)
    assert "hang_seng_bank" in out and "1.22%" in out
    assert "futu" in out and "0.37%" in out


def test_cli_cost_main_prints(monkeypatch, capsys):
    monkeypatch.setattr(price_store, "read_bars", lambda *a, **k: _bars([]))
    assert analyze_cli.main(["cost", "--symbol", "0005.HK", "--amount", "20000"]) == 0
    assert "1.22%" in capsys.readouterr().out
