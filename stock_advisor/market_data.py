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


INTRADAY_CACHE_DIR = _REPO_ROOT / "data" / "cache" / "prices_intraday"

# Yahoo limits per interval: (days of history available, max days per request).
# 1m: about the last 30 days, 7 days per request. 60m: about 730 days.
INTRADAY_LIMITS = {
    "1m": (30, 7),
    "5m": (60, 60),
    "15m": (60, 60),
    "30m": (60, 60),
    "60m": (730, 730),
}


def _intraday_cache_file(symbol: str, interval: str) -> Path:
    return INTRADAY_CACHE_DIR / interval / f"{symbol.replace('.', '_').replace('^', '_')}.parquet"


def _to_utc_index(frame: pd.DataFrame) -> pd.DataFrame:
    """Return the frame with a tz-aware UTC index."""
    frame = frame.copy()
    index = pd.DatetimeIndex(frame.index)
    frame.index = index.tz_localize("UTC") if index.tz is None else index.tz_convert("UTC")
    return frame


def _fetch_intraday_range(
    symbol: str, interval: str, start: pd.Timestamp, end: pd.Timestamp, chunk_days: int
) -> List[pd.DataFrame]:
    """Download [start, end) from Yahoo in chunks no longer than `chunk_days`."""
    frames: List[pd.DataFrame] = []
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + pd.Timedelta(days=chunk_days), end)
        rows = yf.Ticker(symbol).history(
            start=chunk_start, end=chunk_end, interval=interval, auto_adjust=False
        )
        if rows is not None and not rows.empty:
            frames.append(_to_utc_index(rows))
        chunk_start = chunk_end
    return frames


def fetch_intraday(
    symbol: str,
    interval: str,
    start: Optional[pd.Timestamp] = None,
    end: Optional[pd.Timestamp] = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Fetch intraday bars (index = tz-aware UTC timestamps), merged into a disk cache.

    The cache lives at `data/cache/prices_intraday/<interval>/<symbol>.parquet`.
    Only the parts of the requested range missing from the cache are downloaded,
    in chunks Yahoo allows. `start` is clamped to what Yahoo still serves for the
    interval. Pass `use_cache=False` to bypass the cache (nothing is read or written).
    """
    if interval not in INTRADAY_LIMITS:
        raise ValueError(f"Unsupported intraday interval: {interval!r}")
    symbol = normalize_symbol(symbol)
    lookback_days, chunk_days = INTRADAY_LIMITS[interval]

    now = pd.Timestamp.now(tz="UTC")
    end_ts = now if end is None else pd.Timestamp(end)
    end_ts = end_ts.tz_localize("UTC") if end_ts.tzinfo is None else end_ts.tz_convert("UTC")
    # One day of margin: Yahoo rejects ranges right at the edge of its limit.
    earliest = now - pd.Timedelta(days=lookback_days - 1)
    start_ts = earliest if start is None else pd.Timestamp(start)
    start_ts = start_ts.tz_localize("UTC") if start_ts.tzinfo is None else start_ts.tz_convert("UTC")
    start_ts = max(start_ts, earliest)

    path = _intraday_cache_file(symbol, interval)
    cached: Optional[pd.DataFrame] = None
    if use_cache and path.exists():
        try:
            cached = pd.read_parquet(path)
        except Exception:
            cached = None
        if cached is not None and cached.empty:
            cached = None

    new_frames: List[pd.DataFrame] = []
    if cached is None:
        new_frames += _fetch_intraday_range(symbol, interval, start_ts, end_ts, chunk_days)
    else:
        cached = _to_utc_index(cached)
        if start_ts < cached.index.min():
            new_frames += _fetch_intraday_range(
                symbol, interval, start_ts, cached.index.min(), chunk_days
            )
        # Re-fetch from the last cached bar, which may have been a partial one.
        tail_start = max(cached.index.max(), start_ts)
        if tail_start < end_ts:
            new_frames += _fetch_intraday_range(symbol, interval, tail_start, end_ts, chunk_days)

    parts = ([cached] if cached is not None else []) + new_frames
    if not parts:
        return pd.DataFrame()
    merged = pd.concat(parts)
    merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    if use_cache and new_frames:
        path.parent.mkdir(parents=True, exist_ok=True)
        merged.to_parquet(path)
    return merged[(merged.index >= start_ts) & (merged.index <= end_ts)]


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
