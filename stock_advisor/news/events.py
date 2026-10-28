"""Group headlines about the same story into events, and flag high-impact events.

How clustering works
--------------------
Items are processed in time order. Each open event keeps the mean of its members' embeddings
(the centroid). A new headline joins the open event with the most similar centroid when:

- cosine similarity to that centroid >= `threshold`, and
- it is close in time: within `window` of one of the event's exact-time headlines, or on the
  same UTC day as one of its members when either side has only a date (`time_precision="day"`,
  e.g. Wikipedia), and
- the event would not span more than `max_span` from its first to its last headline (this stops
  a running story such as daily war reports from chaining into one event that lasts weeks).

Otherwise it starts a new event. Only events that can still accept headlines are kept in memory,
so a backfill of millions of items never compares all pairs; the live watcher calls the same
`cluster_pending` after each batch and new headlines join events already in the store.

Event ids are "ev_" + a hash of the event's founding item id, so rerunning on the same items
gives the same ids. Event time is the earliest exact-time headline, else the day (00:00 UTC).
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set
from urllib.parse import urlparse

import numpy as np

from stock_advisor.news import categories as _categories
from stock_advisor.news.models import Event, ItemScore
from stock_advisor.news.scoring import embedding_from_bytes

# Tuned on the real store on 2026-10-27 (see the Task 3.3 report). The plan's start values
# were 0.75 and 6 hours.
DEFAULT_THRESHOLD = 0.60
DEFAULT_WINDOW = timedelta(hours=12)
DEFAULT_MAX_SPAN = timedelta(hours=48)

# High-impact rule (plan Task 3.3).
HIGH_IMPACT_TONE = 0.6
HIGH_IMPACT_SOURCES = 3

_DAY = timedelta(days=1)
_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f+00:00"  # same fixed-width format as store.py
_RSS_FEED = re.compile(r"^\[([^|\]]+)")


def _to_text(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime(_TIME_FORMAT)


def _from_text(text: str) -> datetime:
    return datetime.strptime(text, _TIME_FORMAT).replace(tzinfo=timezone.utc)


def event_id_for(item_id: str) -> str:
    """Stable event id derived from the item that founded the event."""
    return "ev_" + hashlib.sha1(item_id.encode("utf-8")).hexdigest()[:16]


def source_key(source: str, url: str = "", summary: str = "") -> str:
    """The outlet a headline came from, for counting distinct sources.

    RSS items all have source "rss"; each feed counts separately ("rss:BBC Business", read from
    the "[feed | category]" summary prefix). GDELT items count per publishing domain.
    """
    if source == "rss":
        match = _RSS_FEED.match(summary or "")
        if match:
            return "rss:" + match.group(1).strip()
        return "rss:" + (urlparse(url).hostname or "")
    if source == "gdelt":
        domain = (summary or "").strip() or (urlparse(url).hostname or "")
        return "gdelt:" + domain.lower().removeprefix("www.")
    return source


@dataclass
class ClusterItem:
    """What clustering needs to know about one scored headline."""

    item_id: str
    published_at: datetime
    embedding: np.ndarray  # unit length
    source_key: str
    time_precision: str = "exact"
    title: str = ""
    tone: Optional[float] = None
    category: Optional[str] = None

    @property
    def day(self):
        return self.published_at.date()

    @property
    def is_exact(self) -> bool:
        return self.time_precision != "day"


@dataclass
class _OpenEvent:
    id: str
    members: List[ClusterItem] = field(default_factory=list)
    vector_sum: Optional[np.ndarray] = None
    exact_times: List[datetime] = field(default_factory=list)
    days: Set = field(default_factory=set)  # UTC dates of every member
    first: Optional[datetime] = None  # earliest member time (day items count as 00:00)
    last: Optional[datetime] = None
    slot: int = -1

    def add(self, item: ClusterItem) -> None:
        self.members.append(item)
        vec = item.embedding.astype(np.float64)
        self.vector_sum = vec if self.vector_sum is None else self.vector_sum + vec
        if item.is_exact:
            self.exact_times.append(item.published_at)
        self.days.add(item.day)
        t = item.published_at
        self.first = t if self.first is None else min(self.first, t)
        self.last = t if self.last is None else max(self.last, t)

    def centroid(self) -> np.ndarray:
        norm = float(np.linalg.norm(self.vector_sum))
        return (self.vector_sum / max(norm, 1e-12)).astype(np.float32)

    def accepts_time(self, item: ClusterItem, window: timedelta, max_span: timedelta) -> bool:
        t = item.published_at
        if max(self.last, t) - min(self.first, t) > max_span:
            return False
        if item.is_exact:
            if any(abs(t - e) <= window for e in self.exact_times):
                return True
            # Same day as a date-only member.
            return any(not m.is_exact and m.day == item.day for m in self.members)
        # A date-only item matches any member on the same day.
        return item.day in self.days

    def active_until(self, window: timedelta, max_span: timedelta) -> datetime:
        """After this time (in time-ordered processing) no new item can join."""
        ends = [e + window for e in self.exact_times]
        # A date-only member keeps the event open to the end of its day.
        ends += [
            datetime(m.day.year, m.day.month, m.day.day, tzinfo=timezone.utc) + _DAY
            for m in self.members if not m.is_exact
        ]
        return min(max(ends), self.first + max_span)


class EventClusterer:
    """Incremental clusterer. Feed items in (roughly) time order with `add`.

    `seed` loads an event that already exists (from the store) so new items can join it.
    Centroids live in one matrix so each `add` costs one matrix-vector product over the
    events that are still open.
    """

    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        window: timedelta = DEFAULT_WINDOW,
        max_span: timedelta = DEFAULT_MAX_SPAN,
    ) -> None:
        self.threshold = threshold
        self.window = window
        self.max_span = max_span
        self.events: Dict[str, _OpenEvent] = {}
        self._matrix: Optional[np.ndarray] = None
        self._slot_owner: List[Optional[str]] = []
        self._free: List[int] = []

    # -- matrix of centroids ---------------------------------------------------------------

    def _alloc(self, dim: int) -> int:
        if self._free:
            return self._free.pop()
        if self._matrix is None:
            self._matrix = np.zeros((64, dim), dtype=np.float32)
        elif len(self._slot_owner) >= self._matrix.shape[0]:
            grown = np.zeros((self._matrix.shape[0] * 2, dim), dtype=np.float32)
            grown[: self._matrix.shape[0]] = self._matrix
            self._matrix = grown
        self._slot_owner.append(None)
        return len(self._slot_owner) - 1

    def _store_centroid(self, event: _OpenEvent) -> None:
        if event.slot < 0:
            event.slot = self._alloc(event.vector_sum.shape[0])
        self._slot_owner[event.slot] = event.id
        self._matrix[event.slot] = event.centroid()

    def close(self, event_id: str) -> None:
        event = self.events.pop(event_id, None)
        if event is not None and event.slot >= 0:
            self._matrix[event.slot] = 0.0
            self._slot_owner[event.slot] = None
            self._free.append(event.slot)

    def close_idle(self, now: datetime) -> None:
        """Drop events that no item at or after `now` can join."""
        for event_id in [
            e.id for e in self.events.values()
            if e.active_until(self.window, self.max_span) < now
        ]:
            self.close(event_id)

    # -- clustering ------------------------------------------------------------------------

    def seed(self, event_id: str, members: Iterable[ClusterItem]) -> None:
        event = self.events.get(event_id) or _OpenEvent(id=event_id)
        for item in members:
            event.add(item)
        if event.members:
            self.events[event_id] = event
            self._store_centroid(event)

    def add(self, item: ClusterItem) -> str:
        """Put one item into the best matching open event, or a new one. Returns the event id."""
        best = None
        if self._matrix is not None and self.events:
            sims = self._matrix @ item.embedding.astype(np.float32)
            for slot in np.argsort(-sims, kind="stable"):
                if sims[slot] < self.threshold:
                    break
                owner = self._slot_owner[slot]
                if owner is None:
                    continue
                event = self.events[owner]
                if event.accepts_time(item, self.window, self.max_span):
                    best = event
                    break
        if best is None:
            best = _OpenEvent(id=event_id_for(item.item_id))
            self.events[best.id] = best
        best.add(item)
        self._store_centroid(best)
        return best.id


def cluster_items(
    items: Sequence[ClusterItem],
    threshold: float = DEFAULT_THRESHOLD,
    window: timedelta = DEFAULT_WINDOW,
    max_span: timedelta = DEFAULT_MAX_SPAN,
) -> Dict[str, str]:
    """Cluster items in memory. Returns {item_id: event_id}. Used for tuning and tests."""
    clusterer = EventClusterer(threshold, window, max_span)
    result = {}
    for item in sorted(items, key=lambda i: (i.published_at, i.item_id)):
        clusterer.close_idle(item.published_at)
        result[item.item_id] = clusterer.add(item)
    return result


# ---- event summary and the high-impact rule ------------------------------------------------


def is_high_impact(
    category: Optional[str],
    tone: Optional[float],
    n_sources: int,
    market_moving: Iterable[str] = (),
) -> bool:
    """Plan rule: a macro category and (|tone| >= 0.6 or >= 3 distinct sources).

    `market_moving` is the hook for the later backtest: categories it proves move markets are
    high impact whatever their tone or source count.
    """
    if category is not None and category in set(market_moving):
        return True
    if category not in _categories.MACRO_CATEGORIES:
        return False
    strong_tone = tone is not None and abs(tone) >= HIGH_IMPACT_TONE
    return strong_tone or n_sources >= HIGH_IMPACT_SOURCES


def event_time_precision(members: Sequence[ClusterItem]) -> str:
    """"exact" when any member has an exact time, else "batch" when any member has a crawl-batch
    time (no sub-hour horizons), else "day" (daily horizons only)."""
    if any(m.time_precision == "exact" for m in members):
        return "exact"
    return "batch" if any(m.time_precision == "batch" for m in members) else "day"


def summarize_event(
    event_id: str, members: Sequence[ClusterItem], market_moving: Iterable[str] = ()
) -> Event:
    """Build the Event row: time, title and category from the members, plus high impact."""
    ordered = sorted(members, key=lambda m: (m.published_at, m.item_id))
    exact = [m for m in ordered if m.is_exact]
    lead = exact[0] if exact else ordered[0]  # the headline that broke the story
    started_at = lead.published_at
    if not exact:
        started_at = datetime(lead.day.year, lead.day.month, lead.day.day, tzinfo=timezone.utc)
    # Majority category; a tie goes to the category seen first.
    counts = Counter(m.category for m in ordered if m.category)
    category = None
    if counts:
        top = max(counts.values())
        category = next(m.category for m in ordered if m.category and counts[m.category] == top)
    tones = [m.tone for m in ordered if m.tone is not None]
    tone = float(np.mean(tones)) if tones else None
    n_sources = len({m.source_key for m in ordered})
    return Event(
        id=event_id,
        started_at=started_at,
        category=category,
        title=lead.title,
        n_items=len(ordered),
        n_sources=n_sources,
        high_impact=is_high_impact(category, tone, n_sources, market_moving),
    )


# ---- store side ----------------------------------------------------------------------------
# These queries live here until the store gains matching methods (see the Task 3.3 report).
# They write event_id/high_impact with direct UPDATEs because store.update_scores always
# overwrites high_impact.

_MEMBER_COLUMNS = (
    "i.id, i.source, i.published_at, i.title, i.url, i.summary, i.time_precision, "
    "s.embedding, s.tone, s.category, s.event_id"
)


def _row_to_cluster_item(row) -> ClusterItem:
    return ClusterItem(
        item_id=row["id"],
        published_at=_from_text(row["published_at"]),
        embedding=embedding_from_bytes(row["embedding"]),
        source_key=source_key(row["source"], row["url"], row["summary"]),
        time_precision=row["time_precision"],
        title=row["title"],
        tone=row["tone"],
        category=row["category"],
    )


def event_members(store, event_id: str) -> List[ClusterItem]:
    rows = store._conn.execute(
        f"SELECT {_MEMBER_COLUMNS} FROM items i JOIN scores s ON s.item_id = i.id "
        "WHERE s.event_id = ? AND s.embedding IS NOT NULL ORDER BY i.published_at, i.id",
        (event_id,),
    ).fetchall()
    return [_row_to_cluster_item(r) for r in rows]


def _pending_rows(store, limit: int, since: Optional[datetime] = None):
    """Items ready to cluster: embedded and categorized, no event yet, oldest first (only those
    published at or after `since`, when given)."""
    recent, params = "", []
    if since is not None:
        recent, params = " AND i.published_at >= ?", [_to_text(since)]
    return store._conn.execute(
        f"SELECT {_MEMBER_COLUMNS} FROM items i JOIN scores s ON s.item_id = i.id "
        "WHERE s.event_id IS NULL AND s.embedding IS NOT NULL AND s.category IS NOT NULL"
        f"{recent} ORDER BY i.published_at, i.id LIMIT ?",
        (*params, limit),
    ).fetchall()


def _context_events(store, start: datetime, end: datetime) -> Dict[str, List[ClusterItem]]:
    """All members of the stored events that have a member between start and end."""
    rows = store._conn.execute(
        f"SELECT {_MEMBER_COLUMNS} FROM items i JOIN scores s ON s.item_id = i.id "
        "WHERE s.embedding IS NOT NULL AND s.event_id IN ("
        "  SELECT DISTINCT s2.event_id FROM items i2 JOIN scores s2 ON s2.item_id = i2.id "
        "  WHERE s2.event_id IS NOT NULL AND i2.published_at >= ? AND i2.published_at <= ?"
        ") ORDER BY i.published_at, i.id",
        (_to_text(start), _to_text(end)),
    ).fetchall()
    grouped: Dict[str, List[ClusterItem]] = {}
    for row in rows:
        grouped.setdefault(row["event_id"], []).append(_row_to_cluster_item(row))
    return grouped


def save_events(store, groups: Dict[str, Sequence[ClusterItem]],
                market_moving: Iterable[str] = ()) -> List[Event]:
    """Write event rows and copy each event's id and high_impact flag to its members' score
    rows, all in one transaction (one commit per event is far too slow for a backfill)."""
    built = [(summarize_event(eid, members, market_moving), members)
             for eid, members in groups.items()]
    with store._conn:
        # Same columns as store.upsert_event.
        store._conn.executemany(
            "INSERT OR REPLACE INTO events "
            "(id, started_at, category, title, n_items, n_sources, high_impact) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(e.id, _to_text(e.started_at), e.category, e.title, e.n_items, e.n_sources,
              int(e.high_impact)) for e, _ in built],
        )
        store._conn.executemany(
            "UPDATE scores SET event_id = ?, high_impact = ? WHERE item_id = ?",
            [(e.id, int(e.high_impact), m.item_id) for e, members in built for m in members],
        )
    return [e for e, _ in built]


def save_event(store, event_id: str, members: Sequence[ClusterItem],
               market_moving: Iterable[str] = ()) -> Event:
    """Write one event row and copy its high_impact flag to every member's score row."""
    return save_events(store, {event_id: members}, market_moving)[0]


