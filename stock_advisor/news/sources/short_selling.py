"""Short-selling files: the SFC's weekly aggregated short positions for Hong Kong stocks.

Terms read 2026-11-17 (hand-back for docs/decisions.md):
- SFC (sfc.hk): robots.txt disallows only /dod/, /sfcprd/, /dodWeb/, /publicregWeb/ and similar;
  the listing page and `/-/media/EN/pdf/spr/` CSVs are open. The data is published for the
  public; personal research use is allowed (terms read earlier). Fetched politely: one request
  a second, once per backfill run, only files not stored yet.
- FINRA (US daily short volume, twice-monthly short interest): NOT BUILT. Its terms of use
  (finra.org/terms-of-use, restrictions d, e, g) forbid "data mining, scraping or harvesting
  tools (including robots)", copying the site in bulk, and building a database from it unless
  FINRA allows it in writing. The files on cdn.finra.org are open to a browser, but the rule
  of 2026-10-27 (skip sources whose terms forbid scripted access) applies. See known-issues.

SFC listing: one HTML page links every weekly CSV from 2012-08-31, named
`.../spr/<Y>/<MM>/<DD>/Short_Position_Reporting_Aggregated_Data_<YYYYMMDD>.csv?rev=<hash>`.
CSV columns: `Date` (dd/mm/yyyy), `Stock Code`, `Stock Name`, aggregated reportable short
positions in shares and in HK$. The SFC publishes on Fridays, but a week can come late or on
another weekday, so the file list and each row's own Date column decide, not a Friday calendar.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from datetime import date, datetime
from typing import Dict, Iterable, List, Optional, Set, Tuple

from stock_advisor.news.sources import PoliteSession

logger = logging.getLogger(__name__)

SOURCE = "sfc_short"
LISTING_URL = (
    "https://www.sfc.hk/en/Regulatory-functions/Market/Short-position-reporting/"
    "Aggregated-reportable-short-positions-of-specified-shares"
)
_CSV_LINK = re.compile(
    r'href="([^"]*?/spr/\d{4}/\d{2}/\d{2}/Short_Position_Reporting_Aggregated_Data_(\d{8})\.csv[^"]*)"'
)

Row = Tuple[str, str, str, float, Optional[float], Optional[float]]


def parse_listing(html: str, base: str = "https://www.sfc.hk") -> Dict[date, str]:
    """Map each weekly file's date (from its name) to its absolute URL."""
    files: Dict[date, str] = {}
    for url, stamp in _CSV_LINK.findall(html):
        url = url.replace("&amp;", "&")
        if url.startswith("/"):
            url = base + url
        files[datetime.strptime(stamp, "%Y%m%d").date()] = url
    return files


def hk_symbol(code: str) -> str:
    """SFC stock code '700' -> the watchlist's '0700.HK'."""
    return f"{int(code):04d}.HK"


def parse_csv(text: str, symbols: Optional[Set[str]] = None) -> List[Row]:
    """Rows (symbol, 'YYYY-MM-DD', source, shares, HK$ value, None) for the wanted symbols.
    The date comes from each row, not from the file name."""
    rows: List[Row] = []
    for rec in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        try:
            symbol = hk_symbol(rec["Stock Code"])
            day = datetime.strptime(rec["Date"].strip(), "%d/%m/%Y").date().isoformat()
            shares = float(rec["Aggregated Reportable Short Positions (Shares)"])
            value = float(rec["Aggregated Reportable Short Positions (HK$)"])
        except (KeyError, ValueError, AttributeError):
            logger.warning("skipping an unreadable SFC short-position row: %r", rec)
            continue
        if symbols is None or symbol in symbols:
            rows.append((symbol, day, SOURCE, shares, value, None))
    return rows


def fetch_sfc(
    store, symbols: Iterable[str], session: Optional[PoliteSession] = None,
    since: Optional[date] = None,
) -> int:
    """Load every weekly file not stored yet (from `since` on) for the Hong Kong `symbols`.
    A file that fails is logged and left for the next run. Returns the rows stored."""
    wanted = {s.upper() for s in symbols if s.upper().endswith(".HK")}
    session = session or PoliteSession(min_delay=1.0)
    files = parse_listing(session.get(LISTING_URL).text)
    stored = store.short_selling_dates(SOURCE)
    total = 0
    for day in sorted(files):
        if since and day < since:
            continue
        if day.isoformat() in stored:
            continue
        try:
            text = session.get(files[day]).content.decode("utf-8-sig")
        except Exception as exc:  # network or HTTP error: retry next run
            logger.warning("SFC short positions %s failed: %s", day, exc)
            continue
        total += store.add_short_selling(parse_csv(text, wanted))
    logger.info("SFC short positions: %d new rows from %d files listed", total, len(files))
    return total
