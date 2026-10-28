"""GDELT DOC 2.0 API adapter (article list mode, English only).

Endpoint: https://api.gdeltproject.org/api/v2/doc/doc. One request per query and window. GDELT
allows about one request per 5 seconds per IP; when it is exceeded it answers HTTP 429 or a
plain-text "Please limit requests..." body instead of JSON. Both cases are handled here by
waiting and retrying. Each call returns at most 250 articles, so `fetch_range` splits a window
in half whenever it comes back full.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Iterator, List, Optional

import requests

from stock_advisor.news.models import NewsItem, SourceLimitReached, ensure_utc
from stock_advisor.news.sources import PoliteSession

logger = logging.getLogger(__name__)

API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
MAX_RECORDS = 250  # hard cap of the DOC API per call
MIN_SPLIT = timedelta(hours=6)  # a full window is split in half only while longer than this
RECENT_SLICES = 4 # fetch_recent asks for the last 24 hours as four 6-hour windows

# Market-moving themes, joined with OR into two queries. GDELT rejects a query longer than
# about 400 characters ("Your query was too short or too long": 416 failed, 204 and 229 work),
# so one query per call for all ten themes does not fit; two do. " sourcelang:english" is
# appended. Fewer calls matter because GDELT locks out clients that send many requests.
THEME_QUERIES: Dict[str, str] = {
    "macro_and_conflict": (
        '(tariffs OR "trade war" OR "central bank" OR "interest rates" OR "rate cut" '
        'OR "rate hike" OR war OR "military strike" OR invasion OR cyberattack '
        'OR "data breach" OR outage OR pandemic)'
    ),
    "disaster_credit_politics_oil": (
        '(outbreak OR epidemic OR earthquake OR hurricane OR typhoon OR "bank collapse" '
        'OR "bank failure" OR default OR bankruptcy OR sanctions OR embargo OR election '
        'OR referendum OR "oil price" OR "crude oil" OR OPEC)'
    ),
}


def _format_dt(moment: datetime) -> str:
    return ensure_utc(moment).strftime("%Y%m%d%H%M%S")


def clean_title(title: str) -> str:
    """GDELT titles often have spaces before punctuation ("Stocks fall , oil rises .") and
    repeated spaces. Tidy them so the text reads like the other sources."""
    title = re.sub(r"\s+", " ", title).strip()
    return re.sub(r"\s+([,.;:!?])", r"\1", title)


def _parse_seendate(text: str) -> datetime:
    return datetime.strptime(text, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


class GdeltSource:
    name = "gdelt"

    def __init__(
        self,
        session: Optional[PoliteSession] = None,
        queries: Optional[Dict[str, str]] = None,
        window: timedelta = timedelta(days=1),
        rate_limit_wait: float = 30.0,
        rate_limit_tries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        strict: bool = False,
    ) -> None:
        self._clock = clock
        # 5.5 s between requests keeps us just under GDELT's one-per-5-seconds limit.
        self.session = session or PoliteSession(min_delay=5.5, timeout=60.0, max_retries=2, backoff=3.0)
        self.queries = queries or THEME_QUERIES
        self.window = window
        self.rate_limit_wait = rate_limit_wait
        self.rate_limit_tries = rate_limit_tries
        self._sleep = sleep
        self.strict = strict  # True: raise SourceLimitReached instead of skipping a window

    # -- public API ---------------------------------------------------------------------
    def fetch_recent(self) -> List[NewsItem]:
        """Articles seen in the last 24 hours, for every theme query (de-duplicated)."""
        # One "timespan=1d" call is not enough: with sort=datedesc the API returns the 250
        # newest articles, and GDELT stamps seendate per 15-minute crawl batch, so those 250
        # can all share one timestamp. Fetch fixed slices of the day instead; a slice that
        # comes back full is split further by _fetch_window.
        now = ensure_utc(self._clock())
        slice_length = timedelta(hours=24) / RECENT_SLICES
        items: Dict[str, NewsItem] = {}
        for theme, query in self.queries.items():
            found = 0
            for n in range(RECENT_SLICES):
                start = now - timedelta(hours=24) + slice_length * n
                for item in self._fetch_window(query, start, start + slice_length):
                    found += 1
                    items.setdefault(item.id, item)
            logger.info("gdelt %s: %d articles", theme, found)
        ordered = sorted(items.values(), key=lambda i: i.published_at)
        # GDELT's index can stall for a day (seen 2026-10-28: nothing newer than 2026-10-27
        # 05:15Z). Log the newest stamp so a stall reads differently from a code bug.
        if ordered:
            logger.info("gdelt newest seendate %s, %d distinct", ordered[-1].published_at.isoformat(),
                        len({i.published_at for i in ordered}))
        else:
            logger.info("gdelt returned no articles for the last 24 hours")
        return ordered

    def fetch_range(self, start: datetime, end: datetime) -> Iterator[NewsItem]:
        """Articles seen between `start` and `end` (tz-aware UTC), window by window."""
        start, end = ensure_utc(start), ensure_utc(end)
        seen = set()
        cursor = start
        while cursor < end:
            window_end = min(cursor + self.window, end)
            for query in self.queries.values():
                for item in self._fetch_window(query, cursor, window_end):
                    if item.id not in seen:
                        seen.add(item.id)
                        yield item
            cursor = window_end

    # -- internals ----------------------------------------------------------------------
    def _fetch_window(self, query: str, start: datetime, end: datetime) -> List[NewsItem]:
        articles = self._request(
            query, {"startdatetime": _format_dt(start), "enddatetime": _format_dt(end)}
        )
        # A full page means older/newer articles were cut off: split the window and retry.
        if len(articles) >= MAX_RECORDS and (end - start) > MIN_SPLIT:
            middle = start + (end - start) / 2
            return self._fetch_window(query, start, middle) + self._fetch_window(
                query, middle, end
            )
        return self._to_items(articles)

    def _request(self, query: str, time_params: Dict[str, str]) -> List[dict]:
        params = {
            "query": f"{query} sourcelang:english",
            "mode": "artlist",
            "format": "json",
            "maxrecords": str(MAX_RECORDS),
            "sort": "datedesc",
            **time_params,
        }
        for attempt in range(self.rate_limit_tries):
            try:
                response = self.session.get(API_URL, params=params)
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 429:
                    logger.warning("gdelt rate limit (429); waiting %.0fs", self.rate_limit_wait)
                    self._sleep(self.rate_limit_wait)
                    continue
                logger.warning("gdelt request failed: %s", exc)
                return []
            text = response.text.strip()
            if text.startswith("{"):
                try:
                    return json.loads(text).get("articles", [])
                except json.JSONDecodeError:
                    logger.warning("gdelt returned malformed JSON for %r", query)
                    return []
            if "limit requests" in text:
                logger.warning("gdelt rate-limit text; waiting %.0fs", self.rate_limit_wait)
                self._sleep(self.rate_limit_wait)
                continue
            # Empty body or an error text (e.g. "query too short"): no articles.
            if text:
                logger.warning("gdelt non-JSON reply for %r: %s", query, text[:120])
            return []
        logger.warning("gdelt gave up on %r after repeated rate limits", query)
        if self.strict:
            # A backfill must not move its cursor past a window that was never fetched.
            raise SourceLimitReached("gdelt rate limit: gave up after repeated waits")
        return []

    @staticmethod
    def _to_items(articles: List[dict]) -> List[NewsItem]:
        items = []
        for article in articles:
            title = clean_title(article.get("title") or "")
            seen = article.get("seendate")
            if not title or not seen:
                continue
            try:
                published = _parse_seendate(seen)
            except ValueError:
                continue
            items.append(
                NewsItem(
                    source="gdelt",
                    published_at=published,
                    title=title,
                    url=article.get("url", ""),
                    summary=article.get("domain", ""),
                    language="en",
                )
            )
        return items
