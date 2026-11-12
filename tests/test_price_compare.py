import pandas as pd
import pytest

from stock_advisor import price_compare, price_store


@pytest.fixture(autouse=True)
def _store(tmp_path, monkeypatch):
    monkeypatch.setattr(price_store, "STORE_ROOT", tmp_path)


def _bars(dates, close):
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                         "volume": 1000}, index=pd.to_datetime(dates))


DAYS = ["2025-03-03", "2025-03-04", "2025-03-05", "2025-03-06", "2025-03-07"]


def _load():
    # Yahoo lacks 03-05 and has a 50% jump on 03-06 that Futu lacks; Futu's 03-04 close is 2% off.
    price_store.write_bars("yahoo", "1d", "0005.HK", _bars(
        ["2025-03-03", "2025-03-04", "2025-03-06", "2025-03-07"], [100.0, 100.0, 150.0, 150.0]), None)
    price_store.write_bars("futu", "1d", "0005.HK", _bars(DAYS, [100.0, 102.0, 100.0, 100.0, 100.0]), None)


def test_compare_symbol_counts_differences():
    _load()
    row = price_compare.compare_symbol("0005.HK", "1d")
    assert row["common_bars"] == 4 and row["yahoo_only"] == 0 and row["futu_only"] == 1
    assert row["raw_close_diff"] == 3  # 03-04 (2%), 03-06 and 03-07 (50%)
    assert row["yahoo_unmatched_big"] == 1 and row["futu_unmatched_big"] == 0


def test_missing_symbol_or_no_overlap_gives_none():
    assert price_compare.compare_symbol("0005.HK", "1d") is None
    price_store.write_bars("yahoo", "1d", "0005.HK", _bars(["2025-01-02"], [1.0]), None)
    price_store.write_bars("futu", "1d", "0005.HK", _bars(["2025-02-03"], [1.0]), None)
    assert price_compare.compare_symbol("0005.HK", "1d") is None


def test_totals_score_each_source():
    _load()
    detail = price_compare.compare_all(["0005.HK", "AAPL"], intervals=("1d",))
    summary = price_compare.totals(detail)
    assert list(summary["market"]) == ["HK"]
    # yahoo lacks 1 bar (futu_only); futu lacks none but yahoo's big move is unmatched (1)
    assert summary.loc[0, "yahoo_score"] == 1 and summary.loc[0, "futu_score"] == 1


def test_preferred_order_follows_scores():
    summary = pd.DataFrame([
        {"market": "HK", "interval": "1d", "yahoo_score": 9, "futu_score": 2},
        {"market": "US", "interval": "1d", "yahoo_score": 1, "alpaca_score": 5}])
    order = price_compare.preferred_order(summary)
    assert order["HK"] == ("futu", "yahoo") and order["US"] == ("yahoo", "alpaca")
    assert order["OTHER"] == ("yahoo",)
