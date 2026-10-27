"""Yahoo Finance headlines through yfinance (recent items only, no history).

Per symbol the adapter reads `yfinance.Ticker(symbol).news`. Two payload shapes exist:
  * new: {"id", "content": {"title", "summary", "pubDate", "canonicalUrl": {"url"}, ...}}
  * old: {"uuid", "title", "link", "providerPublishTime" (epoch seconds), "publisher", ...}
yfinance 1.7.0 calls a Yahoo endpoint (`/xhr/ncp`) that currently answers 404, so
`Ticker.news` returns an empty list. When that happens the adapter falls back to
`yfinance.Search(symbol).news`, which still returns the old flat shape. Both are parsed.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional

import yfinance as yf

from stock_advisor.market_data import normalize_symbol
from stock_advisor.news.models import NewsItem, ensure_utc

logger = logging.getLogger(__name__)

# Indices (Hang Seng, S&P 500), Hong Kong ETFs and US sector proxies. The collector passes
# holdings instead once it exists.
DEFAULT_SYMBOLS = ["^HSI", "^GSPC", "2800.HK", "3033.HK", "XLK", "XLF", "XLE"]
YAHOO_MIN_DELAY = 1.0  # seconds between symbol requests
NEWS_COUNT = 20


def _parse_time(value) -> Optional[datetime]:
    """Accept epoch seconds (old shape) or an ISO 8601 string (new shape)."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        return ensure_utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError:
        return None


def _url_of(content: dict) -> str:
    """Pull the article url from either shape (several keys exist in the new one)."""
    for key in ("canonicalUrl", "clickThroughUrl"):
        value = content.get(key)
        if isinstance(value, dict) and value.get("url"):
            return str(value["url"])
        if isinstance(value, str) and value:
            return value
    return str(content.get("link") or content.get("url") or "")


def parse_article(raw: dict, symbol: str) -> Optional[NewsItem]:
    """Turn one yfinance news dict (either shape) into a NewsItem, or None if unusable."""
    if not isinstance(raw, dict):
        return None
    content = raw.get("content") if isinstance(raw.get("content"), dict) else raw
    title = str(content.get("title") or "").strip()
    published = _parse_time(content.get("pubDate") or content.get("providerPublishTime")
                            or content.get("displayTime"))
    if not title or published is None:
        return None
    summary = str(content.get("summary") or content.get("description") or "").strip()
    return NewsItem(
        source="yahoo",
        published_at=published,
        title=title,
        url=_url_of(content),
        summary=summary,
        symbols=[symbol],
    )


def merge_items(items: Iterable[NewsItem]) -> List[NewsItem]:
    """Collapse the same story (same item id, so same url) seen under several tickers."""
    merged: Dict[str, NewsItem] = {}
    for item in items:
        seen = merged.get(item.id)
        if seen is None:
            merged[item.id] = item
        else:
            seen.symbols.extend(s for s in item.symbols if s not in seen.symbols)
    return list(merged.values())


class YahooNewsSource:
    name = "yahoo"

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        sleep: Callable[[float], None] = time.sleep,
        min_delay: float = YAHOO_MIN_DELAY,
    ) -> None:
        raw = symbols if symbols else DEFAULT_SYMBOLS
        self.symbols = list(dict.fromkeys(normalize_symbol(s) for s in raw))
        self._sleep = sleep
        self._min_delay = min_delay

    def _fetch_raw(self, symbol: str) -> list:
        articles = yf.Ticker(symbol).news or []
        if not articles:
            articles = yf.Search(symbol, news_count=NEWS_COUNT, max_results=1).news or []
        return articles

    def fetch_symbol(self, symbol: str) -> List[NewsItem]:
        try:
            articles = self._fetch_raw(symbol)
        except Exception as exc:  # yfinance raises many types; one bad ticker must not stop the rest
            logger.warning("Yahoo news for %s failed (%s)", symbol, type(exc).__name__)
            return []
        items = [parse_article(a, symbol) for a in articles]
        return [i for i in items if i is not None]

    def fetch_recent(self) -> List[NewsItem]:
        collected: List[NewsItem] = []
        for index, symbol in enumerate(self.symbols):
            if index:
                self._sleep(self._min_delay)
            collected.extend(self.fetch_symbol(symbol))
        return merge_items(collected)
