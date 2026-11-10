import numpy as np
import pandas as pd
import pytest

from stock_advisor import price_store, risk


@pytest.fixture(autouse=True)
def _store(tmp_path, monkeypatch):
    monkeypatch.setattr(price_store, "STORE_ROOT", tmp_path)


def _put(symbol, weekly_rets, weeks=None):
    """Write daily bars (Fridays only) whose weekly returns are ``weekly_rets``."""
    n = len(weekly_rets)
    idx = pd.date_range(end="2025-12-26", periods=n + 1, freq="W-FRI")
    close = 100 * np.concatenate([[1.0], np.cumprod(1 + np.asarray(weekly_rets))])
    df = pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                       "volume": 1000.0}, index=idx)
    price_store.write_bars("yahoo", "1d", symbol, df, df)


def _rets(seed, n=120, scale=0.02):
    return np.random.default_rng(seed).normal(0, scale, n)


def test_too_short_symbol_left_out():
    _put("AAA", _rets(1, 120))
    _put("BBB", _rets(2, 30))
    got, short = risk.weekly_returns(["AAA", "BBB"])
    assert list(got.columns) == ["AAA"] and short == ["BBB"]


def test_comoving_stocks_share_a_group():
    base = _rets(1)
    _put("A", base)
    _put("B", base)
    _put("C", _rets(7))
    got, _ = risk.weekly_returns(["A", "B", "C"])
    gs = risk.groups(got)
    assert any(set(g) == {"A", "B"} for g in gs) and any(g == ["C"] for g in gs)


def test_risk_shares_sum_to_one_and_larger_swing_larger_share():
    _put("A", _rets(1, scale=0.01))
    _put("B", _rets(2, scale=0.02))
    got, _ = risk.weekly_returns(["A", "B"])
    shares = risk.risk_shares(got, {"A": 0.5, "B": 0.5})
    assert shares.sum() == pytest.approx(1.0)
    assert shares["B"] > shares["A"]


def test_planted_driver_beta_recovered_and_unlinked_driver_not_clear():
    mkt, oil, kweb = _rets(10, 150), _rets(11, 150), _rets(12, 150)
    stock = 1.0 * mkt + 0.5 * oil + _rets(13, 150, 0.005)
    _put("^GSPC", mkt)
    _put("CL=F", oil)
    _put("KWEB", kweb)
    _put("XYZ", stock)
    got, _ = risk.weekly_returns(["^GSPC", "CL=F", "KWEB", "XYZ"])
    exp = risk.exposures(got, "XYZ")
    assert exp["market"] == "^GSPC"
    assert exp["drivers"]["oil"]["coef"] == pytest.approx(0.5, abs=0.1)
    assert exp["drivers"]["oil"]["clear"]
    assert abs(exp["drivers"]["china_hk_tech"]["t"]) < 2
    assert not exp["drivers"]["china_hk_tech"]["clear"]
    assert exp["market_beta"] == pytest.approx(1.0, abs=0.1)


def test_hk_symbol_uses_hsi():
    m = _rets(1)
    _put("^HSI", m)
    _put("0005.HK", m * 2)
    got, _ = risk.weekly_returns(["^HSI", "0005.HK"])
    assert risk.exposures(got, "0005.HK")["market_beta"] == pytest.approx(2.0, abs=0.1)
