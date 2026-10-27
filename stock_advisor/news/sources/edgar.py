"""SEC EDGAR 8-K adapter: current-event filings of listed US companies.

Live: the "latest filings" Atom feed (`browse-edgar?action=getcurrent&type=8-K&output=atom`).
One request returns the newest ~100 8-Ks of all companies, each with its item numbers
("Item 2.02: Results of Operations ...") and an acceptance time with a UTC offset.

History: EDGAR form indexes, filtered to form type "8-K" and to a CIK allowlist, because
all companies together file roughly 70,000 8-Ks a year.
- Quarterly `full-index/<Y>/QTR<q>/form.idx` (about 40 MB for a modern quarter, streamed).
  The earliest quarter with real 8-K rows is 1994 QTR1 (1993 QTR4 holds a single row).
- Daily `daily-index/<Y>/QTR<q>/form.<YYYYMMDD>.idx` (about 1 MB), used for short ranges.
- Each allowlisted filing costs one more request: the first bytes of the filing's `.txt`
  hold the SGML header with `ACCEPTANCE-DATETIME` (Eastern time, 2000s onward) and the
  `ITEM INFORMATION` lines. Without an acceptance time the item gets the filing date at
  00:00 UTC, so treat it as day precision only.

Item numbers (1.05 cybersecurity incident, 2.02 results, 5.02 executive change) appear in the
item summary for filings from 2004-08-23, the day the current 8-K item numbering began.
Older headers carry only free-text item names; those go in the title.

Fair access (https://www.sec.gov/os/accessing-edgar-data): the User-Agent is
"stock_advisor <email>" with the email from `SEC_CONTACT_EMAIL`, and we keep 0.15 s between
requests (under 7 requests per second; the SEC limit is 10). With no email configured the
adapter logs one warning and returns nothing.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, Iterator, List, Optional, Tuple
from zoneinfo import ZoneInfo

import feedparser

from stock_advisor.news.models import NewsItem
from stock_advisor.news.settings import sec_contact_email
from stock_advisor.news.sources import PoliteSession

logger = logging.getLogger(__name__)

ATOM_URL = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcurrent&type=8-K&company=&dateb=&owner=include&start=0&count=100&output=atom"
)
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
ARCHIVES = "https://www.sec.gov/Archives/"
FULL_INDEX_URL = ARCHIVES + "edgar/full-index/{year}/QTR{quarter}/form.idx"
DAILY_INDEX_URL = ARCHIVES + "edgar/daily-index/{year}/QTR{quarter}/form.{day:%Y%m%d}.idx"
FILING_INDEX_URL = ARCHIVES + "edgar/data/{cik}/{nodash}/{acc}-index.htm"

EARLIEST_QUARTER = (1994, 1)  # first quarter whose form.idx lists many 8-Ks
DAILY_INDEX_MAX_DAYS = 14  # ranges up to this long read daily files, longer ones quarterly
HEADER_BYTES = 8192
NEW_ITEMS_START = date(2004, 8, 23)  # 8-K item numbers (1.01 ... 9.01) took effect
EASTERN = ZoneInfo("America/New_York")

DEFAULT_TICKERS = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM", "XOM", "UNH")

# Item names from the SEC's Form 8-K instructions, used to turn the free-text names in
# filing headers back into item numbers (matched on the first 20 characters, lower case).
ITEM_NAMES = {
    "1.01": "Entry into a Material Definitive Agreement",
    "1.02": "Termination of a Material Definitive Agreement",
    "1.03": "Bankruptcy or Receivership",
    "1.04": "Mine Safety - Reporting of Shutdowns and Patterns of Violations",
    "1.05": "Material Cybersecurity Incidents",
    "2.01": "Completion of Acquisition or Disposition of Assets",
    "2.02": "Results of Operations and Financial Condition",
    "2.03": "Creation of a Direct Financial Obligation or an Obligation under an Off-Balance Sheet Arrangement",
    "2.04": "Triggering Events That Accelerate or Increase a Direct Financial Obligation",
    "2.05": "Costs Associated with Exit or Disposal Activities",
    "2.06": "Material Impairments",
    "3.01": "Notice of Delisting or Failure to Satisfy a Continued Listing Rule or Standard",
    "3.02": "Unregistered Sales of Equity Securities",
    "3.03": "Material Modification to Rights of Security Holders",
    "4.01": "Changes in Registrant's Certifying Accountant",
    "4.02": "Non-Reliance on Previously Issued Financial Statements or a Related Audit Report",
    "5.01": "Changes in Control of Registrant",
    "5.02": "Departure of Directors or Certain Officers; Election of Directors; Appointment of Certain Officers",
    "5.03": "Amendments to Articles of Incorporation or Bylaws; Change in Fiscal Year",
    "5.04": "Temporary Suspension of Trading Under Registrant's Employee Benefit Plans",
    "5.05": "Amendments to the Registrant's Code of Ethics, or Waiver of a Provision of the Code of Ethics",
    "5.06": "Change in Shell Company Status",
    "5.07": "Submission of Matters to a Vote of Security Holders",
    "5.08": "Shareholder Director Nominations",
    "7.01": "Regulation FD Disclosure",
    "8.01": "Other Events",
    "9.01": "Financial Statements and Exhibits",
}
_NAME_KEY = 20
_NUMBER_BY_NAME = {name.lower()[:_NAME_KEY]: num for num, name in ITEM_NAMES.items()}

_INDEX_LINE = re.compile(
    r"^(?P<form>\S+(?: \S+)*?)\s{2,}(?P<company>.+?)\s+(?P<cik>\d+)\s+"
    r"(?P<date>\d{8}|\d{4}-\d{2}-\d{2})\s+(?P<file>edgar/\S+)\s*$"
)
_FEED_TITLE = re.compile(r"^(?P<form>\S+)\s+-\s+(?P<company>.+?)\s+\((?P<cik>\d+)\)\s+\(.*\)\s*$")
_FEED_ITEM = re.compile(r"Item (\d\.\d\d):\s*([^<\r\n]+)")
_HEADER_ITEM = re.compile(r"^ITEM INFORMATION:\s*(.+?)\s*$", re.M)
_HEADER_ACCEPTED = re.compile(r"<ACCEPTANCE-DATETIME>(\d{14})")


def _parse_day(text: str) -> date:
    fmt = "%Y%m%d" if len(text) == 8 else "%Y-%m-%d"
    return datetime.strptime(text, fmt).date()


def _filing_url(cik: int, accession: str) -> str:
    return FILING_INDEX_URL.format(cik=cik, nodash=accession.replace("-", ""), acc=accession)


def item_number(name: str) -> Optional[str]:
    """Item number for a free-text item name from a filing header, or None if unknown."""
    return _NUMBER_BY_NAME.get(re.sub(r"\s+", " ", name).strip().lower()[:_NAME_KEY])


def _title(company: str, names: List[str]) -> str:
    return f"{company}: 8-K {'; '.join(names)}" if names else f"{company}: 8-K"


def _summary(numbers: List[str]) -> str:
    return f"Items: {', '.join(numbers)}" if numbers else ""


def parse_feed(xml: bytes, ciks: Optional[Dict[int, List[str]]] = None) -> List[NewsItem]:
    """NewsItems from the 'latest 8-K filings' Atom feed. `ciks` maps CIK to tickers and is
    only used to fill `symbols`."""
    items: List[NewsItem] = []
    for entry in feedparser.parse(xml).entries:
        term = (entry.get("tags") or [{}])[0].get("term", "")
        title = _FEED_TITLE.match(entry.get("title", ""))
        if term != "8-K" or not title or not entry.get("link") or not entry.get("updated"):
            continue
        listed = _FEED_ITEM.findall(entry.get("summary", ""))
        items.append(NewsItem(
            source=EdgarSource.name,
            published_at=datetime.fromisoformat(entry["updated"]),
            title=_title(title["company"], [name.strip() for _, name in listed]),
            url=entry["link"],
            summary=_summary([number for number, _ in listed]),
            symbols=list((ciks or {}).get(int(title["cik"]), [])),
        ))
    return items


def parse_index(lines: Iterable[str]) -> Iterator[Tuple[str, int, date, str]]:
    """Yield (company, cik, filing date, accession) for each plain '8-K' row of a form index."""
    for line in lines:
        if not line.startswith("8-K "):  # also drops 8-K/A, 8-K12B and the header lines
            continue
        row = _INDEX_LINE.match(line)
        if row is None or row["form"] != "8-K":
            continue
        accession = row["file"].rsplit("/", 1)[-1].removesuffix(".txt")
        yield row["company"], int(row["cik"]), _parse_day(row["date"]), accession


def parse_header(text: str) -> Tuple[Optional[datetime], List[str]]:
    """(acceptance time in UTC or None, item names) from the start of a filing's .txt file."""
    text = text.split("</SEC-HEADER>", 1)[0]
    names = _HEADER_ITEM.findall(text)
    accepted = _HEADER_ACCEPTED.search(text)
    moment = None
    if accepted:
        moment = datetime.strptime(accepted[1], "%Y%m%d%H%M%S").replace(tzinfo=EASTERN)
        moment = moment.astimezone(timezone.utc)
    return moment, names


