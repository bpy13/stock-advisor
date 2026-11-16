import pandas as pd

from stock_advisor import price_store, prices_cli
from stock_advisor.watchlist import WatchItem


class FakeSource:
    def fetch(self, symbol, interval, start, end):
        if symbol == "BAD":
            raise RuntimeError("boom")
        idx = pd.to_datetime(["2005-03-03", "2005-03-04"])
        raw = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                            "volume": 10}, index=idx)
        return raw, raw


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(price_store, "STORE_ROOT", tmp_path)
    monkeypatch.setattr(prices_cli, "SOURCES", {"yahoo": FakeSource()})
    monkeypatch.setattr(prices_cli, "PAUSE_SECONDS", 0)
    items = [WatchItem("AAPL", "US", "stock", "Apple"), WatchItem("BAD", "US", "stock", "Bad"),
             WatchItem("0700.HK", "HK", "stock", "Tencent")]
    monkeypatch.setattr(prices_cli, "load_watchlist", lambda: items)


def test_refresh_continues_after_failure_and_counts(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert prices_cli.refresh("yahoo", ["1d"]) == (2, 1, 4)
    assert prices_cli.refresh("yahoo", ["1d"]) == (2, 1, 0)  # second run adds nothing


def test_limit(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert prices_cli.refresh("yahoo", ["1d"], limit=1) == (1, 0, 2)


def test_main_prints_summary_and_status_without_symbols(monkeypatch, tmp_path, capsys):
    _setup(monkeypatch, tmp_path)
    prices_cli.main(["refresh", "--interval", "1d"])
    assert "2 symbols done, 1 failed, 4 bars added" in capsys.readouterr().out
    prices_cli.main(["status"])
    out = capsys.readouterr().out
    assert "US" in out and "HK" in out and "AAPL" not in out


def test_hourly_refresh_fetches_only_from_a_week_before_the_last_stored_bar(monkeypatch, tmp_path):
    starts = []

    class HourlySource:
        def fetch(self, symbol, interval, start, end):
            starts.append(start)
            idx = pd.DatetimeIndex(["2026-11-10 14:30", "2026-11-10 15:30"], tz="UTC")
            raw = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                                "volume": 10}, index=idx)
            return raw, None

    monkeypatch.setattr(price_store, "STORE_ROOT", tmp_path)
    monkeypatch.setattr(prices_cli, "SOURCES", {"yahoo": HourlySource()})
    monkeypatch.setattr(prices_cli, "PAUSE_SECONDS", 0)
    monkeypatch.setattr(prices_cli, "load_watchlist",
                        lambda: [WatchItem("AAPL", "US", "stock", "Apple")])
    prices_cli.refresh("yahoo", ["60m"])
    prices_cli.refresh("yahoo", ["60m"])
    assert starts == [None, pd.Timestamp("2026-11-03 15:30", tz="UTC")]
    assert not list(tmp_path.rglob("*.tmp"))  # writes go through a temp file, then rename


class OneMarketSource:
    """Like Futu: serves HK stocks only; the quota runs out after ``quota`` symbols."""
    MARKET = "HK"
    ELIGIBLE_KINDS = ("stock", "index_fund", "holding")

    def __init__(self, quota=99):
        self.asked, self.quota = [], quota

    def fetch(self, symbol, interval, start, end):
        from stock_advisor.price_sources.futu import QuotaExhausted

        if len(self.asked) >= self.quota:
            raise QuotaExhausted("used up")
        self.asked.append(symbol)
        if symbol == "0002.HK":
            raise RuntimeError("boom")
        idx = pd.to_datetime(["2005-03-03"])
        raw = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 10}, index=idx)
        return raw, raw


def _one_market(monkeypatch, tmp_path, source):
    monkeypatch.setattr(price_store, "STORE_ROOT", tmp_path)
    monkeypatch.setattr(prices_cli, "SOURCES", {"futu": source})
    monkeypatch.setattr(prices_cli, "PAUSE_SECONDS", 0)
    items = [WatchItem("0700.HK", "HK", "stock", "Tencent"), WatchItem("AAPL", "US", "stock", "Apple"),
             WatchItem("^HSI", "HK", "index", "Hang Seng"), WatchItem("2800.HK", "HK", "index_fund", "Tracker"),
             WatchItem("0002.HK", "HK", "holding", "0002.HK")]
    monkeypatch.setattr(prices_cli, "load_watchlist", lambda: items)


def test_unserved_symbols_skipped_holdings_first_and_holding_names_not_logged(monkeypatch, tmp_path, caplog):
    source = OneMarketSource()
    _one_market(monkeypatch, tmp_path, source)
    assert prices_cli.refresh("futu", ["1d"]) == (2, 1, 2)  # AAPL and the index are skipped, not failed
    assert source.asked == ["0002.HK", "2800.HK", "0700.HK"]
    assert "0002.HK" not in caplog.text and "a holding 1d failed" in caplog.text


def test_quota_exhausted_stops_the_walk(monkeypatch, tmp_path, caplog):
    source = OneMarketSource(quota=1)
    _one_market(monkeypatch, tmp_path, source)
    assert prices_cli.refresh("futu", ["1d", "60m"]) == (0, 6, 0)  # 1 failed + 5 waiting
    assert len(source.asked) == 1 and "5 symbol fetches wait" in caplog.text
