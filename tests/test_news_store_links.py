"""Links stored per story: on insert, in the history run, and the migration (Task 5.2)."""

import importlib.util
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from stock_advisor.news.link import Alias, Linker
from stock_advisor.news.models import NewsItem
from stock_advisor.news.store import NewsStore

_SPEC = importlib.util.spec_from_file_location(
    "link_history", Path(__file__).resolve().parent.parent / "scripts" / "link_history.py"
)
link_history = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(link_history)

LINKER = Linker([
    Alias("0700.HK", "Tencent", "short"),
    Alias("AAPL", "Apple Inc", "name"),
    Alias("oil", "crude oil", "driver"),
])


def _item(n, title, symbols=()):
    return NewsItem(
        id=f"id{n:03d}", source="rss", title=title, url=f"http://x/{n}",
        published_at=datetime(2026, 11, n, 12, tzinfo=timezone.utc), symbols=list(symbols),
    )


def test_new_story_linked_on_insert_and_merged_with_source_symbols(tmp_path):
    with NewsStore(tmp_path / "n.db") as store:
        store.add_items([
            _item(1, "Tencent profit beats forecasts"),
            _item(2, "Crude oil jumps"),
            _item(3, "Weather in Paris"),
            _item(4, "Apple Inc cuts prices", symbols=["MSFT"]),  # the source's symbol is kept
            _item(5, "Quiet day", symbols=["NVDA"]),  # linked by the source alone
        ], LINKER)
        got = {i: store.get_item(i) for i in ("id001", "id002", "id003", "id004", "id005")}
        assert got["id001"].symbols == ["0700.HK"]
        assert got["id004"].symbols == ["MSFT", "AAPL"]
        assert got["id005"].symbols == ["NVDA"]
        assert store.link_counts() == {"linked": 4, "dropped": 1}
        row = store._conn.execute("SELECT drivers, link_state FROM items WHERE id='id002'").fetchone()
        assert (row["drivers"], row["link_state"]) == ('["oil"]', "linked")
        # a dropped story stays stored
        assert store.get_item("id003") is not None


def test_without_linker_stories_stay_unlinked(tmp_path):
    with NewsStore(tmp_path / "n.db") as store:
        store.add_items([_item(1, "Tencent up")])
        assert store.link_counts() == {None: 1}


def test_migration_adds_columns_to_an_old_database(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE items (id TEXT PRIMARY KEY, source TEXT NOT NULL, published_at TEXT NOT NULL,"
        " title TEXT NOT NULL, url TEXT NOT NULL DEFAULT '', summary TEXT NOT NULL DEFAULT '',"
        " symbols TEXT NOT NULL DEFAULT '[]', language TEXT NOT NULL DEFAULT 'en', body TEXT,"
        " time_precision TEXT NOT NULL DEFAULT 'exact', event_items TEXT NOT NULL DEFAULT '[]')"
    )
    conn.execute("INSERT INTO items (id, source, published_at, title) VALUES "
                 "('a', 's', '2026-11-01T00:00:00.000000+00:00', 'Tencent up')")
    conn.commit()
    conn.close()
    with NewsStore(path) as store:
        assert store.link_counts() == {None: 1}
        assert len(store.items_to_link()) == 1


def test_history_run_links_in_batches_and_resumes(tmp_path):
    with NewsStore(tmp_path / "n.db") as store:
        store.add_items([_item(n, t) for n, t in enumerate(
            ["Tencent up", "Paris weather", "Crude oil falls", "Dog show", "Apple Inc news"], 1)])
        # first run stops after one batch of 2 (simulated by linking two by hand)
        first = store.items_to_link(limit=2)
        store.set_links([(i.id, [], []) for i in first])
        assert link_history.link_history(store, LINKER, batch=2) == 3
        assert link_history.link_history(store, LINKER, batch=2) == 0  # a rerun does nothing
        stats = link_history.summary(store)
        assert (stats["total"], stats["unlinked"]) == (5, 0)
        assert stats["linked"] == 2 and stats["dropped"] == 3  # the two hand-set rows stay dropped
        assert dict(stats["per_symbol"]) == {"AAPL": 1}


def test_report_has_counts_and_samples(tmp_path):
    with NewsStore(tmp_path / "n.db") as store:
        store.add_items([_item(1, "Tencent up"), _item(2, "Dog show")], LINKER)
        path = link_history.write_report(
            store, link_history.summary(store), tmp_path / "rep", today=datetime(2026, 11, 17).date()
        )
    text = path.read_text(encoding="utf-8")
    assert path.name == "news-links-2026-11-17.md"
    assert "Stories total: 2" in text and "Tencent up" in text and "Dog show" in text
    assert "- 0700.HK: 1" in text
