"""Tests for scripts/backtest_ma_rule.py on a tiny synthetic series worked by hand."""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backtest_ma_rule.py"
spec = importlib.util.spec_from_file_location("backtest_ma_rule", SCRIPT)
bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)

# 2-day average: [nan, 10.5, 11.5, 11, 9, 8.5, 10.5]; close above it on days 1, 2, 5, 6.
CLOSE = pd.Series([10.0, 11, 12, 10, 8, 9, 12], index=pd.bdate_range("2020-01-01", periods=7))


def test_rule_without_costs_matches_hand_result():
    res = bt.backtest(CLOSE, window=2, kind="sma", cost=0.0)
    # In for 11->12 and 12->10, out for 10->8 and 8->9, in for 9->12.
    assert res["rule"].iloc[-1] == pytest.approx(12 / 11 * 10 / 12 * 12 / 9)
    assert res["hold"].iloc[-1] == pytest.approx(12 / 11)
    assert list(res["pos"]) == [1, 1, 0, 0, 1, 1]
    m = bt.metrics(res["rule"], res["pos"])
    assert m["trades"] == 2  # sell on day 3, buy on day 5 (the entry on day 1 is the base)
    assert m["in_market"] == pytest.approx(3 / 5)
    assert m["max_dd"] == pytest.approx((10 / 11) / (12 / 11) - 1)


def test_costs_charge_every_switch_and_cash_earns_interest():
    free = bt.backtest(CLOSE, window=2, kind="sma", cost=0.0)["rule"].iloc[-1]
    costly = bt.backtest(CLOSE, window=2, kind="sma", cost=0.01)["rule"].iloc[-1]
    assert costly == pytest.approx(free * 0.99 ** 3)  # entry, sell, buy
    cash = pd.Series(0.01, index=CLOSE.index)
    paid = bt.backtest(CLOSE, window=2, kind="sma", cost=0.0, cash_daily=cash)["rule"].iloc[-1]
    assert paid == pytest.approx(free * 1.01 ** 2)  # two days out of the market


def test_tbill_rate_conversion_and_ema_start():
    assert bt.tbill_daily(pd.Series([0.0])).iloc[0] == 0.0
    assert (1 + bt.tbill_daily(pd.Series([5.0])).iloc[0]) ** 252 == pytest.approx(1.05)
    res = bt.backtest(CLOSE, window=2, kind="ema", cost=0.0)
    assert res.index[0] == CLOSE.index[1]
