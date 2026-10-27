"""RSS adapter tests: parse real trimmed feeds from fixtures; no network."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from stock_advisor.news.sources import NewsSource
from stock_advisor.news.sources.rss_feeds import FEEDS, Feed, RssFeedsSource, parse_feed

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "news" / "rss"
BBC = Feed("BBC Business", "https://example.test/bbc", "market")
USGS = Feed("USGS Significant Earthquakes", "https://example.test/usgs", "disaster")


def test_parse_rss_fixture():
    items = parse_feed((FIXTURES / "bbc_business.xml").read_bytes(), BBC)
    assert len(items) == 5
    first = items[0]
    assert first.source == "rss"
    assert first.title and first.url.startswith("http")
    assert first.summary.startswith("[BBC Business | market]")
    assert first.published_at.tzinfo is not None
    assert first.published_at.year >= 2025
    assert len({i.id for i in items}) == 5


def test_parse_atom_fixture():
    items = parse_feed((FIXTURES / "usgs_significant.atom").read_bytes(), USGS)
    assert len(items) == 4
    assert all(i.summary.startswith("[USGS Significant Earthquakes | disaster]") for i in items)
    assert all(i.url.startswith("http") for i in items)


def test_missing_date_uses_now():
    xml = b"<rss version='2.0'><channel><item><title>No date</title><link>http://x/1</link></item></channel></rss>"
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    items = parse_feed(xml, BBC, now=now)
    assert items[0].published_at == now


def test_untitled_entry_dropped_and_html_stripped():
    xml = (b"<rss version='2.0'><channel>"
           b"<item><link>http://x/1</link></item>"
           b"<item><title>T</title><link>http://x/2</link>"
           b"<description>&lt;p&gt;Hello &lt;b&gt;world&lt;/b&gt;&lt;/p&gt;</description></item>"
           b"</channel></rss>")
    items = parse_feed(xml, BBC)
    assert len(items) == 1
    assert items[0].summary == "[BBC Business | market] Hello world"


def test_fetch_recent_survives_a_failing_feed():
    good = (FIXTURES / "bbc_business.xml").read_bytes()
    http = MagicMock()
    http.get.side_effect = [RuntimeError("down"), MagicMock(content=good)]
    source = RssFeedsSource(session=http, feeds=[USGS, BBC])
    assert isinstance(source, NewsSource)
    items = source.fetch_recent()
    assert len(items) == 5
    assert http.get.call_count == 2


def test_default_feeds_are_valid():
    assert {f.category for f in FEEDS} <= {"market", "macro", "policy", "cyber", "disaster"}
    assert len({f.url for f in FEEDS}) == len(FEEDS)
    assert RssFeedsSource(session=MagicMock()).name == "rss"
    assert not hasattr(RssFeedsSource, "fetch_range")
