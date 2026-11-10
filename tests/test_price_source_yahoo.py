import pandas as pd

from stock_advisor import calendars
from stock_advisor.price_sources import yahoo


class FakeTicker:
    def __init__(self, frame):
        self.frame = frame
        self.calls = []

    def history(self, **kwargs):
        self.calls.append(kwargs)
        return self.frame


def _patch(monkeypatch, frame):
    ticker = FakeTicker(frame)
    monkeypatch.setattr(yahoo.yf, "Ticker", lambda symbol: ticker)
    return ticker


def _daily():
    idx = pd.DatetimeIndex(["2025-03-03", "2025-03-04"], tz="America/New_York")
    return pd.DataFrame({"Open": [10.0, 20.0], "High": [11.0, 21.0], "Low": [9.0, 19.0],
                         "Close": [10.0, 20.0], "Adj Close": [5.0, 20.0],
                         "Volume": [100, 200]}, index=idx)


def test_daily_raw_and_adjusted(monkeypatch):
    ticker = _patch(monkeypatch, _daily())
    raw, adj = yahoo.fetch("AAPL", "1d", None, None)
    assert ticker.calls[0]["period"] == "max" and ticker.calls[0]["auto_adjust"] is False
    assert raw.index.tz is None and list(raw["close"]) == [10.0, 20.0]
    assert list(adj["close"]) == [5.0, 20.0] and list(adj["high"]) == [5.5, 21.0]
    assert list(adj["volume"]) == [100, 200]


def test_empty_history(monkeypatch):
    _patch(monkeypatch, pd.DataFrame())
    raw, adj = yahoo.fetch("AAPL", "1d", None, None)
    assert raw.empty and adj is None


def test_hourly_keeps_canonical_starts_and_has_no_adjusted(monkeypatch):
    day = pd.Timestamp("2025-03-04")
    starts = calendars.hourly_bar_starts("US", day)
    odd = starts[0] + pd.Timedelta(minutes=15)
    idx = pd.DatetimeIndex(list(starts) + [odd]).tz_convert("America/New_York")
    n = len(idx)
    frame = pd.DataFrame({"Open": [1.0] * n, "High": [1.0] * n, "Low": [1.0] * n,
                          "Close": [1.0] * n, "Volume": [10] * n}, index=idx)
    _patch(monkeypatch, frame)
    raw, adj = yahoo.fetch("AAPL", "60m", None, None)
    assert adj is None and len(raw) == len(starts)
    assert str(raw.index.tz) == "UTC" and odd not in raw.index


def test_hourly_window_is_725_days(monkeypatch):
    ticker = _patch(monkeypatch, pd.DataFrame())
    yahoo.fetch("0700.HK", "60m", None, None)
    start = pd.Timestamp(ticker.calls[0]["start"])
    age = (pd.Timestamp.now() - start).days
    assert 724 <= age <= 726


def test_hourly_skips_non_stock_markets(monkeypatch):
    ticker = _patch(monkeypatch, _daily())
    raw, adj = yahoo.fetch("^HSI", "60m", None, None)
    assert raw.empty and adj is None and ticker.calls == []
