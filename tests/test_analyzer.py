"""Hand-checked numbers for stock_advisor.analyzer (synthetic data, no network)."""
from datetime import date

import pandas as pd
import pytest

from stock_advisor.analyzer import summarize
from stock_advisor.transactions import Transaction


def tx(d, ticker, ccy, price, qty):
    return Transaction(trade_date=d, name=ticker, ticker=ticker, currency=ccy, price=price, quantity=qty)


def series(values, start="2024-01-01"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


def test_two_stocks_three_trades_usd_converted():
    # A (HKD): 100 shares from day 1, prices 10, 11, 12.1. B (USD): 10 shares from day 2, 20, 20, 22.
    a = series([10, 11, 12.1])
    b = series([20, 20, 22])
    fx = series([8, 8, 8])
    trades = [tx(date(2024, 1, 1), "AAA", "HKD", 10, 100), tx(date(2024, 1, 2), "BBB", "USD", 20, 6),
              tx(date(2024, 1, 2), "BBB", "USD", 20, 4)]
    s = summarize(trades, {"AAA": a, "BBB": b}, fx, cash_hkd=500, as_of="2024-01-03")
    # day 2: 10% on A alone; day 3: (110 + 160) / 2700 = 10% -> chained 21%
    assert s.return_without_timing == pytest.approx(0.21)
    assert s.holdings_value == pytest.approx(1210 + 10 * 22 * 8)
    assert s.value_today == pytest.approx(2970 + 500)
    assert s.weights["AAA"] == pytest.approx(1210 / 2970)
    assert sum(s.weights.values()) == pytest.approx(1.0)
    assert s.top3_weight == pytest.approx(1.0)
    w = s.weights["AAA"]
    assert s.effective_holdings == pytest.approx(1 / (w * w + (1 - w) ** 2))
    assert s.unpriced == []


def test_deepest_fall_dates():
    p = series([10, 12, 9, 10, 11])
    s = summarize([tx(date(2024, 1, 1), "AAA", "HKD", 10, 100)], {"AAA": p}, as_of="2024-01-05")
    assert s.deepest_fall == pytest.approx(-0.25)
    assert s.fall_start == pd.Timestamp("2024-01-02")
    assert s.fall_end == pd.Timestamp("2024-01-03")
    assert s.yearly_swing > 0


def test_sale_to_zero():
    p = series([10, 11, 12, 12])
    trades = [tx(date(2024, 1, 1), "AAA", "HKD", 10, 100), tx(date(2024, 1, 3), "AAA", "HKD", 12, -100)]
    s = summarize(trades, {"AAA": p}, as_of="2024-01-04")
    assert s.holdings_value == 0
    assert s.weights == {}
    assert s.return_without_timing == pytest.approx(0.2)  # day 4 holds nothing: no change


def test_return_with_timing_one_year():
    p = pd.Series([10.0, 11.0], index=pd.to_datetime(["2023-01-01", "2024-01-01"]))
    s = summarize([tx(date(2023, 1, 1), "AAA", "HKD", 10, 100)], {"AAA": p}, as_of="2024-01-01")
    assert s.return_with_timing == pytest.approx(0.10, abs=1e-6)


def test_unpriced_holding_valued_at_cost():
    p = series([10, 11])
    trades = [tx(date(2024, 1, 1), "AAA", "HKD", 10, 100), tx(date(2024, 1, 1), "ZZZ", "HKD", 5, 200)]
    s = summarize(trades, {"AAA": p}, as_of="2024-01-02")
    assert s.unpriced == ["ZZZ"]
    assert s.holdings_value == pytest.approx(1100 + 1000)
    assert s.weights["ZZZ"] == pytest.approx(1000 / 2100)
    assert s.return_without_timing == pytest.approx(0.10)  # unpriced left out of the series


def test_no_trades_rejected():
    with pytest.raises(ValueError):
        summarize([], {})
