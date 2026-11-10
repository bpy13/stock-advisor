"""On-disk store of price bars, per source, interval and symbol.

Layout: ``STORE_ROOT/<source>/<interval>/<raw|adjusted>/<symbol>.parquet``. Raw bars are
appended (new rows win on a duplicate index); adjusted bars are replaced whole on each write,
because an adjusted history changes after every dividend. Quality flags live in the raw file.
Index: "1d" = session date (tz-naive); "60m" = bar start, UTC.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from stock_advisor import quality

STORE_ROOT = Path(__file__).resolve().parent.parent / "data" / "cache" / "store"
SOURCES = ("yahoo", "futu", "alpaca")
INTERVALS = ("1d", "60m")
OHLCV = ["open", "high", "low", "close", "volume"]
FLAGS = list(quality.FLAG_COLUMNS)
COLUMNS = OHLCV + FLAGS
# First source in the tuple that holds the symbol wins. Task 2.9 sets these from the comparison.
PREFERRED_SOURCES = {"HK": ("yahoo",), "US": ("yahoo",), "OTHER": ("yahoo",)}


def _path(source: str, interval: str, kind: str, symbol: str) -> Path:
    if source not in SOURCES:
        raise ValueError(f"unknown source {source!r}")
    if interval not in INTERVALS:
        raise ValueError(f"unknown interval {interval!r}")
    name = symbol.replace(".", "_").replace("^", "_").replace("=", "_")
    return STORE_ROOT / source / interval / kind / f"{name}.parquet"


def write_bars(source: str, interval: str, symbol: str, raw: pd.DataFrame,
               adjusted: pd.DataFrame | None) -> None:
    """Merge ``raw`` into the stored raw file, replace the adjusted file, recompute flags."""
    raw_path = _path(source, interval, "raw", symbol)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    merged = raw[OHLCV]
    if raw_path.exists():
        merged = pd.concat([pd.read_parquet(raw_path)[OHLCV], merged])
        merged = merged[~merged.index.duplicated(keep="last")]
    market = quality.market_of(symbol)
    quality.flag_bars(merged, market, interval, tradable=market != "OTHER").to_parquet(raw_path)
    if adjusted is not None:
        adj_path = _path(source, interval, "adjusted", symbol)
        adj_path.parent.mkdir(parents=True, exist_ok=True)
        adjusted[OHLCV].sort_index().to_parquet(adj_path)


def _clip(df: pd.DataFrame, start, end) -> pd.DataFrame:
    def bound(value):
        ts = pd.Timestamp(value)
        if df.index.tz is not None and ts.tzinfo is None:
            return ts.tz_localize("UTC")
        if df.index.tz is None and ts.tzinfo is not None:
            return ts.tz_convert("UTC").tz_localize(None)
        return ts

    if start is not None:
        df = df[df.index >= bound(start)]
    if end is not None:
        df = df[df.index <= bound(end)]
    return df


def read_bars(symbol: str, interval: str = "1d", adjusted: bool = True,
              source: str | None = None, start=None, end=None) -> pd.DataFrame:
    """Bars of one symbol. ``source=None`` reads the preferred source that holds the symbol.

    A symbol the store lacks gives an empty frame with the standard columns.
    """
    if source is None:
        order = PREFERRED_SOURCES[quality.market_of(symbol)]
        source = next((s for s in order if _path(s, interval, "raw", symbol).exists()), None)
    if source is None or not _path(source, interval, "raw", symbol).exists():
        return pd.DataFrame(columns=COLUMNS)
    bars = pd.read_parquet(_path(source, interval, "raw", symbol))
    adj_path = _path(source, interval, "adjusted", symbol)
    if adjusted and adj_path.exists():
        flags = bars[FLAGS]
        bars = pd.read_parquet(adj_path).join(flags)
        bars["no_trade"] = bars["no_trade"].fillna(False).astype(bool)
        bars["big_move"] = bars["big_move"].fillna(False).astype(bool)
        bars["gap_before"] = bars["gap_before"].fillna(0).astype(int)
    return _clip(bars, start, end)[COLUMNS]


def _market_of_stem(stem: str) -> str:
    """File names lose '.', '^' and '='; recover the market from the name's shape."""
    if stem.upper().endswith("_HK"):
        return "HK"
    if stem.startswith("_") or stem.endswith(("_X", "_F")):
        return "OTHER"
    return "US"


def status() -> pd.DataFrame:
    """Per source, interval and market: symbol count, first and last bar, flag counts."""
    rows = []
    for source in SOURCES:
        for interval in INTERVALS:
            folder = STORE_ROOT / source / interval / "raw"
            per_market: dict[str, list[pd.DataFrame]] = {}
            for f in folder.glob("*.parquet"):
                df = pd.read_parquet(f)
                if not df.empty:
                    per_market.setdefault(_market_of_stem(f.stem), []).append(df)
            for market, frames in sorted(per_market.items()):
                rows.append({
                    "source": source, "interval": interval, "market": market,
                    "symbols": len(frames),
                    "first_bar": min(d.index.min() for d in frames),
                    "last_bar": max(d.index.max() for d in frames),
                    "no_trade": int(sum(d["no_trade"].sum() for d in frames)),
                    "big_move": int(sum(d["big_move"].sum() for d in frames)),
                    "gap_bars": int(sum(d["gap_before"].sum() for d in frames)),
                })
    return pd.DataFrame(rows, columns=["source", "interval", "market", "symbols", "first_bar",
                                       "last_bar", "no_trade", "big_move", "gap_bars"])
