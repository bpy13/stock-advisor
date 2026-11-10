"""Alpaca source for US bars: daily raw and adjusted, hourly built from 30-minute bars.

Needs ALPACA_API_KEY and ALPACA_API_SECRET in the environment (``.env``). Tries the paid-grade
``sip`` feed first and falls back to the free ``iex`` feed, remembering the choice for the run.
"""
from __future__ import annotations

import logging
from functools import lru_cache

import pandas as pd
import requests

from stock_advisor import calendars, quality
from stock_advisor.news.settings import get_setting

log = logging.getLogger(__name__)
URL = "https://data.alpaca.markets/v2/stocks/bars"
ELIGIBLE_KINDS = ("stock", "index_fund", "holding")
_COLS = ["open", "high", "low", "close", "volume"]
_MAP = {"t": "t", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
_state = {"feed": "sip"}  # the feed in use; switches to "iex" once for the run


def _api_symbol(symbol: str) -> str:
    """Yahoo writes share classes as BRK-B; Alpaca writes BRK.B."""
    return symbol.replace("-", ".")


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=_COLS)


def _headers() -> dict:
    key, secret = get_setting("ALPACA_API_KEY"), get_setting("ALPACA_API_SECRET")
    if not key or not secret:
        raise RuntimeError("Alpaca keys missing: set ALPACA_API_KEY and ALPACA_API_SECRET in .env")
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


@lru_cache(maxsize=1)
def _eligible_symbols() -> frozenset[str]:
    from stock_advisor.watchlist import load_watchlist

    return frozenset(i.symbol for i in load_watchlist() if i.kind in ELIGIBLE_KINDS)


def _get_pages(params: dict) -> list[dict]:
    """Follow ``next_page_token``; on a subscription error switch feed sip -> iex once."""
    headers, bars, token = _headers(), [], None
    while True:
        q = {**params, "feed": _state["feed"], "limit": 10000}
        if token:
            q["page_token"] = token
        resp = requests.get(URL, params=q, headers=headers, timeout=30)
        if resp.status_code in (403, 422) and _state["feed"] == "sip" \
                and "subscription" in resp.text.lower():
            log.info("Alpaca: sip feed refused, using iex for this run")
            _state["feed"] = "iex"
            continue
        resp.raise_for_status()
        body = resp.json()
        bars += (body.get("bars") or {}).get(params["symbols"], [])
        token = body.get("next_page_token")
        if not token:
            return bars


def _frame(bars: list[dict]) -> pd.DataFrame:
    if not bars:
        return _empty()
    df = pd.DataFrame(bars).rename(columns=_MAP)
    df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("t"), utc=True))
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df[_COLS]


def _daily(symbol: str, adjustment: str, start, end) -> pd.DataFrame:
    params = {"symbols": _api_symbol(symbol), "timeframe": "1Day", "adjustment": adjustment,
              "start": str(pd.Timestamp(start).date()) if start is not None else "2000-01-01"}
    if end is not None:
        params["end"] = str(pd.Timestamp(end).date())
    df = _frame(_get_pages(params))
    # Daily bars are stamped at midnight Eastern: keep the date only.
    df.index = pd.DatetimeIndex(df.index.tz_convert("America/New_York").tz_localize(None).normalize())
    return df


def _hourly(symbol: str, start, end) -> pd.DataFrame:
    params = {"symbols": _api_symbol(symbol), "timeframe": "30Min", "adjustment": "raw",
              "start": pd.Timestamp(start).strftime("%Y-%m-%d") if start is not None else "2016-01-01"}
    if end is not None:
        params["end"] = pd.Timestamp(end).strftime("%Y-%m-%d")
    half = _frame(_get_pages(params))
    if half.empty:
        return half
    # Each half-hour belongs to the canonical hourly bar that contains it (regular session only).
    starts: list[pd.Timestamp] = []
    closes: list[pd.Timestamp] = []
    cal = calendars._calendar("US")
    for day in pd.DatetimeIndex(half.index.tz_convert("America/New_York").date).unique():
        day_starts = calendars.hourly_bar_starts("US", day)
        starts += day_starts
        if day_starts:
            closes.append(cal.session_close(pd.Timestamp(day).tz_localize(None).normalize()))
    # Drop after-hours half-hours (a half-hour must end by the close) in one pass, not per day.
    if closes:
        closes_idx = pd.DatetimeIndex(sorted(closes)).tz_convert("UTC")
        pos_c = closes_idx.searchsorted(half.index, side="right") - 1
        after = (pos_c >= 0) & (half.index < closes_idx[pos_c.clip(0)] + pd.Timedelta(hours=12))
        half = half[~after]
    starts_idx = pd.DatetimeIndex(sorted(starts))
    pos = starts_idx.searchsorted(half.index, side="right") - 1
    valid = pos >= 0
    half, pos = half[valid], pos[valid]
    bar = starts_idx[pos]
    # Drop half-hours after the bar's hour (e.g. after close, or the 15:30 bar's tail is kept).
    keep = (half.index - bar) < pd.Timedelta(hours=1)
    half, bar = half[keep], bar[keep]
    out = half.groupby(bar).agg(open=("open", "first"), high=("high", "max"),
                                low=("low", "min"), close=("close", "last"),
                                volume=("volume", "sum"))
    out.index = pd.DatetimeIndex(out.index)
    return out[_COLS]


def fetch(symbol: str, interval: str, start=None, end=None) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Return (raw, adjusted); hourly has no adjusted form (``None``). Non-US or other kinds: empty."""
    if interval not in ("1d", "60m"):
        raise ValueError(f"unknown interval {interval!r}")
    _headers()  # fail early with a clear message
    if quality.market_of(symbol) != "US" or symbol.upper() not in _eligible_symbols():
        return _empty(), None
    if interval == "60m":
        return _hourly(symbol, start, end), None
    return _daily(symbol, "raw", start, end), _daily(symbol, "all", start, end)
