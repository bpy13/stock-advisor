"""Tests for stock_advisor.market_data's local disk cache (no network calls)."""

import pandas as pd
import pytest

import stock_advisor.market_data as market_data


def _history_frame(dates, prices):
    index = pd.DatetimeIndex(dates, tz="America/New_York")
    return pd.DataFrame({"Close": prices, "Open": prices, "High": prices, "Low": prices,
                          "Volume": [1000] * len(prices)}, index=index)


class _FakeTicker:
    """Records every `.history()` call so tests can assert on cache-hit/miss behavior."""

    calls = []

    def __init__(self, symbol):
        self.symbol = symbol

    def history(self, period=None, start=None, interval="1d", auto_adjust=False):
        _FakeTicker.calls.append({"symbol": self.symbol, "period": period, "start": start})
        today = pd.Timestamp.now().normalize()
        if start is not None:
            # Incremental fetch: just the new/most-recent bar (not yet cached).
            return _history_frame([today], [130.0])
        recent_dates = [today - pd.Timedelta(days=d) for d in (4, 3, 2, 1)]
        return _history_frame(recent_dates, [100.0, 110.0, 120.0, 125.0])


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(market_data, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(market_data.yf, "Ticker", _FakeTicker)
    _FakeTicker.calls = []
    yield


def test_cache_miss_fetches_and_writes_cache():
    result = market_data.fetch_price_history(["AAPL"], period="1y")

    assert len(_FakeTicker.calls) == 1
    assert _FakeTicker.calls[0]["period"] == "1y"
    assert market_data._cache_file("AAPL").exists()
    assert len(result["AAPL"]) == 4


def test_fresh_cache_is_served_without_calling_yfinance():
    market_data.fetch_price_history(["AAPL"], period="3d")
    assert len(_FakeTicker.calls) == 1

    result = market_data.fetch_price_history(["AAPL"], period="3d")

    assert len(_FakeTicker.calls) == 1  # no new call: cache hit
    assert not result["AAPL"].empty


def test_stale_cache_triggers_incremental_fetch_and_merges(monkeypatch):
    market_data.fetch_price_history(["AAPL"], period="3d")
    assert len(_FakeTicker.calls) == 1

    # Simulate the cache aging past the TTL.
    cache_path = market_data._cache_file("AAPL")
    old_mtime = pd.Timestamp.now().timestamp() - (market_data.CACHE_TTL_HOURS + 1) * 3600
    import os

    os.utime(cache_path, (old_mtime, old_mtime))

    result = market_data.fetch_price_history(["AAPL"], period="3d")

    assert len(_FakeTicker.calls) == 2
    assert _FakeTicker.calls[1]["start"] is not None
    # The new bar should have been merged into the on-disk cache...
    full_cache = market_data._read_cache("AAPL")
    assert len(full_cache) == 5  # 4 original bars + 1 new bar
    # ...and be present in the (cutoff-sliced) returned result too.
    assert result["AAPL"].index.max() == full_cache.index.max()


def test_use_cache_false_always_calls_yfinance():
    market_data.fetch_price_history(["AAPL"], period="3d")
    market_data.fetch_price_history(["AAPL"], period="3d", use_cache=False)

    assert len(_FakeTicker.calls) == 2
    assert _FakeTicker.calls[1]["period"] == "3d"


def test_cache_refetches_fresh_when_requested_period_exceeds_cached_range():
    market_data.fetch_price_history(["AAPL"], period="1d")
    assert len(_FakeTicker.calls) == 1

    market_data.fetch_price_history(["AAPL"], period="5y")

    assert len(_FakeTicker.calls) == 2
    assert _FakeTicker.calls[1]["period"] == "5y"
