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


# ---- main(): crash logging and --process-only ------------------------------------------------


class _FakeStore:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeProgress:
    def __init__(self, store, previous):
        self.states = []

    def refresh(self, state=None):
        self.states.append(state)


def _patch_main(monkeypatch, tmp_path):
    monkeypatch.setattr(backfill, "NEWS_CACHE_DIR", tmp_path)
    monkeypatch.setattr(backfill, "STATUS_FILE", tmp_path / "status.json")
    monkeypatch.setattr(backfill, "LOCK_FILE", tmp_path / "backfill.lock")
    monkeypatch.setattr(backfill, "LOG_FILE", tmp_path / "log.txt")
    monkeypatch.setattr(backfill, "NewsStore", _FakeStore)
    monkeypatch.setattr(backfill, "Progress", _FakeProgress)
    monkeypatch.setattr(backfill, "_enable_faulthandler", lambda: None)
    monkeypatch.setattr(backfill, "holdings_symbols", lambda: [])
    monkeypatch.setattr(backfill, "build_sources", lambda symbols: [
        type("S", (), {"name": n})() for n in ("wikipedia_events", "edgar", "gdelt", "guardian", "nyt")])


def test_main_logs_crash_writes_state_and_releases_lock(monkeypatch, tmp_path, caplog):
    _patch_main(monkeypatch, tmp_path)

    def boom(*args, **kwargs):
        raise ValueError("scoring blew up")

    monkeypatch.setattr(backfill, "run", boom)
    assert backfill.main([]) == 1
    assert backfill.read_status(tmp_path / "status.json")["state"] == "crashed: ValueError"
    assert not (tmp_path / "backfill.lock").exists()
    assert any(r.exc_info and "scoring blew up" in str(r.exc_info[1]) for r in caplog.records)


def test_main_records_interrupt_and_exit(monkeypatch, tmp_path):
    import pytest

    _patch_main(monkeypatch, tmp_path)
    for error, state in ((KeyboardInterrupt(), "interrupted"), (SystemExit(3), "exited: 3")):
        def stop(*args, _error=error, **kwargs):
            raise _error

        monkeypatch.setattr(backfill, "run", stop)
        with pytest.raises(type(error)):
            backfill.main([])
        assert backfill.read_status(tmp_path / "status.json")["state"] == state
        assert not (tmp_path / "backfill.lock").exists()


def test_process_only_fetches_no_source(monkeypatch, tmp_path):
    _patch_main(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(backfill, "run", lambda *a, **k: calls.append("run"))
    monkeypatch.setattr(backfill, "build_sources", lambda s: calls.append("build_sources"))
    monkeypatch.setattr(backfill, "process_new_items",
                        lambda store, progress, stop_at, final=False: calls.append(("process", final)))
    monkeypatch.setattr(backfill, "processing_counts",
                        lambda store: {"unscored": 0, "uncategorized": 0, "unclustered": 0})
    assert backfill.main(["--process-only"]) == 0
    assert calls == [("process", False)]


def test_process_new_items_logs_progress_and_heartbeats(monkeypatch, caplog):
    import logging
    import types

    pending = {"n": 1500}

    def fake_score(store, limit):
        done = min(limit, pending["n"])
        pending["n"] -= done
        return done

    monkeypatch.setitem(sys.modules, "stock_advisor.news.scoring",
                        types.SimpleNamespace(score_pending=fake_score))
    monkeypatch.setitem(sys.modules, "stock_advisor.news.categories",
                        types.SimpleNamespace(categorize_pending=lambda s, limit: 0))
    monkeypatch.setitem(sys.modules, "stock_advisor.news.events", types.SimpleNamespace(
        cluster_pending=lambda s: 0, fetch_high_impact_bodies=lambda s, since: 0))
    monkeypatch.setattr(backfill, "processing_counts", lambda store: {
        "unscored": pending["n"], "uncategorized": 0, "unclustered": 0})

    class P:
        beats, refreshes = 0, []

        def refresh(self, state=None):
            self.refreshes.append(state)

        def heartbeat(self):
            self.beats += 1

    progress = P()
    with caplog.at_level(logging.INFO, logger="backfill_news"):
        backfill.process_new_items(object(), progress, float("inf"))
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("scoring:")]
    assert len(lines) == 3 and "0 remaining" in lines[-1]
    assert progress.beats == 3
