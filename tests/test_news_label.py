"""Tests for the Claude labeller (news/label.py) with a fake client: no network, no key."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from stock_advisor.news import label as lab
from stock_advisor.news.models import NewsItem
from stock_advisor.news.store import NewsStore

NOW = datetime(2026, 11, 17, 9, 0, tzinfo=timezone.utc)
GOOD = {"relevant": True, "event_type": "results", "novelty": "new", "severity": 2}
NAMES = {"0700.HK": "Tencent Holdings", "AAPL": "Apple Inc."}


class FakeClient:
    """Stands in for anthropic.Anthropic(): returns queued answers and records each request."""

    def __init__(self, answers, tokens_in=400, tokens_out=30):
        self.answers = list(answers)
        self.requests = []
        self.messages = SimpleNamespace(create=self._create)
        self.tokens = (tokens_in, tokens_out)

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        answer = self.answers.pop(0)
        text = answer if isinstance(answer, str) else json.dumps(answer)
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(input_tokens=self.tokens[0], output_tokens=self.tokens[1]),
        )


@pytest.fixture
def store(tmp_path):
    with NewsStore(tmp_path / "news.db") as s:
        yield s


def _item(title="Tencent profit beats forecasts", symbols=("0700.HK",)) -> NewsItem:
    return NewsItem(
        source="yahoo", published_at=NOW, title=title, url=f"https://x/{title}",
        summary="Quarterly profit rose 20%.", symbols=list(symbols),
    )


def _run(store, items, client, **kw):
    return lab.label_items(store, items, NAMES, client=client, now=lambda: NOW, **kw)


def test_one_story_gives_one_label_row_with_tokens_and_cost(store):
    item = _item()
    store.add_items([item])
    run = _run(store, [item], FakeClient([GOOD]))

    row = store.get_label(item.id, lab.PROMPT_VERSION)
    assert row["status"] == "ok"
    assert (row["relevant"], row["event_type"], row["novelty"], row["severity"]) == (
        1, "results", "new", 2
    )
    assert (row["tokens_in"], row["tokens_out"]) == (400, 30)
    # 400 * 0.10 / 1e6 + 30 * 0.50 / 1e6 = 0.000055
    assert row["cost_usd"] == pytest.approx(0.000055)
    assert row["model"] == "claude-haiku-5-5"
    assert run.labelled == 1 and run.cost_usd == pytest.approx(0.000055)


def test_request_uses_structured_output_and_holds_only_the_story(store):
    item = _item()
    client = FakeClient([GOOD])
    _run(store, [item], client)

    request = client.requests[0]
    assert request["model"] == "claude-haiku-5-5"
    assert request["output_config"]["format"]["schema"] == lab.LABEL_SCHEMA
    prompt = request["messages"][0]["content"]
    assert "Tencent profit beats forecasts" in prompt
    assert "Quarterly profit rose 20%." in prompt
    assert "0700.HK: Tencent Holdings" in prompt
    assert "AAPL" not in prompt  # only the linked symbols, not the whole names map


def test_malformed_answer_is_retried_once_then_accepted(store):
    item = _item()
    client = FakeClient(["not json", GOOD])
    run = _run(store, [item], client)

    assert len(client.requests) == 2
    row = store.get_label(item.id, lab.PROMPT_VERSION)
    assert row["status"] == "ok"
    assert row["tokens_in"] == 800  # both requests are paid for and recorded
    assert run.labelled == 1 and run.errors == 0


def test_two_malformed_answers_store_an_error_never_a_guess(store):
    item = _item()
    bad_type = dict(GOOD, event_type="earnings")  # outside the fixed list
    client = FakeClient(["{oops", bad_type])
    run = _run(store, [item], client)

    assert len(client.requests) == 2
    row = store.get_label(item.id, lab.PROMPT_VERSION)
    assert row["status"] == "error"
    assert row["relevant"] is None and row["event_type"] is None and row["severity"] is None
    assert row["cost_usd"] > 0
    assert run.errors == 1 and run.labelled == 0


@pytest.mark.parametrize("answer", [
    dict(GOOD, severity=4),
    dict(GOOD, severity=True),
    dict(GOOD, relevant="yes"),
    dict(GOOD, novelty="old"),
    dict(GOOD, extra=1),
    {k: v for k, v in GOOD.items() if k != "novelty"},
    "[1, 2]",
])
def test_parse_label_rejects_anything_outside_the_schema(answer):
    text = answer if isinstance(answer, str) else json.dumps(answer)
    assert lab.parse_label(text) is None


def test_cut_off_or_refused_answer_counts_as_malformed(store):
    item = _item()
    client = FakeClient([GOOD, GOOD])
    original = client._create

    def refuse_first(**kwargs):
        response = original(**kwargs)
        if len(client.requests) == 1:
            response.stop_reason = "max_tokens"
        return response

    client.messages.create = refuse_first
    run = _run(store, [item], client)
    assert len(client.requests) == 2 and run.labelled == 1


def test_ceiling_stops_every_paid_call_and_logs(store, caplog):
    first, second = _item("A"), _item("B")
    # Spend already at the ceiling this month (an earlier story).
    store.add_label("earlier", lab.PROMPT_VERSION, lab.MODEL, GOOD, 0, 0, 10.0, NOW)
    client = FakeClient([GOOD, GOOD])
    with caplog.at_level(logging.WARNING):
        run = _run(store, [first, second], client, ceiling_usd=10.0)

    assert client.requests == []
    assert run.stopped_at_ceiling and run.labelled == 0
    assert store.get_label(first.id, lab.PROMPT_VERSION) is None
    assert "ceiling" in caplog.text


def test_ceiling_counts_only_the_current_month(store):
    last_month = datetime(2026, 10, 31, 23, 0, tzinfo=timezone.utc)
    store.add_label("old", lab.PROMPT_VERSION, lab.MODEL, GOOD, 0, 0, 10.0, last_month)
    client = FakeClient([GOOD])
    run = _run(store, [_item()], client, ceiling_usd=10.0)
    assert run.labelled == 1


def test_ceiling_reached_mid_run_stops_the_rest(store):
    items = [_item(t) for t in ("A", "B", "C")]
    # Each story costs 1000 * 0.10/1e6 + 0 = US$0.0001; a ceiling of 0.00015 allows two.
    client = FakeClient([GOOD] * 3, tokens_in=1000, tokens_out=0)
    run = _run(store, items, client, ceiling_usd=0.00015)
    assert run.labelled == 2 and run.stopped_at_ceiling
    assert len(client.requests) == 2


def test_ceiling_setting_defaults_to_ten(monkeypatch):
    monkeypatch.setattr(lab, "get_setting", lambda name: "")
    assert lab.monthly_ceiling_usd() == 10.0
    monkeypatch.setattr(lab, "get_setting", lambda name: "2.5")
    assert lab.monthly_ceiling_usd() == 2.5
    monkeypatch.setattr(lab, "get_setting", lambda name: "lots")
    assert lab.monthly_ceiling_usd() == 10.0


def test_story_already_labelled_with_same_version_is_not_sent_again(store):
    item = _item()
    _run(store, [item], FakeClient([GOOD]))
    client = FakeClient([GOOD])
    run = _run(store, [item], client)
    assert client.requests == [] and run.skipped == 1


def test_new_prompt_version_labels_again(store, monkeypatch):
    item = _item()
    _run(store, [item], FakeClient([GOOD]))
    monkeypatch.setattr(lab, "PROMPT_VERSION", "v2")
    client = FakeClient([GOOD])
    run = _run(store, [item], client)
    assert len(client.requests) == 1 and run.labelled == 1
