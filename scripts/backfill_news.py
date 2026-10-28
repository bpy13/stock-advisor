"""Backfill the news store with history from every source, then score, categorize and cluster.

    python scripts/backfill_news.py                    # run until done or every source is capped
    python scripts/backfill_news.py --max-minutes 90   # bounded run
    python scripts/backfill_news.py --status           # print progress and exit
    python scripts/backfill_news.py --process-only     # score/categorize/cluster, fetch nothing

Sources run one after another (Wikipedia, EDGAR, GDELT, Guardian, NYT). Each gets a time slice
per pass (--slice-minutes), then scoring, categorizing and clustering catch up on the new
items, then the next pass starts. Everything is resumable: cursors live in the store, so a
stopped or crashed run continues where it was, and items already stored are skipped.

One process at a time (lock file). Progress goes to data/cache/news/backfill_status.json after
each batch and to backfill_log.txt. A source that reaches its daily call cap (Guardian, NYT)
stops for the day; the daily scheduled task (register_backfill_task.ps1) continues it.
"""

from __future__ import annotations

import argparse
import faulthandler
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from stock_advisor.news.collect import (  # noqa: E402
    BATCH_SIZE,
    DAILY_CALL_BUDGETS,
    backfill_source,
    build_sources,
    holdings_symbols,
)
from stock_advisor.news.settings import (  # noqa: E402
    NEWS_CACHE_DIR,
    guardian_api_key,
    nyt_api_key,
    sec_contact_email,
)
from stock_advisor.news.store import NewsStore  # noqa: E402

logger = logging.getLogger("backfill_news")

STATUS_FILE = NEWS_CACHE_DIR / "backfill_status.json"
LOCK_FILE = NEWS_CACHE_DIR / "backfill.lock"
LOG_FILE = NEWS_CACHE_DIR / "backfill_log.txt"

# A source whose cursor is within this of "now" has caught up; the daily task keeps it fresh.
COMPLETE_LAG = timedelta(days=3)
STILL_ACTIVE = 259  # Windows exit code of a running process
STALL_RETRIES = 3  # passes to retry a rate-limited source (GDELT) before giving up for the run
STALL_WAIT_SECONDS = 180
SCORE_CHUNK = 640  # ten model batches of 64; one log line and one status heartbeat per chunk
FULL_REFRESH_EVERY = 10  # chunks between full status refreshes (which recount the database)
CATEGORY_CHUNK = 20000
BODY_FETCH_DAYS = 30  # only recent high-impact events get an article body (old URLs are dead)


@dataclass(frozen=True)
class SourceSpec:
    name: str
    start: datetime
    step: timedelta  # length of one slice; progress is saved after each slice
    key_check: Optional[Callable[[], str]] = None  # returns "" when a needed key is missing
    missing: str = ""  # message when key_check fails


