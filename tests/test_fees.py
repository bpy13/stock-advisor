import pytest

from stock_advisor.fees import HSB_CUSTODY_FEE_HKD_MONTHLY, round_trip_pct, trade_cost


def both(broker, market, kind, price, shares):
    return sum(trade_cost(broker, market, kind, price, shares, s).total for s in ("buy", "sell"))


@pytest.mark.parametrize(
    "broker,kind,value,expected",
    [
        ("hang_seng_bank", "stock", 20_000, 243.40),
        ("hang_seng_bank", "stock", 100_000, 717.00),
        ("futu", "stock", 20_000, 73.40),
        ("futu", "stock", 100_000, 247.00),
        ("hang_seng_bank", "index_fund", 20_000, 203.40),
        ("futu", "index_fund", 20_000, 33.40),
    ],
)
def test_hk_round_trip(broker, kind, value, expected):
    assert both(broker, "HK", kind, 100.0, value / 100.0) == pytest.approx(expected, abs=0.01)


@pytest.mark.parametrize("broker,expected", [("hang_seng_bank", 30.05), ("futu", 4.04)])
def test_us_round_trip(broker, expected):
    assert both(broker, "US", "stock", 100.0, 25) == pytest.approx(expected, abs=0.01)


def test_currency_and_lines():
    c = trade_cost("futu", "US", "stock", 100.0, 25, "sell")
    assert c.currency == "USD"
    assert c.total == pytest.approx(sum(a for _, a in c.lines))
    assert trade_cost("futu", "HK", "stock", 100.0, 200, "buy").currency == "HKD"


def test_stamp_duty_rounds_up():
    lines = dict(trade_cost("futu", "HK", "stock", 10.0, 1_001, "buy").lines)
    assert lines["stamp duty"] == 11.0  # 10.01 rounds up


def test_round_trip_pct():
    assert round_trip_pct("hang_seng_bank", "HK", "stock", 100.0, 200) == pytest.approx(1.217, abs=0.001)
    assert round_trip_pct("futu", "HK", "stock", 100.0, 200) == pytest.approx(0.367, abs=0.001)


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        trade_cost("ibkr", "HK", "stock", 1, 1, "buy")
    with pytest.raises(ValueError):
        trade_cost("futu", "JP", "stock", 1, 1, "buy")
    with pytest.raises(ValueError):
        trade_cost("futu", "HK", "stock", 1, 1, "hold")


def test_custody_constant():
    assert HSB_CUSTODY_FEE_HKD_MONTHLY == 25.0
