"""New York Times Archive API adapter (history back to 1851, one call per month).

GET https://api.nytimes.com/svc/archive/v1/{year}/{month}.json?api-key=...
A month response holds every article (several MB to tens of MB), so the adapter keeps only
the sections in `KEEP_SECTIONS` plus anything printed on page 1, and drops the rest at once.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Iterator, List, Optional

import requests

from stock_advisor.news.models import NewsItem, ensure_utc
from stock_advisor.news.settings import nyt_api_key
from stock_advisor.news.sources import PoliteSession

logger = logging.getLogger(__name__)

ARCHIVE_URL = "https://api.nytimes.com/svc/archive/v1/{year}/{month}.json"
KEEP_SECTIONS = frozenset({"business", "business day", "world", "technology", "u.s."})
FRONT_PAGE = "1"
NYT_MIN_DELAY = 12.0  # NYT allows 5 calls/minute and 500/day; 12 s keeps us at the limit
NYT_TIMEOUT = 120.0  # month files are large


def _parse_pub_date(text: str) -> Optional[datetime]:
    """Parse '2026-10-26T14:05:00+0000' (NYT's format) or ISO 8601 into UTC."""
    if not text:
        return None
    try:
        return ensure_utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
    except ValueError:
        pass
    try:
        return ensure_utc(datetime.strptime(text, "%Y-%m-%dT%H:%M:%S%z"))
    except ValueError:
        return None


def _wanted(doc: dict) -> bool:
    section = (doc.get("section_name") or "").strip().lower()
    return section in KEEP_SECTIONS or str(doc.get("print_page") or "") == FRONT_PAGE


def parse_archive(payload: dict) -> List[NewsItem]:
    """Turn one Archive API response into NewsItems, keeping only wanted articles."""
    docs = (payload.get("response") or {}).get("docs") or []
    items: List[NewsItem] = []
    for doc in docs:
        if not _wanted(doc):
            continue
        title = ((doc.get("headline") or {}).get("main") or "").strip()
        published = _parse_pub_date(doc.get("pub_date", ""))
        if not title or published is None:
            continue
        items.append(
            NewsItem(
                source="nyt",
                published_at=published,
                title=title,
                url=doc.get("web_url") or "",
                summary=(doc.get("abstract") or doc.get("snippet") or "").strip(),
            )
        )
    return items


class NytSource:
    name = "nyt"

    def __init__(
        self,
        session: Optional[PoliteSession] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self._session = session or PoliteSession(min_delay=NYT_MIN_DELAY, timeout=NYT_TIMEOUT)
        self._api_key = api_key
        self._warned = False

    def _key(self) -> str:
        key = self._api_key if self._api_key is not None else nyt_api_key()
        if not key and not self._warned:
            logger.warning("NYT_API_KEY is not set; the NYT source returns nothing")
            self._warned = True
        return key

    def _fetch_month(self, year: int, month: int, key: str) -> List[NewsItem]:
        url = ARCHIVE_URL.format(year=year, month=month)
        try:
            response = self._session.get(url, params={"api-key": key})
            return parse_archive(response.json())
        except (requests.RequestException, ValueError) as exc:
            # Log the type only: the exception text can contain the URL with the key.
            logger.warning("NYT archive %d-%02d failed (%s)", year, month, type(exc).__name__)
            return []

    def fetch_recent(self) -> List[NewsItem]:
        """Current month, filtered to the last 24 hours (and the previous month on the 1st)."""
        key = self._key()
        if not key:
            return []
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)
        months = [(now.year, now.month)]
        if (cutoff.year, cutoff.month) != (now.year, now.month):
            months.insert(0, (cutoff.year, cutoff.month))
        items: List[NewsItem] = []
        for year, month in months:
            items.extend(i for i in self._fetch_month(year, month, key) if i.published_at >= cutoff)
        return items

    def fetch_range(self, start: datetime, end: datetime) -> Iterator[NewsItem]:
        """Yield items published in [start, end], one API call per calendar month."""
        key = self._key()
        if not key:
            return
        start, end = ensure_utc(start), ensure_utc(end)
        year, month = start.year, start.month
        while (year, month) <= (end.year, end.month):
            for item in self._fetch_month(year, month, key):
                if start <= item.published_at <= end:
                    yield item
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
