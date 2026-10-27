"""NYT adapter tests: parsing from a hand-built fixture, no network."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

from stock_advisor.news.sources import NewsSource
from stock_advisor.news.sources.nyt import NytSource, parse_archive

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "news" / "nyt" / "archive_2026_10.json"


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _source(payload: dict, key: str = "k") -> tuple:
    session = MagicMock()
    session.get.return_value.json.return_value = payload
    return NytSource(session=session, api_key=key), session


def test_parse_keeps_wanted_sections_and_front_page():
    items = parse_archive(_payload())
    titles = [i.title for i in items]
    assert len(items) == 5  # the Food article (page 2) is dropped
    assert "A Brooklyn Newcomer Worth the Wait" not in titles
    assert "The Mayor's Last Lap" in titles  # New York section, but print_page 1


def test_parse_fields():
    first = parse_archive(_payload())[0]
    assert first.source == "nyt"
    assert first.title == "Stocks Slide as Yields Climb"
    assert first.summary.startswith("Stocks fell")
    assert first.url.endswith("stocks-yields.html")
    assert first.published_at == datetime(2026, 10, 26, 14, 5, tzinfo=timezone.utc)


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
    start = datetime(2026, 10, 12, tzinfo=timezone.utc)
    end = datetime(2026, 11, 30, tzinfo=timezone.utc)
    items = list(source.fetch_range(start, end))
    urls = [c.args[0] for c in session.get.call_args_list]
    assert urls == [
        "https://api.nytimes.com/svc/archive/v1/2026/10.json",
        "https://api.nytimes.com/svc/archive/v1/2026/11.json",
    ]
    assert session.get.call_args.kwargs["params"] == {"api-key": "k"}
    assert {i.title for i in items} == {
        "Stocks Slide as Yields Climb", "Ceasefire Talks Open in Geneva",
        "Chip Maker Warns on Export Limits", "The Mayor's Last Lap",
    }  # "Spending Bill" (Oct 5) is before start
    assert len(items) == 8  # the mock returns the same month twice


def test_fetch_range_crosses_year_end():
    source, session = _source({"response": {"docs": []}})
    list(source.fetch_range(datetime(2025, 12, 5), datetime(2026, 1, 5)))
    assert [c.args[0].rsplit("v1/", 1)[1] for c in session.get.call_args_list] == [
        "2025/12.json", "2026/1.json",
    ]


def test_fetch_recent_keeps_only_last_24_hours():
    now = datetime.now(timezone.utc)
    payload = {"response": {"docs": [
        {"headline": {"main": "Fresh"}, "pub_date": (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S+0000"),
         "section_name": "World", "print_page": "5", "web_url": "u1"},
        {"headline": {"main": "Stale"}, "pub_date": (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%S+0000"),
         "section_name": "World", "print_page": "5", "web_url": "u2"},
    ]}}
    source, _ = _source(payload)
    assert [i.title for i in source.fetch_recent()] == ["Fresh"]


def test_http_error_returns_nothing_without_leaking_key(caplog):
    import requests

    session = MagicMock()
    session.get.side_effect = requests.HTTPError("403 for url ...api-key=SECRET")
    source = NytSource(session=session, api_key="SECRET")
    with caplog.at_level(logging.WARNING):
        assert list(source.fetch_range(datetime(2026, 10, 1), datetime(2026, 10, 31))) == []
    assert "SECRET" not in caplog.text


def test_satisfies_protocol():
    assert isinstance(NytSource(session=MagicMock(), api_key="k"), NewsSource)
