"""The recorder script refreshes every price source; one failing source must not stop the rest."""
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "record_minutes.py"


def _load():
    spec = importlib.util.spec_from_file_location("record_minutes", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_one_source_raising_does_not_stop_the_others(monkeypatch):
    rm = _load()
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
