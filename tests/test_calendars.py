import pandas as pd
import pytest

from stock_advisor.calendars import hourly_bar_starts, sessions


def test_hk_half_day_has_three_bars():
    bars = hourly_bar_starts("HK", "2025-12-24")
    assert [b.tz_convert("Asia/Hong_Kong").strftime("%H:%M") for b in bars] == [
        "09:30", "10:30", "11:30"]


def test_hk_full_day_has_six_bars_with_lunch_gap():
    bars = hourly_bar_starts("HK", "2025-12-23")
    assert [b.tz_convert("Asia/Hong_Kong").strftime("%H:%M") for b in bars] == [
        "09:30", "10:30", "11:30", "13:00", "14:00", "15:00"]
    assert all(str(b.tz) == "UTC" for b in bars)


def test_hk_holiday_has_no_session_or_bars():
    assert hourly_bar_starts("HK", "2025-01-29") == []
    days = sessions("HK", "2025-01-27", "2025-01-31")
    assert pd.Timestamp("2025-01-29") not in days
    assert pd.Timestamp("2025-01-27") in days


def test_us_early_close_has_four_bars():
    bars = hourly_bar_starts("US", "2025-11-28")
    assert len(bars) == 4
    assert bars[-1].tz_convert("America/New_York").strftime("%H:%M") == "12:30"


def test_us_full_day_has_seven_bars():
    bars = hourly_bar_starts("US", "2025-11-26")
    assert len(bars) == 7
    assert bars[-1].tz_convert("America/New_York").strftime("%H:%M") == "15:30"


def test_us_summer_and_winter_start_at_different_utc_hours():
    summer = hourly_bar_starts("US", "2025-07-15")[0]
    winter = hourly_bar_starts("US", "2025-01-15")[0]
    assert (summer.hour, winter.hour) == (13, 14)


def test_sessions_are_tz_naive_and_unknown_market_fails():
    days = sessions("US", "2025-11-24", "2025-11-28")
    assert days.tz is None and len(days) == 4  # Thanksgiving missing
    with pytest.raises(ValueError):
        sessions("JP", "2025-01-01", "2025-01-10")
