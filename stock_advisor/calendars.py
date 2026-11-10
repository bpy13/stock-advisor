"""Trading calendars: which sessions exist and which hourly bars each one holds.

Wraps ``exchange_calendars`` (XHKG for Hong Kong, XNYS for the US). Typhoon closures are not
modelled on purpose: such a day shows up as a ``gap_before`` flag in the price store.
"""
from __future__ import annotations

from functools import lru_cache

import exchange_calendars as xc
import pandas as pd

_CALENDARS = {"HK": "XHKG", "US": "XNYS"}
_TZ = {"HK": "Asia/Hong_Kong", "US": "America/New_York"}
# Canonical hourly bar starts, local clock time. Bars that start at or after the real close
# (half days, early closes) are dropped.
_BAR_TIMES = {
    "HK": ("09:30", "10:30", "11:30", "13:00", "14:00", "15:00"),
    "US": ("09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30"),
}


@lru_cache(maxsize=None)
def _calendar(market: str):
    if market not in _CALENDARS:
        raise ValueError(f"unknown market {market!r}; expected one of {sorted(_CALENDARS)}")
    return xc.get_calendar(_CALENDARS[market])


def sessions(market: str, start, end) -> pd.DatetimeIndex:
    """Session dates (tz-naive) from ``start`` to ``end`` inclusive."""
    cal = _calendar(market)
    first, last = cal.first_session, cal.last_session
    lo = max(pd.Timestamp(start).tz_localize(None).normalize(), first.tz_localize(None))
    hi = min(pd.Timestamp(end).tz_localize(None).normalize(), last.tz_localize(None))
    if lo > hi:
        return pd.DatetimeIndex([])
    return pd.DatetimeIndex(cal.sessions_in_range(lo, hi).tz_localize(None))


def hourly_bar_starts(market: str, session_date) -> list[pd.Timestamp]:
    """UTC start times of the hourly bars of one session; empty if the market is closed."""
    cal = _calendar(market)
    day = pd.Timestamp(session_date).tz_localize(None).normalize()
    if not cal.is_session(day):
        return []
    close = cal.session_close(day)
    tz = _TZ[market]
    starts = []
    for hhmm in _BAR_TIMES[market]:
        local = pd.Timestamp(f"{day.date()} {hhmm}", tz=tz)
        utc = local.tz_convert("UTC")
        if utc < close:
            starts.append(utc)
    return starts
