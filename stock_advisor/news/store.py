"""SQLite store for news items, their scores and the events they form."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Union

from stock_advisor.news.models import Event, ItemScore, NewsItem, ensure_utc
from stock_advisor.news.settings import DEFAULT_DB_PATH

# Fixed-width UTC text so that string order equals time order in SQL comparisons.
_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f+00:00"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    published_at TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    symbols TEXT NOT NULL DEFAULT '[]',
    language TEXT NOT NULL DEFAULT 'en',
    body TEXT,
    time_precision TEXT NOT NULL DEFAULT 'exact'
);
CREATE INDEX IF NOT EXISTS idx_items_time ON items (published_at);
CREATE INDEX IF NOT EXISTS idx_items_source_time ON items (source, published_at);

CREATE TABLE IF NOT EXISTS scores (
    item_id TEXT PRIMARY KEY REFERENCES items (id),
    tone_pos REAL,
    tone_neg REAL,
    tone_neu REAL,
    tone REAL,
    category TEXT,
    embedding BLOB,
    event_id TEXT,
    high_impact INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_scores_event ON scores (event_id);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    category TEXT,
    title TEXT NOT NULL DEFAULT '',
    n_items INTEGER NOT NULL DEFAULT 0,
    n_sources INTEGER NOT NULL DEFAULT 0,
    high_impact INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_events_time ON events (started_at);

-- Calls made to rate-capped APIs, per source and UTC day (see NewsStore.spend_call).
CREATE TABLE IF NOT EXISTS api_calls (
    source TEXT NOT NULL,
    day TEXT NOT NULL,
    calls INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (source, day)
);

-- How far a backfill has got per source. The newest stored item is not enough, because a
-- --recent run stores items from today and would make a backfill skip all of history.
CREATE TABLE IF NOT EXISTS backfill_cursor (
    source TEXT PRIMARY KEY,
    cursor TEXT NOT NULL
);
"""


def _to_text(moment: datetime) -> str:
    return ensure_utc(moment).strftime(_TIME_FORMAT)


def _from_text(text: str) -> datetime:
    return datetime.strptime(text, _TIME_FORMAT).replace(tzinfo=timezone.utc)


def _row_to_item(row: sqlite3.Row) -> NewsItem:
    return NewsItem(
        id=row["id"],
        source=row["source"],
        published_at=_from_text(row["published_at"]),
        title=row["title"],
        url=row["url"],
        summary=row["summary"],
        symbols=json.loads(row["symbols"]),
        language=row["language"],
        body=row["body"],
        time_precision=row["time_precision"],
    )


def _row_to_score(row: sqlite3.Row) -> ItemScore:
    return ItemScore(
        item_id=row["item_id"],
        tone_pos=row["tone_pos"],
        tone_neg=row["tone_neg"],
        tone_neu=row["tone_neu"],
        tone=row["tone"],
        category=row["category"],
        embedding=row["embedding"],
        event_id=row["event_id"],
        high_impact=bool(row["high_impact"]),
    )


def _row_to_event(row: sqlite3.Row) -> Event:
    return Event(
        id=row["id"],
        started_at=_from_text(row["started_at"]),
        category=row["category"],
        title=row["title"],
        n_items=row["n_items"],
        n_sources=row["n_sources"],
        high_impact=bool(row["high_impact"]),
    )


