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


class _FakeIntradayTicker:
    """Returns one bar per interval step inside [start, end), recording each call."""

    calls = []

    def __init__(self, symbol):
        self.symbol = symbol

    def history(self, start=None, end=None, interval="1m", auto_adjust=False, period=None):
        _FakeIntradayTicker.calls.append({"start": start, "end": end, "interval": interval})
        step = pd.Timedelta(minutes=60 if interval == "60m" else 1)
        first = pd.Timestamp(start).ceil(step)
        stamps = pd.date_range(first, pd.Timestamp(end), freq=step, inclusive="left")
        # Yahoo returns exchange-local timestamps; the module must convert to UTC.
        stamps = stamps.tz_convert("America/New_York")
        return pd.DataFrame({"Close": 1.0, "Open": 1.0, "High": 1.0, "Low": 1.0,
                             "Volume": 1}, index=stamps)


@pytest.fixture
def intraday(monkeypatch, tmp_path):
    monkeypatch.setattr(market_data, "INTRADAY_CACHE_DIR", tmp_path / "intraday")
    monkeypatch.setattr(market_data.yf, "Ticker", _FakeIntradayTicker)
    _FakeIntradayTicker.calls = []
    return _FakeIntradayTicker


def test_intraday_1m_chunks_to_7_days_and_caches_utc(intraday):
    end = pd.Timestamp.now(tz="UTC").floor("min")
    start = end - pd.Timedelta(days=20)

    result = market_data.fetch_intraday("AAPL", "1m", start=start, end=end)

    assert len(intraday.calls) == 3  # 20 days in chunks of at most 7
    assert all(
        pd.Timestamp(c["end"]) - pd.Timestamp(c["start"]) <= pd.Timedelta(days=7)
        for c in intraday.calls
    )
    assert str(result.index.tz) == "UTC"
    assert result.index.is_unique and result.index.is_monotonic_increasing
    path = market_data._intraday_cache_file("AAPL", "1m")
    assert path.exists() and path.parent.name == "1m"


def test_intraday_second_call_merges_without_duplicates(intraday):
    end = pd.Timestamp.now(tz="UTC").floor("min")
    first = market_data.fetch_intraday("AAPL", "1m", start=end - pd.Timedelta(days=2), end=end)
    n_calls = len(intraday.calls)

    later = end + pd.Timedelta(minutes=30)
    second = market_data.fetch_intraday("AAPL", "1m", start=end - pd.Timedelta(days=2), end=later)

    assert len(intraday.calls) == n_calls + 1  # only the tail is downloaded
    assert second.index.is_unique
    assert len(second) > len(first)
    on_disk = pd.read_parquet(market_data._intraday_cache_file("AAPL", "1m"))
    assert on_disk.index.is_unique and len(on_disk) == len(second)


def test_intraday_60m_single_request_and_start_clamped(intraday):
    result = market_data.fetch_intraday("^GSPC", "60m", start="2000-01-01")

    assert len(intraday.calls) == 1
    earliest = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=730)
    assert result.index.min() > earliest
    assert market_data._intraday_cache_file("^GSPC", "60m").exists()


def test_intraday_use_cache_false_skips_disk(intraday):
    market_data.fetch_intraday("AAPL", "60m", use_cache=False)

    assert not market_data._intraday_cache_file("AAPL", "60m").exists()


def test_intraday_rejects_unknown_interval(intraday):
    with pytest.raises(ValueError):
        market_data.fetch_intraday("AAPL", "3m")


def test_use_cache_false_always_calls_yfinance():
    market_data.fetch_price_history(["AAPL"], period="3d")
    market_data.fetch_price_history(["AAPL"], period="3d", use_cache=False)

    assert len(_FakeTicker.calls) == 2
    assert _FakeTicker.calls[1]["period"] == "3d"


class _LongHistoryTicker:
    """Has 30 years of daily bars for period="max"; only recent bars for start=..."""

    calls = []

    def __init__(self, symbol):
        self.symbol = symbol

    def history(self, period=None, start=None, interval="1d", auto_adjust=False):
        _LongHistoryTicker.calls.append({"period": period, "start": start})
        today = pd.Timestamp.now().normalize()
        if start is not None:
            return _history_frame([today], [130.0])
        # Ends two days ago so the incremental "today" bar is new.
        dates = pd.date_range(today - pd.Timedelta(days=30 * 365), today - pd.Timedelta(days=2),
                              freq="30D")
        return _history_frame(dates, list(range(len(dates))))


@pytest.fixture
def long_history(monkeypatch):
    monkeypatch.setattr(market_data.yf, "Ticker", _LongHistoryTicker)
    _LongHistoryTicker.calls = []
    return _LongHistoryTicker


def _age_cache(symbol):
    import os

    old = pd.Timestamp.now().timestamp() - (market_data.CACHE_TTL_HOURS + 1) * 3600
    os.utime(market_data._cache_file(symbol), (old, old))


def test_max_returns_all_history_not_twenty_years(long_history):
    result = market_data.fetch_price_history(["^GSPC"], period="max")["^GSPC"]

    assert long_history.calls == [{"period": "max", "start": None}]
    assert result.index.min() < pd.Timestamp.now(tz="America/New_York") - pd.Timedelta(days=25 * 365)
    # A fresh cache serves the whole history again without a network call.
    again = market_data.fetch_price_history(["^GSPC"], period="max")["^GSPC"]
    assert len(long_history.calls) == 1 and len(again) == len(result)


def test_max_refetches_once_when_cache_may_have_been_cut(long_history):
    # An old-style cache: 20 years only, no marker.
    today = pd.Timestamp.now().normalize()
    cut = _history_frame(pd.date_range(today - pd.Timedelta(days=20 * 365), today, freq="30D"),
                         [1.0] * len(pd.date_range(today - pd.Timedelta(days=20 * 365), today,
                                                   freq="30D")))
    market_data._write_cache("^GSPC", cut)

    first = market_data.fetch_price_history(["^GSPC"], period="max")["^GSPC"]
    assert long_history.calls[-1]["period"] == "max" and len(first) > len(cut)
    assert market_data._max_marker("^GSPC").exists()

    # Afterwards the usual incremental update of recent bars works and keeps the history.
    _age_cache("^GSPC")
    second = market_data.fetch_price_history(["^GSPC"], period="max")["^GSPC"]
    assert len(long_history.calls) == 2
    assert long_history.calls[1]["start"] is not None and long_history.calls[1]["period"] is None
    assert second.index.min() == first.index.min() and len(second) == len(first) + 1


def test_full_history_cache_serves_shorter_periods_without_refetch(long_history):
    market_data.fetch_price_history(["^GSPC"], period="max")
    result = market_data.fetch_price_history(["^GSPC"], period="5y")["^GSPC"]

    assert len(long_history.calls) == 1
    assert result.index.min() >= pd.Timestamp.now(tz="America/New_York") - pd.Timedelta(days=5 * 366)


def test_period_to_days_ytd_is_since_january_first():
    days = market_data._period_to_days("ytd")
    first = pd.Timestamp(year=pd.Timestamp.now().year, month=1, day=1)
    assert days == (pd.Timestamp.now().normalize() - first).days + 1
    assert market_data._period_cutoff("max") is None


def test_cache_refetches_fresh_when_requested_period_exceeds_cached_range():
    market_data.fetch_price_history(["AAPL"], period="1d")
    assert len(_FakeTicker.calls) == 1

    market_data.fetch_price_history(["AAPL"], period="5y")

    assert len(_FakeTicker.calls) == 2
    assert _FakeTicker.calls[1]["period"] == "5y"
