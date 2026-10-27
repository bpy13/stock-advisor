"""Tests for the SEC EDGAR adapter. They parse saved responses and never touch the network."""

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from stock_advisor.news.sources import NewsSource, edgar
from stock_advisor.news.sources.edgar import EdgarSource

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "news" / "edgar"
UTC = timezone.utc
FAKE_EMAIL = "test@example.com"


def read_bytes(name):
    return (FIXTURES / name).read_bytes()


def read_text(name):
    return (FIXTURES / name).read_bytes().decode("latin-1")


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def json(self):
        return json.loads(self.content)

    def iter_lines(self):
        return iter(self.content.splitlines())

    def close(self):
        pass


class FakeHttp:
    """Stands in for PoliteSession: maps url substrings to saved bytes and counts calls."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        for part, content in self.routes:
            if part in url:
                return FakeResponse(content)
        raise RuntimeError(f"404 for {url}")


def aapl_source(routes, **kwargs):
    http = FakeHttp([("company_tickers.json", read_bytes("company_tickers.json"))] + routes)
    return EdgarSource(session=http, email=FAKE_EMAIL, **kwargs), http


def test_conforms_to_protocol():
    assert isinstance(EdgarSource(email=FAKE_EMAIL), NewsSource)


def test_parse_feed_extracts_items_and_utc_time():
    items = edgar.parse_feed(read_bytes("latest_8k.atom"), {1526243: ["PPTA"]})
    assert len(items) == 7
    first = items[0]
    assert first.title == (
        "PERPETUA RESOURCES CORP.: 8-K Unregistered Sales of Equity Securities; Other Events"
    )
    assert first.summary == "Items: 3.02, 8.01"
    assert first.published_at == datetime(2026, 10, 26, 21, 30, 28, tzinfo=UTC)  # 17:30 -04:00
    assert first.url.endswith("0001104659-26-118875-index.htm")
    assert first.symbols == ["PPTA"]
    assert all(i.source == "edgar" for i in items)
    assert len({i.id for i in items}) == 7


def test_parse_index_keeps_only_plain_8k():
    rows = list(edgar.parse_index(read_text("form_2024q3.idx").splitlines()))
    assert (("Apple Inc.", 320193, date(2024, 8, 1), "0000320193-24-000080")) in rows
    assert len([r for r in rows if r[1] == 320193]) == 4  # the 10-Q row is dropped
    assert any(r[0] == "1 800 FLOWERS COM INC" for r in rows)


def test_parse_index_handles_daily_date_format():
    rows = list(edgar.parse_index(read_text("form_daily_20260915.idx").splitlines()))
    assert len(rows) == 3
    assert rows[0][0] == "5E Advanced Materials, Inc."
    assert rows[0][2] == date(2026, 9, 15)


def test_parse_header_converts_eastern_to_utc_and_lists_items():
    accepted, names = edgar.parse_header(read_text("header_aapl_2024.txt"))
    assert accepted == datetime(2024, 8, 1, 20, 30, 26, tzinfo=UTC)  # 16:30:26 EDT
    assert names == ["Results of Operations and Financial Condition",
                     "Financial Statements and Exhibits"]
    assert [edgar.item_number(n) for n in names] == ["2.02", "9.01"]


def test_parse_header_without_acceptance_time():
    accepted, names = edgar.parse_header(read_text("header_1996.txt"))
    assert accepted is None
    assert names == ["Other events", "Financial statements and exhibits"]


def test_winter_acceptance_uses_standard_time():
    accepted, _ = edgar.parse_header("<ACCEPTANCE-DATETIME>20240102090000\n</SEC-HEADER>")
    assert accepted == datetime(2024, 1, 2, 14, 0, tzinfo=UTC)


def test_allowlist_maps_tickers_to_ciks():
    source, http = aapl_source([])
    allow = source.allowlist()
    assert allow[320193] == ["AAPL"]
    assert allow[1652044] == ["GOOGL"]
    assert "BRK-B" not in allow.values()
    assert len(http.calls) == 1
    source.allowlist()
    assert len(http.calls) == 1  # cached


def test_fetch_range_quarterly_filters_by_cik_and_reads_headers():
    source, http = aapl_source([
        ("full-index/2024/QTR3/form.idx", read_bytes("form_2024q3.idx")),
        ("0000320193-24-000080.txt", read_bytes("header_aapl_2024.txt")),
        (".txt", b"no header here"),
    ])
    items = list(source.fetch_range(datetime(2024, 7, 1, tzinfo=UTC),
                                    datetime(2024, 9, 30, tzinfo=UTC)))
    assert len(items) == 4
    assert items[0].published_at.date() == date(2024, 8, 1)
    results = items[0]
    assert results.title == ("Apple Inc.: 8-K Results of Operations and Financial Condition; "
                             "Financial Statements and Exhibits")
    assert results.summary == "Items: 2.02, 9.01"
    assert results.symbols == ["AAPL"]
    assert results.published_at == datetime(2024, 8, 1, 20, 30, 26, tzinfo=UTC)
    assert results.url == ("https://www.sec.gov/Archives/edgar/data/320193/"
                           "000032019324000080/0000320193-24-000080-index.htm")
    assert items[1].published_at == datetime(2024, 8, 23, tzinfo=UTC)  # header lacked a time
    assert items[1].title == "Apple Inc.: 8-K"
    assert results.time_precision == "exact"
    assert items[1].time_precision == "day"  # no acceptance time in the header
    # 1 tickers file + 1 index + 4 headers; the other companies' rows cost nothing.
    assert len(http.calls) == 6


def test_old_filing_uses_filing_date_and_no_item_numbers():
    row = "8-K    3-D GEOPHYSICAL INC    1003382     1996-06-19  edgar/data/1003382/0000922423-96-000276.txt\n"
    source, _ = aapl_source(
        [("full-index/1996/QTR2", row.encode()), (".txt", read_bytes("header_1996.txt"))],
        tickers=[], ciks=[1003382],
    )
    [item] = list(source.fetch_range(datetime(1996, 4, 1, tzinfo=UTC),
                                     datetime(1996, 6, 30, tzinfo=UTC)))
    assert item.published_at == datetime(1996, 6, 19, tzinfo=UTC)
    assert item.title == "3-D GEOPHYSICAL INC: 8-K Other events; Financial statements and exhibits"
    assert item.summary == ""


def test_short_range_reads_daily_index_and_skips_weekends():
    source, http = aapl_source(
        [("daily-index/2026/QTR3/form.20260915.idx", read_bytes("form_daily_20260915.idx"))],
        tickers=[], ciks=[1888654],
    )
    items = list(source.fetch_range(datetime(2026, 9, 12, tzinfo=UTC),
                                    datetime(2026, 9, 16, tzinfo=UTC)))
    assert len(items) == 1
    assert items[0].title.startswith("5E Advanced Materials, Inc.: 8-K")
    urls = [c[0] for c in http.calls]
    assert not any("20260912" in u or "20260913" in u for u in urls)  # Saturday and Sunday
    assert any("form.20260914.idx" in u for u in urls)  # Monday: missing file is tolerated


def test_fetch_range_clamps_to_earliest_quarter():
    source, http = aapl_source([("full-index", b"")])
    list(source.fetch_range(datetime(1980, 1, 1, tzinfo=UTC), datetime(1994, 3, 31, tzinfo=UTC)))
    assert any("full-index/1994/QTR1/" in c[0] for c in http.calls)
    assert not any("1980" in c[0] for c in http.calls)


def test_fetch_recent_keeps_only_allowlisted_by_default():
    routes = [("browse-edgar", read_bytes("latest_8k.atom"))]
    source, _ = aapl_source(routes)  # allowlist: the default megacaps, none in the fixture
    assert source.fetch_recent() == []
    # A holding passed in as a CIK (Perpetua Resources) lets its filing through.
    source, _ = aapl_source(routes, ciks=[1526243])
    items = source.fetch_recent()
    assert [i.title.split(":")[0] for i in items] == ["PERPETUA RESOURCES CORP."]
    assert all(i.time_precision == "exact" for i in items)  # the feed carries a time
    source, _ = aapl_source(routes, live_allowlist_only=False)
    assert len(source.fetch_recent()) == 7


def test_missing_email_warns_once_and_returns_nothing(caplog):
    source = EdgarSource(email="")
    with caplog.at_level(logging.WARNING):
        assert source.fetch_recent() == []
        assert list(source.fetch_range(datetime(2024, 1, 1, tzinfo=UTC),
                                       datetime(2024, 3, 1, tzinfo=UTC))) == []
    warnings = [r for r in caplog.records if "SEC_CONTACT_EMAIL" in r.message]
    assert len(warnings) == 1


def test_session_user_agent_and_delay(monkeypatch):
    source = EdgarSource(email=FAKE_EMAIL)
    http = source._session()
    assert http._session.headers["User-Agent"] == f"stock_advisor {FAKE_EMAIL}"
    assert http.min_delay == pytest.approx(0.15)
