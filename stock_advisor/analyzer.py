"""Portfolio numbers from the trade files, the price store and the accounts file.

All money is in HKD. USD trades and prices convert with ``HKD=X`` (HKD per USD).

Limits (the CLI and the dashboard repeat this in one line): the trade file records no cash and
no dividends. So the returns cover the invested holdings only, and dividends count as
reinvested (adjusted prices). Cash in the accounts file counts in "value today" only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from stock_advisor import accounts as accounts_mod
from stock_advisor import price_store
from stock_advisor.transactions import Transaction, load_transactions, normalize_transaction_ticker

CAVEAT = ("Returns cover the invested holdings only: the trade file records no cash and no "
          "dividends, so dividends count as reinvested.")
DEFAULT_USDHKD = 7.8
TRADING_DAYS = 252


@dataclass
class PortfolioSummary:
    value_today: float                 # holdings + cash
    holdings_value: float              # priced holdings + unpriced holdings at cost
    cash: float
    return_without_timing: float       # chained daily return of the priced holdings
    return_with_timing: float          # yearly rate (money-weighted); NaN when undefined
    deepest_fall: float                # <= 0
    fall_start: pd.Timestamp | None
    fall_end: pd.Timestamp | None
    yearly_swing: float                # daily standard deviation x sqrt(252)
    weights: dict[str, float]          # share of holdings_value, sums to 1
    top3_weight: float
    effective_holdings: float          # 1 / sum(weight^2)
    unpriced: list[str] = field(default_factory=list)
    value_series: pd.Series | None = None   # daily value of the priced holdings
    index_series: pd.Series | None = None   # chained index, starts at 1.0


def _symbol(t: Transaction) -> str:
    return normalize_transaction_ticker(t.ticker, t.currency)


def _fx_lookup(fx: pd.Series | None):
    series = fx.dropna().sort_index() if fx is not None else pd.Series(dtype=float)

    def at(date) -> float:
        if series.empty:
            return DEFAULT_USDHKD
        pos = series.index.searchsorted(pd.Timestamp(date), side="right") - 1
        return float(series.iloc[max(pos, 0)])
    return at


def _irr(flows: list[tuple[pd.Timestamp, float]]) -> float:
    t0 = min(d for d, _ in flows)

    def npv(rate: float) -> float:
        return sum(a / (1 + rate) ** ((d - t0).days / 365.0) for d, a in flows)

    try:
        return brentq(npv, -0.99, 100.0)
    except ValueError:  # no sign change: the rate is undefined
        return float("nan")


def summarize(trades: list[Transaction], bars: dict[str, pd.Series], fx: pd.Series | None = None,
              cash_hkd: float = 0.0, as_of=None) -> PortfolioSummary:
    """``bars`` maps symbol to a daily adjusted close series (tz-naive session dates)."""
    if not trades:
        raise ValueError("no trades")
    fx_at = _fx_lookup(fx)
    ccy = {_symbol(t): t.currency.upper() for t in trades}
    priced = [s for s in ccy if s in bars and not bars[s].dropna().empty]
    unpriced = sorted(set(ccy) - set(priced))
    as_of = pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.today().normalize()

    def rate(symbol: str, date) -> float:
        return fx_at(date) if ccy[symbol] == "USD" else 1.0

    # Holdings with no prices are valued at cost and left out of the return series.
    weights_val: dict[str, float] = {}
    for s in unpriced:
        mine = [t for t in trades if _symbol(t) == s]
        qty = sum(t.quantity for t in mine)
        buys = [t for t in mine if t.quantity > 0]
        if qty > 0 and buys:
            avg = sum(t.quantity * t.price for t in buys) / sum(t.quantity for t in buys)
            weights_val[s] = qty * avg * rate(s, as_of)
    unpriced_value = sum(weights_val.values())

    value_series = index = None
    fall, f_start, f_end = 0.0, None, None
    swing = r_total = float("nan")
    priced_value = 0.0
    if priced:
        first_trade = min(pd.Timestamp(t.trade_date) for t in trades if _symbol(t) in priced)
        dates = pd.DatetimeIndex(sorted(
            {d for s in priced for d in bars[s].index if first_trade <= d <= as_of}))
        fx_days = pd.Series([fx_at(d) for d in dates], index=dates)
        px = pd.DataFrame({s: bars[s].reindex(dates).ffill() * (fx_days if ccy[s] == "USD" else 1.0)
                           for s in priced})
        shares = pd.DataFrame(0.0, index=dates, columns=priced)
        for s in priced:
            mine = [t for t in trades if _symbol(t) == s]
            by_day = pd.Series([t.quantity for t in mine],
                               index=pd.DatetimeIndex([pd.Timestamp(t.trade_date) for t in mine]))
            cum = by_day.groupby(level=0).sum().cumsum()
            shares[s] = cum.reindex(cum.index.union(dates)).ffill().reindex(dates).fillna(0.0)
        value = (shares * px).fillna(0.0)
        value_series = value.sum(axis=1)
        prev_value = value_series.shift(1)
        pnl = (shares.shift(1) * (px - px.shift(1))).sum(axis=1)
        daily = (pnl / prev_value).where(prev_value > 0).dropna()
        index = (1 + daily.reindex(dates).fillna(0.0)).cumprod()
        r_total = float(index.iloc[-1] - 1)
        if len(daily) > 1:
            swing = float(daily.std(ddof=1) * np.sqrt(TRADING_DAYS))
        draw = index / index.cummax() - 1
        fall = float(draw.min())
        if fall < 0:
            f_end = draw.idxmin()
            f_start = index.loc[:f_end].idxmax()
        priced_value = float(value_series.iloc[-1])
        weights_val.update({s: float(value[s].iloc[-1]) for s in priced})

    holdings_value = priced_value + unpriced_value
    weights = ({s: v / holdings_value for s, v in weights_val.items() if v > 0}
               if holdings_value > 0 else {})
    top3 = sum(sorted(weights.values(), reverse=True)[:3])
    eff = 1.0 / sum(w * w for w in weights.values()) if weights else float("nan")

    flows = [(pd.Timestamp(t.trade_date), -t.quantity * t.price * rate(_symbol(t), t.trade_date))
             for t in trades]
    flows.append((as_of, holdings_value))

    return PortfolioSummary(
        value_today=holdings_value + cash_hkd, holdings_value=holdings_value, cash=cash_hkd,
        return_without_timing=r_total, return_with_timing=_irr(flows), deepest_fall=fall,
        fall_start=f_start, fall_end=f_end, yearly_swing=swing, weights=weights,
        top3_weight=top3, effective_holdings=eff, unpriced=unpriced,
        value_series=value_series, index_series=index)


def load_summary(accounts_path=None, as_of=None) -> PortfolioSummary:
    """Summary of the real portfolio: trades and cash from the accounts file, bars from the store."""
    accounts, _limits = accounts_mod.load_accounts(accounts_path)
    root = Path(__file__).resolve().parent.parent
    trades: list[Transaction] = []
    for acc in accounts:
        if acc.trade_file:
            trades += load_transactions(root / acc.trade_file)
    bars = {}
    for t in trades:
        s = _symbol(t)
        if s not in bars:
            b = price_store.read_bars(s, "1d", adjusted=True)
            if not b.empty:
                bars[s] = b["close"]
    fx_bars = price_store.read_bars("HKD=X", "1d", adjusted=False)
    fx = fx_bars["close"] if not fx_bars.empty else None
    usd = float(fx.dropna().iloc[-1]) if fx is not None and not fx.dropna().empty else DEFAULT_USDHKD
    cash = sum(a.cash.get("HKD", 0.0) + a.cash.get("USD", 0.0) * usd for a in accounts)
    return summarize(trades, bars, fx, cash, as_of)