def refresh_event(store, event_id: str, market_moving: Iterable[str] = ()) -> Optional[Event]:
    """Recompute one stored event from its members (e.g. after a member's tone changed)."""
    members = event_members(store, event_id)
    return save_event(store, event_id, members, market_moving) if members else None


def cluster_pending(
    store,
    threshold: float = DEFAULT_THRESHOLD,
    window: timedelta = DEFAULT_WINDOW,
    max_span: timedelta = DEFAULT_MAX_SPAN,
    market_moving: Iterable[str] = (),
    chunk_size: int = 5000,
    since: Optional[datetime] = None,
) -> int:
    """Assign events to every embedded, categorized item that has none. Returns items placed.

    Works in chunks of `chunk_size` items in time order. Before each chunk it reloads the
    stored events that overlap the chunk's time range, so new headlines (a live batch, or late
    arrivals) can join existing events. Run scoring and categorize_pending first. `since`
    limits it to items published at or after that time (a live run leaves the backlog alone).
    """
    market_moving = tuple(market_moving)
    placed = 0
    while True:
        rows = _pending_rows(store, chunk_size, since)
        if not rows:
            return placed
        items = [_row_to_cluster_item(r) for r in rows]
        margin = max_span + _DAY
        clusterer = EventClusterer(threshold, window, max_span)
        for event_id, members in _context_events(
            store, items[0].published_at - margin, items[-1].published_at + margin
        ).items():
            clusterer.seed(event_id, members)
        touched: Dict[str, _OpenEvent] = {}
        for item in items:
            clusterer.close_idle(item.published_at)
            event_id = clusterer.add(item)
            touched[event_id] = clusterer.events[event_id]
        save_events(store, {eid: e.members for eid, e in touched.items()}, market_moving)
        placed += len(items)


