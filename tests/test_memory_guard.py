"""Tests for the memory guard: fake reader, fake exit and fake sleep, no real thread timing."""

from __future__ import annotations

import logging
import threading

import pytest

from stock_advisor import memory_guard as mg

GB = 1024 ** 3
LIMIT = 8.0


@pytest.fixture(autouse=True)
def fresh_guard(monkeypatch):
    """Each test starts with no guard running (conftest marks it started for everyone else)."""
    monkeypatch.setattr(mg, "_started", False)


class Stop(Exception):
    """Raised by the fake reader when the readings run out, to end the guard loop."""


def run_loop(readings, caplog):
    """Run the guard loop on this thread over `readings` (bytes or None). Returns exit codes."""
    values = iter(readings)
    exits = []

    def sleep(_seconds):
        pass

    def reader():
        try:
            return next(values)
        except StopIteration:
            raise Stop

    caplog.set_level(logging.INFO)
    try:
        mg._watch("test", LIMIT, LIMIT * GB, 15.0, reader, exits.append, sleep, mg.logger)
    except Stop:
        pass
    return exits


def test_exits_with_code_above_limit(caplog):
    exits = run_loop([int(9.5 * GB)], caplog)
    assert exits == [mg.MEMORY_EXIT_CODE]
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "test uses 9.5 GB private memory, over the 8.0 GB limit" in errors[0].getMessage()
    assert "exiting so the wrapper restarts it" in errors[0].getMessage()


def test_nothing_below_threshold(caplog):
    exits = run_loop([GB, 2 * GB, 5 * GB], caplog)
    assert exits == []
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


def test_warns_once_until_it_drops_back(caplog):
    # 7 GB is over 75% of 8 GB (6 GB). Two readings warn once; a drop and a rise warn again.
    exits = run_loop([7 * GB, 7 * GB, 7.5 * GB, 2 * GB, 7 * GB], caplog)
    assert exits == []
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 2


def test_reader_none_makes_guard_inactive(caplog):
    exits = run_loop([None], caplog)
    assert exits == []
    assert any("inactive" in r.getMessage() and r.levelno == logging.INFO
               for r in caplog.records)


def test_start_runs_once_per_process(caplog):
    caplog.set_level(logging.INFO)
    seen = threading.Event()

    def reader():
        seen.set()
        return None  # inactive: the thread ends after the first read

    first = mg.start_memory_guard("a", 1.0, reader=reader, exit_fn=lambda c: None)
    second = mg.start_memory_guard("b", 1.0, reader=reader, exit_fn=lambda c: None)
    assert (first, second) == (True, False)
    assert seen.wait(5)
    starts = [r for r in caplog.records if "limited to 1.0 GB" in r.getMessage()]
    assert len(starts) == 1


def test_thread_exits_via_fake_exit():
    codes = []
    done = threading.Event()

    def exit_fn(code):
        codes.append(code)
        done.set()

    mg.start_memory_guard("t", 1.0, reader=lambda: 2 * GB, exit_fn=exit_fn)
    assert done.wait(5)
    assert codes == [mg.MEMORY_EXIT_CODE]


def test_env_override(monkeypatch):
    monkeypatch.setenv(mg.WATCHER_LIMIT_ENV, "3.5")
    assert mg.limit_from_env(mg.WATCHER_LIMIT_ENV, mg.WATCHER_DEFAULT_GB) == 3.5


def test_env_unset_uses_default(monkeypatch):
    monkeypatch.setenv(mg.DASHBOARD_LIMIT_ENV, "")
    assert mg.limit_from_env(mg.DASHBOARD_LIMIT_ENV, mg.DASHBOARD_DEFAULT_GB) == 10.0


@pytest.mark.parametrize("bad", ["lots", "-2", "0"])
def test_bad_env_warns_and_uses_default(monkeypatch, caplog, bad):
    monkeypatch.setenv(mg.WATCHER_LIMIT_ENV, bad)
    assert mg.limit_from_env(mg.WATCHER_LIMIT_ENV, mg.WATCHER_DEFAULT_GB) == 8.0
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_private_bytes_is_positive_on_windows():
    value = mg.private_bytes()
    if value is None:
        pytest.skip("private bytes are only read on Windows")
    assert isinstance(value, int) and value > 0
