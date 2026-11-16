"""The recorder script refreshes every price source; one failing source must not stop the rest."""
from __future__ import annotations

import importlib.util
import threading
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "record_minutes.py"


def _load():
    spec = importlib.util.spec_from_file_location("record_minutes", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_with_log(monkeypatch, tmp_path):
    rm = _load()
    monkeypatch.setattr(rm.market_data, "INTRADAY_CACHE_DIR", tmp_path)
    return rm


def test_one_source_raising_does_not_stop_the_others(monkeypatch, tmp_path):
    rm = _load_with_log(monkeypatch, tmp_path)
    calls = []

    def fake_refresh(source, intervals, limit=None):
        calls.append((source, intervals))
        if source == "futu":
            raise RuntimeError("Futu OpenD is not running")
        return 3, 1, 10

    monkeypatch.setattr(rm.prices_cli, "refresh", fake_refresh)
    lines = rm.refresh_store()
    assert [c[0] for c in calls] == list(rm.SOURCES)
    assert all(c[1] == ["1d", "60m"] for c in calls)
    assert len(lines) == len(rm.SOURCES)
    assert any("futu: ERROR RuntimeError" in line for line in lines)
    assert any("yahoo: done=3 failed=1 bars_added=10" in line for line in lines)


def test_a_source_that_never_answers_ends_with_an_error_line_inside_the_limit(monkeypatch, tmp_path):
    rm = _load_with_log(monkeypatch, tmp_path)
    never = threading.Event()  # never set: the fake source blocks for good

    def fake_refresh(source, intervals, limit=None):
        if source == "alpaca":
            never.wait()
        return 1, 0, 2

    monkeypatch.setattr(rm.prices_cli, "refresh", fake_refresh)
    monkeypatch.setattr(rm, "SOURCE_LIMIT_SECONDS", 0.3)
    began = time.monotonic()
    lines = rm.refresh_store()
    assert time.monotonic() - began < 0.3 * len(rm.SOURCES) + 2
    assert "store alpaca: ERROR timeout after 0 s" in lines
    assert sum("done=1" in line for line in lines) == len(rm.SOURCES) - 1
    never.set()  # release the left-behind thread


def test_each_source_line_reaches_the_log_as_it_ends(monkeypatch, tmp_path):
    rm = _load_with_log(monkeypatch, tmp_path)
    log = tmp_path / "recorder_log.txt"
    seen = []

    def fake_refresh(source, intervals, limit=None):
        seen.append(log.read_text(encoding="utf-8").count("\n") if log.exists() else 0)
        return 1, 0, 2

    monkeypatch.setattr(rm.prices_cli, "refresh", fake_refresh)
    rm.refresh_store()
    assert seen == list(range(len(rm.SOURCES)))  # earlier sources already logged
    assert log.read_text(encoding="utf-8").count("store ") == len(rm.SOURCES)


def test_each_source_is_closed_after_its_refresh(monkeypatch, tmp_path):
    rm = _load_with_log(monkeypatch, tmp_path)
    closed = []
    monkeypatch.setattr(rm.prices_cli, "refresh", lambda source, intervals, limit=None: (0, 0, 0))
    monkeypatch.setattr(rm.SOURCES["futu"], "close", lambda: closed.append("futu"))
    rm.refresh_store()
    assert closed == ["futu"]
