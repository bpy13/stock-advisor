"""Yahoo source for the price store: daily (20+ years) and hourly (last 729 days)."""
from __future__ import annotations

import logging

import pandas as pd
import yfinance as yf

from stock_advisor import calendars, quality

log = logging.getLogger(__name__)
HOURLY_DAYS = 725  # Yahoo allows 730 days; the HK date start lands ahead of UTC
_RENAME = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
_PRICE = ["open", "high", "low", "close"]


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=list(_RENAME.values()))


def _canonical_hourly(df: pd.DataFrame, market: str, symbol: str) -> pd.DataFrame:
    """Keep only bars that start on a canonical bar start of Task 1.3; count the rest."""
    idx = df.index.tz_convert("UTC") if df.index.tz is not None else df.index.tz_localize("UTC")
    df = df.set_axis(idx)
    days = pd.DatetimeIndex(df.index.tz_convert(calendars._TZ[market]).date).unique()
    valid: set[pd.Timestamp] = set()
    for day in days:
        valid.update(calendars.hourly_bar_starts(market, day))
    keep = df.index.isin(list(valid))
    dropped = int((~keep).sum())
    if dropped:
        log.info("%s: dropped %d hourly bars that match no canonical start", symbol, dropped)
    return df[keep]


def fetch(symbol: str, interval: str, start=None, end=None) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Return (raw, adjusted) bars. Hourly bars have no adjusted form (``None``)."""
    if interval not in ("1d", "60m"):
        raise ValueError(f"unknown interval {interval!r}")
    market = quality.market_of(symbol)
    ticker = yf.Ticker(symbol)
    if interval == "1d":
        hist = ticker.history(period="max", interval="1d", auto_adjust=False, repair=True)
    else:
        if market not in ("HK", "US"):
            return _empty(), None
        lo = pd.Timestamp.now("UTC").tz_localize(None) - pd.Timedelta(days=HOURLY_DAYS)
        if start is not None:
            lo = max(lo, pd.Timestamp(start).tz_localize(None))
        hist = ticker.history(start=lo.strftime("%Y-%m-%d"),
                              end=None if end is None else pd.Timestamp(end).strftime("%Y-%m-%d"),
                              interval="60m", auto_adjust=False, repair=True)
    if hist is None or hist.empty:
        return _empty(), None
    hist = hist[~hist.index.duplicated(keep="last")].sort_index()
    hist = hist.dropna(subset=["Close"])
    raw = hist.rename(columns=_RENAME)[list(_RENAME.values())]
    if interval == "60m":
        return _canonical_hourly(raw, market, symbol), None
    day_index = hist.index.tz_localize(None) if hist.index.tz is not None else hist.index
    raw.index = adj_index = pd.DatetimeIndex(day_index).normalize()
    adjusted = raw.copy()
    if "Adj Close" in hist.columns:
        factor = (hist["Adj Close"] / hist["Close"]).fillna(1.0).set_axis(adj_index)
        adjusted[_PRICE] = raw[_PRICE].mul(factor, axis=0)
    return raw, adjusted
