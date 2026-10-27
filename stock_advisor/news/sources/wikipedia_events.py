"""Wikipedia "Portal:Current events" adapter (one page per day, via the MediaWiki API).

Precision: Wikipedia lists events per calendar day only, so every item gets `published_at` =
that date at 00:00 UTC. Intraday ordering is not available; do not use it for hour-level
alignment with prices.

Page formats found by probing en.wikipedia.org:
- Daily pages `Portal:Current events/<YYYY> <Month> <D>` exist from 2002-04-11 (the 2002 set is
  sparse; from 2003 onward every day exists). Earlier history is only in year pages and in
  main-namespace monthly pages (`Current events/July 2002`); this adapter does not read them.
- Modern pages (about 2004 on) group bullets under bold category headings ("Armed conflicts
  and attacks"), with nested topic bullets. Older pages are a flat bullet list without
  categories. Both are handled: every innermost bullet becomes one item; the category and the
  enclosing topic bullets go into `summary`.

Politeness: the Wikimedia User-Agent policy asks for a descriptive agent with contact details
(set in `PoliteSession`), and we send one request per second at most. One request per day, so
a backfill from 2002 is roughly 8,600 requests (about 2.5 to 3 hours).
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Iterator, List, Optional

from bs4 import BeautifulSoup, Tag

from stock_advisor.news.models import NewsItem
from stock_advisor.news.sources import PoliteSession

logger = logging.getLogger(__name__)

API_URL = "https://en.wikipedia.org/w/api.php"
PAGE_URL = "https://en.wikipedia.org/wiki/Portal:Current_events/{year}_{month}_{day}"
EARLIEST_DAILY_PAGE = date(2002, 4, 11)
RECENT_DAYS = 3  # fetch_recent covers today and the two days before it

# English names written out so the result does not depend on the machine's locale.
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

_CITATION_LABEL = re.compile(r"^\s*\(.*\)\s*$", re.S)
_LONG_PARENT_TEXT = 120  # a parent bullet longer than this is a news sentence, not a label


def page_title(day: date) -> str:
    return f"Portal:Current events/{day.year} {MONTHS[day.month - 1]} {day.day}"


def page_url(day: date) -> str:
    return PAGE_URL.format(year=day.year, month=MONTHS[day.month - 1], day=day.day)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _own_text_and_links(li: Tag):
    """Text of a bullet without its nested lists, plus (cited source urls, cited labels).

    Citations on these pages are external links whose text is a parenthesised outlet name,
    for example "(Reuters)". They are removed from the text and returned separately.
    """
    li = BeautifulSoup(str(li), "lxml").find("li")  # work on a copy
    for nested in li.find_all(["ul", "ol"]):
        nested.decompose()
    for sup in li.find_all("sup"):  # footnote marks and "[dead link]" tags
        sup.decompose()
    urls: List[str] = []
    labels: List[str] = []
    for anchor in li.find_all("a", class_="external"):
        if _CITATION_LABEL.match(anchor.get_text()):
            href = anchor.get("href", "")
            if href.startswith("//"):
                href = "https:" + href
            if href:
                urls.append(href)
            labels.append(_clean(anchor.get_text()).strip("() "))
            anchor.decompose()
    text = _clean(li.get_text())
    text = re.sub(r"\(\s*\)", "", text)
    return _clean(text), urls, labels


def _walk_list(ul: Tag, category: str, topics: List[str], out: list) -> None:
    for li in ul.find_all("li", recursive=False):
        text, urls, labels = _own_text_and_links(li)
        nested = li.find_all(["ul", "ol"], recursive=False)
        if not nested:
            if text:
                out.append((category, list(topics), text, urls, labels))
            continue
        # Short parent text without a citation is only a topic label such as
        # "Russian invasion of Ukraine"; a long or cited one is a news sentence too.
        if text and (urls or len(text) > _LONG_PARENT_TEXT):
            out.append((category, list(topics), text, urls, labels))
        child_topics = topics + ([text] if text else [])
        for sub in nested:
            _walk_list(sub, category, child_topics, out)


def parse_day_html(html: str, day: date) -> List[NewsItem]:
    """Turn the rendered HTML of one daily page into NewsItems (published_at = day, 00:00 UTC)."""
    soup = BeautifulSoup(html, "lxml")
    content = soup.find("div", class_="current-events-content") or soup
    rows: list = []
    category = ""
    for child in content.children:
        if not isinstance(child, Tag):
            continue
        if child.name in ("ul", "ol"):
            _walk_list(child, category, [], rows)
        elif child.name == "p" or re.fullmatch(r"h[2-6]", child.name):
            heading = _clean(child.get_text())
            if heading and (child.name != "p" or child.find("b")):
                category = heading
    published = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    day_url = page_url(day)
    items: List[NewsItem] = []
    seen_urls: set = set()
    for category, topics, text, urls, labels in rows:
        url = urls[0] if urls else ""
        if not url or url in seen_urls:
            # Several bullets can cite the same article. Items need unique urls, so point at
            # the day page with a short hash of the text.
            url = f"{day_url}#{hashlib.sha1(text.encode('utf-8')).hexdigest()[:10]}"
        seen_urls.add(url)
        summary = " > ".join(part for part in [category, *topics] if part)
        if labels:
            summary = f"{summary} [{'; '.join(labels)}]" if summary else f"[{'; '.join(labels)}]"
        items.append(NewsItem(source="wikipedia_events", published_at=published,
                              title=text, url=url, summary=summary))
    return items


class WikipediaEventsSource:
    name = "wikipedia_events"

    def __init__(self, session: Optional[PoliteSession] = None) -> None:
        self._http = session or PoliteSession(min_delay=1.0)

    def fetch_day_html(self, day: date) -> Optional[str]:
        """Rendered HTML of one daily page, or None when the page does not exist."""
        response = self._http.get(
            API_URL,
            params={
                "action": "parse", "page": page_title(day), "prop": "text",
                "disableeditsection": 1, "disabletoc": 1, "redirects": 1,
                "format": "json", "formatversion": 2,
            },
        )
        data = response.json()
        if "error" in data:
            if data["error"].get("code") == "missingtitle":
                return None
            raise RuntimeError(f"Wikipedia API error for {page_title(day)}: {data['error']}")
        return data["parse"]["text"]

    def fetch_day(self, day: date) -> List[NewsItem]:
        html = self.fetch_day_html(day)
        return parse_day_html(html, day) if html else []

    def fetch_recent(self) -> List[NewsItem]:
        today = datetime.now(timezone.utc).date()
        items: List[NewsItem] = []
        for offset in range(RECENT_DAYS):
            items.extend(self._safe_fetch_day(today - timedelta(days=offset)))
        return items

    def fetch_range(self, start: datetime, end: datetime) -> Iterator[NewsItem]:
        """Yield items for every day from `start` to `end` inclusive (tz-aware UTC)."""
        day = max(start.date(), EARLIEST_DAILY_PAGE)
        last = end.date()
        while day <= last:
            yield from self._safe_fetch_day(day)
            day += timedelta(days=1)

    def _safe_fetch_day(self, day: date) -> List[NewsItem]:
        try:
            return self.fetch_day(day)
        except Exception as exc:  # one bad day must not stop a multi-year backfill
            logger.warning("Wikipedia current events %s failed: %s", day, exc)
            return []
