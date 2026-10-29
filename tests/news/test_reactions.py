"""Tests for the reaction table, on synthetic price frames (no network, no caches)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from stock_advisor.news import reactions
from stock_advisor.news.reactions import HORIZONS, build_reaction_table, compute_reaction

DAILY_HORIZONS = ["1d", "2d", "3d", "5d", "10d"]
INTRADAY_HORIZONS = ["1m", "5m", "15m", "1h", "4h"]


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


def bars(start: str, periods: int, freq: str, first_open: float, step: float) -> pd.DataFrame:
    """Bars whose Open rises by `step` per bar; Close is Open + step / 2."""
    index = pd.date_range(start, periods=periods, freq=freq, tz="UTC")
    opens = first_open + step * np.arange(periods)
    return pd.DataFrame({"Open": opens, "Close": opens + step / 2}, index=index)


def us_session_1m(day: str, first_open: float = 100.0) -> pd.DataFrame:
    """US session 09:30-16:00 ET in January (14:30-21:00 UTC): 390 one-minute bars."""
    return bars(f"{day} 14:30", 390, "1min", first_open, 0.1)


def daily_frame(first_day: str, periods: int, tz: str, first_close: float = 100.0) -> pd.DataFrame:
    """Business-day bars, Close = first_close + position, Open = Close - 0.5."""
    index = pd.date_range(first_day, periods=periods, freq="B", tz=tz)
    closes = first_close + np.arange(periods, dtype=float)
    return pd.DataFrame({"Open": closes - 0.5, "Close": closes}, index=index)


def all_nan(result: dict, labels) -> bool:
    return all(np.isnan(result[h][0]) and np.isnan(result[h][1]) for h in labels)


def test_in_session_minute_horizons_use_the_open_of_the_covering_bar():
    prices = {"1m": us_session_1m("2024-01-02")}  # Tuesday
    # 15:00:20 UTC lies in the 15:00 bar, which is bar number 30 (open 103.0).
    result = compute_reaction(utc("2024-01-02 15:00:20"), "exact", prices)
    assert result["1m"][0] == pytest.approx(103.1 / 103.0 - 1)
    assert result["5m"][0] == pytest.approx(103.5 / 103.0 - 1)
    assert result["15m"][0] == pytest.approx(104.5 / 103.0 - 1)
    assert result["1h"][0] == pytest.approx(109.0 / 103.0 - 1)
    assert result["4h"][0] == pytest.approx(127.0 / 103.0 - 1)  # 19:00 UTC, bar 270
    assert np.isnan(result["1d"][0])  # no daily data given


def test_batch_precision_drops_sub_hour_horizons_but_keeps_hour_and_day():
    ny = "America/New_York"
    prices = {"1m": us_session_1m("2024-01-02"), "1d": daily_frame("2024-01-02", 15, ny)}
    market = {"1m": us_session_1m("2024-01-02", 50.0),
              "1d": daily_frame("2024-01-02", 15, ny, 50.0)}
    exact = compute_reaction(utc("2024-01-02 15:00:20"), "exact", prices, market)
    batch = compute_reaction(utc("2024-01-02 15:00:20"), "batch", prices, market)
    assert all_nan(batch, ["1m", "5m", "15m"])
    assert not all_nan(exact, ["1m", "5m", "15m"])
    for horizon in ["1h", "4h", "1d"]:
        assert not np.isnan(batch[horizon][0]) and not np.isnan(batch[horizon][1])
        assert batch[horizon] == pytest.approx(exact[horizon])


def test_start_source_is_reported_per_event():
    prices = {"1m": us_session_1m("2024-01-02")}
    start_ts, source, _ = reactions.compute_reaction_path(utc("2024-01-02 15:00:20"), "exact", prices)
    assert source == "1m"
    assert start_ts == pd.Timestamp("2024-01-02 15:00", tz="UTC")


def test_event_after_the_close_starts_at_the_next_session_open():
    day1 = us_session_1m("2024-01-02", 100.0)
    day2 = us_session_1m("2024-01-03", 200.0)
    prices = {"1m": pd.concat([day1, day2])}
    # 23:00 UTC is 18:00 ET: after the close.
    start_ts, source, result = reactions.compute_reaction_path(utc("2024-01-02 23:00"), "exact", prices)
    assert start_ts == pd.Timestamp("2024-01-03 14:30", tz="UTC")
    assert source == "1m"
    assert result["1m"][0] == pytest.approx(200.1 / 200.0 - 1)
    assert result["1h"][0] == pytest.approx(206.0 / 200.0 - 1)


def test_holiday_is_detected_from_the_data_not_a_calendar():
    # Monday 2024-01-01 has no bars; an event at 15:00 UTC then starts on Tuesday's open.
    prices = {"1m": us_session_1m("2024-01-02")}
    start_ts, _, result = reactions.compute_reaction_path(utc("2024-01-01 15:00"), "exact", prices)
    assert start_ts == pd.Timestamp("2024-01-02 14:30", tz="UTC")
    assert result["1m"][0] == pytest.approx(100.1 / 100.0 - 1)


def test_hong_kong_lunch_break_counts_as_outside_trading_hours():
    # 60m bars 09:30, 10:30, 11:30 (to 12:00), then 13:00, 14:00, 15:00 HKT = 01:30 ... UTC.
    morning = bars("2024-01-02 01:30", 3, "60min", 100.0, 1.0)
    afternoon = bars("2024-01-02 05:00", 3, "60min", 110.0, 1.0)
    prices = {"60m": pd.concat([morning, afternoon])}
    # 04:30 UTC = 12:30 HKT: the bar at 03:30 UTC ended at 04:00, so this is lunch.
    start_ts, source, result = reactions.compute_reaction_path(utc("2024-01-02 04:30"), "exact", prices)
    assert source == "60m"
    assert start_ts == pd.Timestamp("2024-01-02 05:00", tz="UTC")  # 13:00 HKT
    assert result["1h"][0] == pytest.approx(111.0 / 110.0 - 1)
    # Minute horizons need 1m bars, which are absent.
    assert all_nan(result, ["1m", "5m", "15m"])


def test_minute_bars_win_over_hourly_bars_when_both_cover_the_event():
    prices = {"1m": us_session_1m("2024-01-02"), "60m": bars("2024-01-02 14:30", 7, "60min", 50.0, 1.0)}
    _, source, result = reactions.compute_reaction_path(utc("2024-01-02 15:00"), "exact", prices)
    assert source == "1m"
    assert result["1h"][0] == pytest.approx(109.0 / 103.0 - 1)


def test_falls_back_to_hourly_when_minute_bars_do_not_cover_the_event():
    prices = {
        "1m": us_session_1m("2024-03-01"),  # far from the event
        "60m": bars("2024-01-02 14:30", 7, "60min", 50.0, 1.0),
    }
    _, source, _ = reactions.compute_reaction_path(utc("2024-01-02 15:45"), "exact", prices)
    assert source == "60m"


def test_daily_horizons_are_the_nth_close_after_an_in_session_start():
    ny = "America/New_York"
    prices = {
        "1m": us_session_1m("2024-01-02"),
        "1d": daily_frame("2024-01-02", 15, ny),  # closes 100, 101, 102, ...
    }
    result = compute_reaction(utc("2024-01-02 15:00"), "exact", prices)  # start price 103.0
    # The 1st close after the event is the same day's close (100).
    assert result["1d"][0] == pytest.approx(100.0 / 103.0 - 1)
    assert result["2d"][0] == pytest.approx(101.0 / 103.0 - 1)
    assert result["3d"][0] == pytest.approx(102.0 / 103.0 - 1)
    assert result["5d"][0] == pytest.approx(104.0 / 103.0 - 1)
    assert result["10d"][0] == pytest.approx(109.0 / 103.0 - 1)


def test_after_hours_event_counts_closes_from_the_next_session():
    ny = "America/New_York"
    prices = {
        "1m": pd.concat([us_session_1m("2024-01-02"), us_session_1m("2024-01-03", 200.0)]),
        "1d": daily_frame("2024-01-02", 15, ny),
    }
    result = compute_reaction(utc("2024-01-02 23:00"), "exact", prices)
    # Start: Wednesday's open (200). The 1st close after it is Wednesday's close (101).
    assert result["1d"][0] == pytest.approx(101.0 / 200.0 - 1)
    assert result["2d"][0] == pytest.approx(102.0 / 200.0 - 1)


def test_day_precision_items_get_only_daily_horizons():
    ny = "America/New_York"
    prices = {"1m": us_session_1m("2024-01-03"), "1d": daily_frame("2024-01-02", 15, ny)}
    start_ts, source, result = reactions.compute_reaction_path(utc("2024-01-03 00:00"), "day", prices)
    assert source == "1d"
    assert all_nan(result, INTRADAY_HORIZONS)
    # Start: the close before Jan 3 (Jan 2 = 100). The 1st close after is Jan 3 = 101.
    assert result["1d"][0] == pytest.approx(0.01)
    assert result["2d"][0] == pytest.approx(0.02)
    assert result["5d"][0] == pytest.approx(0.05)
    assert result["10d"][0] == pytest.approx(0.10)
    assert start_ts == pd.Timestamp("2024-01-02", tz=ny)


def test_exact_event_with_only_daily_data_uses_a_coarse_start():
    ny = "America/New_York"
    prices = {"1d": daily_frame("2024-01-02", 15, ny)}
    # 14:00 UTC is 09:00 ET on Wednesday Jan 3: before the close, so start = Jan 2 close (100).
    morning = compute_reaction(utc("2024-01-03 14:00"), "exact", prices)
    assert morning["1d"][0] == pytest.approx(0.01)
    # 22:00 UTC is 17:00 ET: after the close, so start = Thursday's open (101.5), 1st close 102.
    _, source, evening = reactions.compute_reaction_path(utc("2024-01-03 22:00"), "exact", prices)
    assert source == "1d"
    assert evening["1d"][0] == pytest.approx(102.0 / 101.5 - 1)
    assert all_nan(evening, INTRADAY_HORIZONS)


def test_missing_data_is_nan_not_zero():
    ny = "America/New_York"
    # Event after the last bar.
    result = compute_reaction(utc("2024-02-01 15:00"), "exact", {"1m": us_session_1m("2024-01-02")})
    assert all_nan(result, HORIZONS)
    # No prices at all, or empty frames.
    assert all_nan(compute_reaction(utc("2024-01-02 15:00"), "exact", {}), HORIZONS)
    empty = {"1m": pd.DataFrame(), "60m": None, "1d": pd.DataFrame()}
    assert all_nan(compute_reaction(utc("2024-01-02 15:00"), "exact", empty), HORIZONS)
    # Daily history too short for the 10th close.
    short = {"1d": daily_frame("2024-01-02", 6, ny)}
    result = compute_reaction(utc("2024-01-03 00:00"), "day", short)
    assert not np.isnan(result["3d"][0])
    assert np.isnan(result["10d"][0])
    # A horizon that runs past the end of the minute bars is NaN, while earlier ones remain.
    late = compute_reaction(utc("2024-01-02 20:30"), "exact", {"1m": us_session_1m("2024-01-02")})
    assert not np.isnan(late["15m"][0])
    assert np.isnan(late["4h"][0])


def test_hole_in_daily_data_gives_nan():
    ny = "America/New_York"
    daily = daily_frame("2024-01-02", 15, ny)
    daily = daily.drop(daily.index[3:8])  # a 7+ day hole
    result = compute_reaction(utc("2024-01-03 00:00"), "day", {"1d": daily})
    assert not np.isnan(result["2d"][0])
    assert np.isnan(result["5d"][0])


def test_market_adjusted_return_subtracts_the_index_return():
    ny = "America/New_York"
    stock = {"1d": daily_frame("2024-01-02", 15, ny, 100.0)}
    index = {"1d": daily_frame("2024-01-02", 15, ny, 1000.0)}
    result = compute_reaction(utc("2024-01-03 00:00"), "day", stock, index)
    raw_stock, adjusted = result["1d"]
    assert raw_stock == pytest.approx(0.01)
    assert adjusted == pytest.approx(0.01 - 1.0 / 1000.0)
    # Without a market the adjusted return is NaN but the raw return stays.
    no_market = compute_reaction(utc("2024-01-03 00:00"), "day", stock)
    assert no_market["1d"][0] == pytest.approx(0.01)
    assert np.isnan(no_market["1d"][1])


def _loader_with_calls(frames: dict):
    calls = []

    def loader(symbol: str, interval: str):
        calls.append((symbol, interval))
        return frames.get((symbol, interval))

    return loader, calls


def test_build_reaction_table_shape_and_one_load_per_symbol_interval():
    ny = "America/New_York"
    frames = {
        ("AAPL", "1d"): daily_frame("2024-01-02", 15, ny, 100.0),
        ("^GSPC", "1d"): daily_frame("2024-01-02", 15, ny, 1000.0),
        ("^GSPC", "1m"): None,
    }
    loader, calls = _loader_with_calls(frames)
    events = [
        SimpleNamespace(id="e1", started_at=utc("2024-01-03 00:00"), time_precision="day"),
        SimpleNamespace(id="e2", started_at=utc("2024-01-04 00:00"), time_precision="day"),
    ]
    compact = build_reaction_table(events, ["AAPL", "^GSPC"], loader)
    first_calls = list(calls)
    calls.clear()
    assert compact["raw"].dtype == "float32"
    assert not (compact["raw"].isna() & compact["adjusted"].isna()).any()  # no empty rows
    assert 0 < len(compact) < 2 * 2 * len(HORIZONS)
    table = build_reaction_table(events, ["AAPL", "^GSPC"], loader, keep_empty=True)
    assert list(table.columns) == [
        "event_id", "target", "horizon", "raw", "adjusted", "start_ts", "start_source"
    ]
    assert len(table) == 2 * 2 * len(HORIZONS)
    known = table[table["raw"].notna() | table["adjusted"].notna()]
    assert len(known) == len(compact)
    assert len(first_calls) == len(set(first_calls))  # each (symbol, interval) loaded once
    assert ("^GSPC", "1d") in first_calls

    aapl = table[(table.target == "AAPL") & (table.event_id == "e1") & (table.horizon == "1d")].iloc[0]
    assert aapl.raw == pytest.approx(0.01)
    assert aapl.adjusted == pytest.approx(0.01 - 0.001)
    assert aapl.start_source == "1d"
    # An index is not adjusted against itself.
    gspc = table[(table.target == "^GSPC") & (table.event_id == "e1") & (table.horizon == "1d")].iloc[0]
    assert gspc.raw == pytest.approx(0.001)
    assert np.isnan(gspc.adjusted)
    # Intraday horizons stay NaN for day-precision events.
    intraday = table[table.horizon == "1h"]
    assert intraday.raw.isna().all()


def test_hong_kong_tickers_are_adjusted_by_the_hang_seng_index():
    hk = "Asia/Hong_Kong"
    frames = {
        ("0700.HK", "1d"): daily_frame("2024-01-02", 15, hk, 100.0),
        ("^HSI", "1d"): daily_frame("2024-01-02", 15, hk, 1000.0),
    }
    loader, _ = _loader_with_calls(frames)
    events = [SimpleNamespace(id="e1", started_at=utc("2024-01-03 00:00"), time_precision="day")]
    table = build_reaction_table(events, ["0700.HK"], loader)
    row = table[table.horizon == "1d"].iloc[0]
    assert row.event_id == "e1" and row.target == "0700.HK"
    assert row.adjusted == pytest.approx(0.01 - 0.001)


def test_events_without_a_precision_attribute_default_to_exact():
    loader, _ = _loader_with_calls({("^GSPC", "1m"): us_session_1m("2024-01-02")})
    events = [SimpleNamespace(id="e1", started_at=utc("2024-01-02 15:00"))]
    table = build_reaction_table(events, ["^GSPC"], loader)
    assert table[table.horizon == "1m"].iloc[0].raw == pytest.approx(103.1 / 103.0 - 1)
