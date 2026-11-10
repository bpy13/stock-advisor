import pandas as pd

from stock_advisor import quality


def _bars(index, close, volume=None):
    n = len(index)
    return pd.DataFrame({
        "open": close, "high": close, "low": close, "close": close,
        "volume": volume if volume is not None else [1000] * n,
    }, index=index)


def test_market_of():
    assert quality.market_of("0005.HK") == "HK"
    assert quality.market_of("AAPL") == "US"
    assert quality.market_of("BRK-B") == "US"
    assert quality.market_of("^HSI") == "OTHER"
    assert quality.market_of("CL=F") == "OTHER"


def test_no_trade_only_when_tradable():
    idx = pd.to_datetime(["2025-03-03", "2025-03-04"])
    bars = _bars(idx, [10.0, 10.0], volume=[0, 500])
    assert list(quality.flag_bars(bars, "US", "1d", True)["no_trade"]) == [True, False]
    assert not quality.flag_bars(bars, "OTHER", "1d", False)["no_trade"].any()


def test_big_move_daily_and_hourly_limits():
    idx = pd.to_datetime(["2025-03-03", "2025-03-04", "2025-03-05"])
    flagged = quality.flag_bars(_bars(idx, [100.0, 125.0, 190.0]), "US", "1d", True)
    # +25% is below the 40% daily limit; +52% is above it.
    assert list(flagged["big_move"]) == [False, False, True]
    hidx = pd.DatetimeIndex(["2025-03-03 14:30", "2025-03-03 15:30", "2025-03-03 16:30"], tz="UTC")
    hourly = quality.flag_bars(_bars(hidx, [100.0, 125.0, 126.0]), "US", "60m", True)
    assert list(hourly["big_move"]) == [False, True, False]  # +25% beats the 20% hourly limit


def test_gap_before_daily_one_missing_session():
    # 2025-03-05 (Wed) is missing between Tue 4 and Thu 6; the weekend is not a gap.
    idx = pd.to_datetime(["2025-02-28", "2025-03-03", "2025-03-04", "2025-03-06"])
    flagged = quality.flag_bars(_bars(idx, [10.0] * 4), "US", "1d", True)
    assert list(flagged["gap_before"]) == [0, 0, 0, 1]


def test_gap_before_hourly_counts_missing_bars():
    # US winter: bars start 14:30, 15:30, ... UTC. Skip the 16:30 and 17:30 bars.
    idx = pd.DatetimeIndex(["2025-01-06 14:30", "2025-01-06 15:30", "2025-01-06 18:30"], tz="UTC")
    flagged = quality.flag_bars(_bars(idx, [10.0] * 3), "US", "60m", True)
    assert list(flagged["gap_before"]) == [0, 0, 2]


def test_other_market_has_no_gaps():
    idx = pd.to_datetime(["2025-03-03", "2025-03-10"])
    assert list(quality.flag_bars(_bars(idx, [1.0, 1.0]), "OTHER", "1d", False)["gap_before"]) == [0, 0]
