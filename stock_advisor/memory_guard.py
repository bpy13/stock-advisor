"""Memory guard: a process that grows past a limit logs it and exits, so its wrapper restarts it.

On 2026-10-29 the watcher reached 21.4 GB and the dashboard 17.9 GB (a bug since fixed), and the
machine ran out of RAM. `scripts/run_watcher.ps1` and `scripts/run_dashboard.ps1` start their
process again after any exit, so a clean self-exit above a limit is a safe stop.

The guard watches this process's private bytes (memory only this process owns) from a daemon
thread. Above 75% of the limit it logs one warning; above the limit it logs an error and calls
`os._exit(MEMORY_EXIT_CODE)`. Limits come from env vars (see `WATCHER_*` / `DASHBOARD_*` below).
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import time
from ctypes import wintypes
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Exit code of a guard exit, so a log line "exited with code 86" is recognisable as this guard.
MEMORY_EXIT_CODE = 86

WATCHER_LIMIT_ENV = "STOCK_ADVISOR_WATCHER_MEMORY_GB"
DASHBOARD_LIMIT_ENV = "STOCK_ADVISOR_DASHBOARD_MEMORY_GB"
WATCHER_DEFAULT_GB = 8.0  # the watcher keeps ~2.4 GB and peaks ~3.1 GB on a model refresh
DASHBOARD_DEFAULT_GB = 10.0

CHECK_INTERVAL = 15.0  # seconds between checks
WARN_FRACTION = 0.75
_GB = 1024 ** 3

_lock = threading.Lock()
_started = False  # one guard per process: Streamlit reruns app.py on every interaction


class _ProcessMemoryCountersEx(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


def private_bytes() -> Optional[int]:
    """This process's private bytes (Windows `PrivateUsage`), or None where it cannot be read."""
    if sys.platform != "win32":
        return None
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(_ProcessMemoryCountersEx), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        counters = _ProcessMemoryCountersEx()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters),
                                          counters.cb):
            return None
        return int(counters.PrivateUsage)
    except Exception:  # a failed read must never take the process down
        return None


def limit_from_env(env_name: str, default_gb: float) -> float:
    """The limit in GB from `env_name`; a missing, bad or non-positive value gives the default."""
    from stock_advisor.news.settings import get_setting

    raw = get_setting(env_name)
    if not raw:
        return default_gb
    try:
        value = float(raw)
        if value > 0:
            return value
    except ValueError:
        pass
    logger.warning("memory guard: %s=%r is not a positive number; using the default %.1f GB",
                   env_name, raw, default_gb)
    return default_gb


def _ensure_log_output() -> None:
    """Give our logger a stderr handler when nothing is configured (Streamlit does not set up
    root logging), so the guard's lines reach the wrapper's log file."""
    if logging.getLogger().handlers or logger.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _flush_log_handlers() -> None:
    for log in (logger, logging.getLogger()):
        for handler in log.handlers:
            try:
                handler.flush()
            except Exception:
                pass


def start_memory_guard(
    name: str,
    limit_gb: float,
    interval_s: float = CHECK_INTERVAL,
    *,
    reader: Callable[[], Optional[int]] = private_bytes,
    exit_fn: Callable[[int], None] = os._exit,
    sleep: Callable[[float], None] = time.sleep,
    log: Optional[logging.Logger] = None,
) -> bool:
    """Start the guard thread for this process. Returns False if one already runs.

    `reader`, `exit_fn`, `sleep` and `log` are injectable for tests. `os._exit` skips cleanup
    on purpose: a process over its limit may not be able to unwind cleanly.
    """
    global _started
    with _lock:
        if _started:
            return False
        _started = True
    log = log or logger
    if log is logger:
        _ensure_log_output()
    limit_bytes = limit_gb * _GB
    log.info("memory guard: %s limited to %.1f GB private memory (checked every %g s)",
             name, limit_gb, interval_s)
    thread = threading.Thread(
        target=_watch, args=(name, limit_gb, limit_bytes, interval_s, reader, exit_fn, sleep, log),
        daemon=True, name="memory-guard")
    thread.start()
    return True


def _watch(name, limit_gb, limit_bytes, interval_s, reader, exit_fn, sleep, log) -> None:
    warned = False
    while True:
        used = reader()
        if used is None:
            log.info("memory guard: cannot read memory use here; guard for %s is inactive", name)
            return
        if used > limit_bytes:
            log.error("memory guard: %s uses %.1f GB private memory, over the %.1f GB limit; "
                      "exiting so the wrapper restarts it", name, used / _GB, limit_gb)
            _flush_log_handlers()
            exit_fn(MEMORY_EXIT_CODE)
            return  # only reached when exit_fn is a test fake
        if used > WARN_FRACTION * limit_bytes:
            if not warned:
                log.warning("memory guard: %s uses %.1f GB private memory, over %d%% of the "
                            "%.1f GB limit", name, used / _GB, round(WARN_FRACTION * 100),
                            limit_gb)
                warned = True
        else:
            warned = False
        sleep(interval_s)
