"""Guardian adapter tests: parse a saved response, paging and the missing-key behaviour."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

from stock_advisor.news.models import SourceLimitReached
from stock_advisor.news.sources.guardian import GuardianSource, parse_response

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "news" / "guardian" / "search_business.json"


def _payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class FakeHttp:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(kwargs["params"])
        payload = self.payloads.pop(0)

        class Resp:
            def json(self_inner):
                return payload

        return Resp()


def test_parse_fixture():
    items = parse_response(_payload())
    assert len(items) == 5
    first = items[0]
    assert first.source == "guardian"
    assert first.published_at == datetime(2020, 3, 9, 0, 1, 48, tzinfo=timezone.utc)
    assert first.url.startswith("https://www.theguardian.com/business/")
    assert first.summary.startswith("Severe rain in February")
    assert not first.summary.endswith(" ")  # trailing space in the real trailText is stripped


def test_parse_skips_rows_without_title():
    payload = _payload()
    payload["response"]["results"][0]["webTitle"] = ""
    assert len(parse_response(payload)) == 4


def test_fetch_range_pages_and_trims():
    page1 = _payload()
    page1["response"]["pages"] = 2
    page2 = _payload()
    page2["response"]["currentPage"] = 2
    page2["response"]["pages"] = 2
    http = FakeHttp([page1, page2])
    source = GuardianSource(api_key="k", session=http)
    start = datetime(2020, 3, 9, 5, 0, tzinfo=timezone.utc)
    end = datetime(2020, 3, 10, tzinfo=timezone.utc)
    items = list(source.fetch_range(start, end))
    assert [c["page"] for c in http.calls] == [1, 2]
    assert http.calls[0]["order-by"] == "oldest"
    assert http.calls[0]["page-size"] == 200
    assert "us-news" in http.calls[0]["section"]
    assert len(items) == 6  # three items after 05:00 per page; 00:01 and 03:00 trimmed
    assert all(i.published_at >= start for i in items)


def test_missing_key_warns_once_and_returns_nothing(caplog):
    http = FakeHttp([])
    source = GuardianSource(api_key="", session=http)
    with caplog.at_level(logging.WARNING):
        assert source.fetch_recent() == []
        assert list(source.fetch_range(datetime(2020, 1, 1), datetime(2020, 2, 1))) == []
    assert http.calls == []
    assert sum("GUARDIAN_API_KEY" in r.message for r in caplog.records) == 1


def test_budget_stops_before_the_call_that_would_exceed_it():
    page = _payload()
    page["response"]["pages"] = 3
    http = FakeHttp([page, page, page])
    allowed = iter([True, False])
    source = GuardianSource(api_key="k", session=http, budget=lambda: next(allowed))
    got = []
    with pytest.raises(SourceLimitReached):
        for item in source.fetch_range(datetime(2020, 3, 9, tzinfo=timezone.utc),
                                       datetime(2020, 3, 10, tzinfo=timezone.utc)):
            got.append(item)
    assert len(http.calls) == 1  # the second call never went out
    assert got  # items of the first page were already yielded


def test_rate_limit_response_raises_limit_reached():
    class Limited:
        def get(self, url, **kwargs):
            response = requests.Response()
            response.status_code = 429
            raise requests.HTTPError(response=response)

    source = GuardianSource(api_key="k", session=Limited())
    with pytest.raises(SourceLimitReached):
        source.fetch_recent()


def test_fetch_recent_single_page():
    page = _payload()
    page["response"]["pages"] = 5
    http = FakeHttp([page])
    items = GuardianSource(api_key="k", session=http).fetch_recent()
    assert len(items) == 5
    assert len(http.calls) == 1
    assert http.calls[0]["order-by"] == "newest"
