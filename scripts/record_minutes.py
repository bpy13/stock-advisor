"""Record the latest 1m and 60m bars for every news target and holding.

Yahoo keeps 1m bars for only about 30 days, so a daily run builds our own history.
Run: python scripts/record_minutes.py
Then it refreshes the price store from every source (daily, then hourly).
Writes a one-line summary, plus one line per store source, to data/cache/prices_intraday/recorder_log.txt.
"""

from __future__ import annotations

import os
import sys
import threading
from datetime import datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd  # noqa: E402

from stock_advisor import market_data, prices_cli  # noqa: E402
from stock_advisor.config import news_targets  # noqa: E402
from stock_advisor.price_sources import SOURCES  # noqa: E402
from stock_advisor.price_store import INTERVALS as STORE_INTERVALS  # noqa: E402
from stock_advisor.report import resolve_symbols_and_portfolio  # noqa: E402

INTERVALS = ("1m", "60m")
# Time limits. A normal night takes about 40 minutes (measured 2026-11-16); the scheduled
# task's own limit (register_recorder_task.ps1) is 4 hours, above RUN_LIMIT_SECONDS.
SOURCE_LIMIT_SECONDS = 60 * 60
RUN_LIMIT_SECONDS = 3 * 60 * 60


def _cached_rows(symbol: str, interval: str) -> int:
    """Count the rows now stored in the disk cache for one symbol and interval."""
    path = market_data._intraday_cache_file(market_data.normalize_symbol(symbol), interval)
    if not path.exists():
        return 0
    try:
        return len(pd.read_parquet(path))
    except Exception:
        return 0


def _holdings() -> list[str]:
    try:
        symbols, portfolio = resolve_symbols_and_portfolio()
    except Exception as exc:
        print(f"Could not resolve holdings ({type(exc).__name__}); using fixed targets only.")
        return []
    # Without a portfolio the symbols are only the default universe, not holdings.
    return list(portfolio.positions) if portfolio is not None else []


def record(symbols: list[str]) -> tuple[dict[str, int], list[str]]:
    """Fetch every symbol; return (rows added per symbol, failed symbols)."""
    added: dict[str, int] = {}
    failed: list[str] = []
    for symbol in symbols:
        total = 0
        try:
            for interval in INTERVALS:
                before = _cached_rows(symbol, interval)
                market_data.fetch_intraday(symbol, interval)
                total += _cached_rows(symbol, interval) - before
        except Exception as exc:
            print(f"FAILED {symbol}: {type(exc).__name__}: {exc}")
            failed.append(symbol)
            continue
        added[symbol] = total
        print(f"{symbol}: {total} rows added")
    return added, failed


def _log_path() -> Path:
    return market_data.INTRADAY_CACHE_DIR / "recorder_log.txt"


def write_log(line: str) -> None:
    """Append one time-stamped line to the recorder log at once, so a later hang loses nothing."""
    log = _log_path()
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as handle:
        handle.write(f"{datetime.now().isoformat(timespec='seconds')} {line}\n")


def _refresh_with_limit(source: str, limit_seconds: float) -> str:
    """Run one source's refresh in a daemon thread; give up on it after ``limit_seconds``.

    Some network calls (yfinance, the Futu SDK) have no hard deadline of their own. A source
    that never answers is left running in its daemon thread and dies when the process exits.
    """
    result: dict[str, str] = {}

    def work() -> None:
        try:
            done, failed, added = prices_cli.refresh(source, list(STORE_INTERVALS))
            result["line"] = f"store {source}: done={done} failed={failed} bars_added={added}"
        except Exception as exc:
            result["line"] = f"store {source}: ERROR {type(exc).__name__}: {exc}"
        finally:
            close = getattr(SOURCES[source], "close", None)
            if close is not None:
                try:
                    close()
                except Exception as exc:
                    print(f"store {source}: close failed: {type(exc).__name__}: {exc}")

    thread = threading.Thread(target=work, name=f"refresh-{source}", daemon=True)
    thread.start()
    thread.join(limit_seconds)
    if thread.is_alive():
        return f"store {source}: ERROR timeout after {limit_seconds:.0f} s"
    return result["line"]


def refresh_store() -> list[str]:
    """Refresh the price store from every source, daily then hourly; one log line per source.

    Each source has its own try block and time limit, so a failure or a hang (Futu OpenD
    closed, no Alpaca key, a call that never returns) does not stop the others. Each line
    goes to the log as soon as its source ends.
    """
    lines = []
    for source in SOURCES:
        line = _refresh_with_limit(source, SOURCE_LIMIT_SECONDS)
        print(line)
        write_log(line)
        lines.append(line)
    return lines


def _start_watchdog(limit_seconds: float) -> threading.Timer:
    """End the whole process after ``limit_seconds`` with an error line, whatever it is doing."""

    def stop() -> None:
        try:
            write_log(f"ERROR run limit of {limit_seconds:.0f} s reached; recorder stopped")
        finally:
            os._exit(3)

    timer = threading.Timer(limit_seconds, stop)
    timer.daemon = True
    timer.start()
    return timer


def main() -> int:
    _start_watchdog(RUN_LIMIT_SECONDS)
    symbols = news_targets(_holdings())
    added, failed = record(symbols)
    summary = (
        f"symbols_ok={len(added)} symbols_failed={len(failed)} "
        f"rows_added={sum(added.values())}"
    )
    if failed:
        summary += f" failed={','.join(failed)}"
    print(summary)
    write_log(summary)
    refresh_store()
    return 1 if symbols and not added else 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    # os._exit, not sys.exit: a thread left behind by a source (a timed-out refresh, an SDK
    # thread) must never keep the process alive and block the next night's run.
    os._exit(code)
