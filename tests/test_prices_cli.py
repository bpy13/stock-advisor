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
