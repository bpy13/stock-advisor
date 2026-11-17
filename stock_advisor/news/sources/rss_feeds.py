"""Public RSS/Atom feeds from news outlets and official bodies (recent items only).

All items carry source "rss". The feed name and category hint go into the summary prefix, for
example "[BBC Business | market] text...". Categories: market, macro, policy, cyber, disaster.

Feeds were probed on 2026-10-27: each URL was fetched, robots.txt was read for
`User-agent: *`, and a feed was kept unless robots disallowed the path. Feeds are published for
syndication, so only an explicit ban counts. Site terms were not read line by line; see
docs/open-items.md.

Terms read 2026-11-17 (Task 6.4), for the feeds added:
- news.gov.hk Finance: robots.txt allows it; copyright note allows personal use and media use with
  credit, and forbids commercial use without permission. This tool is a personal research tool.
- SFC Press Releases and Circulars: robots.txt disallows only /dod/ and similar paths; the page
  carries no terms against reuse beyond "all rights reserved". Personal use.
- CNA Finance and Cross-Strait (via feedburner): RSS terms allow personal, non-profit,
  non-commercial use; titles, leads and links only, credit the source, may be withdrawn at any
  time. Its robots.txt has "ai-train=no": stories must never train a model.
Feeds in Chinese are stored as published; Simplified sources are not converted.

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
- SCMP (Business, China Economy; removed 2026-11-17, stored stories kept): terms clause 3.2.1 bars
  "any automated system (including web crawlers, spiders, or scrapers)" and clause 3.2.6 limits
  use to personal non-commercial use.
- Investing.com (removed 2026-11-17, stored stories kept): its terms page and robots.txt answer
  HTTP 403 to a script, and its page footer bans storing its data without written permission.
- Census and Statistics Department: no RSS feed exists (every guessed feed URL is 404). It offers
  a JSON data API for statistics tables, not news; that belongs to a data task, not this adapter.
- HKEX: stays out (its terms forbid scripted access).
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
    Feed("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml", "market"),
    Feed("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml", "macro"),
    Feed("news.gov.hk Finance", "https://www.news.gov.hk/en/categories/finance/html/articlelist.rss.xml", "market"),
    Feed("SFC Press Releases", "https://www.sfc.hk/en/RSS-Feeds/Press-releases", "policy"),
    Feed("SFC Circulars", "https://www.sfc.hk/en/RSS-Feeds/Circulars", "policy"),
    Feed("CNA Finance", "https://feeds.feedburner.com/rsscna/finance", "market"),
    Feed("CNA Cross-Strait", "https://feeds.feedburner.com/rsscna/mainland", "macro"),
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
