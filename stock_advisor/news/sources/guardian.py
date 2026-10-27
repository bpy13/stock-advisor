"""Guardian Open Platform adapter (content API `/search`).

Developer keys allow about 12 calls/s and 5,000 calls/day; we stay at ~1 call/s. One query
covers all wanted sections (`section=a|b|c`), so `fetch_range` yields items in publication
order and a caller can resume by passing the last seen date as the new `start`.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Iterator, List, Optional

from stock_advisor.news.models import NewsItem, ensure_utc
from stock_advisor.news.settings import guardian_api_key
from stock_advisor.news.sources import PoliteSession

logger = logging.getLogger(__name__)

API_URL = "https://content.guardianapis.com/search"
SECTIONS = ("business", "world", "technology", "politics", "us-news")
PAGE_SIZE = 200
_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    """Strip HTML tags and entities from the trail text."""
    return html.unescape(_TAG_RE.sub("", text or "")).strip()


def parse_response(payload: dict) -> List[NewsItem]:
    """Turn one `/search` JSON payload into NewsItems. Skips results without a title or date."""
    items: List[NewsItem] = []
    for row in payload.get("response", {}).get("results", []):
        title = _clean(row.get("webTitle", ""))
        stamp = row.get("webPublicationDate")
        if not title or not stamp:
            continue
        published = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        items.append(
            NewsItem(
                source="guardian",
                published_at=published,
                title=title,
                url=row.get("webUrl", ""),
                summary=_clean(row.get("fields", {}).get("trailText", "")),
            )
        )
    return items


class GuardianSource:
    name = "guardian"

    def __init__(
        self,
        api_key: Optional[str] = None,
        session: Optional[PoliteSession] = None,
        sections=SECTIONS,
    ) -> None:
        self._api_key = guardian_api_key() if api_key is None else api_key
        self._http = session or PoliteSession(min_delay=1.0)
        self._sections = "|".join(sections)
        self._warned = False

    def _has_key(self) -> bool:
        if self._api_key:
            return True
        if not self._warned:
            logger.warning("GUARDIAN_API_KEY is not set; the Guardian source returns nothing")
            self._warned = True
        return False

    def _pages(self, from_date: str, to_date: str, order_by: str, max_pages: Optional[int]):
        """Yield one parsed page at a time."""
        page = 1
        while True:
            params = {
                "api-key": self._api_key,
                "section": self._sections,
                "from-date": from_date,
                "to-date": to_date,
                "order-by": order_by,
                "page-size": PAGE_SIZE,
                "page": page,
                "show-fields": "trailText",
            }
            payload = self._http.get(API_URL, params=params).json()
            yield parse_response(payload)
            total_pages = payload.get("response", {}).get("pages", 1)
            if page >= total_pages or (max_pages is not None and page >= max_pages):
                return
            page += 1

    def fetch_recent(self) -> List[NewsItem]:
        """Latest items from the last two days (one page of up to 200, newest first)."""
        if not self._has_key():
            return []
        today = datetime.now(timezone.utc).date()
        start = (today - timedelta(days=2)).isoformat()
        items: List[NewsItem] = []
        for page_items in self._pages(start, today.isoformat(), "newest", max_pages=1):
            items.extend(page_items)
        return items

    def fetch_range(self, start: datetime, end: datetime) -> Iterator[NewsItem]:
        """Yield items with start <= published_at < end, oldest first, one month window at a
        time. The API filters by whole day; we trim to the exact times here."""
        if not self._has_key():
            return
        start, end = ensure_utc(start), ensure_utc(end)
        window_start = start.date()
        last_day = end.date()
        while window_start <= last_day:
            window_end = min((window_start + timedelta(days=31)).replace(day=1) - timedelta(days=1), last_day)
            for page_items in self._pages(
                window_start.isoformat(), window_end.isoformat(), "oldest", max_pages=None
            ):
                for item in page_items:
                    if start <= item.published_at < end:
                        yield item
            window_start = window_end + timedelta(days=1)