# ---- full article for high-impact events ---------------------------------------------------


def fetch_high_impact_bodies(
    store,
    fetch: Optional[Callable[[str], Optional[str]]] = None,
    finbert=None,
    since: Optional[datetime] = None,
    max_tries_per_event: int = 3,
    market_moving: Iterable[str] = (),
) -> int:
    """Fetch one article body per high-impact event and re-score that headline's tone on the
    title plus the first 2,000 characters. Returns the number of bodies stored.

    Members are tried oldest first (up to `max_tries_per_event` with a URL). When none gives a
    body (paywalled, robots.txt, error), the tried items get body "" so later runs skip them.
    The event is then recomputed, because a member's tone may have changed.
    """
    from stock_advisor.news import article

    fetch = fetch or article.fetch_body
    stored = 0
    for event in store.query_events(start=since, high_impact_only=True):
        items = store.items_for_event(event.id)
        if any(i.body is not None for i in items):
            continue  # already fetched, or already tried
        tried = 0
        for item in items:
            if tried >= max_tries_per_event:
                break
            if not item.url:
                continue
            tried += 1
            body = fetch(item.url)
            if not body:
                store.set_body(item.id, "")
                continue
            store.set_body(item.id, body)
            pos, neg, neu, tone = article.rescore_tone(item.title, body, finbert=finbert)
            store.update_scores(
                ItemScore(item_id=item.id, tone_pos=pos, tone_neg=neg, tone_neu=neu, tone=tone,
                          high_impact=True)
            )
            stored += 1
            refresh_event(store, event.id, market_moving)
            break
    return stored
