"""Loads historical stock price data from Yahoo Finance, with a local disk cache."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd
import yfinance as yf

_REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = _REPO_ROOT / "data" / "cache" / "prices"

# How long a cached symbol is considered fresh before we bother re-checking
# Yahoo for new bars. Daily OHLCV only changes once per trading day, so there's
# no point re-fetching more often than this.
CACHE_TTL_HOURS = 12


def normalize_symbol(symbol: str) -> str:
    """Normalize a raw user-supplied ticker string for Yahoo Finance lookups."""
    normalized = str(symbol).strip().upper()
    if not normalized:
        raise ValueError("A stock symbol is required.")
    return normalized


def _period_to_days(period: str) -> int:
    """Approximate a Yahoo Finance period string (e.g. "2y", "6mo") as days."""
    normalized = period.strip().lower()
    if normalized in ("max", "ytd"):
        return 20 * 365
    if normalized.endswith("mo"):
        return int(normalized[:-2]) * 31
    if normalized.endswith("y"):
        return int(normalized[:-1]) * 366
    if normalized.endswith("d"):
        return int(normalized[:-1])
    raise ValueError(f"Unsupported period format: {period!r}")


def _cache_file(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol.replace('.', '_')}.parquet"


def _read_cache(symbol: str) -> Optional[pd.DataFrame]:
    path = _cache_file(symbol)
    if not path.exists():
        return None
    try:
        cached = pd.read_parquet(path)
    except Exception:
        return None
    return cached if not cached.empty else None


def _write_cache(symbol: str, history: pd.DataFrame) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    history.to_parquet(_cache_file(symbol))


def _cache_is_fresh(symbol: str) -> bool:
    path = _cache_file(symbol)
    if not path.exists():
        return False
    age_hours = (pd.Timestamp.now().timestamp() - path.stat().st_mtime) / 3600
    return age_hours < CACHE_TTL_HOURS


def _fetch_symbol_history(
    symbol: str, period: str, interval: str, use_cache: bool
) -> pd.DataFrame:
    """Fetch one symbol's OHLCV history, serving from/updating the disk cache."""
    if not use_cache or interval != "1d":
        return yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=False)

    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=_period_to_days(period))
    cached = _read_cache(symbol)
    covers_period = cached is not None and cached.index.min() <= cutoff

    if cached is not None and covers_period and _cache_is_fresh(symbol):
        return cached[cached.index >= cutoff]

    if cached is not None and covers_period:
        # Cache covers the requested range but may be missing the latest bars.
        last_cached_date = cached.index.max().tz_localize(None)
        start = (last_cached_date - pd.Timedelta(days=5)).date().isoformat()
        new_rows = yf.Ticker(symbol).history(start=start, interval=interval, auto_adjust=False)
        if not new_rows.empty:
            merged = pd.concat([cached, new_rows])
            merged = merged[~merged.index.duplicated(keep="last")].sort_index()
        else:
            merged = cached
        _write_cache(symbol, merged)
        return merged[merged.index >= cutoff]

    # No cache, or cache doesn't go back far enough: fetch the full period fresh.
    fresh = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=False)
    if not fresh.empty:
        _write_cache(symbol, fresh)
    return fresh


def fetch_price_history(
    symbols: Iterable[str],
    period: str = "2y",
    interval: str = "1d",
    use_cache: bool = True,
) -> Dict[str, pd.DataFrame]:
    """Fetch OHLCV history for each symbol individually.

    Returns a dict mapping the normalized symbol to its history DataFrame.
    Symbols with no data are omitted, since a delisted/invalid ticker should
    not silently zero out the analysis for the rest of the batch. Daily
    history is cached to disk under `data/cache/prices/` to avoid re-fetching
    from Yahoo Finance on every call; pass `use_cache=False` to bypass it.
    """
    result: Dict[str, pd.DataFrame] = {}
    for raw_symbol in symbols:
        symbol = normalize_symbol(raw_symbol)
        history = _fetch_symbol_history(symbol, period, interval, use_cache)
        if history.empty:
            continue
        result[symbol] = history
    return result


def fetch_close_prices(
    symbols: Iterable[str],
    period: str = "2y",
    interval: str = "1d",
    use_cache: bool = True,
) -> pd.DataFrame:
    """Fetch adjusted-close price history for a batch of symbols.

    Returns a single DataFrame indexed by date, one column per symbol,
    forward-filled to align trading calendars across exchanges.
    """
    histories = fetch_price_history(symbols, period=period, interval=interval, use_cache=use_cache)
    if not histories:
        raise ValueError("No Yahoo Finance data found for any requested symbol.")

    closes = {symbol: history["Close"] for symbol, history in histories.items()}
    frame = pd.DataFrame(closes).sort_index()
    return frame.ffill().dropna(how="all")


def missing_symbols(requested: Iterable[str], fetched: Dict[str, pd.DataFrame]) -> List[str]:
    """Return normalized symbols that were requested but had no data returned."""
    requested_normalized = {normalize_symbol(symbol) for symbol in requested}
    return sorted(requested_normalized - set(fetched.keys()))
