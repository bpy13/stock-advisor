"""CFTC Commitments of Traders (Task R4): weekly futures positions by speculators and hedgers.

Source: the CFTC's public reporting site (Socrata JSON, no key), legacy futures-only report,
dataset 6dca-aqww. US government open data; read-only, polite, one request per page.
History: weekly from 1986. Reports are for Tuesday and come out on Friday.

Markets kept are the futures behind the watchlist's symbols (CONTRACTS below). Non-commercial
traders are the speculators; commercial traders are the hedgers.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from stock_advisor.news.sources import PoliteSession

logger = logging.getLogger(__name__)

URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
PAGE = 5000

# CFTC contract market code -> the watchlist symbol it stands for.
CONTRACTS: Dict[str, str] = {
    "13874A": "^GSPC",  # E-mini S&P 500, CME
    "209742": "^NDX",  # Nasdaq-100 mini, CME
    "067651": "CL=F",  # WTI light sweet crude oil, NYMEX
    "043602": "^TNX",  # 10-year US Treasury notes, CBOT
}

_FIELDS = (
    "open_interest_all",
    "noncomm_positions_long_all",
    "noncomm_positions_short_all",
    "comm_positions_long_all",
    "comm_positions_short_all",
)

Row = Tuple[str, str, str, float, float, float, float, float]


def parse_rows(records: List[dict]) -> List[Row]:
    """(contract_code, 'YYYY-MM-DD', symbol, open interest, non-commercial long and short,
    commercial long and short) for the watched markets. Unreadable rows are skipped."""
    rows: List[Row] = []
    for rec in records:
        code = rec.get("cftc_contract_market_code")
        if code not in CONTRACTS:
            continue
        try:
            day = datetime.strptime(rec["report_date_as_yyyy_mm_dd"][:10], "%Y-%m-%d").date()
            numbers = tuple(float(rec[f]) for f in _FIELDS)
        except (KeyError, ValueError, TypeError):
            logger.warning("skipping an unreadable CFTC row: %r", rec)
            continue
        rows.append((code, day.isoformat(), CONTRACTS[code], *numbers))
    return rows


def fetch_cot(store, session: Optional[PoliteSession] = None) -> int:
    """Load every weekly report newer than the newest stored one (all history on the first
    run). Returns the rows stored."""
    session = session or PoliteSession(min_delay=1.0)
    quoted = ",".join(f"'{c}'" for c in CONTRACTS)
    where = f"cftc_contract_market_code in({quoted})"
    latest = store.cot_latest_date()
    if latest:
        where += f" AND report_date_as_yyyy_mm_dd > '{latest}T00:00:00.000'"
    total, offset = 0, 0
    while True:
        params = {
            "$where": where,
            "$order": "report_date_as_yyyy_mm_dd,cftc_contract_market_code",
            "$limit": PAGE,
            "$offset": offset,
        }
        records = session.get(URL, params=params).json()
        total += store.add_cot(parse_rows(records))
        if len(records) < PAGE:
            break
        offset += PAGE
    logger.info("CFTC Commitments of Traders: %d new rows", total)
    return total
