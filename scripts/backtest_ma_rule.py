"""Backtest the "200-day rule" from a shared video (requests Task R5, 2026-11-28).

Rule: hold the index while its close is above its 200-day moving average; hold cash (earning the
13-week T-bill rate where the data has it) while the close is below. The decision uses the close
of day t and takes effect for the move from t to t+1, so the rule never sees tomorrow's price.
Each switch in or out costs ``cost`` (0.1 %). Buy-and-hold pays one entry trade.

    python scripts/backtest_ma_rule.py          # prints the tables, writes the PNG

Reads the price store (Yahoo daily). ^IRX (T-bill rate) is fetched from Yahoo into the store once.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PNG = ROOT / "docs" / "research" / "2026-11-28-200-day-rule.png"
WINDOW = 200
COST = 0.001


def moving_average(close: pd.Series, window: int, kind: str) -> pd.Series:
    if kind == "sma":
        return close.rolling(window).mean()
    if kind == "ema":
        return close.ewm(span=window, adjust=False, min_periods=window).mean()
    raise ValueError(f"unknown kind {kind!r}")


def backtest(close: pd.Series, window: int = WINDOW, kind: str = "sma", cost: float = COST,
             cash_daily: pd.Series | None = None) -> pd.DataFrame:
    """Daily equity of the rule and of buy-and-hold, both starting at 1 before the entry trade.

    Starts on the first day the average exists. Columns: pos (1 = in the index after that day's
    close), rule, hold.
    """
    ma = moving_average(close, window, kind)
    start = ma.first_valid_index()
    close, ma = close.loc[start:], ma.loc[start:]
    pos = (close > ma).astype(int)
    ret = close.pct_change().fillna(0.0)
    cash = (pd.Series(0.0, index=close.index) if cash_daily is None
            else cash_daily.reindex(close.index).ffill().fillna(0.0))
    held = pos.shift(1, fill_value=0)              # position carried over the move into day t
    trades = (pos != held).astype(int)             # switch at day t's close
    rule = (1 + held * ret + (1 - held) * cash.shift(1, fill_value=0.0)) * (1 - cost) ** trades
    hold = (1 + ret)
    hold.iloc[0] *= 1 - cost
    return pd.DataFrame({"pos": pos, "rule": rule.cumprod(), "hold": hold.cumprod()})


def metrics(equity: pd.Series, pos: pd.Series | None = None) -> dict:
    """Total and yearly return, deepest fall, trades and time in the market over ``equity``."""
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    total = equity.iloc[-1] / equity.iloc[0]
    out = {"total": total - 1, "yearly": total ** (1 / years) - 1 if years > 0 else np.nan,
           "max_dd": (equity / equity.cummax() - 1).min()}
    if pos is not None:
        out["trades"] = int((pos.diff().fillna(0) != 0).sum())
        out["in_market"] = float(pos.shift(1).iloc[1:].mean())
    return out


def tbill_daily(irx: pd.Series) -> pd.Series:
    """^IRX is the 13-week T-bill yield in percent a year; turn it into a per-trading-day return."""
    return (1 + irx / 100) ** (1 / 252) - 1


def _load(symbol: str) -> pd.Series:
    from stock_advisor import price_store
    return price_store.read_bars(symbol, "1d", adjusted=True, source="yahoo")["close"].dropna()


def _load_irx() -> pd.Series:
    from stock_advisor import price_store
    from stock_advisor.price_sources import yahoo
    irx = _load("^IRX")
    if irx.empty or irx.index[-1] < pd.Timestamp.now() - pd.Timedelta(days=10):
        raw, adj = yahoo.fetch("^IRX", "1d")
        price_store.write_bars("yahoo", "1d", "^IRX", raw, adj)
        irx = _load("^IRX")
    return irx


def _pct(x: float) -> str:
    return f"{x * 100:,.1f}%"


def table(runs: dict[str, pd.DataFrame]) -> str:
    """Markdown rows: whole period, first half, second half, for each run and each line."""
    lines = ["| Test | Period | Line | Total return | Yearly | Deepest fall | Trades | In market |",
             "|---|---|---|---:|---:|---:|---:|---:|"]
    for name, bt in runs.items():
        idx = bt.index
        mid = idx[0] + (idx[-1] - idx[0]) / 2
        periods = [("whole", bt), ("1st half", bt.loc[:mid]), ("2nd half", bt.loc[mid:])]
        for label, part in periods:
            span = f"{label} {part.index[0]:%Y-%m}..{part.index[-1]:%Y-%m}"
            for line in ("hold", "rule"):
                m = metrics(part[line], part["pos"] if line == "rule" else None)
                trades = str(m.get("trades", 1 if label == "whole" else 0))
                inm = _pct(m.get("in_market", 1.0))
                lines.append(f"| {name} | {span} | {line} | {_pct(m['total'])} | "
                             f"{_pct(m['yearly'])} | {_pct(m['max_dd'])} | {trades} | {inm} |")
    return "\n".join(lines)


def draw_png(panels: list[tuple[str, pd.DataFrame, pd.DataFrame]], path: Path) -> None:
    """One picture, one panel per data set: hold, SMA rule and EMA rule on a log scale."""
    from PIL import Image, ImageDraw, ImageFont

    width, panel_h, pad_l, pad_r, pad_t, pad_b = 1080, 700, 130, 40, 110, 70
    img = Image.new("RGB", (width, panel_h * len(panels)), "white")
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=30)
    small = ImageFont.load_default(size=24)
    colours = {"Buy and hold": (90, 90, 90), "200-day simple": (0, 114, 178),
               "200-day exponential": (230, 120, 0)}
    for i, (title, sma, ema) in enumerate(panels):
        top = i * panel_h
        lines = {"Buy and hold": sma["hold"], "200-day simple": sma["rule"],
                 "200-day exponential": ema["rule"].reindex(sma.index).ffill()}
        lo = np.log10(min(s.min() for s in lines.values()))
        hi = np.log10(max(s.max() for s in lines.values()))
        x0, x1, y0, y1 = pad_l, width - pad_r, top + pad_t, top + panel_h - pad_b
        t0, t1 = sma.index[0].value, sma.index[-1].value

        def xy(ts, v, x0=x0, x1=x1, y0=y0, y1=y1, t0=t0, t1=t1, lo=lo, hi=hi):
            return (x0 + (ts.value - t0) / (t1 - t0) * (x1 - x0),
                    y1 - (np.log10(v) - lo) / (hi - lo) * (y1 - y0))

        d.text((pad_l, top + 15), title, fill="black", font=font)
        for p in range(int(np.floor(lo)), int(np.ceil(hi)) + 1):
            if lo <= p <= hi:
                y = xy(sma.index[0], 10.0 ** p)[1]
                d.line([(x0, y), (x1, y)], fill=(225, 225, 225), width=1)
                d.text((10, y - 12), f"x{10 ** p:,.0f}" if p >= 0 else f"x{10 ** p:g}",
                       fill="black", font=small)
        years = sma.index.year
        step = 20 if years[-1] - years[0] > 50 else 5
        for yr in range((years[0] // step + 1) * step, years[-1] + 1, step):
            x = xy(pd.Timestamp(f"{yr}-01-01"), 1.0)[0]
            d.line([(x, y0), (x, y1)], fill=(235, 235, 235), width=1)
            d.text((x - 30, y1 + 15), str(yr), fill="black", font=small)
        for k, (name, s) in enumerate(lines.items()):
            weekly = s.resample("W").last().dropna()
            d.line([xy(ts, v) for ts, v in weekly.items()], fill=colours[name], width=4)
            lx = pad_l + 10 + k * 300
            d.line([(lx, top + 75), (lx + 40, top + 75)], fill=colours[name], width=6)
            d.text((lx + 48, top + 62), f"{name} {s.iloc[-1]:,.0f}x" if s.iloc[-1] >= 10
                   else f"{name} {s.iloc[-1]:.1f}x", fill="black", font=small)
    img.save(path)


def main() -> int:
    sys.path.insert(0, str(ROOT))
    irx = tbill_daily(_load_irx())
    gspc, spy = _load("^GSPC"), _load("SPY")
    runs = {
        "S&P 500 price, simple": backtest(gspc, kind="sma"),
        "S&P 500 price, exponential": backtest(gspc, kind="ema"),
        "SPY with dividends + T-bills, simple": backtest(spy, kind="sma", cash_daily=irx),
        "SPY with dividends + T-bills, exponential": backtest(spy, kind="ema", cash_daily=irx),
    }
    print(table(runs))
    # The video's own set-up starts in 1926 with dividends; the store's index has no dividends.
    print(f"\nT-bill data from {irx.index[0]:%Y-%m-%d}; S&P 500 from {gspc.index[0]:%Y-%m-%d};"
          f" SPY from {spy.index[0]:%Y-%m-%d}; last day {gspc.index[-1]:%Y-%m-%d}")
    names = list(runs)
    draw_png([("S&P 500 index, 1928-2026 (price only, cash earns 0)", runs[names[0]], runs[names[1]]),
              ("SPY, 1993-2026 (dividends in, T-bills when out)", runs[names[2]], runs[names[3]])],
             PNG)
    print(f"picture: {PNG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