def _utc(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


SPECS: List[SourceSpec] = [
    SourceSpec("wikipedia_events", _utc(2002, 4, 11), timedelta(days=365)),
    SourceSpec("edgar", _utc(1994, 1, 1), timedelta(days=92), sec_contact_email,
               "SEC_CONTACT_EMAIL is not set"),
    SourceSpec("gdelt", _utc(2017, 1, 1), timedelta(days=14)),
    SourceSpec("guardian", _utc(1990, 2, 8), timedelta(days=365), guardian_api_key,
               "GUARDIAN_API_KEY is not set"),
    SourceSpec("nyt", _utc(1990, 1, 1), timedelta(days=365), nyt_api_key,
               "NYT_API_KEY is not set"),
]


# ---- status file, lock, log ------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: Optional[datetime]) -> Optional[str]:
    return moment.isoformat(timespec="seconds") if moment else None


def read_status(path: Path = STATUS_FILE) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_status(status: dict, path: Path = STATUS_FILE) -> None:
    """Write atomically so `--status` never reads half a file."""
    status["updated"] = _iso(_now())
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(status, indent=2), encoding="utf-8")
    os.replace(temp, path)


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    import ctypes

    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        return bool(ok) and code.value == STILL_ACTIVE
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def acquire_lock(path: Path = LOCK_FILE) -> bool:
    """Create the lock file holding our pid. A lock left by a dead process is replaced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                owner = int(path.read_text(encoding="utf-8").strip() or 0)
            except (OSError, ValueError):
                owner = 0
            if pid_alive(owner):
                return False
            path.unlink(missing_ok=True)  # stale lock from a crashed run
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
        return True
    return False


def release_lock(path: Path = LOCK_FILE) -> None:
    path.unlink(missing_ok=True)


# ---- progress numbers ------------------------------------------------------------------------


def processing_counts(store: NewsStore) -> dict:
    """How much is left to score, categorize and cluster."""
    one = lambda sql: store._conn.execute(sql).fetchone()[0]  # noqa: E731
    return {
        "unscored": one("SELECT COUNT(*) FROM items i LEFT JOIN scores s ON s.item_id = i.id "
                        "WHERE s.item_id IS NULL OR s.tone IS NULL"),
        "uncategorized": one("SELECT COUNT(*) FROM scores WHERE category IS NULL "
                             "AND embedding IS NOT NULL"),
        "unclustered": one("SELECT COUNT(*) FROM scores WHERE event_id IS NULL "
                           "AND category IS NOT NULL AND embedding IS NOT NULL"),
        "items": one("SELECT COUNT(*) FROM items"),
        "events": one("SELECT COUNT(*) FROM events"),
        "high_impact_events": one("SELECT COUNT(*) FROM events WHERE high_impact = 1"),
    }


class Progress:
    """Holds the status dict and rewrites the file whenever something changes."""

    def __init__(self, store: NewsStore, previous: dict) -> None:
        self.store = store
        old_sources = previous.get("sources", {})
        self.data: dict = {
            "pid": os.getpid(),
            "started": _iso(_now()),
            "state": "starting",
            "sources": {},
            "processing": {},
        }
        for spec in SPECS:
            self.data["sources"][spec.name] = {
                "last_error": old_sources.get(spec.name, {}).get("last_error", ""),
                "run_status": "pending",
            }
        self.refresh()

    def refresh(self, state: Optional[str] = None) -> None:
        if state:
            self.data["state"] = state
        stored = self.store.counts_by_source()
        for spec in SPECS:
            entry = self.data["sources"][spec.name]
            cursor = self.store.get_backfill_cursor(spec.name)
            entry["cursor"] = _iso(cursor)
            entry["items_stored"] = stored.get(spec.name, 0)
            entry["complete"] = bool(cursor and _now() - cursor <= COMPLETE_LAG)
            entry["calls_today"] = self.store.calls_today(spec.name)
        self.data["processing"] = {**self.data["processing"], **processing_counts(self.store)}
        write_status(self.data)

    def heartbeat(self) -> None:
        """Rewrite the status file (refreshes `updated`) without recounting the database."""
        write_status(self.data)

    def source(self, name: str, run_status: Optional[str] = None, error: Optional[str] = None) -> None:
        entry = self.data["sources"][name]
        if run_status is not None:
            entry["run_status"] = run_status
        if error is not None:
            entry["last_error"] = error
        self.refresh()


# ---- sources ---------------------------------------------------------------------------------


def run_range_source(store, source, spec: SourceSpec, progress: Progress,
                     stop_at: float) -> str:
    """Backfill `source` slice by slice until it is done, capped, failed or out of time.

    Returns "complete", "paused" (time slice used up), "capped" (daily call cap),
    "stalled" (rate-limited by the server, worth retrying later) or "failed"."""
    while True:
        now = _now()
        cursor = store.get_backfill_cursor(spec.name)
        first = max(spec.start, cursor) if cursor else spec.start
        if now - first <= COMPLETE_LAG:
            return "complete"
        if time.monotonic() >= stop_at:
            return "paused"
        end = min(first + spec.step, now)
        logger.info("%s: slice %s to %s", spec.name, first.date(), end.date())
        result = backfill_source(store, source, first, end, DAILY_CALL_BUDGETS, BATCH_SIZE)
        logger.info("%s: fetched %d, new %d, %s %s", spec.name, result.fetched, result.new,
                    result.status, result.error)
        if result.status == "ok":
            progress.source(spec.name, "running", error="")
            continue
        progress.source(spec.name, error=result.error)
        if result.status == "limit":
            return "capped" if spec.name in DAILY_CALL_BUDGETS else "stalled"
        return "failed"


def _quarter_start(moment: datetime) -> datetime:
    return datetime(moment.year, 3 * ((moment.month - 1) // 3) + 1, 1, tzinfo=timezone.utc)


def _next_quarter(moment: datetime) -> datetime:
    start = _quarter_start(moment)
    return datetime(start.year + (start.month == 10), (start.month + 2) % 12 + 1, 1,
                    tzinfo=timezone.utc)


def run_edgar(store, source, spec: SourceSpec, progress: Progress, stop_at: float) -> str:
    """Backfill EDGAR one finished quarter at a time.

    EDGAR's quarterly index lists filings in form-type order, not date order, so the cursor
    moves only after a whole quarter has been read. The current quarter is left to the live
    `--recent` poll (re-reading a 40 MB index every day would be wasteful)."""
    while True:
        cursor = store.get_backfill_cursor(spec.name)
        quarter = _quarter_start(max(spec.start, cursor) if cursor else spec.start)
        upcoming = _next_quarter(quarter)
        if upcoming > _quarter_start(_now()):
            return "complete"
        if time.monotonic() >= stop_at:
            return "paused"
        logger.info("edgar: reading quarter starting %s", quarter.date())
        batch, stored = [], 0
        try:
            for item in source.fetch_range(quarter, upcoming - timedelta(seconds=1)):
                batch.append(item)
                if len(batch) >= BATCH_SIZE:
                    stored += store.add_items(batch)
                    batch.clear()
            stored += store.add_items(batch)
        except Exception as exc:
            store.add_items(batch)  # keep what was read; the quarter is read again next time
            progress.source(spec.name, error=f"{type(exc).__name__}: {exc}")
            return "failed"
        if stored == 0 and quarter.year >= 2003 and not _quarter_has_items(store, quarter, upcoming):
            # Ten megacaps file 8-Ks every quarter, so an empty modern quarter means a failed
            # download (the adapter hides those). Do not move the cursor past it.
            progress.source(spec.name, error=f"no filings read for {quarter.date()}; will retry")
            return "failed"
        store.advance_backfill_cursor(spec.name, upcoming)
        progress.source(spec.name, "running", error="")


def _quarter_has_items(store, start: datetime, end: datetime) -> bool:
    return bool(store.query_items(start=start, end=end, source="edgar", limit=1))


# ---- scoring, categories, clustering ---------------------------------------------------------


def process_new_items(store, progress: Progress, stop_at: float, final: bool = False) -> None:
    """Score, categorize and cluster everything fetched so far, in chunks with progress saves."""
    from stock_advisor.news.categories import categorize_pending
    from stock_advisor.news.events import cluster_pending, fetch_high_impact_bodies
    from stock_advisor.news.scoring import score_pending

    progress.refresh("scoring")
    remaining = processing_counts(store)["unscored"]
    scored_total, began, chunks = 0, time.monotonic(), 0
    while remaining and time.monotonic() < stop_at:
        scored = score_pending(store, limit=SCORE_CHUNK)
        if not scored:
            logger.warning("scoring: %d items still unscored but none could be scored", remaining)
            break
        scored_total += scored
        remaining = max(remaining - scored, 0)
        chunks += 1
        rate = scored_total / max(time.monotonic() - began, 1e-9)
        # One line per chunk: when a run dies, the last line shows when and how far it got.
        logger.info("scoring: %d scored this pass, %.1f items/s, %d remaining",
                    scored_total, rate, remaining)
        if chunks % FULL_REFRESH_EVERY == 0:
            progress.refresh()  # also recounts the database: slow on a large store
        else:
            progress.heartbeat()
    progress.refresh("categorizing")
    while processing_counts(store)["uncategorized"] and time.monotonic() < stop_at:
        categorize_pending(store, limit=CATEGORY_CHUNK)
        progress.refresh()
    counts = processing_counts(store)
    if counts["unclustered"] and time.monotonic() < stop_at:
        progress.refresh("clustering")
        cluster_pending(store)
        progress.refresh()
    if final and time.monotonic() < stop_at:
        progress.refresh("fetching article bodies")
        since = _now() - timedelta(days=BODY_FETCH_DAYS)
        try:
            n = fetch_high_impact_bodies(store, since=since)
            logger.info("article bodies stored for %d high-impact events", n)
        except Exception as exc:  # network trouble must not fail the whole run
            logger.warning("article fetch failed: %s: %s", type(exc).__name__, exc)


# ---- the run ---------------------------------------------------------------------------------


def run(store, sources: Dict[str, object], progress: Progress, max_minutes: Optional[float],
        slice_minutes: float, sleep: Callable[[float], None] = time.sleep) -> None:
    run_stop = time.monotonic() + max_minutes * 60 if max_minutes else float("inf")
    finished: Dict[str, str] = {}  # sources that are done for this run, with the reason
    stalls = 0
    for spec in SPECS:  # a missing key skips the source up front
        if spec.key_check and not spec.key_check():
            finished[spec.name] = "no key"
            progress.source(spec.name, "no key", error=spec.missing)
    while len(finished) < len(SPECS) and time.monotonic() < run_stop:
        stalled_now = []
        for spec in SPECS:
            if spec.name in finished or time.monotonic() >= run_stop:
                continue
            source = sources[spec.name]
            stop_at = min(run_stop, time.monotonic() + slice_minutes * 60)
            progress.source(spec.name, "running")
            runner = run_edgar if spec.name == "edgar" else run_range_source
            try:
                outcome = runner(store, source, spec, progress, stop_at)
            except Exception as exc:  # one source's bug must not stop the others
                logger.exception("%s crashed", spec.name)
                progress.source(spec.name, error=f"{type(exc).__name__}: {exc}")
                outcome = "failed"
            progress.source(spec.name, outcome)
            if outcome == "stalled":
                stalled_now.append(spec.name)
            elif outcome != "paused":
                finished[spec.name] = outcome
        process_new_items(store, progress, run_stop)
        if stalled_now:
            stalls += 1
            if stalls > STALL_RETRIES:
                for name in stalled_now:
                    finished[name] = "stalled"
                    progress.source(name, "stalled")
            else:
                logger.info("rate-limited: %s; waiting %d s", stalled_now, STALL_WAIT_SECONDS)
                sleep(STALL_WAIT_SECONDS)
        else:
            stalls = 0
    process_new_items(store, progress, run_stop, final=True)
    done = all(finished.get(s.name) in ("complete", "no key") for s in SPECS)
    progress.refresh("complete" if done else "stopped")


# ---- status command --------------------------------------------------------------------------


def format_status(status: dict) -> str:
    if not status:
        return "No backfill status yet (data/cache/news/backfill_status.json is missing)."
    pid = status.get("pid", 0)
    running = pid_alive(pid) and LOCK_FILE.exists()
    lines = [f"state: {status.get('state')} ({'running, pid ' + str(pid) if running else 'not running'})",
             f"started {status.get('started')}, updated {status.get('updated')}", ""]
    lines.append(f"{'source':<18}{'cursor':<12}{'items':>9} {'done':<5}{'calls':>6}  {'run':<9} last error")
    for name, s in status.get("sources", {}).items():
        cursor = (s.get("cursor") or "-")[:10]
        lines.append(f"{name:<18}{cursor:<12}{s.get('items_stored', 0):>9} "
                     f"{'yes' if s.get('complete') else 'no':<5}{s.get('calls_today', 0):>6}  "
                     f"{s.get('run_status', ''):<9} {(s.get('last_error') or '')[:70]}")
    p = status.get("processing", {})
    lines += ["", f"items {p.get('items', 0)}, events {p.get('events', 0)} "
                  f"(high impact {p.get('high_impact_events', 0)})",
              f"waiting: {p.get('unscored', 0)} to score, {p.get('uncategorized', 0)} to categorize, "
              f"{p.get('unclustered', 0)} to cluster"]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill news history, then score and cluster it.")
    parser.add_argument("--status", action="store_true", help="print progress and exit")
    parser.add_argument("--max-minutes", type=float, help="stop after about this many minutes")
    parser.add_argument("--slice-minutes", type=float, default=30,
                        help="time each source gets per pass before scoring runs (default 30)")
    parser.add_argument("--process-only", action="store_true",
                        help="score, categorize and cluster pending items; fetch from no source")
    parser.add_argument("--db", help="path of the SQLite store (default: data/cache/news/news.db)")
    args = parser.parse_args(argv)

    if args.status:
        print(format_status(read_status()))
        return 0

    NEWS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
    )
    if not acquire_lock(LOCK_FILE):
        print("Another backfill is running (see backfill.lock). Exiting.")
        return 2
    _enable_faulthandler()
    exit_code = 0
    try:
        previous = read_status(STATUS_FILE)
        with NewsStore(args.db) as store:
            progress = Progress(store, previous)
            if args.process_only:
                run_process_only(store, progress, args.max_minutes)
            else:
                sources = {s.name: s for s in build_sources(holdings_symbols())}
                gdelt = sources["gdelt"]
                gdelt.strict = True  # stop instead of skipping a window the server refused
                gdelt.rate_limit_wait, gdelt.rate_limit_tries = 75.0, 4  # lockouts last 1+ minutes
                run(store, sources, progress, args.max_minutes, args.slice_minutes)
    except Exception as exc:
        # The headless task has no console, so the traceback must go to the log file.
        logger.exception("backfill crashed")
        _record_end_state(f"crashed: {type(exc).__name__}")
        exit_code = 1  # non-zero so Task Scheduler records a failure
    except KeyboardInterrupt:
        logger.error("backfill interrupted (Ctrl+C)")
        _record_end_state("interrupted")
        raise
    except SystemExit as exc:
        logger.error("backfill exited early: SystemExit(%r)", exc.code)
        _record_end_state(f"exited: {exc.code}")
        raise
    finally:
        release_lock(LOCK_FILE)
    print(format_status(read_status(STATUS_FILE)))
    return exit_code


def run_process_only(store, progress: Progress, max_minutes: Optional[float]) -> None:
    """Score, categorize and cluster pending items without fetching from any source."""
    stop_at = time.monotonic() + max_minutes * 60 if max_minutes else float("inf")
    process_new_items(store, progress, stop_at)
    left = processing_counts(store)
    done = not (left["unscored"] or left["uncategorized"] or left["unclustered"])
    progress.refresh("processed (no fetch)" if done else "stopped (processing only)")


def _record_end_state(state: str) -> None:
    """Write the final state to the status file without needing the store or Progress."""
    try:
        write_status({**read_status(STATUS_FILE), "state": state}, STATUS_FILE)
    except Exception:
        logger.exception("could not write end state %r", state)


def _enable_faulthandler() -> None:
    """Dump the Python stack to the log on a fatal signal (segfault, abort).

    A hard kill (out-of-memory, terminate) cannot be caught; this covers native crashes."""
    global _fault_file
    try:
        _fault_file = open(LOG_FILE, "a", encoding="utf-8")
        faulthandler.enable(file=_fault_file, all_threads=True)
    except Exception:
        logger.exception("could not enable faulthandler")


_fault_file = None


if __name__ == "__main__":
    sys.exit(main())
