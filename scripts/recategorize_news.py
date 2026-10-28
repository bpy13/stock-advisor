"""Re-categorize every categorized news item with the current rules in categories.py.

    python scripts/recategorize_news.py --dry-run     # print old -> new category counts, write nothing
    python scripts/recategorize_news.py               # update changed rows and affected events

Why: the first backfill categorized items with the rules from before the single-stock fix.
`scores` has no "categorized at" column, so every categorized row is recomputed from its stored
embedding (no model is loaded) and only the rows whose category changes are written.

A real run writes only `scores.category` (via the store, so `high_impact` is not reset), then
recomputes category and `high_impact` of each affected event with the rule in events.py.
Item and event counts must not change; the script checks this and exits non-zero if they do.

A real run takes the backfill lock and refuses to start while another process holds it. Take a
copy of news.db first. A dry run only reads, so it does not need the lock.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, Optional

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from stock_advisor.news.categories import categorize  # noqa: E402
from stock_advisor.news.events import event_members, summarize_event  # noqa: E402
from stock_advisor.news.scoring import embedding_from_bytes  # noqa: E402
from stock_advisor.news.store import NewsStore  # noqa: E402

CHUNK_SIZE = 20000  # rows (and 384-float embeddings) held in memory at once
EVENT_BATCH = 500  # events recomputed per transaction


def store_counts(store: NewsStore) -> Dict[str, int]:
    one = lambda sql: store._conn.execute(sql).fetchone()[0]  # noqa: E731
    return {
        "items": one("SELECT COUNT(*) FROM items"),
        "events": one("SELECT COUNT(*) FROM events"),
        "high_impact_events": one("SELECT COUNT(*) FROM events WHERE high_impact = 1"),
    }


def recategorize_items(
    store: NewsStore,
    dry_run: bool,
    chunk_size: int = CHUNK_SIZE,
    log: Callable[[str], None] = print,
):
    """Recompute categories chunk by chunk. Returns (transitions, affected_event_ids).

    `transitions` maps (old, new) to a row count for changed rows only. Unchanged rows are
    counted under `stable` in the log but not stored, to keep the result small.
    """
    transitions: Counter = Counter()
    affected_events = set()
    seen = 0
    last_id = ""
    while True:
        rows = store.categorized_chunk(last_id, chunk_size)
        if not rows:
            break
        last_id = rows[-1][0]
        vectors = np.vstack([embedding_from_bytes(r[2]) for r in rows])
        labels = categorize([r[1] for r in rows], embeddings=vectors)
        changed = []
        for (item_id, _title, _emb, old, event_id), new in zip(rows, labels):
            if new != old:
                changed.append((item_id, new))
                transitions[(old, new)] += 1
                if event_id:
                    affected_events.add(event_id)
        if changed and not dry_run:
            store.set_categories(changed)
        seen += len(rows)
        log(f"  checked {seen} rows, {sum(transitions.values())} changed so far")
    return transitions, affected_events


def refresh_event_flags(store: NewsStore, event_ids, log: Callable[[str], None] = print) -> int:
    """Recompute category and high_impact of events, and copy high_impact to member scores.

    Only those two event columns change; n_items, n_sources, title and time stay as stored.
    """
    ids = sorted(event_ids)
    done = 0
    for start in range(0, len(ids), EVENT_BATCH):
        with store._conn:
            for event_id in ids[start:start + EVENT_BATCH]:
                members = event_members(store, event_id)
                if not members:
                    continue
                event = summarize_event(event_id, members)
                store._conn.execute(
                    "UPDATE events SET category = ?, high_impact = ? WHERE id = ?",
                    (event.category, int(event.high_impact), event_id),
                )
                store._conn.execute(
                    "UPDATE scores SET high_impact = ? WHERE event_id = ?",
                    (int(event.high_impact), event_id),
                )
                done += 1
        log(f"  recomputed {done} of {len(ids)} events")
    return done


def print_transitions(transitions: Counter, log: Callable[[str], None] = print) -> None:
    if not transitions:
        log("No category changes.")
        return
    log(f"{sum(transitions.values())} rows change category (old -> new: rows):")
    for (old, new), n in sorted(transitions.items(), key=lambda kv: -kv[1]):
        log(f"  {old} -> {new}: {n}")


def run(
    db_path: Optional[Path],
    dry_run: bool,
    chunk_size: int = CHUNK_SIZE,
    lock_path: Optional[Path] = None,
    log: Callable[[str], None] = print,
) -> int:
    import backfill_news  # reuse its lock helpers and lock path

    lock_path = lock_path or backfill_news.LOCK_FILE
    have_lock = False
    if dry_run:
        if lock_path.exists():
            log(f"Note: {lock_path.name} exists; the dry run only reads, so it carries on.")
    else:
        if not backfill_news.acquire_lock(lock_path):
            log(f"Refusing to write: another process holds {lock_path}. Stop it first.")
            return 2
        have_lock = True
    try:
        with NewsStore(db_path) as store:
            before = store_counts(store)
            log(f"Before: {before}")
            transitions, affected = recategorize_items(store, dry_run, chunk_size, log)
            print_transitions(transitions, log)
            log(f"{len(affected)} events contain a changed row.")
            if dry_run:
                log("Dry run: nothing written.")
                return 0
            refresh_event_flags(store, affected, log)
            after = store_counts(store)
            log(f"After:  {after}")
            if (before["items"], before["events"]) != (after["items"], after["events"]):
                log("ERROR: item or event count changed. Restore the backup.")
                return 1
            log(f"High-impact events: {before['high_impact_events']} -> "
                f"{after['high_impact_events']}")
        return 0
    finally:
        if have_lock:
            backfill_news.release_lock(lock_path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="print the changes, write nothing")
    parser.add_argument("--db", type=Path, default=None, help="news.db path (default: the real store)")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)
    args = parser.parse_args(argv)
    return run(args.db, args.dry_run, args.chunk_size)


if __name__ == "__main__":
    sys.exit(main())
