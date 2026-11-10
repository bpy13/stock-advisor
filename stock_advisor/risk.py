"""Portfolio risk structure from weekly returns: groups, risk shares and driver exposures.

Weekly returns come from adjusted daily bars in the price store. A symbol with under
``MIN_WEEKS`` weekly returns is reported as too short and left out.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from sklearn.covariance import LedoitWolf

from stock_advisor import price_store

MIN_WEEKS = 52
GROUP_CUT = 0.5  # distance 1 - correlation
CLEAR_T = 2.0
HAC_LAGS = 4
MARKETS = {"HK": "^HSI", "US": "^GSPC"}
# The six drivers Brian chose on 2026-10-30. US rates are a yield, so its weekly change is a
# difference, not a percentage return.
DRIVERS = {"oil": "CL=F", "us_rates": "^TNX", "china_hk_tech": "KWEB",
           "us_tech": "^NDX", "cyber_security": "HACK", "usd_cny": "CNY=X"}
_DIFF_SYMBOLS = {"^TNX"}


def _weekly(symbol: str, years: int) -> pd.Series:
    bars = price_store.read_bars(symbol, "1d", adjusted=True)
    if bars.empty:
        return pd.Series(dtype=float)
    close = bars["close"].astype(float)
    close.index = pd.DatetimeIndex(close.index).tz_localize(None) if close.index.tz else close.index
    close = close[close.index >= close.index.max() - pd.DateOffset(years=years)]
    weekly = close.resample("W-FRI").last().dropna()
    out = weekly.diff() if symbol in _DIFF_SYMBOLS else weekly.pct_change()
    return out.dropna()


def weekly_returns(symbols: list[str], years: int = 3) -> tuple[pd.DataFrame, list[str]]:
    """Weekly returns (one column per symbol) and the symbols left out as too short."""
    series, too_short = {}, []
    for symbol in symbols:
        s = _weekly(symbol, years)
        if len(s) < MIN_WEEKS:
            too_short.append(symbol)
        else:
            series[symbol] = s
    return pd.DataFrame(series), too_short


def groups(returns: pd.DataFrame) -> list[list[str]]:
    """Clusters of symbols that move together: average linkage on 1 - correlation, cut at 0.5."""
    cols = list(returns.columns)
    if len(cols) < 2:
        return [cols] if cols else []
    dist = (1 - returns.corr().clip(-1, 1)).to_numpy()
    dist = np.nan_to_num((dist + dist.T) / 2, nan=1.0)
    np.fill_diagonal(dist, 0.0)
    labels = fcluster(linkage(squareform(dist, checks=False), "average"), GROUP_CUT, "distance")
    out: dict[int, list[str]] = {}
    for col, label in zip(cols, labels):
        out.setdefault(int(label), []).append(col)
    return list(out.values())


def risk_shares(returns: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Each holding's share of the portfolio variance (Ledoit-Wolf covariance); sums to 1."""
    cols = [c for c in returns.columns if c in weights]
    w = np.array([weights[c] for c in cols], dtype=float)
    cov = LedoitWolf().fit(returns[cols].dropna().to_numpy()).covariance_
    contrib = w * (cov @ w)
    return pd.Series(contrib / contrib.sum(), index=cols)


def exposures(returns: pd.DataFrame, symbol: str) -> dict:
    """Market beta, and per driver the coefficient and t-value with the market in the model.

    ``returns`` must hold the symbol, its market and the drivers as columns (use
    ``weekly_returns`` on all of them). Drivers missing from it are left out.
    """
    market = MARKETS["HK" if symbol.upper().endswith(".HK") else "US"]
    y = returns[symbol]
    result: dict = {"market": market, "market_beta": None, "drivers": {}}
    if market in returns:
        data = pd.concat([y, returns[market]], axis=1).dropna()
        fit = sm.OLS(data.iloc[:, 0], sm.add_constant(data.iloc[:, 1:])).fit()
        result["market_beta"] = float(fit.params[market])
    for name, driver in DRIVERS.items():
        if driver not in returns or market not in returns or driver == symbol:
            continue
        data = pd.concat([y, returns[[market, driver]]], axis=1).dropna()
        if len(data) < MIN_WEEKS:
            continue
        fit = sm.OLS(data.iloc[:, 0], sm.add_constant(data.iloc[:, 1:])).fit(
            cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS})
        t = float(fit.tvalues[driver])
        result["drivers"][name] = {"coef": float(fit.params[driver]), "t": t, "clear": abs(t) >= CLEAR_T}
    return result
