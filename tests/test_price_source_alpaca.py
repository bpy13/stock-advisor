import json
from pathlib import Path

import pandas as pd
import pytest

from stock_advisor.price_sources import alpaca

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "alpaca_bars.json").read_text())


class Resp:
    def __init__(self, status=200, body=None, text=""):
        self.status_code, self._body, self.text = status, body or {}, text

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_API_SECRET", "s")
    monkeypatch.setitem(alpaca._state, "feed", "sip")
    monkeypatch.setattr(alpaca, "_eligible_symbols", lambda: frozenset({"AAPL"}))


def _serve(monkeypatch, responder):
    calls = []

    def get(url, params, headers, timeout):
        calls.append((params, headers))
        return responder(params)

    monkeypatch.setattr(alpaca.requests, "get", get)
    return calls


def test_daily_raw_and_adjusted_calls(monkeypatch):
    calls = _serve(monkeypatch, lambda p: Resp(body=FIXTURE))
    raw, adj = alpaca.fetch("AAPL", "1d")
    assert [c[0]["adjustment"] for c in calls] == ["raw", "all"]
    assert calls[0][1]["APCA-API-KEY-ID"] == "k"
    assert list(raw.index.strftime("%Y-%m-%d")) == ["2025-03-03", "2025-03-04"]
    assert list(raw["close"]) == [10.5, 11.0] and list(adj["volume"]) == [100, 200]


def test_paging(monkeypatch):
    def responder(p):
        if "page_token" not in p:
            return Resp(body={"bars": {"AAPL": [FIXTURE["bars"]["AAPL"][0]]}, "next_page_token": "T"})
        assert p["page_token"] == "T"
        return Resp(body={"bars": {"AAPL": [FIXTURE["bars"]["AAPL"][1]]}, "next_page_token": None})

    _serve(monkeypatch, responder)
    raw, _ = alpaca.fetch("AAPL", "1d")
    assert len(raw) == 2


def test_feed_fallback_remembered(monkeypatch):
    def responder(p):
        if p["feed"] == "sip":
            return Resp(403, text="subscription does not permit querying recent SIP data")
        return Resp(body=FIXTURE)

    calls = _serve(monkeypatch, responder)
    alpaca.fetch("AAPL", "1d")
    assert [c[0]["feed"] for c in calls][:2] == ["sip", "iex"]
    assert all(c[0]["feed"] == "iex" for c in calls[1:])
    assert alpaca._state["feed"] == "iex"


def test_hourly_built_from_half_hours(monkeypatch):
    t = lambda hhmm: f"2025-03-03T{hhmm}:00Z"  # noqa: E731  (09:30 ET = 14:30 UTC in early March)
    bars = [
        {"t": t("14:30"), "o": 1, "h": 3, "l": 0.5, "c": 2, "v": 10},
        {"t": t("15:00"), "o": 2, "h": 4, "l": 1.5, "c": 3, "v": 20},
        {"t": t("15:30"), "o": 3, "h": 3.5, "l": 2, "c": 2.5, "v": 5},
        {"t": t("21:00"), "o": 9, "h": 9, "l": 9, "c": 9, "v": 1},  # 16:00 ET, after close
        {"t": t("13:00"), "o": 8, "h": 8, "l": 8, "c": 8, "v": 1},  # pre-market
    ]
    _serve(monkeypatch, lambda p: Resp(body={"bars": {"AAPL": bars}}))
    raw, adj = alpaca.fetch("AAPL", "60m")
    assert adj is None
    first = pd.Timestamp("2025-03-03 14:30", tz="UTC")
    assert list(raw.index) == [first, pd.Timestamp("2025-03-03 15:30", tz="UTC")]
    row = raw.loc[first]
    assert (row["open"], row["high"], row["low"], row["close"], row["volume"]) == (1, 4, 0.5, 3, 30)
    assert raw.iloc[1]["close"] == 2.5


def test_missing_key_names_both_variables(monkeypatch):
    monkeypatch.setattr(alpaca, "get_setting", lambda name: "")  # ignore any real .env
    with pytest.raises(RuntimeError, match="ALPACA_API_KEY.*ALPACA_API_SECRET"):
        alpaca.fetch("AAPL", "1d")


def test_keys_come_from_get_setting(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY")
    monkeypatch.setattr(alpaca, "get_setting", lambda name: "from-dotenv")
    assert alpaca._headers()["APCA-API-KEY-ID"] == "from-dotenv"


def test_share_class_symbol_uses_dot():
    assert alpaca._api_symbol("BRK-B") == "BRK.B"


def test_skips_non_us_and_other_kinds(monkeypatch):
    calls = _serve(monkeypatch, lambda p: Resp(body=FIXTURE))
    assert alpaca.fetch("0005.HK", "1d")[0].empty
    assert alpaca.fetch("MSFT", "1d")[0].empty  # not an eligible watchlist kind
    assert calls == []
