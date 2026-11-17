"""US insider trades (SEC Form 4) for the US watchlist, stored in the table `insider_trades`.

Two ways in, both from sec.gov and both under the SEC's fair-access rules (see `edgar.py`):
- History: the SEC "Insider Transactions Data Sets", one zip per quarter from 2006 Q1
  (https://www.sec.gov/dera/data/insider-transactions-data-sets). `parse_dataset_zip` reads
  SUBMISSION.tsv, REPORTINGOWNER.tsv and NONDERIV_TRANS.tsv. The sets carry the 10b5-1 flag
  (column AFF10B5ONE) only for filings from April 2023; older rows get `None` (unknown).
- Live: EDGAR's daily form index lists the day's Form 4 and 4/A filings. `fetch_day` fetches
  each allowlisted issuer's filing text and parses its XML (`parse_form4`).

One row per non-derivative transaction line (an option exercise shows as code "M" there).
Derivative-table lines are not stored. `value` is shares * price (None when no price).

An amended filing (4/A) replaces its original: `apply_amendments` marks the original's rows
`superseded_by` the amendment's accession. Nothing is deleted, and the result does not depend
on which of the two was loaded first. Readers use `WHERE superseded_by IS NULL`.
The match is the same issuer symbol, same filer and the original filing date the amendment
names (`orig_filed_date`).
"""

from __future__ import annotations

import csv
import io
import logging
import re
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Union

from stock_advisor.news.sources import PoliteSession
from stock_advisor.news.sources.edgar import _INDEX_LINE, ARCHIVES, DAILY_INDEX_URL

logger = logging.getLogger(__name__)

DATASET_URL = ("https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/"
               "{year}q{quarter}_form345.zip")
