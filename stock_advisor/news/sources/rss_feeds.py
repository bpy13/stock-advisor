"""Public RSS/Atom feeds from news outlets and official bodies (recent items only).

All items carry source "rss". The feed name and category hint go into the summary prefix, for
example "[BBC Business | market] text...". Categories: market, macro, policy, cyber, disaster.

Feeds were probed on 2026-10-27: each URL was fetched, robots.txt was read for
`User-agent: *`, and a feed was kept unless robots disallowed the path. Feeds are published for
syndication, so only an explicit ban counts. Site terms were not read line by line; see
docs/open-items.md.

Rejected candidates (reason in one line each):
- Yahoo Finance rssindex / topstories: HTTP 404, the public feed no longer exists.
- Nasdaq rssoutbound: request times out (ReadTimeout after 40 s, three tries).
- RTHK business (e_expressnews_ebusiness.xml): URL returns an HTML page, not a feed.
- CNBC top news / world / economy: search.cnbc.com robots.txt has `User-agent: *` / `Disallow: /`.
- MarketWatch (Dow Jones feed): robots.txt returns 403 and Dow Jones terms bar automated access.
- Reuters (feeds.reuters.com): connection fails, free feeds were discontinued.
- AP (apnews.com hub RSS): HTTP 403.
- The Standard HK: RSS URL returns an HTML page, not a feed.
- US Treasury press releases: old feed URL times out, the replacement path is 404.
- PBoC English press releases: robots.txt has `User-agent: *` / `Disallow: /`, and no feed exists.
"""

from __future__ import annotations

import calendar
import logging
import re
from datetime import datetime, timezone
from typing import List, NamedTuple, Optional

import feedparser
from bs4 import BeautifulSoup

from stock_advisor.news.models import NewsItem
from stock_advisor.news.sources import PoliteSession

logger = logging.getLogger(__name__)

MAX_ITEMS_PER_FEED = 50  # the HKMA feed lists 430 entries; recent ones are enough


class Feed(NamedTuple):
    name: str
    url: str
    category: str  # market / macro / policy / cyber / disaster


FEEDS: List[Feed] = [
    Feed("RTHK Finance", "https://rthk.hk/rthk/news/rss/e_expressnews_efinance.xml", "market"),
    Feed("RTHK International", "https://rthk.hk/rthk/news/rss/e_expressnews_einternational.xml", "macro"),
    Feed("SCMP Business", "https://www.scmp.com/rss/92/feed", "market"),
    Feed("SCMP China Economy", "https://www.scmp.com/rss/318421/feed", "macro"),
    Feed("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml", "market"),
    Feed("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml", "macro"),
    Feed("Investing.com", "https://www.investing.com/rss/news.rss", "market"),
    Feed("HKFP", "https://hongkongfp.com/feed/", "policy"),
    Feed("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml", "policy"),
    Feed("HKMA Press Releases", "https://www.hkma.gov.hk/eng/other-information/rss/rss_press-release.xml", "policy"),
    Feed("CISA Advisories", "https://www.cisa.gov/cybersecurity-advisories/all.xml", "cyber"),
    Feed("USGS Significant Earthquakes", "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.atom", "disaster"),
]


def _clean(text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    if "<" in text:
        text = BeautifulSoup(text, "lxml").get_text(" ")
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _entry_time(entry) -> Optional[datetime]:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    # feedparser normalises struct_time to UTC
    return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)


def parse_feed(content: bytes, feed: Feed, now: Optional[datetime] = None) -> List[NewsItem]:
    """Turn raw feed bytes into NewsItems. Entries without a title are dropped; entries without
    a date get `now` (the fetch time)."""
    now = now or datetime.now(timezone.utc)
    parsed = feedparser.parse(content)
    items: List[NewsItem] = []
    for entry in parsed.entries[:MAX_ITEMS_PER_FEED]:
        title = _clean(entry.get("title", ""))
        if not title:
            continue
        text = _clean(entry.get("summary", ""))
        prefix = f"[{feed.name} | {feed.category}]"
        items.append(NewsItem(
            source="rss",
            published_at=_entry_time(entry) or now,
            title=title,
            url=entry.get("link", ""),
            summary=f"{prefix} {text}".strip(),
        ))
    return items


class RssFeedsSource:
    name = "rss"

    def __init__(self, session: Optional[PoliteSession] = None,
                 feeds: Optional[List[Feed]] = None) -> None:
        # At least 2 s between feed requests.
        self._http = session or PoliteSession(min_delay=2.0)
        self.feeds = feeds if feeds is not None else FEEDS

    def fetch_feed(self, feed: Feed) -> List[NewsItem]:
        response = self._http.get(feed.url)
        return parse_feed(response.content, feed)

    def fetch_recent(self) -> List[NewsItem]:
        items: List[NewsItem] = []
        for feed in self.feeds:
            try:
                items.extend(self.fetch_feed(feed))
            except Exception as exc:  # one dead feed must not stop the others
                logger.warning("RSS feed %s failed: %s", feed.name, exc)
        return items
