"""Futu source for Hong Kong bars, read from the local gateway Futu OpenD (127.0.0.1:11111).

OpenD runs on Brian's PC under his own login, so this code holds no credential. History quota:
the lowest account tier covers a limited number of different stocks per rolling period; the
quota is checked before each new symbol and the fetch stops when none is left.

VERIFIED on real data (Task 2.8, 2026-11-12): Futu labels an hourly bar by its END time, in
Hong Kong time. The canonical bars of ``calendars`` are labelled by start, so bars are mapped
back by end time; the 11:30 bar ends at 12:00 because of the lunch break.
"""
from __future__ import annotations

import logging
import socket
import time
from collections import deque

import pandas as pd

from stock_advisor import calendars, quality

log = logging.getLogger(__name__)
HOST, PORT = "127.0.0.1", 11111
ELIGIBLE_KINDS = ("stock", "index_fund", "holding")
MAX_REQUESTS, WINDOW_SECONDS = 60, 30.0
_COLS = ["open", "high", "low", "close", "volume"]
_state = {"ctx": None, "seen": set()}  # one connection per run; symbols already counted vs quota


class FutuNotRunning(RuntimeError):
    """OpenD is not reachable on its local port."""


class QuotaExhausted(RuntimeError):
    """No history quota left for a new symbol."""


class _RateLimiter:
    """At most ``MAX_REQUESTS`` calls in any ``WINDOW_SECONDS`` window."""

    def __init__(self, clock=time.monotonic, sleep=time.sleep):
        self.clock, self.sleep, self.stamps = clock, sleep, deque()

    def wait(self) -> None:
        now = self.clock()
        while self.stamps and now - self.stamps[0] >= WINDOW_SECONDS:
            self.stamps.popleft()
        if len(self.stamps) >= MAX_REQUESTS:
            self.sleep(WINDOW_SECONDS - (now - self.stamps[0]))
            self.stamps.popleft()
        self.stamps.append(self.clock())


_limiter = _RateLimiter()


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=_COLS)


def _eligible() -> set[str]:
    from stock_advisor.watchlist import load_watchlist

    return {i.symbol for i in load_watchlist() if i.kind in ELIGIBLE_KINDS}


def to_futu_code(symbol: str) -> str:
    """``0005.HK`` -> ``HK.00005``."""
    num, _, suffix = symbol.upper().partition(".")
    if suffix != "HK" or not num.isdigit():
        raise ValueError(f"not a Hong Kong symbol: {symbol!r}")
    return f"HK.{int(num):05d}"


def _port_open() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=2):
            return True
    except OSError:
        return False


def _context():
    """Open (once) the quote context; a closed port gives one clear error, not a retry loop."""
    if _state["ctx"] is None:
        if not _port_open():
            raise FutuNotRunning(f"Futu OpenD is not running (nothing listens on {HOST}:{PORT})")
        import futu

        _state["ctx"] = futu.OpenQuoteContext(host=HOST, port=PORT)
    return _state["ctx"]


def _check_quota(ctx, code: str) -> None:
    if code in _state["seen"]:
        return
    ret, data = ctx.get_history_kl_quota(get_detail=False)
    if ret != 0:
        raise RuntimeError(f"Futu quota check failed: {data}")
    if data[1] <= 0:
        raise QuotaExhausted("Futu history quota is used up; remaining symbols wait")
    _state["seen"].add(code)


def _history(ctx, code: str, ktype: str, autype: str, start: str, end: str) -> pd.DataFrame:
    frames, key = [], None
    while True:
        _limiter.wait()
        ret, data, key = ctx.request_history_kline(
            code, start=start, end=end, ktype=ktype, autype=autype, max_count=1000, page_req_key=key)
        if ret != 0:
            raise RuntimeError(f"Futu history request failed: {data}")
        frames.append(data)
        if key is None:
            break
    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        return df
    df = df.drop_duplicates("time_key", keep="last")
    df.index = pd.DatetimeIndex(pd.to_datetime(df["time_key"]))
    return df.sort_index()[_COLS]



def _daily(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return _empty()
    out = df.copy()
    out.index = pd.DatetimeIndex(out.index.normalize())
    return out[_COLS]


def _hourly(df: pd.DataFrame) -> pd.DataFrame:
    """Re-index end-labelled Hong Kong bars to canonical UTC bar starts; drop the rest."""
    if df.empty:
        return _empty()
    end_to_start: dict[pd.Timestamp, pd.Timestamp] = {}
    for day in df.index.normalize().unique():
        starts = calendars.hourly_bar_starts("HK", day)
        for s in starts:
            lunch = s.tz_convert("Asia/Hong_Kong").strftime("%H:%M") == "11:30"
            end = s + pd.Timedelta(minutes=30 if lunch else 60)
            end_to_start[end.tz_convert("Asia/Hong_Kong").tz_localize(None)] = s
    starts = [end_to_start.get(ts) for ts in df.index]
    keep = [s is not None for s in starts]
    dropped = len(keep) - sum(keep)
    if dropped:
        log.info("Futu hourly: dropped %d bars that match no canonical bar", dropped)
    out = df[keep].copy()
    out.index = pd.DatetimeIndex([s for s in starts if s is not None])
    return out[~out.index.duplicated(keep="last")].sort_index()[_COLS]


def fetch(symbol: str, interval: str, start=None, end=None) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Return (raw, adjusted); hourly has no adjusted form (``None``). Non-HK or other kinds: empty."""
    if interval not in ("1d", "60m"):
        raise ValueError(f"unknown interval {interval!r}")
    if quality.market_of(symbol) != "HK" or symbol.upper() not in _eligible():
        return _empty(), None
    code = to_futu_code(symbol)
    ctx = _context()
    _check_quota(ctx, code)
    default_start = "2000-01-01" if interval == "1d" else "2016-01-01"
    s = str(pd.Timestamp(start).date()) if start is not None else default_start
    e = str(pd.Timestamp(end).date()) if end is not None else str(pd.Timestamp.today().date())
    if interval == "60m":
        return _hourly(_history(ctx, code, "K_60M", "None", s, e)), None
    raw = _daily(_history(ctx, code, "K_DAY", "None", s, e))
    adjusted = _daily(_history(ctx, code, "K_DAY", "qfq", s, e))
    return raw, adjusted
