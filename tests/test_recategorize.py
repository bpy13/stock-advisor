"""Tests for scripts/recategorize_news.py, on a synthetic tmp_path store."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from stock_advisor.news.models import ItemScore, NewsItem
from stock_advisor.news.scoring import embedding_to_bytes
from stock_advisor.news.store import NewsStore

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "recategorize_news.py"
_spec = importlib.util.spec_from_file_location("recategorize_news", _SCRIPT)
recat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recat)

T0 = datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)


def fake_categorize(titles, embeddings=None, embedder=None):
    """Stand-in for the embedding model: 'stock' headlines are now 'other', the rest war."""
    assert embeddings is not None and embeddings.shape == (len(titles), 384)
    return ["other" if "stock" in t else "war_conflict" for t in titles]


@pytest.fixture(autouse=True)
def no_model(monkeypatch):
    monkeypatch.setattr(recat, "categorize", fake_categorize)


def add(store, n, title, category, event_id=None, tone=0.0, source="nyt"):
    item = NewsItem(source=source, published_at=T0 + timedelta(minutes=n), title=title,
                    url=f"https://example.com/{n}")
    store.add_items([item])
    vec = np.random.default_rng(n).normal(size=384).astype(np.float32)
    store.update_scores(ItemScore(item_id=item.id, tone=tone, category=category,
                                  embedding=embedding_to_bytes(vec), event_id=event_id))
    return item.id


def build(store):
    """Event e1 (3 sources, all 'war_conflict' -> high impact) has one headline that the new
    rules call 'other'. Event e2 stays as it is. One row has no category yet."""
    a = add(store, 1, "troops cross border", "war_conflict", "e1", source="nyt")
    b = add(store, 2, "why is X stock down", "war_conflict", "e1", source="guardian")
    c = add(store, 3, "troops advance", "war_conflict", "e1", source="rss")
    d = add(store, 4, "stock rally", "other", "e2")
    e = add(store, 5, "pending", None)
    store._conn.execute(
        "INSERT INTO events (id, started_at, category, title, n_items, n_sources, high_impact) "
        "VALUES ('e1', ?, 'war_conflict', 't', 3, 3, 1), ('e2', ?, 'other', 't', 1, 1, 0)",
        (T0.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00"),) * 2,
    )
    store._conn.execute("UPDATE scores SET high_impact = 1 WHERE event_id = 'e1'")
    store._conn.commit()
    return a, b, c, d, e


def test_dry_run_writes_nothing(tmp_path):
    db = tmp_path / "news.db"
    with NewsStore(db) as store:
        a, b, c, d, e = build(store)
    logs = []
    lock = tmp_path / "backfill.lock"
    assert recat.run(db, True, chunk_size=2, lock_path=lock, log=logs.append) == 0
    text = "\n".join(logs)
    assert "war_conflict -> other: 1" in text
    assert "Dry run" in text
    with NewsStore(db) as store:
        assert store.get_score(b).category == "war_conflict"
        assert store.get_event("e1").high_impact is True


def test_real_run_updates_changed_rows_and_events(tmp_path):
    db = tmp_path / "news.db"
    with NewsStore(db) as store:
        a, b, c, d, e = build(store)
        # stock rally is 'other' already; make the old rules disagree for one more row.
        store.set_category(d, "financial_crisis")
    logs = []
    lock = tmp_path / "backfill.lock"
    assert recat.run(db, False, chunk_size=2, lock_path=lock, log=logs.append) == 0
    assert not lock.exists()  # released
    with NewsStore(db) as store:
        assert store.get_score(b).category == "other"
        assert store.get_score(a).category == "war_conflict"
        assert store.get_score(d).category == "other"
        assert store.get_score(e).category is None  # uncategorized rows are not touched
        # e1: majority is still war_conflict, 3 sources: stays high impact.
        assert store.get_event("e1").category == "war_conflict"
        assert store.get_event("e1").high_impact is True
        assert store.get_score(a).high_impact is True
        # Row counts did not change.
        assert store.count_items() == 5
        assert len(store.query_events()) == 2
        # Items the run did not touch keep their embeddings.
        assert store.get_score(a).embedding is not None
    assert "After:" in "\n".join(logs)


def test_event_flag_drops_when_majority_category_changes(tmp_path):
    db = tmp_path / "news.db"
    with NewsStore(db) as store:
        ids = [add(store, n, "why is X stock down", "war_conflict", "e1", source=f"s{n}")
               for n in range(1, 4)]
        store._conn.execute(
            "INSERT INTO events (id, started_at, category, title, n_items, n_sources, high_impact)"
            " VALUES ('e1', ?, 'war_conflict', 't', 3, 3, 1)",
            (T0.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00"),),
        )
        store._conn.execute("UPDATE scores SET high_impact = 1")
        store._conn.commit()
    assert recat.run(db, False, lock_path=tmp_path / "b.lock", log=lambda _: None) == 0
    with NewsStore(db) as store:
        event = store.get_event("e1")
        assert (event.category, event.high_impact, event.n_items) == ("other", False, 3)
        assert not any(store.get_score(i).high_impact for i in ids)


def test_real_run_refuses_while_lock_is_held(tmp_path):
    import os

    db = tmp_path / "news.db"
    with NewsStore(db) as store:
        b = build(store)[1]
    lock = tmp_path / "backfill.lock"
    lock.write_text(str(os.getpid()), encoding="utf-8")  # this process is alive
    logs = []
    assert recat.run(db, False, lock_path=lock, log=logs.append) == 2
    assert lock.exists()  # not removed by the refused run
    with NewsStore(db) as store:
        assert store.get_score(b).category == "war_conflict"
    # A dry run still works with the lock present.
    assert recat.run(db, True, lock_path=lock, log=lambda _: None) == 0
