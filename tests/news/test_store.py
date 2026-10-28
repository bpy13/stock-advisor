"""Tests for the news store, models, settings and the polite-HTTP helper (no network)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
import requests

from stock_advisor.news import settings
from stock_advisor.news.models import Event, ItemScore, NewsItem, make_item_id
from stock_advisor.news.sources import NewsSource, PoliteSession
from stock_advisor.news.store import NewsStore

T0 = datetime(2024, 3, 1, 12, 0, tzinfo=timezone.utc)


def _item(source="wiki", minutes=0, title="Stocks fall", url=None, **kw) -> NewsItem:
    if url is None:
        url = f"https://example.com/{source}/{title.replace(' ', '-')}/{minutes}"
    return NewsItem(
        source=source,
        published_at=T0 + timedelta(minutes=minutes),
        title=title,
        url=url,
        **kw,
    )


@pytest.fixture
def store(tmp_path):
    with NewsStore(tmp_path / "news.db") as s:
        yield s


def test_wal_mode_lets_a_second_connection_read_during_a_write(tmp_path):
    import sqlite3

    path = tmp_path / "news.db"
    with NewsStore(path) as s:
        s.add_items([_item()])
    writer = NewsStore(path)
    reader = sqlite3.connect(str(path), timeout=1)
    try:
        assert writer._conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        before = reader.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        writer._conn.execute("BEGIN IMMEDIATE")  # the writer now holds an open write
        writer._conn.execute("DELETE FROM items")
        # In the default journal mode this read would fail with "database is locked".
        assert reader.execute("SELECT COUNT(*) FROM items").fetchone()[0] == before
        writer._conn.rollback()
    finally:
        reader.close()
        writer.close()


# ---- models ----------------------------------------------------------------------------


def test_id_is_stable_and_depends_on_source_and_url():
    a = make_item_id("wiki", "http://x", "t", T0)
    assert a == make_item_id("wiki", "http://x", "other title", T0 + timedelta(days=1))
    assert a != make_item_id("gdelt", "http://x", "t", T0)
    assert len(a) == 40


def test_id_without_url_uses_title_and_time():
    a = make_item_id("wiki", "", "War starts", T0)
    assert a != make_item_id("wiki", "", "War ends", T0)
    assert a != make_item_id("wiki", "", "War starts", T0 + timedelta(seconds=1))


def test_naive_datetime_becomes_utc():
    item = NewsItem(source="s", published_at=datetime(2024, 1, 1), title="t")
    assert item.published_at.tzinfo is not None
    assert item.published_at.utcoffset() == timedelta(0)


# ---- store -----------------------------------------------------------------------------


def test_insert_and_roundtrip(store):
    item = _item(symbols=["^HSI", "0005.HK"], summary="s", language="en", body="full text")
    assert store.add_items([item]) == 1
    got = store.get_item(item.id)
    assert got == item
    assert got.published_at.tzinfo is not None


def test_duplicates_are_ignored(store):
    item = _item()
    assert store.add_items([item, item]) == 1
    assert store.add_items([_item()]) == 0
    assert store.count_items() == 1


def test_query_by_time_range_and_source(store):
    store.add_items(
        [
            _item("wiki", 0, "a"),
            _item("wiki", 60, "b"),
            _item("gdelt", 30, "c"),
            _item("gdelt", 120, "d"),
        ]
    )
    window = store.query_items(start=T0 + timedelta(minutes=30), end=T0 + timedelta(minutes=120))
    assert [i.title for i in window] == ["c", "b"]  # end is exclusive, oldest first
    assert [i.title for i in store.query_items(source="gdelt")] == ["c", "d"]
    only = store.query_items(source="wiki", start=T0 + timedelta(minutes=1))
    assert [i.title for i in only] == ["b"]
    assert len(store.query_items(limit=2)) == 2
    assert store.count_items("wiki") == 2
    assert store.counts_by_source() == {"wiki": 2, "gdelt": 2}


def test_latest_and_earliest_published(store):
    assert store.latest_published("wiki") is None
    store.add_items([_item("wiki", 0, "a"), _item("wiki", 90, "b")])
    assert store.latest_published("wiki") == T0 + timedelta(minutes=90)
    assert store.earliest_published("wiki") == T0


def test_update_scores_and_unscored(store):
    a, b = _item(title="a"), _item(title="b", minutes=1)
    store.add_items([a, b])
    assert {i.id for i in store.unscored_items()} == {a.id, b.id}

    store.update_scores(
        ItemScore(a.id, tone_pos=0.1, tone_neg=0.7, tone_neu=0.2, tone=-0.6)
    )
    assert [i.id for i in store.unscored_items()] == [b.id]
    score = store.get_score(a.id)
    assert score.tone == pytest.approx(-0.6)
    assert score.category is None
    assert score.high_impact is False

    # A later step fills other fields without wiping the tone.
    store.update_scores(
        ItemScore(a.id, category="war_conflict", embedding=b"\x00\x01", event_id="e1",
                  high_impact=True)
    )
    score = store.get_score(a.id)
    assert score.tone == pytest.approx(-0.6)
    assert score.category == "war_conflict"
    assert score.embedding == b"\x00\x01"
    assert score.event_id == "e1"
    assert score.high_impact is True
    assert [i.id for i in store.items_for_event("e1")] == [a.id]
    assert store.get_score("missing") is None


def test_items_awaiting_category_and_set_category(store):
    a, b, c = _item(title="a"), _item(title="b", minutes=1), _item(title="c", minutes=2)
    store.add_items([a, b, c])
    store.update_scores(ItemScore(a.id, embedding=b"\x01", high_impact=True))
    store.update_scores(ItemScore(b.id, embedding=b"\x02", category="other"))
    store.update_scores(ItemScore(c.id, tone=0.1))  # no embedding

    waiting = store.items_awaiting_category()
    assert [(i.id, emb) for i, emb in waiting] == [(a.id, b"\x01")]
    assert store.items_awaiting_category(limit=0) == []

    store.set_category(a.id, "war_conflict")
    score = store.get_score(a.id)
    assert score.category == "war_conflict"
    assert score.high_impact is True  # untouched
    assert score.embedding == b"\x01"
    assert store.items_awaiting_category() == []


def test_categorized_chunk_pages_and_set_categories(store):
    items = [_item(title=f"t{n}", minutes=n) for n in range(5)]
    store.add_items(items)
    for n, it in enumerate(items):
        category = None if n == 4 else "other"
        emb = None if n == 3 else bytes([n])
        store.update_scores(ItemScore(it.id, category=category, embedding=emb, event_id="e1",
                                      high_impact=True))
    # Rows 3 (no embedding) and 4 (no category) are left out.
    seen, after = [], ""
    while True:
        page = store.categorized_chunk(after, 2)
        if not page:
            break
        seen += page
        after = page[-1][0]
    assert sorted(r[0] for r in seen) == sorted(it.id for it in items[:3])
    assert all(r[3] == "other" and r[4] == "e1" for r in seen)
    assert {r[1] for r in seen} == {"t0", "t1", "t2"}

    store.set_categories([(items[0].id, "war_conflict"), (items[1].id, "terrorism")])
    assert store.get_score(items[0].id).category == "war_conflict"
    assert store.get_score(items[1].id).category == "terrorism"
    assert store.get_score(items[0].id).high_impact is True  # untouched
    store.set_categories([])  # no-op


def test_events_roundtrip_and_query(store):
    e1 = Event(id="e1", started_at=T0, category="war_conflict", title="War", n_items=3,
               n_sources=2, high_impact=True)
    e2 = Event(id="e2", started_at=T0 + timedelta(days=1), category="other")
    store.upsert_event(e1)
    store.upsert_event(e2)
    assert store.get_event("e1") == e1
    assert [e.id for e in store.query_events()] == ["e1", "e2"]
    assert [e.id for e in store.query_events(start=T0 + timedelta(hours=1))] == ["e2"]
    assert [e.id for e in store.query_events(high_impact_only=True)] == ["e1"]
    e1.n_items = 5
    store.upsert_event(e1)
    assert store.get_event("e1").n_items == 5


def test_set_body(store):
    item = _item()
    store.add_items([item])
    store.set_body(item.id, "article text")
    assert store.get_item(item.id).body == "article text"


def test_store_persists_on_disk(tmp_path):
    path = tmp_path / "sub" / "news.db"  # parent folder is created
    with NewsStore(path) as s:
        s.add_items([_item()])
    with NewsStore(path) as s:
        assert s.count_items() == 1


# ---- settings --------------------------------------------------------------------------


def test_settings_read_environment(monkeypatch):
    monkeypatch.setattr(settings, "load_env", lambda env_file=None: None)  # ignore real .env
    monkeypatch.setenv("SEC_CONTACT_EMAIL", " me@example.com ")
    monkeypatch.delenv("GUARDIAN_API_KEY", raising=False)
    assert settings.sec_contact_email() == "me@example.com"
    assert settings.guardian_api_key() == ""


def test_load_env_reads_a_given_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("NYT_API_KEY=abc123\n", encoding="utf-8")
    monkeypatch.delenv("NYT_API_KEY", raising=False)
    settings.load_env(env_file)
    assert os.environ["NYT_API_KEY"] == "abc123"
    monkeypatch.delenv("NYT_API_KEY")  # keep the value out of other tests


# ---- polite session --------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status, headers=None):
        self.status_code = status
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


class _FakeSession:
    def __init__(self, results):
        self.headers = {}
        self.results = list(results)
        self.calls = 0

    def get(self, url, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class _Clock:
    """Fake time: sleeping advances the clock, so the delay logic is checkable."""

    def __init__(self):
        self.now = 100.0
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def _polite(results, **kw):
    clock = _Clock()
    fake = _FakeSession(results)
    session = PoliteSession(session=fake, sleep=clock.sleep, clock=clock.time, **kw)
    return session, fake, clock


def test_polite_session_sets_user_agent_and_timeout():
    session, fake, _ = _polite([_FakeResponse(200)], user_agent="stock_advisor test", timeout=7)
    session.get("http://x")
    assert fake.headers["User-Agent"] == "stock_advisor test"
    assert fake.last_kwargs["timeout"] == 7


def test_polite_session_enforces_minimum_delay():
    session, fake, clock = _polite([_FakeResponse(200)] * 3, min_delay=2.0)
    session.get("http://x")
    assert clock.sleeps == []  # first request goes at once
    session.get("http://x")
    assert clock.sleeps == [pytest.approx(2.0)]
    clock.now += 5  # a slow caller already waited longer than the minimum
    session.get("http://x")
    assert len(clock.sleeps) == 1


def test_polite_session_retries_429_and_5xx_with_backoff():
    session, fake, clock = _polite(
        [_FakeResponse(429), _FakeResponse(503), _FakeResponse(200)],
        min_delay=0, backoff=2.0,
    )
    assert session.get("http://x").status_code == 200
    assert fake.calls == 3
    assert clock.sleeps == [1.0, 2.0]  # backoff ** attempt


def test_polite_session_honours_retry_after():
    session, fake, clock = _polite(
        [_FakeResponse(429, {"Retry-After": "30"}), _FakeResponse(200)], min_delay=0
    )
    session.get("http://x")
    assert clock.sleeps == [30.0]


def test_polite_session_gives_up_after_max_retries():
    session, fake, _ = _polite([_FakeResponse(500)] * 3, min_delay=0, max_retries=2)
    with pytest.raises(requests.HTTPError):
        session.get("http://x")
    assert fake.calls == 3


def test_polite_session_does_not_retry_404():
    session, fake, _ = _polite([_FakeResponse(404)], min_delay=0)
    with pytest.raises(requests.HTTPError):
        session.get("http://x")
    assert fake.calls == 1


def test_polite_session_retries_connection_errors():
    session, fake, _ = _polite(
        [requests.ConnectionError("boom"), _FakeResponse(200)], min_delay=0
    )
    assert session.get("http://x").status_code == 200
    assert fake.calls == 2


def test_news_source_protocol_accepts_a_simple_adapter():
    class Fake:
        name = "fake"

        def fetch_recent(self):
            return []

    assert isinstance(Fake(), NewsSource)
