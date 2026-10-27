"""GDELT adapter tests: parse a saved real response; no network access."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from stock_advisor.news.sources import NewsSource
from stock_advisor.news.sources.gdelt import MAX_RECORDS, GdeltSource, clean_title

FIXTURE = Path(__file__).parent.parent / "fixtures" / "news" / "gdelt" / "artlist_tariffs.json"
RATE_LIMIT_TEXT = "Please limit requests to one every 5 seconds or contact someone."


class FakeResponse:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("bad", response=self)


class FakeSession:
    """Returns queued replies (str or Exception) and records each call's params."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def get(self, url, params=None, **kwargs):
        self.calls.append(params)
        reply = self.replies.pop(0) if self.replies else '{"articles": []}'
        if isinstance(reply, Exception):
            raise reply
        return FakeResponse(reply)


def make_source(replies, queries=None, sleeps=None):
    sleeps = sleeps if sleeps is not None else []
    return GdeltSource(
        session=FakeSession(replies),
        queries=queries or {"t": "tariffs"},
        sleep=sleeps.append,
    )


def article(n, seen="20261027T051500Z"):
    return {"url": f"http://x/{n}", "title": f"T{n}", "seendate": seen, "domain": "x.com"}


def test_parses_fixture():
    source = make_source([FIXTURE.read_text(encoding="utf-8")])
    items = source.fetch_recent()
    assert isinstance(source, NewsSource)
    assert len(items) == 5
    first = items[0]
    assert first.source == "gdelt"
    assert first.published_at == datetime(2026, 10, 27, 5, 15, tzinfo=timezone.utc)
    assert first.title and first.url.startswith("http")
    assert source.session.calls[0]["timespan"] == "1d"
    assert source.session.calls[0]["query"].endswith("sourcelang:english")
    assert source.session.calls[0]["format"] == "json"


def test_title_spacing_is_normalised():
    assert clean_title("Stocks fall  , oil rises .") == "Stocks fall, oil rises."
    assert clean_title("  Fed   holds rates ; markets calm ! ") == "Fed holds rates; markets calm!"
    assert clean_title("Already clean, fine.") == "Already clean, fine."
    reply = json.dumps({"articles": [
        {"url": "http://x/1", "title": "War  talks , again .", "seendate": "20261027T051500Z"}]})
    [item] = make_source([reply]).fetch_recent()
    assert item.title == "War talks, again."


def test_fetch_recent_dedups_across_queries():
    body = FIXTURE.read_text(encoding="utf-8")
    source = make_source([body, body], queries={"a": "x", "b": "y"})
    assert len(source.fetch_recent()) == 5


def test_rate_limit_text_waits_and_retries():
    sleeps = []
    source = make_source([RATE_LIMIT_TEXT, FIXTURE.read_text(encoding="utf-8")], sleeps=sleeps)
    assert len(source.fetch_recent()) == 5
    assert sleeps == [30.0]


def test_rate_limit_429_retries_then_gives_up():
    err = requests.HTTPError("429", response=FakeResponse("", 429))
    sleeps = []
    source = make_source([err, err, err], sleeps=sleeps)
    assert source.fetch_recent() == []
    assert len(sleeps) == 3


def test_other_error_returns_nothing():
    err = requests.HTTPError("500", response=FakeResponse("", 500))
    assert make_source([err]).fetch_recent() == []


def test_empty_and_bad_replies():
    assert make_source([""]).fetch_recent() == []
    assert make_source(["The specified phrase is too short."]).fetch_recent() == []
    assert make_source(["{not json"]).fetch_recent() == []


def test_fetch_range_uses_datetime_windows():
    source = make_source(['{"articles": []}'] * 2)
    source.window = timedelta(days=7)
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    list(source.fetch_range(start, start + timedelta(days=10)))
    calls = source.session.calls
    assert [c["startdatetime"] for c in calls] == ["20240101000000", "20240108000000"]
    assert [c["enddatetime"] for c in calls] == ["20240108000000", "20240111000000"]


def test_fetch_range_splits_full_window():
    import json

    full = json.dumps({"articles": [article(i) for i in range(MAX_RECORDS)]})
    half = json.dumps({"articles": [article(1000), article(1001)]})
    source = make_source([full, half, half])
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    items = list(source.fetch_range(start, start + timedelta(days=1)))
    calls = source.session.calls
    assert len(calls) == 3
    assert calls[1]["startdatetime"] == "20240101000000"
    assert calls[1]["enddatetime"] == "20240101120000"
    assert calls[2]["startdatetime"] == "20240101120000"
    assert len(items) == 2  # the two halves return the same articles; de-duplicated
