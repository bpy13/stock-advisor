"""Price reaction of a target to an event: cumulative returns at fixed horizons.

For an event at time t the start is the last price at or before t.  When t falls outside
trading hours (no bar covers t) the start is the next session's open.  Horizons are:

* "1m", "5m", "15m", "1h", "4h": clock time after the start, read from intraday bars
  (1m bars for everything; 60m bars only for "1h" and "4h").
* "1d", "2d", "3d", "5d", "10d": the Nth daily close after the start.

Missing data gives NaN, never 0.  Items with ``time_precision="day"`` get daily horizons
only.  Items with ``time_precision="batch"`` (GDELT: the time is the crawl batch, not the
story) get the 1h, 4h and daily horizons; 1m, 5m and 15m are NaN.  Trading hours are never hard-coded: a time is "in session" only when an intraday bar
covers it, so holidays and lunch breaks (Hong Kong) are handled by the data itself.

Known approximations, kept simple on purpose:
* A 60m bar is assumed to last a full hour, so the last, shorter bar of a US session makes
  the final 30 minutes look in-session.
* The daily-only fallback (no intraday data) treats an event before 16:00 exchange time on a
  session day as in-session (start = previous close) and later events as after hours.
* A price at time T inside a gap between bars (lunch, overnight) is the last traded price.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

HORIZONS: Tuple[str, ...] = ("1m", "5m", "15m", "1h", "4h", "1d", "2d", "3d", "5d", "10d")
_INTRADAY_SECONDS: Dict[str, int] = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}
_DAILY_CLOSES: Dict[str, int] = {"1d": 1, "2d": 2, "3d": 3, "5d": 5, "10d": 10}
# Horizons each bar size can serve (60m bars are too coarse for minutes).
_INTERVAL_HORIZONS: Dict[str, Tuple[str, ...]] = {
    "1m": ("1m", "5m", "15m", "1h", "4h"),
    "60m": ("1h", "4h"),
}
_BAR_SECONDS: Dict[str, int] = {"1m": 60, "60m": 3600}
_SUB_HOUR_HORIZONS: Tuple[str, ...] = ("1m", "5m", "15m")  # not meaningful for "batch" items
_MAX_GAP = pd.Timedelta(days=5)  # a longer hole in the bars counts as missing data
_MAX_DAILY_GAP_DAYS = 7
_DAILY_CLOSE_HOUR = 16  # fallback only: exchange-local hour after which daily-only events are after hours

PriceLoader = Callable[[str, str], Optional[pd.DataFrame]]
PricesByInterval = Mapping[str, Optional[pd.DataFrame]]


# ---- price series ---------------------------------------------------------------------------


@dataclass
class _Intraday:
    ts: np.ndarray  # int64 ns, UTC, sorted
    open: np.ndarray
    close: np.ndarray
    dur_ns: int


@dataclass
class _Daily:
    dates: np.ndarray  # datetime64[D], exchange-local session dates
    open: np.ndarray
    close: np.ndarray
    tz: str  # exchange time zone from the index; "UTC" when the index is naive


def _clean(frame: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    if frame is None or len(frame) == 0 or "Close" not in frame:
        return None
    frame = frame[~frame["Close"].isna()]
    if frame.empty:
        return None
    if "Open" not in frame:
        frame = frame.assign(Open=frame["Close"])
    frame = frame.assign(Open=frame["Open"].fillna(frame["Close"]))
    return frame.sort_index()


# While `build_reaction_table` runs, the prepared series of each price frame are kept here
# (key: id of the frame; the frame itself is stored too so the id cannot be reused). Without it
# every event cleaned and sorted the whole price history again (about 4 ms per pair).
_SERIES_MEMO: Optional[Dict[Tuple[int, str], Tuple[object, object]]] = None


def _memoized(frame: Optional[pd.DataFrame], kind: str, make: Callable[[], object]):
    if _SERIES_MEMO is None or frame is None:
        return make()
    key = (id(frame), kind)
    hit = _SERIES_MEMO.get(key)
    if hit is None:
        hit = _SERIES_MEMO[key] = (frame, make())
    return hit[1]


def _intraday_series(frame: Optional[pd.DataFrame], interval: str) -> Optional[_Intraday]:
    return _memoized(frame, interval, lambda: _intraday_series_uncached(frame, interval))


def _intraday_series_uncached(frame: Optional[pd.DataFrame], interval: str) -> Optional[_Intraday]:
    frame = _clean(frame)
    if frame is None:
        return None
    index = pd.DatetimeIndex(frame.index)
    index = index.tz_localize("UTC") if index.tz is None else index.tz_convert("UTC")
    return _Intraday(
        ts=index.as_unit("ns").asi8.astype("int64"),  # pandas 3 may hold microseconds
        open=frame["Open"].to_numpy(float),
        close=frame["Close"].to_numpy(float),
        dur_ns=_BAR_SECONDS[interval] * 1_000_000_000,
    )


def _daily_series(frame: Optional[pd.DataFrame]) -> Optional[_Daily]:
    return _memoized(frame, "1d", lambda: _daily_series_uncached(frame))


def _daily_series_uncached(frame: Optional[pd.DataFrame]) -> Optional[_Daily]:
    frame = _clean(frame)
    if frame is None:
        return None
    index = pd.DatetimeIndex(frame.index)
    tz = str(index.tz) if index.tz is not None else "UTC"
    dates = index.tz_localize(None).normalize().to_numpy().astype("datetime64[D]")
    return _Daily(dates=dates, open=frame["Open"].to_numpy(float),
                  close=frame["Close"].to_numpy(float), tz=tz)


def _price_at(series: _Intraday, ts_ns: int) -> float:
    """Last traded price at time ts_ns: the open of the bar covering it, else the last close."""
    i = int(np.searchsorted(series.ts, ts_ns, side="right")) - 1
    if i < 0:
        return float("nan")
    if ts_ns < series.ts[i] + series.dur_ns:
        return float(series.open[i])
    if i + 1 >= len(series.ts) or series.ts[i + 1] - series.ts[i] > _MAX_GAP.value:
        return float("nan")  # data ends or has a hole here
    return float(series.close[i])


def _intraday_start(series: _Intraday, t_ns: int) -> Optional[Tuple[int, float]]:
    """(start time ns, start price) for event time t, or None when the bars do not cover t."""
    i = int(np.searchsorted(series.ts, t_ns, side="right")) - 1
    if i >= 0 and t_ns < series.ts[i] + series.dur_ns:
        return int(series.ts[i]), float(series.open[i])  # a bar covers t: in session
    nxt = i + 1
    if nxt >= len(series.ts):
        return None
    if series.ts[nxt] - t_ns > _MAX_GAP.value:
        return None
    return int(series.ts[nxt]), float(series.open[nxt])  # outside hours: next open


# ---- one price path -------------------------------------------------------------------------


@dataclass
class _Path:
    start_ts: Optional[pd.Timestamp]
    start_source: Optional[str]
    start_price: float
    end_prices: Dict[str, float]


def _daily_closes_after(
    daily: _Daily, first_idx: int, start_price: float
) -> Dict[str, float]:
    """End prices for the daily horizons: the Nth close counting from bar `first_idx`."""
    out = {h: float("nan") for h in _DAILY_CLOSES}
    if np.isnan(start_price):
        return out
    for label, n in _DAILY_CLOSES.items():
        last = first_idx + n - 1
        if last >= len(daily.close):
            continue
        span = np.diff(daily.dates[first_idx : last + 1]).astype("timedelta64[D]").astype(int)
        if len(span) and span.max() > _MAX_DAILY_GAP_DAYS:
            continue  # a hole in the daily data
        out[label] = float(daily.close[last])
    return out


def _local_date(ts_ns: int, tz: str) -> np.datetime64:
    local = pd.Timestamp(ts_ns, tz="UTC").tz_convert(tz)
    return np.datetime64(local.date(), "D")


def _empty_path() -> _Path:
    return _Path(None, None, float("nan"), {})


def _path(event_time: datetime, precision: str, prices: PricesByInterval) -> _Path:
    t = pd.Timestamp(event_time)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    t_ns = int(t.as_unit("ns").value)
    daily = _daily_series(prices.get("1d"))

    if precision == "day":
        return _daily_day_precision(t, daily)

    for interval in ("1m", "60m"):
        series = _intraday_series(prices.get(interval), interval)
        if series is None:
            continue
        start = _intraday_start(series, t_ns)
        if start is None:
            continue
        start_ns, start_price = start
        ends: Dict[str, float] = {}
        for label in _INTERVAL_HORIZONS[interval]:
            ends[label] = _price_at(series, start_ns + _INTRADAY_SECONDS[label] * 1_000_000_000)
        ends.update({h: float("nan") for h in _DAILY_CLOSES})
        if daily is not None:
            day = _local_date(start_ns, daily.tz)
            idx = int(np.searchsorted(daily.dates, day, side="left"))
            # The start is inside a session, so that session's daily bar must exist.
            if idx < len(daily.dates) and daily.dates[idx] == day:
                ends.update(_daily_closes_after(daily, idx, start_price))
        return _Path(pd.Timestamp(start_ns, tz="UTC"), interval, start_price, ends)

    return _daily_exact(t, daily)


def _day_stamp(day: np.datetime64, tz: str) -> pd.Timestamp:
    return pd.Timestamp(str(day)).tz_localize(tz)


def _daily_day_precision(t: pd.Timestamp, daily: Optional[_Daily]) -> _Path:
    """Date-only event: start at the last close before that date, daily horizons only."""
    if daily is None:
        return _empty_path()
    day = np.datetime64(t.date(), "D")
    first = int(np.searchsorted(daily.dates, day, side="left"))  # first session on/after the date
    prev = first - 1
    if prev < 0 or first >= len(daily.dates):
        return _empty_path()
    if (day - daily.dates[prev]).astype(int) > _MAX_DAILY_GAP_DAYS:
        return _empty_path()
    start_price = float(daily.close[prev])
    return _Path(_day_stamp(daily.dates[prev], daily.tz), "1d", start_price,
                 _daily_closes_after(daily, first, start_price))


def _daily_exact(t: pd.Timestamp, daily: Optional[_Daily]) -> _Path:
    """Exact-time event with no intraday bars: coarse start from daily bars (see module doc)."""
    if daily is None:
        return _empty_path()
    local = t.tz_convert(daily.tz)
    day = np.datetime64(local.date(), "D")
    j = int(np.searchsorted(daily.dates, day, side="left"))
    on_session_day = j < len(daily.dates) and daily.dates[j] == day
    if on_session_day and local.hour < _DAILY_CLOSE_HOUR:
        prev = j - 1  # before the close: start at the previous close, this session counts
        if prev < 0 or (day - daily.dates[prev]).astype(int) > _MAX_DAILY_GAP_DAYS:
            return _empty_path()
        price = float(daily.close[prev])
        return _Path(_day_stamp(daily.dates[prev], daily.tz), "1d", price,
                     _daily_closes_after(daily, j, price))
    nxt = j + 1 if on_session_day else j  # after the close or no session: next session's open
    if nxt >= len(daily.dates) or (daily.dates[nxt] - day).astype(int) > _MAX_DAILY_GAP_DAYS:
        return _empty_path()
    price = float(daily.open[nxt])
    return _Path(_day_stamp(daily.dates[nxt], daily.tz), "1d", price,
                 _daily_closes_after(daily, nxt, price))


def _raw_returns(path: _Path) -> Dict[str, float]:
    out = {h: float("nan") for h in HORIZONS}
    if path.start_source is None or not path.start_price or np.isnan(path.start_price):
        return out
    for label, end in path.end_prices.items():
        if end == end:
            out[label] = end / path.start_price - 1.0
    return out


# ---- public API -----------------------------------------------------------------------------


def compute_reaction_path(
    event_time: datetime,
    time_precision: str,
    prices_by_interval: PricesByInterval,
    market_prices: Optional[PricesByInterval] = None,
) -> Tuple[Optional[pd.Timestamp], Optional[str], Dict[str, Tuple[float, float]]]:
    """Like `compute_reaction`, also returning (start_ts, start_source)."""
    path = _path(event_time, time_precision, prices_by_interval)
    raw = _raw_returns(path)
    if market_prices is None:
        market = {h: float("nan") for h in HORIZONS}
    else:
        market = _raw_returns(_path(event_time, time_precision, market_prices))
    result = {h: (raw[h], raw[h] - market[h]) for h in HORIZONS}  # NaN propagates
    if time_precision == "batch":
        nan = float("nan")
        for h in _SUB_HOUR_HORIZONS:
            result[h] = (nan, nan)
    return path.start_ts, path.start_source, result


def compute_reaction(
    event_time: datetime,
    time_precision: str,
    prices_by_interval: PricesByInterval,
    market_prices: Optional[PricesByInterval] = None,
) -> Dict[str, Tuple[float, float]]:
    """Return {horizon: (raw return, market-adjusted return)} for one event and one target.

    `prices_by_interval` maps "1m", "60m" and "1d" to OHLC frames (Open, Close columns;
    intraday index = bar start times, daily index = session dates). Absent frames mean no
    data. `market_prices` has the same shape for the benchmark index; without it the
    adjusted return is NaN. Every horizon is always present; no data gives NaN.
    """
    return compute_reaction_path(event_time, time_precision, prices_by_interval, market_prices)[2]


def default_price_loader(symbol: str, interval: str) -> Optional[pd.DataFrame]:
    """Daily history from the price cache (fetching if stale); intraday read from cache only."""
    from stock_advisor import market_data

    if interval == "1d":
        return market_data.fetch_price_history([symbol], period="max").get(
            market_data.normalize_symbol(symbol)
        )
    path = market_data._intraday_cache_file(market_data.normalize_symbol(symbol), interval)
    if not Path(path).exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


class _CachingLoader:
    """Calls the loader at most once per (symbol, interval) within one table build."""

    def __init__(self, loader: PriceLoader) -> None:
        self._loader = loader
        self._memo: Dict[Tuple[str, str], Optional[pd.DataFrame]] = {}

    def __call__(self, symbol: str, interval: str) -> Optional[pd.DataFrame]:
        key = (symbol, interval)
        if key not in self._memo:
            self._memo[key] = self._loader(symbol, interval)
        return self._memo[key]


_NAT_NS = np.iinfo(np.int64).min  # how a missing start time is held in the int64 column
_SOURCES: Tuple[str, ...] = ("1m", "60m", "1d")  # values of start_source


def build_reaction_table(
    events: Iterable[object],
    targets: Sequence[str],
    price_loader: PriceLoader = default_price_loader,
    keep_empty: bool = False,
) -> pd.DataFrame:
    """Long table of reactions: one row per event, target and horizon *with a known return*.

    Columns: event_id, target, horizon, start_source (categories), raw, adjusted (float32),
    start_ts (UTC). A row is kept when raw or adjusted is known; rows with no price are dropped
    as they are made (they were 99.9% of a full rebuild, which would not fit in memory as
    Python tuples). `keep_empty=True` keeps every row (tests, small inputs).

    Every (event, target) pair of the call counts as *tried*, whether or not it produced rows:
    the caller (`news_backtest_cli.load_or_build_reactions`) records them in
    reactions_tried.parquet. Rows are collected in typed `array.array` columns, about 30 bytes
    each, and the frame is made once at the end.

    Each event needs `id` and `started_at`; `time_precision` is read when present (default
    "exact"). `price_loader(symbol, interval)` returns a frame or None; it is called once per
    symbol and interval ("1m", "60m", "1d"), so a caller can back it with its own cache.
    """
    from array import array

    from stock_advisor.config import MARKET_INDEX_FOR

    loader = _CachingLoader(price_loader)
    events = list(events)
    event_ids = list(dict.fromkeys(e.id for e in events))  # type: ignore[attr-defined]
    event_code = {i: n for n, i in enumerate(event_ids)}
    target_names = list(dict.fromkeys(targets))

    def prices_for(symbol: str) -> Dict[str, Optional[pd.DataFrame]]:
        return {interval: loader(symbol, interval) for interval in ("1m", "60m", "1d")}

    ev_col, tg_col, hz_col, src_col = array("i"), array("h"), array("b"), array("b")
    raw_col, adj_col, ts_col = array("f"), array("f"), array("q")
    nan = float("nan")
    global _SERIES_MEMO
    _SERIES_MEMO = {}
    try:
        for t_code, target in enumerate(target_names):
            own = prices_for(target)
            index_symbol = MARKET_INDEX_FOR(target)
            market = None if index_symbol == target.strip().upper() else prices_for(index_symbol)
            for event in events:
                precision = getattr(event, "time_precision", "exact") or "exact"
                start_ts, source, reaction = compute_reaction_path(
                    event.started_at, precision, own, market  # type: ignore[attr-defined]
                )
                ts_ns = _NAT_NS if start_ts is None else int(start_ts.as_unit("ns").value)
                src = -1 if source is None else _SOURCES.index(source)
                code = event_code[event.id]  # type: ignore[attr-defined]
                for h_code, horizon in enumerate(HORIZONS):
                    raw, adjusted = reaction[horizon]
                    if not keep_empty and raw != raw and adjusted != adjusted:
                        continue
                    ev_col.append(code)
                    tg_col.append(t_code)
                    hz_col.append(h_code)
                    src_col.append(src)
                    raw_col.append(raw if raw == raw else nan)
                    adj_col.append(adjusted if adjusted == adjusted else nan)
                    ts_col.append(ts_ns)
    finally:
        _SERIES_MEMO = None

    def category(codes: "array", names: Sequence[str]) -> pd.Categorical:
        return pd.Categorical.from_codes(np.frombuffer(codes, dtype=codes.typecode)
                                         if len(codes) else np.zeros(0, dtype=np.int8),
                                         categories=list(names))

    start_ts = pd.DatetimeIndex(
        np.frombuffer(ts_col, dtype="int64").view("datetime64[ns]") if len(ts_col)
        else np.zeros(0, dtype="datetime64[ns]")).tz_localize("UTC")
    return pd.DataFrame({
        "event_id": category(ev_col, event_ids),
        "target": category(tg_col, target_names),
        "horizon": category(hz_col, HORIZONS),
        "raw": np.frombuffer(raw_col, dtype="float32") if len(raw_col)
        else np.zeros(0, dtype="float32"),
        "adjusted": np.frombuffer(adj_col, dtype="float32") if len(adj_col)
        else np.zeros(0, dtype="float32"),
        "start_ts": start_ts,
        "start_source": category(src_col, _SOURCES),
    })
