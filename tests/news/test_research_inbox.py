"""Tests for the research-inbox adapter, on a hand-written file. No network."""

import logging
from pathlib import Path

import pytest

from stock_advisor.news.link import build_linker
from stock_advisor.news.sources import PoliteSession
from stock_advisor.news.sources.research_inbox import ResearchInboxSource
from stock_advisor.news.store import NewsStore

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "news" / "research_inbox" / "items.jsonl"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("research_inbox must not use PoliteSession")
    monkeypatch.setattr(PoliteSession, "get", refuse)


def test_only_stock_items_with_usable_status(caplog):
    with caplog.at_level(logging.WARNING):
        items = ResearchInboxSource(FIXTURE).fetch_recent()
    assert [i.title for i in items] == ["Chip makers face new export rule", "Caption only post"]
    assert sum("unreadable line" in r.message for r in caplog.records) == 1


def test_fields_map():
    first = ResearchInboxSource(FIXTURE).fetch_recent()[0]
    assert first.source == "research_inbox"
    assert first.url == "https://example.com/a"
    assert first.summary == "Export limits widen.\nSuppliers react.\nTopics: chips, regulation"
    assert first.body == "stock Tencent"
    assert first.published_at.isoformat() == "2026-11-26T08:00:00+00:00"
    assert first.time_precision == "exact" and first.language == "en"


def test_stored_once_and_linked(tmp_path):
    linker = build_linker()
    items = ResearchInboxSource(FIXTURE).fetch_recent()
    with NewsStore(tmp_path / "n.db") as store:
        assert store.add_items(items, linker) == 2
        assert store.add_items(ResearchInboxSource(FIXTURE).fetch_recent(), linker) == 0
        rows = {i.title: i for i in store.query_items(source="research_inbox")}
        assert "0700.HK" in rows["Chip makers face new export rule"].symbols
        states = store._conn.execute("SELECT title, link_state FROM items").fetchall()
    assert dict(states)["Caption only post"] == "dropped"
    assert dict(states)["Chip makers face new export rule"] == "linked"


def test_missing_file_returns_empty_and_logs_once(tmp_path, caplog):
    source = ResearchInboxSource(tmp_path / "nope.jsonl")
    with caplog.at_level(logging.WARNING):
        assert source.fetch_recent() == [] and source.fetch_recent() == []
    assert len(caplog.records) == 1


def test_env_path(monkeypatch):
    monkeypatch.setenv("RESEARCH_INBOX_ITEMS", str(FIXTURE))
    assert len(ResearchInboxSource().fetch_recent()) == 2