FIRST_YEAR = 2006
FORMS = ("4", "4/A")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS insider_trades (
    symbol TEXT NOT NULL,
    filer TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    trade_date TEXT NOT NULL,
    filed_date TEXT NOT NULL,
    code TEXT NOT NULL,
    acquired_disposed TEXT NOT NULL DEFAULT '',
    shares REAL,
    price REAL,
    value REAL,
    plan_10b5_1 INTEGER,
    accession TEXT NOT NULL,
    line_no INTEGER NOT NULL,
    is_amendment INTEGER NOT NULL DEFAULT 0,
    orig_filed_date TEXT,
    superseded_by TEXT,
    UNIQUE (accession, line_no)
);
CREATE INDEX IF NOT EXISTS idx_insider_symbol_date ON insider_trades (symbol, trade_date);
"""


@dataclass(frozen=True)
class InsiderTrade:
    symbol: str
    filer: str
    role: str
    trade_date: date
    filed_date: date
    code: str
    acquired_disposed: str
    shares: Optional[float]
    price: Optional[float]
    plan_10b5_1: Optional[bool]
    accession: str
    line_no: int
    is_amendment: bool = False
    orig_filed_date: Optional[date] = None

    @property
    def value(self) -> Optional[float]:
        if self.shares is None or self.price is None:
            return None
        return round(self.shares * self.price, 2)


def ticker_key(symbol: str) -> str:
    """Comparison form of a ticker: BRK.B, BRK-B and brkb all match."""
    return re.sub(r"[^A-Z0-9]", "", symbol.upper())


def _num(text: Optional[str]) -> Optional[float]:
    try:
        return float(text) if text not in (None, "") else None
    except ValueError:
        return None


def _day(text: Optional[str]) -> Optional[date]:
    text = (text or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text[:11] if fmt == "%d-%b-%Y" else text[:10], fmt).date()
        except ValueError:
            continue
    return None


def _flag(text: Optional[str]) -> Optional[bool]:
    text = (text or "").strip().lower()
    if text in ("1", "true", "y"):
        return True
    if text in ("0", "false", "n"):
        return False
    return None


def _role(is_director: bool, is_officer: bool, title: str, is_ten_pct: bool, is_other: bool) -> str:
    parts = []
    if is_officer:
        parts.append(f"Officer: {title}" if title else "Officer")
    if is_director:
        parts.append("Director")
    if is_ten_pct:
        parts.append("10% owner")
    if is_other and not parts:
        parts.append("Other")
    return "; ".join(parts)


# -- one Form 4 document ---------------------------------------------------------------


def _text(node: Optional[ET.Element], path: str) -> str:
    found = node.find(path) if node is not None else None
    return (found.text or "").strip() if found is not None else ""


def parse_form4(xml: Union[str, bytes], accession: str, filed: date) -> List[InsiderTrade]:
    """Trades of one Form 4 / 4/A ownershipDocument. Other form types give an empty list."""
    root = ET.fromstring(xml)
    doc_type = _text(root, "documentType")
    if doc_type not in FORMS:
        return []
    symbol = _text(root, "issuer/issuerTradingSymbol").upper()
    owners = root.findall("reportingOwner")
    filer = "; ".join(_text(o, "reportingOwnerId/rptOwnerName") for o in owners)
    first = owners[0] if owners else None
    rel = first.find("reportingOwnerRelationship") if first is not None else None
    role = _role(
        _flag(_text(rel, "isDirector")) or False,
        _flag(_text(rel, "isOfficer")) or False,
        _text(rel, "officerTitle"),
        _flag(_text(rel, "isTenPercentOwner")) or False,
        _flag(_text(rel, "isOther")) or False,
    )
    plan = _flag(_text(root, "aff10b5One"))
    amended = doc_type == "4/A"
    original = _day(_text(root, "dateOfOriginalSubmission")) if amended else None
    trades: List[InsiderTrade] = []
    for n, row in enumerate(root.findall("nonDerivativeTable/nonDerivativeTransaction"), start=1):
        traded = _day(_text(row, "transactionDate/value"))
        code = _text(row, "transactionCoding/transactionCode")
        if not symbol or traded is None or not code:
            continue
        trades.append(InsiderTrade(
            symbol=symbol, filer=filer, role=role, trade_date=traded, filed_date=filed,
            code=code,
            acquired_disposed=_text(row, "transactionAmounts/transactionAcquiredDisposedCode/value"),
            shares=_num(_text(row, "transactionAmounts/transactionShares/value")),
            price=_num(_text(row, "transactionAmounts/transactionPricePerShare/value")),
            plan_10b5_1=plan, accession=accession, line_no=n,
            is_amendment=amended, orig_filed_date=original,
        ))
    return trades


def xml_from_submission(text: str) -> Optional[str]:
    """The ownershipDocument inside a full-submission .txt file, or None."""
    found = re.search(r"<ownershipDocument>.*?</ownershipDocument>", text, re.S)
    return found.group(0) if found else None


# -- the quarterly data sets (history) ---------------------------------------------------


def _tsv(zf: zipfile.ZipFile, name: str) -> Iterator[Dict[str, str]]:
    with zf.open(name) as raw:
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline=""),
                                  delimiter="\t")


def parse_dataset_zip(path: Union[str, Path], symbols: Iterable[str]) -> Iterator[InsiderTrade]:
    """Trades of the allowlisted `symbols` (compared by `ticker_key`) in one quarterly zip."""
    wanted = {ticker_key(s): s for s in symbols}
    with zipfile.ZipFile(path) as zf:
        subs = {}
        for row in _tsv(zf, "SUBMISSION.tsv"):
            if row["DOCUMENT_TYPE"] not in FORMS:
                continue
            symbol = wanted.get(ticker_key(row.get("ISSUERTRADINGSYMBOL", "")))
            filed = _day(row["FILING_DATE"])
            if symbol and filed:
                subs[row["ACCESSION_NUMBER"]] = (symbol, filed, row["DOCUMENT_TYPE"] == "4/A",
                                                 _day(row.get("DATE_OF_ORIG_SUB")),
                                                 _flag(row.get("AFF10B5ONE")))
        owners: Dict[str, List[Dict[str, str]]] = {}
        for row in _tsv(zf, "REPORTINGOWNER.tsv"):
            if row["ACCESSION_NUMBER"] in subs:
                owners.setdefault(row["ACCESSION_NUMBER"], []).append(row)
        for row in _tsv(zf, "NONDERIV_TRANS.tsv"):
            accession = row["ACCESSION_NUMBER"]
            if accession not in subs:
                continue
            symbol, filed, amended, original, plan = subs[accession]
            traded = _day(row.get("TRANS_DATE"))
            code = (row.get("TRANS_CODE") or "").strip()
            if traded is None or not code:
                continue
            who = owners.get(accession, [])
            relation = (who[0].get("RPTOWNER_RELATIONSHIP", "") if who else "").lower()
            title = who[0].get("RPTOWNER_TITLE", "").strip() if who else ""
            yield InsiderTrade(
                symbol=symbol, filer="; ".join(o["RPTOWNERNAME"].strip() for o in who),
                role=_role("director" in relation, "officer" in relation, title,
                           "tenpercentowner" in relation.replace(" ", ""), "other" in relation),
                trade_date=traded, filed_date=filed, code=code,
                acquired_disposed=(row.get("TRANS_ACQUIRED_DISP_CD") or "").strip(),
                shares=_num(row.get("TRANS_SHARES")), price=_num(row.get("TRANS_PRICEPERSHARE")),
                plan_10b5_1=plan, accession=accession,
                line_no=int(row.get("NONDERIV_TRANS_SK") or 0),
                is_amendment=amended, orig_filed_date=original,
            )


# -- the table -------------------------------------------------------------------------


class InsiderTrades:
    """The `insider_trades` table, in the news database file (its own connection; WAL, one
    writer at a time, waits up to 30 s like `NewsStore`)."""

    def __init__(self, path: Union[str, Path]) -> None:
        self._conn = sqlite3.connect(str(path), timeout=30)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "InsiderTrades":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def add(self, trades: Iterable[InsiderTrade]) -> int:
        """Insert trades not stored yet (same accession and line) and return how many were new."""
        rows = [(t.symbol, t.filer, t.role, t.trade_date.isoformat(), t.filed_date.isoformat(),
                 t.code, t.acquired_disposed, t.shares, t.price, t.value,
                 None if t.plan_10b5_1 is None else int(t.plan_10b5_1), t.accession, t.line_no,
                 int(t.is_amendment), t.orig_filed_date.isoformat() if t.orig_filed_date else None)
                for t in trades]
        with self._conn:
            before = self._conn.total_changes
            self._conn.executemany(
                "INSERT OR IGNORE INTO insider_trades (symbol, filer, role, trade_date, filed_date, "
                "code, acquired_disposed, shares, price, value, plan_10b5_1, accession, line_no, "
                "is_amendment, orig_filed_date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
            added = self._conn.total_changes - before
            self.apply_amendments()
        return added

    def apply_amendments(self) -> None:
        """Mark each original filing's rows as replaced by its amendment (idempotent)."""
        self._conn.execute(
            "UPDATE insider_trades SET superseded_by = ("
            " SELECT MIN(a.accession) FROM insider_trades a WHERE a.is_amendment = 1"
            " AND a.symbol = insider_trades.symbol AND a.filer = insider_trades.filer"
            " AND a.orig_filed_date = insider_trades.filed_date)"
            " WHERE is_amendment = 0 AND superseded_by IS NULL AND EXISTS ("
            " SELECT 1 FROM insider_trades a WHERE a.is_amendment = 1"
            " AND a.symbol = insider_trades.symbol AND a.filer = insider_trades.filer"
            " AND a.orig_filed_date = insider_trades.filed_date)")

    def rows_per_year(self) -> Dict[str, int]:
        """Live (not superseded) rows per trade year."""
        return {y: n for y, n in self._conn.execute(
            "SELECT substr(trade_date, 1, 4), COUNT(*) FROM insider_trades "
            "WHERE superseded_by IS NULL GROUP BY 1 ORDER BY 1")}

    def trades(self, symbol: str) -> List[sqlite3.Row]:
        self._conn.row_factory = sqlite3.Row
        return self._conn.execute(
            "SELECT * FROM insider_trades WHERE symbol = ? AND superseded_by IS NULL "
            "ORDER BY trade_date, accession, line_no", (symbol,)).fetchall()


