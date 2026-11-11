"""A disk snapshot of the event library, so the dashboard opens the News tab in seconds.

Why: `model.load_event_records` reads every event's member embeddings from news.db (6 GB,
1.78M events on 2026-11-11), which took 3-6 minutes and 12 GB of memory in the dashboard, so the
memory guard killed it. The snapshot stores the finished library once (a scheduled job writes
it) and the dashboard maps it read-only:

    <NEWS_CACHE_DIR>/model/library/LATEST            name of the current snapshot folder
    <NEWS_CACHE_DIR>/model/library/<name>/matrix.npy float32, unit length, one row per event
    <NEWS_CACHE_DIR>/model/library/<name>/meta.parquet id, time_ns, category, title, tone,
                                                    n_sources, high_impact (same row order)

`SnapshotLibrary` answers the questions `EventLibrary` answers for analysis (analog search,
lookups by id), but holds no Python object per event: rows are built on request. It is read-only.
Events newer than the snapshot are not in it; they are analysed through the one-row search
against the snapshot, and as analogs they have no finished reaction yet anyway.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from stock_advisor.news.model import EventLibrary, EventRecord

logger = logging.getLogger(__name__)

SNAPSHOT_FORMAT = 1
_COLUMNS = ["id", "time_ns", "category", "title", "tone", "n_sources", "high_impact"]


def snapshot_root() -> Path:
    from stock_advisor.news.analysis import NEWS_CACHE_DIR

    return NEWS_CACHE_DIR / "model" / "library"


def build_snapshot(store, root: Optional[Path] = None, keep: int = 1) -> Path:
    """Write a new snapshot from the store, switch `LATEST` to it, delete older ones.

    Streams the store one event at a time and writes the matrix row by row, so peak memory is
    the metadata lists (about 1 GB for 1.8M events), not the embeddings. Atomic for readers: the
    new folder is complete before `LATEST` is replaced.
    """
    from stock_advisor.news.scoring import embedding_from_bytes
    from stock_advisor.news.store import _from_text

    root = Path(root) if root is not None else snapshot_root()
    root.mkdir(parents=True, exist_ok=True)
    conn = store._conn
    n_events = conn.execute(
        "SELECT COUNT(DISTINCT e.id) FROM events e JOIN scores s ON s.event_id = e.id "
        "WHERE s.embedding IS NOT NULL").fetchone()[0]
    name = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    folder = root / name
    folder.mkdir()
    rows = conn.execute(
        "SELECT e.id, e.started_at, e.category, e.title, e.n_sources, e.high_impact, "
        "s.embedding, s.tone FROM events e JOIN scores s ON s.event_id = e.id "
        "WHERE s.embedding IS NOT NULL ORDER BY e.started_at, e.id")
    matrix = None
    meta = {c: [] for c in _COLUMNS}
    count = 0
    current, vec_sum, tones = None, None, []

    def flush() -> None:
        nonlocal matrix, count
        if current is None:
            return
        if matrix is None:
            matrix = np.lib.format.open_memmap(
                folder / "matrix.npy", mode="w+", dtype=np.float32,
                shape=(n_events + 1000, len(vec_sum)))  # slack: rows may arrive during the scan
        if count >= len(matrix):
            raise RuntimeError("the store grew during the snapshot; run it again")
        norm = max(float(np.linalg.norm(vec_sum)), 1e-12)
        matrix[count] = (vec_sum / norm).astype(np.float32)
        meta["id"].append(current["id"])
        meta["time_ns"].append(int(pd.Timestamp(_from_text(current["started_at"])).value))
        meta["category"].append(current["category"])
        meta["title"].append(current["title"] or "")
        meta["tone"].append(float(np.mean(tones)) if tones else 0.0)
        meta["n_sources"].append(int(current["n_sources"] or 1))
        meta["high_impact"].append(bool(current["high_impact"]))
        count += 1

    for row in rows:
        if current is None or row["id"] != current["id"]:
            flush()
            current, vec_sum, tones = row, None, []
        vec = embedding_from_bytes(row["embedding"]).astype(np.float64)
        vec_sum = vec if vec_sum is None else vec_sum + vec
        if row["tone"] is not None:
            tones.append(float(row["tone"]))
    flush()
    if matrix is None:
        shutil.rmtree(folder)
        raise RuntimeError("no embedded events in the store; nothing to snapshot")
    matrix.flush()
    dim = matrix.shape[1]
    del matrix
    # Trim the slack rows: rewrite the header by copying the used rows to the final file.
    _trim(folder / "matrix.npy", count, dim)
    pd.DataFrame(meta).to_parquet(folder / "meta.parquet", index=False)
    (folder / "manifest.json").write_text(json.dumps({
        "format": SNAPSHOT_FORMAT, "n": count, "dim": dim,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }), encoding="utf-8")
    latest_tmp = root / "LATEST.tmp"
    latest_tmp.write_text(name, encoding="utf-8")
    os.replace(latest_tmp, root / "LATEST")
    folders = sorted(p for p in root.iterdir() if p.is_dir())
    for old in folders[:-keep] if keep > 0 else []:
        shutil.rmtree(old, ignore_errors=True)
    logger.info("Library snapshot %s: %d events", name, count)
    return folder


def _trim(path: Path, rows: int, dim: int) -> None:
    """Shrink the .npy to `rows` rows (the slack rows at the end are zeros)."""
    big = np.load(path, mmap_mode="r")
    if big.shape[0] == rows:
        return
    tmp = path.with_name("matrix.trim.npy")
    out = np.lib.format.open_memmap(tmp, mode="w+", dtype=np.float32, shape=(rows, dim))
    for start in range(0, rows, 100_000):
        out[start:start + 100_000] = big[start:min(start + 100_000, rows)]
    out.flush()
    del out, big
    os.replace(tmp, path)


class _LazyEvents:
    """Sequence of `EventRecord` built on request from the snapshot arrays."""

    def __init__(self, matrix: np.ndarray, meta: pd.DataFrame) -> None:
        self._matrix = matrix
        # Plain arrays: a DataFrame lookup per field cost 0.65 ms per event.
        self._cols = {c: meta[c].to_numpy() for c in _COLUMNS if c != "id"}
        self._ids = meta["id"].to_numpy(object)

    def __len__(self) -> int:
        return len(self._ids)

    def __getitem__(self, i: int) -> EventRecord:
        i = int(i)
        if i < 0:
            i += len(self)
        if not 0 <= i < len(self):
            raise IndexError(i)
        c = self._cols
        return EventRecord(
            id=self._ids[i],
            started_at=pd.Timestamp(int(c["time_ns"][i]), tz="UTC").to_pydatetime(),
            embedding=np.asarray(self._matrix[i]), category=c["category"][i],
            tone=float(c["tone"][i]), n_sources=int(c["n_sources"][i]),
            high_impact=bool(c["high_impact"][i]), title=c["title"][i],
        )

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]


class _Positions:
    """`dict.get` over event ids, backed by one pandas Index."""

    def __init__(self, index: pd.Index) -> None:
        self._index = index

    def get(self, event_id, default=None):
        loc = self._index.get_indexer([event_id])[0]
        return default if loc < 0 else int(loc)

    def __contains__(self, event_id) -> bool:
        return self.get(event_id) is not None


class SnapshotLibrary(EventLibrary):
    """Read-only `EventLibrary` over a snapshot folder. See the module docstring."""

    def __init__(self, folder: Path, k: Optional[int] = None) -> None:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("format") != SNAPSHOT_FORMAT:
            raise ValueError(f"unknown snapshot format {manifest.get('format')!r}")
        super().__init__((), **({} if k is None else {"k": k}))
        matrix = np.load(folder / "matrix.npy", mmap_mode="r")
        meta = pd.read_parquet(folder / "meta.parquet", columns=_COLUMNS)
        if matrix.shape[0] != manifest["n"] or len(meta) != manifest["n"]:
            raise ValueError("snapshot files disagree about the event count")
        self.folder = folder
        self.built_at = manifest.get("built_at", "")
        self._matrix = matrix
        self._times = meta["time_ns"].to_numpy(np.int64)
        self._id_index = pd.Index(meta["id"].to_numpy(object))
        self._id_index_version = self.version = 1
        self.position = _Positions(self._id_index)
        self.events = _LazyEvents(matrix, meta)

    def extend(self, events) -> None:
        if list(events):
            raise TypeError("a snapshot library is read-only")

    def candidates(self):
        raise TypeError("a snapshot library has no all-pairs table; use candidates_for")


def load_snapshot(root: Optional[Path] = None) -> Optional[SnapshotLibrary]:
    """The current snapshot, or None when there is none or it cannot be read."""
    root = Path(root) if root is not None else snapshot_root()
    try:
        name = (root / "LATEST").read_text(encoding="utf-8").strip()
        return SnapshotLibrary(root / name)
    except FileNotFoundError:
        return None
    except Exception as exc:  # a stale format or half-written folder: caller falls back
        logger.warning("Library snapshot unusable (%s): %s", type(exc).__name__, exc)
        return None
