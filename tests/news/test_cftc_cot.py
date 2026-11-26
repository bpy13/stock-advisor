"""Tests for the CFTC Commitments of Traders adapter, on synthetic rows. No network."""

from stock_advisor.news.sources import cftc_cot as cot
from stock_advisor.news.store import NewsStore


def rec(code="13874A", day="2026-11-17", oi="100", **over):
    row = {
        "cftc_contract_market_code": code,
        "report_date_as_yyyy_mm_dd": f"{day}T00:00:00.000",
        "open_interest_all": oi,
        "noncomm_positions_long_all": "40",
        "noncomm_positions_short_all": "30",
        "comm_positions_long_all": "20",
        "comm_positions_short_all": "50",
    }
    row.update(over)
    return row


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


class FakeSession:
    """Returns the rows whose date is after the `since` in the query, in pages."""

    def __init__(self, rows):
        self.rows = rows
        self.params = []

    def get(self, url, params=None, **kwargs):
        self.params.append(params)
        where = params["$where"]
        since = where.split("> '")[1].split("T")[0] if "> '" in where else ""
        rows = [r for r in self.rows if r["report_date_as_yyyy_mm_dd"][:10] > since]
        offset = int(params.get("$offset", 0))
        return FakeResponse(rows[offset : offset + int(params["$limit"])])


def test_parse_rows_maps_contract_to_watchlist_symbol_and_skips_bad_rows():
    rows = cot.parse_rows([rec(), rec(code="067651", oi="5"), rec(code="999999"), rec(oi="x")])
    assert rows == [
        ("13874A", "2026-11-17", "^GSPC", 100.0, 40.0, 30.0, 20.0, 50.0),
        ("067651", "2026-11-17", "CL=F", 5.0, 40.0, 30.0, 20.0, 50.0),
    ]


def test_fetch_stores_history_then_only_new_weeks(tmp_path):
    store = NewsStore(tmp_path / "n.db")
    data = [rec(day="2026-11-03"), rec(day="2026-11-10"), rec(code="209742", day="2026-11-10")]
    assert cot.fetch_cot(store, FakeSession(data)) == 3
    assert [r["date"] for r in store.query_cot("^GSPC")] == ["2026-11-03", "2026-11-10"]

    later = data + [rec(day="2026-11-17")]
    session = FakeSession(later)
    assert cot.fetch_cot(store, session) == 1
    assert "2026-11-10" in session.params[0]["$where"]  # asked only for newer weeks
    assert cot.fetch_cot(store, FakeSession(later)) == 0
    assert store.query_cot("^GSPC")[-1]["net_noncomm"] == 10.0


def test_fetch_pages_through_a_long_history(tmp_path, monkeypatch):
    monkeypatch.setattr(cot, "PAGE", 2)
    store = NewsStore(tmp_path / "n.db")
    data = [rec(day=f"2026-10-{d:02d}") for d in range(1, 6)]
    assert cot.fetch_cot(store, FakeSession(data)) == 5