# -- live (one day) ----------------------------------------------------------------------


def fetch_day(http: PoliteSession, day: date, allow: Dict[int, List[str]]) -> Iterator[InsiderTrade]:
    """Trades of the allowlisted issuers (`allow` maps CIK to tickers) filed on `day`.

    The daily index lists every Form 4 once per party (the owner and the issuer); only rows
    under an allowlisted issuer CIK are fetched, each filing once."""
    if day.weekday() >= 5:
        return
    url = DAILY_INDEX_URL.format(year=day.year, quarter=(day.month - 1) // 3 + 1, day=day)
    try:
        response = http.get(url, stream=True)
    except Exception as exc:  # holiday or not yet published
        logger.warning("insider index %s failed: %s", url, exc)
        return
    try:
        lines = [raw.decode("latin-1") for raw in response.iter_lines()]
    finally:
        response.close()
    seen = set()
    for line in lines:
        row = _INDEX_LINE.match(line)
        if row is None or row["form"] not in FORMS or int(row["cik"]) not in allow:
            continue
        accession = row["file"].rsplit("/", 1)[-1].removesuffix(".txt")
        if accession in seen:
            continue
        seen.add(accession)
        try:
            text = http.get(f"{ARCHIVES}{row['file']}").content.decode("latin-1")
            document = xml_from_submission(text)
            if document:
                yield from parse_form4(document, accession, day)
        except Exception as exc:  # one bad filing must not lose the day
            logger.warning("insider filing %s failed: %s", accession, exc)
