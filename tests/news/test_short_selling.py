"""Tests for the SFC short-position adapter, on saved files. No network."""

from datetime import date
from pathlib import Path

from stock_advisor.news.sources import short_selling as ss
from stock_advisor.news.store import NewsStore

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "news" / "short_selling"


def read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeResponse:
    def __init__(self, text):
        self.text = text
        self.content = text.encode("utf-8")


class FakeSession:
    """Serves the listing page and the saved CSVs by the date in the URL."""

    def __init__(self, fail_day=None):
        self.requested = []
        self.fail_day = fail_day

    def get(self, url, **kwargs):
        self.requested.append(url)
        if url == ss.LISTING_URL:
            return FakeResponse(read("listing.html"))
        stamp = url.split("Data_")[1][:8]
        if stamp == self.fail_day:
            raise RuntimeError("HTTP 500")
        return FakeResponse(read(f"sfc_{stamp}.csv"))


def test_parse_listing_finds_csvs_only():
    files = ss.parse_listing(read("listing.html"))
    assert sorted(files) == [date(2012, 9, 7), date(2025, 12, 24), date(2026, 11, 6)]
    assert files[date(2026, 11, 6)].endswith("?rev=d3d83e3d4ec44d1d8753f1893ba9c346")


def test_parse_csv_maps_codes_and_filters_symbols():
    rows = ss.parse_csv(read("sfc_20261106.csv"), {"0005.HK", "9988.HK"})
    assert rows == [
        ("0005.HK", "2026-11-06", "sfc_short", 76008597.0, 10451182088.0, None),
        ("9988.HK", "2026-11-06", "sfc_short", 164360116.0, 17241376168.0, None),
    ]


def test_parse_csv_skips_bad_rows():
    text = "Date,Stock Code,Stock Name,Aggregated Reportable Short Positions (Shares),Aggregated Reportable Short Positions (HK$)\n" \
           "06/11/2026,abc,X,1,2\n06/11/2026,5,HSBC,10,20\n"
    assert [r[0] for r in ss.parse_csv(text)] == ["0005.HK"]


def test_fetch_loads_every_week_including_a_late_wednesday_file(tmp_path):
    with NewsStore(tmp_path / "n.db") as store:
        added = ss.fetch_sfc(store, ["0005.HK", "0700.HK", "AAPL"], session=FakeSession())
        assert added == 6  # 2 stocks x 3 files; the US symbol is ignored
        days = [r["date"] for r in store.query_short_selling("0005.HK")]
        assert days == ["2012-09-07", "2025-12-24", "2026-11-06"]  # 2025-12-24 is a Wednesday


def test_fetch_is_resumable_and_adds_no_duplicates(tmp_path):
    with NewsStore(tmp_path / "n.db") as store:
        first = FakeSession(fail_day="20251224")
        assert ss.fetch_sfc(store, ["0005.HK"], session=first) == 2  # the failed week waits
        second = FakeSession()
        assert ss.fetch_sfc(store, ["0005.HK"], session=second) == 1
        assert len(second.requested) == 2  # listing + only the missing file
        assert ss.fetch_sfc(store, ["0005.HK"], session=FakeSession()) == 0


def test_fetch_since_skips_older_files(tmp_path):
    with NewsStore(tmp_path / "n.db") as store:
        assert ss.fetch_sfc(store, ["0005.HK"], session=FakeSession(), since=date(2026, 1, 1)) == 1
