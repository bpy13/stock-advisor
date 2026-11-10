"""Record the latest 1m and 60m bars for every news target and holding.

Yahoo keeps 1m bars for only about 30 days, so a daily run builds our own history.
Run: python scripts/record_minutes.py
Then it refreshes the price store from every source (daily, then hourly).
Writes a one-line summary, plus one line per store source, to data/cache/prices_intraday/recorder_log.txt.
"""

from __future__ import annotations

import sys
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


def refresh_store() -> list[str]:
    """Refresh the price store from every source, daily then hourly; one log line per source.

    Each source has its own try block, so a failure (Futu OpenD closed, no Alpaca key)
    does not stop the others.
    """
    lines = []
    for source in SOURCES:
        try:
            done, failed, added = prices_cli.refresh(source, list(STORE_INTERVALS))
            line = f"store {source}: done={done} failed={failed} bars_added={added}"
        except Exception as exc:
            line = f"store {source}: ERROR {type(exc).__name__}: {exc}"
        print(line)
        lines.append(line)
    return lines


def main() -> int:
    symbols = news_targets(_holdings())
    added, failed = record(symbols)
    summary = (
        f"{datetime.now().isoformat(timespec='seconds')} "
        f"symbols_ok={len(added)} symbols_failed={len(failed)} "
        f"rows_added={sum(added.values())}"
    )
    if failed:
        summary += f" failed={','.join(failed)}"
    print(summary)
    store_lines = refresh_store()
    log = market_data.INTRADAY_CACHE_DIR / "recorder_log.txt"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as handle:
        handle.write(summary + "\n")
        for line in store_lines:
            handle.write(f"{datetime.now().isoformat(timespec='seconds')} {line}\n")
    return 1 if symbols and not added else 0


if __name__ == "__main__":
    sys.exit(main())