class NewsStore:
    """Thin wrapper over one SQLite file. The path is overridable (tests use tmp_path)."""

    def __init__(self, path: Union[str, Path, None] = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """Bring a database created by an older version up to the current schema."""
        columns = {r["name"] for r in self._conn.execute("PRAGMA table_info(items)")}
        if "time_precision" not in columns:
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE items ADD COLUMN time_precision TEXT NOT NULL DEFAULT 'exact'"
                )
                # Rows stored before the column existed: Wikipedia is always day-only, and
                # an item stamped exactly 00:00:00 UTC from EDGAR had no acceptance time.
                self._conn.execute(
                    "UPDATE items SET time_precision = 'day' WHERE source = 'wikipedia_events' "
                    "OR (source = 'edgar' AND published_at LIKE '%T00:00:00.000000+00:00')"
                )

    def spend_call(self, source: str, cap: int, day: Optional[str] = None) -> bool:
        """Count one API call for `source` today (UTC) unless `cap` calls are already used.
        Returns True when the call may go ahead."""
        day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO api_calls (source, day, calls) VALUES (?, ?, 0)",
                (source, day),
            )
            used = self._conn.execute(
                "UPDATE api_calls SET calls = calls + 1 WHERE source = ? AND day = ? AND calls < ?",
                (source, day, cap),
            ).rowcount
        return used == 1

    def get_backfill_cursor(self, source: str) -> Optional[datetime]:
        row = self._conn.execute(
            "SELECT cursor FROM backfill_cursor WHERE source = ?", (source,)
        ).fetchone()
        return _from_text(row[0]) if row else None

    def advance_backfill_cursor(self, source: str, moment: datetime) -> None:
        """Move the cursor forward; it never moves back."""
        current = self.get_backfill_cursor(source)
        if current is not None and current >= ensure_utc(moment):
            return
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO backfill_cursor (source, cursor) VALUES (?, ?)",
                (source, _to_text(moment)),
            )

    def calls_today(self, source: str, day: Optional[str] = None) -> int:
        day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = self._conn.execute(
            "SELECT calls FROM api_calls WHERE source = ? AND day = ?", (source, day)
        ).fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "NewsStore":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # ---- items -------------------------------------------------------------------------

    def add_items(self, items: Iterable[NewsItem]) -> int:
        """Insert items, skipping ids already stored. Returns how many were new."""
        before = self._conn.total_changes
        with self._conn:
            self._conn.executemany(
                "INSERT OR IGNORE INTO items "
                "(id, source, published_at, title, url, summary, symbols, language, body, "
                "time_precision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        i.id,
                        i.source,
                        _to_text(i.published_at),
                        i.title,
                        i.url,
                        i.summary,
                        json.dumps(list(i.symbols)),
                        i.language,
                        i.body,
                        i.time_precision,
                    )
                    for i in items
                ],
            )
        return self._conn.total_changes - before

    def get_item(self, item_id: str) -> Optional[NewsItem]:
        row = self._conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return _row_to_item(row) if row else None

    def query_items(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        source: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[NewsItem]:
        """Items with start <= published_at < end, oldest first, optionally for one source."""
        clauses, params = [], []
        if start is not None:
            clauses.append("published_at >= ?")
            params.append(_to_text(start))
        if end is not None:
            clauses.append("published_at < ?")
            params.append(_to_text(end))
        if source is not None:
            clauses.append("source = ?")
            params.append(source)
        sql = "SELECT * FROM items"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY published_at, id"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return [_row_to_item(r) for r in self._conn.execute(sql, params)]

    def count_items(self, source: Optional[str] = None) -> int:
        if source is None:
            return self._conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        return self._conn.execute(
            "SELECT COUNT(*) FROM items WHERE source = ?", (source,)
        ).fetchone()[0]

    def latest_published(self, source: str) -> Optional[datetime]:
        """Newest stored publish time for a source (used to resume a backfill)."""
        row = self._conn.execute(
            "SELECT MAX(published_at) FROM items WHERE source = ?", (source,)
        ).fetchone()
        return _from_text(row[0]) if row[0] else None

    def earliest_published(self, source: str) -> Optional[datetime]:
        row = self._conn.execute(
            "SELECT MIN(published_at) FROM items WHERE source = ?", (source,)
        ).fetchone()
        return _from_text(row[0]) if row[0] else None

    def counts_by_source(self) -> dict:
        rows = self._conn.execute("SELECT source, COUNT(*) FROM items GROUP BY source")
        return {r[0]: r[1] for r in rows}

    def set_body(self, item_id: str, body: str) -> None:
        with self._conn:
            self._conn.execute("UPDATE items SET body = ? WHERE id = ?", (body, item_id))

    # ---- scores ------------------------------------------------------------------------

    def update_scores(self, score: ItemScore) -> None:
        """Create or update an item's score row. Only fields that are not None change."""
        values = {
            "tone_pos": score.tone_pos,
            "tone_neg": score.tone_neg,
            "tone_neu": score.tone_neu,
            "tone": score.tone,
            "category": score.category,
            "embedding": score.embedding,
            "event_id": score.event_id,
        }
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO scores (item_id) VALUES (?)", (score.item_id,)
            )
            for column, value in values.items():
                if value is not None:
                    self._conn.execute(
                        f"UPDATE scores SET {column} = ? WHERE item_id = ?",
                        (value, score.item_id),
                    )
            # high_impact is a plain bool, so it always overwrites.
            self._conn.execute(
                "UPDATE scores SET high_impact = ? WHERE item_id = ?",
                (int(score.high_impact), score.item_id),
            )

    def get_score(self, item_id: str) -> Optional[ItemScore]:
        row = self._conn.execute(
            "SELECT * FROM scores WHERE item_id = ?", (item_id,)
        ).fetchone()
        return _row_to_score(row) if row else None

    def unscored_items(self, limit: Optional[int] = None) -> List[NewsItem]:
        """Items with no tone yet (no score row, or a row whose tone is still NULL)."""
        sql = (
            "SELECT i.* FROM items i LEFT JOIN scores s ON s.item_id = i.id "
            "WHERE s.item_id IS NULL OR s.tone IS NULL ORDER BY i.published_at, i.id"
        )
        params: list = []
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return [_row_to_item(r) for r in self._conn.execute(sql, params)]

    def items_awaiting_category(self, limit: Optional[int] = None) -> List[Tuple[NewsItem, bytes]]:
        """(item, embedding bytes) for items that have an embedding but no category yet."""
        sql = (
            "SELECT i.*, s.embedding AS score_embedding FROM items i "
            "JOIN scores s ON s.item_id = i.id "
            "WHERE s.category IS NULL AND s.embedding IS NOT NULL ORDER BY i.published_at, i.id"
        )
        params: list = []
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return [(_row_to_item(r), r["score_embedding"]) for r in self._conn.execute(sql, params)]

    def set_category(self, item_id: str, category: str) -> None:
        """Set only the category of an existing score row. high_impact is left alone."""
        with self._conn:
            self._conn.execute(
                "UPDATE scores SET category = ? WHERE item_id = ?", (category, item_id)
            )

    def items_for_event(self, event_id: str) -> List[NewsItem]:
        rows = self._conn.execute(
            "SELECT i.* FROM items i JOIN scores s ON s.item_id = i.id "
            "WHERE s.event_id = ? ORDER BY i.published_at, i.id",
            (event_id,),
        )
        return [_row_to_item(r) for r in rows]

    # ---- events ------------------------------------------------------------------------

    def upsert_event(self, event: Event) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO events "
                "(id, started_at, category, title, n_items, n_sources, high_impact) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    event.id,
                    _to_text(event.started_at),
                    event.category,
                    event.title,
                    event.n_items,
                    event.n_sources,
                    int(event.high_impact),
                ),
            )

    def get_event(self, event_id: str) -> Optional[Event]:
        row = self._conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return _row_to_event(row) if row else None

    def query_events(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        high_impact_only: bool = False,
    ) -> List[Event]:
        clauses, params = [], []
        if start is not None:
            clauses.append("started_at >= ?")
            params.append(_to_text(start))
        if end is not None:
            clauses.append("started_at < ?")
            params.append(_to_text(end))
        if high_impact_only:
            clauses.append("high_impact = 1")
        sql = "SELECT * FROM events"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY started_at, id"
        return [_row_to_event(r) for r in self._conn.execute(sql, params)]