def _quarters(start: date, end: date) -> Iterator[Tuple[int, int]]:
    year, quarter = start.year, (start.month - 1) // 3 + 1
    while (year, quarter) <= (end.year, (end.month - 1) // 3 + 1):
        yield year, quarter
        year, quarter = (year + 1, 1) if quarter == 4 else (year, quarter + 1)


class EdgarSource:
    name = "edgar"

    def __init__(
        self,
        session: Optional[PoliteSession] = None,
        tickers: Iterable[str] = DEFAULT_TICKERS,
        ciks: Iterable[int] = (),
        email: Optional[str] = None,
        live_allowlist_only: bool = False,
    ) -> None:
        """`tickers` and `ciks` form the allowlist for history. `fetch_recent` returns every
        8-K in the feed unless `live_allowlist_only` is set."""
        self._tickers = [t.upper() for t in tickers]
        self._extra_ciks = [int(c) for c in ciks]
        self._email = sec_contact_email() if email is None else email
        self._live_allowlist_only = live_allowlist_only
        self._http = session
        self._allow: Optional[Dict[int, List[str]]] = None
        self._warned = False

    # -- setup ------------------------------------------------------------------------

    def _session(self) -> Optional[PoliteSession]:
        """The HTTP helper, or None (after one warning) when no contact email is configured."""
        if self._http is None:
            if not self._email:
                if not self._warned:
                    logger.warning("SEC_CONTACT_EMAIL is not set; skipping SEC EDGAR "
                                   "(the SEC requires a contact in the User-Agent)")
                    self._warned = True
                return None
            self._http = PoliteSession(user_agent=f"stock_advisor {self._email}", min_delay=0.15)
        return self._http

    def allowlist(self) -> Dict[int, List[str]]:
        """CIK -> tickers for the allowlist. One request on first use (company_tickers.json)."""
        if self._allow is None:
            allow: Dict[int, List[str]] = {cik: [] for cik in self._extra_ciks}
            http = self._session()
            if http is not None and self._tickers:
                rows = http.get(TICKERS_URL).json().values()
                by_ticker = {row["ticker"].upper(): int(row["cik_str"]) for row in rows}
                for ticker in self._tickers:
                    if ticker in by_ticker:
                        allow.setdefault(by_ticker[ticker], []).append(ticker)
                    else:
                        logger.warning("EDGAR: ticker %s not found in company_tickers.json", ticker)
            self._allow = allow
        return self._allow

    # -- live -------------------------------------------------------------------------

    def fetch_recent(self) -> List[NewsItem]:
        http = self._session()
        if http is None:
            return []
        items = parse_feed(http.get(ATOM_URL).content, self.allowlist() if self._tickers else {})
        if self._live_allowlist_only:
            allowed = set(self.allowlist())
            items = [i for i in items if int(i.url.split("/data/")[1].split("/")[0]) in allowed]
        return items

    # -- history ----------------------------------------------------------------------

    def fetch_range(self, start: datetime, end: datetime) -> Iterator[NewsItem]:
        """Yield allowlisted 8-Ks filed from `start` to `end` inclusive (tz-aware UTC)."""
        http = self._session()
        if http is None:
            return
        first = max(start.date(), date(EARLIEST_QUARTER[0], 1, 1))
        last = end.date()
        allow = self.allowlist()
        if not allow or first > last:
            return
        if (last - first).days <= DAILY_INDEX_MAX_DAYS:
            sources = self._daily_rows(http, first, last)
        else:
            sources = self._quarterly_rows(http, first, last)
        for company, cik, filed, accession in sources:
            if cik in allow and first <= filed <= last:
                yield self._build(http, company, cik, filed, accession, allow[cik])

    def _daily_rows(self, http, first: date, last: date):
        day = first
        while day <= last:
            if day.weekday() < 5:  # no index files for weekends
                url = DAILY_INDEX_URL.format(year=day.year, quarter=(day.month - 1) // 3 + 1, day=day)
                yield from self._index_rows(http, url)
            day += timedelta(days=1)

    def _quarterly_rows(self, http, first: date, last: date):
        for year, quarter in _quarters(first, last):
            yield from self._index_rows(http, FULL_INDEX_URL.format(year=year, quarter=quarter))

    def _index_rows(self, http, url: str):
        """Stream one index file. A missing file (holiday, future quarter) yields nothing."""
        try:
            response = http.get(url, stream=True)
        except Exception as exc:
            logger.warning("EDGAR index %s failed: %s", url, exc)
            return
        try:
            yield from parse_index(raw.decode("latin-1") for raw in response.iter_lines())
        finally:
            response.close()

    def _build(self, http, company: str, cik: int, filed: date, accession: str,
               tickers: List[str]) -> NewsItem:
        accepted, names = self._read_header(http, cik, accession)
        numbers = [n for n in map(item_number, names) if n] if filed >= NEW_ITEMS_START else []
        published = accepted or datetime(filed.year, filed.month, filed.day, tzinfo=timezone.utc)
        return NewsItem(
            source=self.name,
            published_at=published,
            title=_title(company, names),
            url=_filing_url(cik, accession),
            summary=_summary(numbers),
            symbols=list(tickers),
        )

    def _read_header(self, http, cik: int, accession: str) -> Tuple[Optional[datetime], List[str]]:
        """Acceptance time and item names from the filing's first bytes; blanks on failure."""
        url = f"{ARCHIVES}edgar/data/{cik}/{accession}.txt"
        try:
            response = http.get(url, headers={"Range": f"bytes=0-{HEADER_BYTES - 1}"})
            return parse_header(response.content[: HEADER_BYTES * 4].decode("latin-1"))
        except Exception as exc:  # the filing is still worth keeping at day precision
            logger.warning("EDGAR header %s failed: %s", url, exc)
            return None, []
