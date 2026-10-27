"""Tests for scripts/backfill_news.py helpers (no network, no models)."""

import importlib.util
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backfill_news.py"
spec = importlib.util.spec_from_file_location("backfill_news", SCRIPT)
backfill = importlib.util.module_from_spec(spec)
sys.modules["backfill_news"] = backfill  # dataclasses look the module up by name
spec.loader.exec_module(backfill)


def utc(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc)


def test_quarter_math():
    assert backfill._quarter_start(utc(2024, 5, 17)) == utc(2024, 4, 1)
    assert backfill._next_quarter(utc(2024, 2, 1)) == utc(2024, 4, 1)
    assert backfill._next_quarter(utc(2024, 11, 20)) == utc(2025, 1, 1)
    assert backfill._next_quarter(utc(2024, 7, 1)) == utc(2024, 10, 1)


def test_lock_blocks_second_process_and_replaces_stale_lock(tmp_path):
    lock = tmp_path / "backfill.lock"
    assert backfill.acquire_lock(lock)
    assert not backfill.acquire_lock(lock)  # our own pid is alive
    backfill.release_lock(lock)
    lock.write_text("999999999")  # no such process
    assert backfill.acquire_lock(lock)
    assert lock.read_text() == str(os.getpid())


def test_status_roundtrip_and_format(tmp_path):
    path = tmp_path / "status.json"
    backfill.write_status({"pid": 0, "state": "scoring", "sources": {
        "gdelt": {"cursor": "2019-03-04T00:00:00+00:00", "items_stored": 12, "complete": False,
                  "calls_today": 3, "run_status": "paused", "last_error": ""}},
        "processing": {"items": 12, "events": 1}}, path)
    text = backfill.format_status(backfill.read_status(path))
    assert "gdelt" in text and "2019-03-04" in text and "12" in text
    assert "No backfill status" in backfill.format_status({})
