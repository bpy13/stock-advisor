"""Quality flags for stored price bars.

Each bar gets three flags: ``no_trade`` (no volume that day or hour), ``big_move`` (the close
jumped beyond a set limit) and ``gap_before`` (how many expected sessions or hourly bars are
missing between the previous bar and this one).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from stock_advisor import calendars

BIG_MOVE_LIMIT = {"1d": 0.40, "60m": 0.20}
FLAG_COLUMNS = ("no_trade", "big_move", "gap_before")


def market_of(symbol: str) -> str:
    """HK for .HK symbols; OTHER for indexes, futures and fx (names with ^ or =); else US."""
    if symbol.upper().endswith(".HK"):
        return "HK"
    if symbol.startswith("^") or "=" in symbol:
        return "OTHER"
    return "US"


def _expected_index(market: str, interval: str, lo, hi) -> pd.DatetimeIndex:
    """Every session date (daily) or canonical bar start in UTC (hourly) from lo to hi."""
    if interval == "1d":
        return calendars.sessions(market, lo, hi)
    pad = pd.Timedelta(days=1)  # a bar's UTC date can differ from its local session date
    days = calendars.sessions(market, lo.tz_convert("UTC").tz_localize(None) - pad,
                              hi.tz_convert("UTC").tz_localize(None) + pad)
    starts = [s for d in days for s in calendars.hourly_bar_starts(market, d)]
    return pd.DatetimeIndex(starts, tz="UTC").sort_values()


def _gap_before(index: pd.DatetimeIndex, market: str, interval: str) -> np.ndarray:
    gaps = np.zeros(len(index), dtype=int)
    if market == "OTHER" or len(index) < 2:
        return gaps
    expected = _expected_index(market, interval, index.min(), index.max())
    if len(expected) == 0:
        return gaps
    pos = expected.searchsorted(index, side="left")
    gaps[1:] = np.maximum(np.diff(pos) - 1, 0)
    return gaps


def flag_bars(bars: pd.DataFrame, market: str, interval: str, tradable: bool) -> pd.DataFrame:
    """Return ``bars`` (sorted by index) with the three flag columns added or replaced."""
    out = bars.drop(columns=list(FLAG_COLUMNS), errors="ignore").sort_index().copy()
    if tradable:
        out["no_trade"] = (out["volume"].fillna(0) == 0).to_numpy()
    else:
        out["no_trade"] = False
    big = out["close"].pct_change().abs() > BIG_MOVE_LIMIT[interval]
    out["big_move"] = big.fillna(False).to_numpy()
    out["gap_before"] = _gap_before(out.index, market, interval)
    return out
