"""Guardian adapter tests: parse a saved response, paging and the missing-key behaviour."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

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
    assert len(items) == 2  # the blank-title live blog is skipped
    first = items[0]
    assert first.source == "guardian"
    assert first.published_at == datetime(2020, 3, 9, 6, 12, 45, tzinfo=timezone.utc)
    assert first.url.startswith("https://www.theguardian.com/business/")
    assert items[1].summary == "Coronavirus fears and the oil rout hit markets & investors."


def test_fetch_range_pages_and_trims():
    page1 = _payload()
    page1["response"]["pages"] = 2
    page2 = _payload()
    page2["response"]["currentPage"] = 2
    http = FakeHttp([page1, page2])
    source = GuardianSource(api_key="k", session=http)
    start = datetime(2020, 3, 9, 8, 0, tzinfo=timezone.utc)
    end = datetime(2020, 3, 10, tzinfo=timezone.utc)
    items = list(source.fetch_range(start, end))
    assert [c["page"] for c in http.calls] == [1, 2]
    assert http.calls[0]["order-by"] == "oldest"
    assert http.calls[0]["page-size"] == 200
    assert "us-news" in http.calls[0]["section"]
    assert len(items) == 2  # one 09:30 item per page; 06:12 trimmed
    assert all(i.published_at >= start for i in items)


def test_missing_key_warns_once_and_returns_nothing(caplog):
    http = FakeHttp([])
    source = GuardianSource(api_key="", session=http)
    with caplog.at_level(logging.WARNING):
        assert source.fetch_recent() == []
        assert list(source.fetch_range(datetime(2020, 1, 1), datetime(2020, 2, 1))) == []
    assert http.calls == []
    assert sum("GUARDIAN_API_KEY" in r.message for r in caplog.records) == 1


def test_fetch_recent_single_page():
    page = _payload()
    page["response"]["pages"] = 5
    http = FakeHttp([page])
    items = GuardianSource(api_key="k", session=http).fetch_recent()
    assert len(items) == 2
    assert len(http.calls) == 1
    assert http.calls[0]["order-by"] == "newest"
