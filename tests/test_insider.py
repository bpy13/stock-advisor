"""Tests for the Form 4 insider-trade adapter. Saved XML and a synthetic zip; no network."""

import zipfile
from datetime import date
from pathlib import Path

import pytest

from stock_advisor.news.sources import insider
from stock_advisor.news.sources.insider import InsiderTrades, parse_dataset_zip, parse_form4

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "news" / "insider"


def xml(name):
    return (FIXTURES / name).read_bytes()


def test_purchase():
    (t,) = parse_form4(xml("form4_purchase.xml"), "0001-24-000001", date(2024, 5, 3))
    assert (t.symbol, t.code, t.acquired_disposed) == ("AAPL", "P", "A")
    assert (t.shares, t.price, t.value) == (1000, 170.5, 170500.0)
    assert t.filer == "COOK TIMOTHY D"
    assert t.role == "Officer: Chief Executive Officer; Director"
    assert t.trade_date == date(2024, 5, 1)
    assert t.plan_10b5_1 is None  # the form carried no flag


def test_sale_with_10b5_1_flag():
    (t,) = parse_form4(xml("form4_sale.xml"), "0001-24-000002", date(2024, 5, 3))
    assert (t.code, t.acquired_disposed, t.plan_10b5_1) == ("S", "D", True)
    assert t.value == 860000.0


def test_option_exercise_keeps_every_line():
    trades = parse_form4(xml("form4_option_exercise.xml"), "0001-24-000003", date(2024, 5, 6))
    assert [(t.line_no, t.code) for t in trades] == [(1, "M"), (2, "F")]


def test_other_form_type_is_ignored():
    text = xml("form4_purchase.xml").replace(b"<documentType>4<", b"<documentType>3<")
    assert parse_form4(text, "x", date(2024, 5, 3)) == []


def test_amendment_replaces_original_in_either_load_order(tmp_path):
    original = parse_form4(xml("form4_sale.xml"), "0001-24-000002", date(2024, 5, 3))
    amended = parse_form4(xml("form4a_amendment.xml"), "0001-24-000009", date(2024, 5, 6))
    assert amended[0].is_amendment and amended[0].orig_filed_date == date(2024, 5, 3)
    for order in ((original, amended), (amended, original)):
        with InsiderTrades(tmp_path / f"{id(order)}.db") as table:
            for batch in order:
                table.add(batch)
            live = table.trades("AAPL")
            assert [(r["accession"], r["shares"]) for r in live] == [("0001-24-000009", 4500.0)]


def test_rerun_adds_nothing(tmp_path):
    trades = parse_form4(xml("form4_option_exercise.xml"), "0001-24-000003", date(2024, 5, 6))
    with InsiderTrades(tmp_path / "n.db") as table:
        assert table.add(trades) == 2
        assert table.add(trades) == 0
        assert table.rows_per_year() == {"2024": 2}


def _write_zip(path):
    header = "\t".join
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("SUBMISSION.tsv", "\n".join([
            header(["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERTRADINGSYMBOL",
                    "DATE_OF_ORIG_SUB", "AFF10B5ONE"]),
            header(["A1", "03-MAY-2024", "4", "AAPL", "", "1"]),
            header(["A2", "03-MAY-2024", "4", "ZZZZ", "", ""]),  # not on the watchlist
            header(["A3", "06-MAY-2024", "3", "AAPL", "", ""]),  # not a Form 4
            header(["A4", "07-MAY-2024", "4", "BRK.B", "", ""]),
        ]))
        zf.writestr("REPORTINGOWNER.tsv", "\n".join([
            header(["ACCESSION_NUMBER", "RPTOWNERNAME", "RPTOWNER_RELATIONSHIP", "RPTOWNER_TITLE"]),
            header(["A1", "DOE JANE", "Director,Officer", "CFO"]),
            header(["A4", "ROE RICH", "TenPercentOwner", ""]),
        ]))
        zf.writestr("NONDERIV_TRANS.tsv", "\n".join([
            header(["ACCESSION_NUMBER", "NONDERIV_TRANS_SK", "TRANS_DATE", "TRANS_CODE", "TRANS_SHARES",
                    "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD"]),
            header(["A1", "11", "01-MAY-2024", "S", "100", "10.5", "D"]),
            header(["A2", "12", "01-MAY-2024", "P", "1", "1", "A"]),
            header(["A3", "13", "01-MAY-2024", "P", "1", "1", "A"]),
            header(["A4", "14", "02-MAY-2024", "P", "50", "", "A"]),
        ]))


def test_dataset_zip_filters_to_watchlist_and_reads_fields(tmp_path):
    path = tmp_path / "2024q2_form345.zip"
    _write_zip(path)
    trades = list(parse_dataset_zip(path, ["AAPL", "BRK-B"]))
    assert [t.symbol for t in trades] == ["AAPL", "BRK-B"]  # BRK.B matched BRK-B; ZZZZ, Form 3 gone
    first, second = trades
    assert (first.role, first.filer, first.plan_10b5_1) == ("Officer: CFO; Director", "DOE JANE", True)
    assert (first.value, first.filed_date, first.trade_date) == (1050.0, date(2024, 5, 3), date(2024, 5, 1))
    assert second.role == "10% owner" and second.price is None and second.value is None


class _Resp:
    def __init__(self, content=b""):
        self.content = content

    def iter_lines(self):
        return iter(self.content.splitlines())

    def close(self):
        pass


class _Http:
    def __init__(self, index, filings):
        self.index, self.filings, self.urls = index, filings, []

    def get(self, url, **kwargs):
        self.urls.append(url)
        if "daily-index" in url:
            return _Resp(self.index)
        return _Resp(self.filings[url.rsplit("/", 1)[-1]])


def test_live_day_fetches_allowlisted_issuers_once_and_adds_no_duplicate(tmp_path):
    index = (
        b"Form Type  Company Name  CIK  Date Filed  File Name\n"
        b"4          APPLE INC                 320193   20240503   edgar/data/320193/0001-24-000001.txt\n"
        b"4          COOK TIMOTHY D           1214156   20240503   edgar/data/1214156/0001-24-000001.txt\n"
        b"4          SOME OTHER CO            999999   20240503   edgar/data/999999/0001-24-000007.txt\n"
        b"8-K        APPLE INC                 320193   20240503   edgar/data/320193/0001-24-000008.txt\n"
    )
    submission = b"<SEC-DOCUMENT>\n<XML>\n" + xml("form4_purchase.xml") + b"\n</XML>\n</SEC-DOCUMENT>"
    http = _Http(index, {"0001-24-000001.txt": submission})
    day = date(2024, 5, 3)
    with InsiderTrades(tmp_path / "live.db") as table:
        assert table.add(insider.fetch_day(http, day, {320193: ["AAPL"]})) == 1
        assert table.add(insider.fetch_day(http, day, {320193: ["AAPL"]})) == 0
    filing_urls = [u for u in http.urls if "daily-index" not in u]
    assert filing_urls == [insider.ARCHIVES + "edgar/data/320193/0001-24-000001.txt"] * 2  # once per run


def test_weekend_makes_no_request():
    http = _Http(b"", {})
    assert list(insider.fetch_day(http, date(2024, 5, 4), {1: ["X"]})) == []
    assert http.urls == []


@pytest.mark.parametrize("raw,key", [("BRK.B", "BRKB"), ("brk-b", "BRKB"), ("AAPL", "AAPL")])
def test_ticker_key(raw, key):
    assert insider.ticker_key(raw) == key
