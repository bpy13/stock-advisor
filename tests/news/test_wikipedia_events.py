"""Tests for the Wikipedia Current events adapter, parsed from saved API responses."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

from stock_advisor.news.sources import NewsSource
from stock_advisor.news.sources.wikipedia_events import (
    EARLIEST_DAILY_PAGE,
    WikipediaEventsSource,
    page_title,
    parse_day_html,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "news" / "wikipedia"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class FakeSession:
    """Stands in for PoliteSession: serves saved pages by title, records requests."""

    def __init__(self, pages: dict) -> None:
        self.pages = pages
        self.titles = []

    def get(self, url, params=None, **kwargs):
        self.titles.append(params["page"])
        return FakeResponse(self.pages.get(params["page"], load("missing.json")))


def test_modern_page_has_categories_and_utc_midnight_date():
    html = load("2024-03-05.json")["parse"]["text"]
    items = parse_day_html(html, date(2024, 3, 5))
    assert len(items) == 12
    assert all(i.published_at == datetime(2024, 3, 5, tzinfo=timezone.utc) for i in items)
    first = items[0]
    assert first.title.startswith("The Russian Navy patrol ship Sergey Kotov is sunk")
    assert "(The Guardian)" not in first.title  # citation moved out of the title
    assert first.summary == "Armed conflicts and attacks > Russian invasion of Ukraine [The Guardian]"
    assert first.url.startswith("https://www.theguardian.com/")
    categories = {i.summary.split(" > ")[0].split(" [")[0] for i in items}
    assert {"Armed conflicts and attacks", "Law and crime", "Science and technology"} <= categories


def test_modern_page_keeps_non_ascii_text():
    html = load("2024-03-05.json")["parse"]["text"]
    items = parse_day_html(html, date(2024, 3, 5))
    assert any("–" in i.summary for i in items)  # en dash in "Iran–Israel conflict"


def test_old_flat_page_has_no_categories():
    html = load("2003-03-05.json")["parse"]["text"]
    items = parse_day_html(html, date(2003, 3, 5))
    assert len(items) == 12
    assert any("Davao City" in i.title for i in items)
    assert all(i.summary == "" for i in items)
    assert all(i.url.startswith("https://en.wikipedia.org/wiki/Portal:Current_events/2003_March_5#") for i in items)


def test_item_ids_are_unique_within_a_day():
    for name, day in (("2024-03-05.json", date(2024, 3, 5)), ("2003-03-05.json", date(2003, 3, 5))):
        items = parse_day_html(load(name)["parse"]["text"], day)
        assert len({i.id for i in items}) == len(items)


def test_page_title_uses_english_month_without_zero_padding():
    assert page_title(date(2024, 3, 5)) == "Portal:Current events/2024 March 5"


def test_fetch_day_returns_empty_for_missing_page():
    source = WikipediaEventsSource(session=FakeSession({}))
    assert source.fetch_day(date(2001, 3, 5)) == []


def test_fetch_range_skips_missing_days_and_clamps_to_earliest_page():
    session = FakeSession({"Portal:Current events/2003 March 5": load("2003-03-05.json")})
    source = WikipediaEventsSource(session=session)
    start = datetime(1999, 1, 1, tzinfo=timezone.utc)
    items = list(source.fetch_range(start, datetime(2002, 4, 12, tzinfo=timezone.utc)))
    assert items == []
    assert session.titles[0] == page_title(EARLIEST_DAILY_PAGE)
    assert len(session.titles) == 2  # 2002-04-11 and 2002-04-12 only

    session = FakeSession({"Portal:Current events/2003 March 5": load("2003-03-05.json")})
    source = WikipediaEventsSource(session=session)
    items = list(
        source.fetch_range(
            datetime(2003, 3, 4, tzinfo=timezone.utc), datetime(2003, 3, 6, tzinfo=timezone.utc)
        )
    )
    assert len(items) == 12
    assert len(session.titles) == 3


def test_conforms_to_news_source_protocol():
    source = WikipediaEventsSource(session=FakeSession({}))
    assert isinstance(source, NewsSource)
    assert source.name == "wikipedia_events"
    assert hasattr(source, "fetch_range")
