import pandas as pd
import pytest

from stock_advisor import price_store


@pytest.fixture(autouse=True)
def _store(tmp_path, monkeypatch):
    monkeypatch.setattr(price_store, "STORE_ROOT", tmp_path)


def _bars(dates, close, volume=1000):
    idx = pd.to_datetime(dates)
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                         "volume": volume}, index=idx)


def test_append_same_bars_twice_gives_no_duplicates():
    raw = _bars(["2025-03-03", "2025-03-04"], [10.0, 11.0])
    price_store.write_bars("yahoo", "1d", "AAPL", raw, None)
    price_store.write_bars("yahoo", "1d", "AAPL", raw, None)
    got = price_store.read_bars("AAPL", adjusted=False)
    assert len(got) == 2 and got.index.is_unique


def test_new_rows_win_and_extend():
    price_store.write_bars("yahoo", "1d", "AAPL", _bars(["2025-03-03", "2025-03-04"], [10.0, 11.0]), None)
    price_store.write_bars("yahoo", "1d", "AAPL", _bars(["2025-03-04", "2025-03-05"], [12.0, 13.0]), None)
    got = price_store.read_bars("AAPL", adjusted=False)
    assert list(got["close"]) == [10.0, 12.0, 13.0]


def test_adjusted_file_is_replaced_whole():
    raw = _bars(["2025-03-03", "2025-03-04"], [10.0, 11.0])
    price_store.write_bars("yahoo", "1d", "AAPL", raw, _bars(["2025-03-03", "2025-03-04"], [9.0, 10.0]))
    price_store.write_bars("yahoo", "1d", "AAPL", raw, _bars(["2025-03-03", "2025-03-04"], [4.5, 5.0]))
    assert list(price_store.read_bars("AAPL", adjusted=True)["close"]) == [4.5, 5.0]
    assert list(price_store.read_bars("AAPL", adjusted=False)["close"]) == [10.0, 11.0]


def test_adjusted_read_carries_raw_flags_and_missing_adjusted_returns_raw():
    # Wed 2025-03-05 is missing: gap_before is 1 on Thu.
    raw = _bars(["2025-03-03", "2025-03-04", "2025-03-06"], [10.0, 10.0, 10.0])
    price_store.write_bars("yahoo", "1d", "AAPL", raw, None)
    got = price_store.read_bars("AAPL", adjusted=True)  # no adjusted file: raw prices
    assert list(got["gap_before"]) == [0, 0, 1]
    price_store.write_bars("yahoo", "1d", "AAPL", raw, raw * 0.5)
    got = price_store.read_bars("AAPL", adjusted=True)
    assert list(got["close"]) == [5.0, 5.0, 5.0] and list(got["gap_before"]) == [0, 0, 1]


def test_symbol_held_by_second_source_only():
    raw = _bars(["2025-03-03"], [10.0])
    price_store.write_bars("alpaca", "1d", "AAPL", raw, None)
    saved = price_store.PREFERRED_SOURCES["US"]
    price_store.PREFERRED_SOURCES["US"] = ("yahoo",)
    try:
        assert price_store.read_bars("AAPL").empty  # preferred source is yahoo only
        assert len(price_store.read_bars("AAPL", source="alpaca")) == 1
        price_store.PREFERRED_SOURCES["US"] = ("alpaca", "yahoo")
        assert len(price_store.read_bars("AAPL")) == 1
    finally:
        price_store.PREFERRED_SOURCES["US"] = saved


def test_missing_symbol_gives_empty_frame_and_start_end_clip():
    assert price_store.read_bars("NOPE").empty
    price_store.write_bars("yahoo", "1d", "AAPL", _bars(["2025-03-03", "2025-03-04", "2025-03-05"], [1.0, 2.0, 3.0]), None)
    got = price_store.read_bars("AAPL", adjusted=False, start="2025-03-04", end="2025-03-04")
    assert list(got["close"]) == [2.0]


def test_hourly_utc_index_and_special_symbol_names():
    idx = pd.DatetimeIndex(["2025-01-06 14:30", "2025-01-06 15:30"], tz="UTC")
    raw = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 5}, index=idx)
    price_store.write_bars("yahoo", "60m", "AAPL", raw, None)
    price_store.write_bars("yahoo", "1d", "^HSI", _bars(["2025-03-03"], [1.0]), None)
    price_store.write_bars("yahoo", "1d", "CL=F", _bars(["2025-03-03"], [1.0]), None)
    assert len(price_store.read_bars("AAPL", "60m", start="2025-01-06 15:00")) == 1
    status = price_store.status()
    assert set(status["market"]) == {"US", "OTHER"}
    assert status[status["market"] == "OTHER"]["symbols"].iloc[0] == 2
