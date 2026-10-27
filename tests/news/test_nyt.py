"""NYT adapter tests: parsing from real (trimmed) fixtures, no network."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from stock_advisor.news.models import SourceLimitReached
from stock_advisor.news.sources import NewsSource
from stock_advisor.news.sources.nyt import NytSource, parse_archive, parse_top_stories

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "news" / "nyt"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _payload() -> dict:
    return _load("archive_2026_10.json")


def _source(payload: dict, key: str = "k") -> tuple:
    session = MagicMock()
    session.get.return_value.json.return_value = payload
    return NytSource(session=session, api_key=key), session


def test_parse_keeps_wanted_sections_and_front_page():
    items = parse_archive(_payload())
    titles = [i.title for i in items]
    assert len(items) == 5  # the Arts article (no front page) is dropped
    assert "Late Night Is Skeptical of A.I. Leaders Self-Regulating" not in titles
    assert "How a Cornell Student Went From Shame to Action" in titles  # New York, print_page 1


def test_parse_fields():
    first = parse_archive(_payload())[0]
    assert first.source == "nyt"
    assert first.title == "The Objects Our Journalists Can’t Forget"
    assert first.summary.startswith("Times reporters and editors")
    assert first.url.endswith("reporting-objects.html")
    assert first.published_at == datetime(2026, 10, 1, 9, 0, 45, tzinfo=timezone.utc)


def test_parse_old_month_section_name_business_day():
    # Archive 1995 uses "Business Day" instead of "Business"; both must be kept.
    payload = {"response": {"docs": [
        {"headline": {"main": "Old"}, "pub_date": "1995-03-02T05:00:00Z",
         "section_name": "Business Day", "print_page": "7", "web_url": "u"},
        {"headline": {"main": "Sports"}, "pub_date": "1995-03-02T05:00:00Z",
         "section_name": "Sports", "print_page": "7", "web_url": "u2"},
    ]}}
    assert [i.title for i in parse_archive(payload)] == ["Old"]


def test_parse_top_stories_fields():
    items = parse_top_stories(_load("topstories_home.json"))
    assert len(items) == 3
    first = items[0]
    assert first.source == "nyt"
    assert first.title.startswith("Two Visions")
    assert first.url.endswith("israel-election-identity.html")
    assert first.published_at == datetime(2026, 10, 27, 4, 1, 18, tzinfo=timezone.utc)
    assert first.summary


def test_missing_key_warns_once_and_returns_nothing(caplog):
    session = MagicMock()
    source = NytSource(session=session, api_key="")
    with caplog.at_level(logging.WARNING):
        assert source.fetch_recent() == []
        assert list(source.fetch_range(datetime(2026, 1, 1), datetime(2026, 3, 1))) == []
    assert len([r for r in caplog.records if "NYT_API_KEY" in r.message]) == 1
    session.get.assert_not_called()


def test_fetch_range_one_call_per_month_and_filters_dates():
    source, session = _source(_payload())
    start = datetime(2026, 10, 1, 5, tzinfo=timezone.utc)
    end = datetime(2026, 11, 30, tzinfo=timezone.utc)
    items = list(source.fetch_range(start, end))
    urls = [c.args[0] for c in session.get.call_args_list]
    assert urls == [
        "https://api.nytimes.com/svc/archive/v1/2026/10.json",
        "https://api.nytimes.com/svc/archive/v1/2026/11.json",
    ]
    assert session.get.call_args.kwargs["params"] == {"api-key": "k"}
    assert {i.title for i in items} == {
        "The Objects Our Journalists Can’t Forget",
        "A.I. Is Going Rogue. Who Should Be Held Responsible?",
    }  # the other kept items are published before 05:00 UTC
    assert len(items) == 4  # the mock returns the same month twice


def test_fetch_range_crosses_year_end():
    source, session = _source({"response": {"docs": []}})
    list(source.fetch_range(datetime(2025, 12, 5), datetime(2026, 1, 5)))
    assert [c.args[0].rsplit("v1/", 1)[1] for c in session.get.call_args_list] == [
        "2025/12.json", "2026/1.json",
    ]


def test_fetch_recent_uses_top_stories_and_deduplicates_by_url():
    source, session = _source(_load("topstories_home.json"))  # same payload for every section
    items = source.fetch_recent()
    urls = [c.args[0] for c in session.get.call_args_list]
    assert urls == [
        f"https://api.nytimes.com/svc/topstories/v2/{s}.json"
        for s in ("home", "business", "world", "technology", "us")
    ]
    assert session.get.call_args.kwargs["params"] == {"api-key": "k"}
    assert len(items) == 3  # five identical responses collapse to one set


def test_fetch_recent_failed_section_does_not_stop_others():
    import requests

    session = MagicMock()
    ok = MagicMock()
    ok.json.return_value = _load("topstories_business.json")
    session.get.side_effect = [requests.HTTPError("429"), ok, requests.HTTPError("429"), ok, ok]
    items = NytSource(session=session, api_key="k").fetch_recent()
    assert len(items) == 3
    assert session.get.call_count == 5


def test_http_error_returns_nothing_without_leaking_key(caplog):
    import requests

    session = MagicMock()
    session.get.side_effect = requests.HTTPError("403 for url ...api-key=SECRET")
    source = NytSource(session=session, api_key="SECRET")
    with caplog.at_level(logging.WARNING):
        assert list(source.fetch_range(datetime(2026, 10, 1), datetime(2026, 10, 31))) == []
        assert source.fetch_recent() == []
    assert "SECRET" not in caplog.text


def test_budget_stops_range_and_recent_keeps_earlier_sections():
    session = MagicMock()
    session.get.return_value.json.return_value = _payload()
    source = NytSource(session=session, api_key="k", budget=lambda: False)
    with pytest.raises(SourceLimitReached):
        list(source.fetch_range(datetime(2026, 10, 1, tzinfo=timezone.utc),
                                datetime(2026, 10, 31, tzinfo=timezone.utc)))
    assert session.get.call_count == 0
    # Top stories: the cap falls after two sections; their items are kept.
    session = MagicMock()
    session.get.return_value.json.return_value = _load("topstories_home.json")
    allowed = iter([True, True, False])
    source = NytSource(session=session, api_key="k", budget=lambda: next(allowed))
    source.fetch_recent()
    assert session.get.call_count == 2


def test_rate_limit_response_raises_limit_reached():
    session = MagicMock()
    response = requests.Response()
    response.status_code = 429
    session.get.side_effect = requests.HTTPError(response=response)
    source = NytSource(session=session, api_key="k")
    with pytest.raises(SourceLimitReached):
        list(source.fetch_range(datetime(2026, 10, 1, tzinfo=timezone.utc),
                                datetime(2026, 10, 31, tzinfo=timezone.utc)))


def test_satisfies_protocol():
    assert isinstance(NytSource(session=MagicMock(), api_key="k"), NewsSource)
