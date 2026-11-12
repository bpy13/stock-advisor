"""Compare Yahoo with a second source (Futu for HK, Alpaca for US) in the price store.

Per symbol and interval, over the period both sources cover: bars held by one source only,
closes that differ by more than a tolerance, flag counts per source, and big moves one source
flags that the other does not. The cleaner source has fewer missing bars plus unmatched big moves.
"""
from __future__ import annotations

import pandas as pd

from stock_advisor import price_store, quality

SECOND_SOURCE = {"HK": "futu", "US": "alpaca"}
BASE_SOURCE = "yahoo"
RAW_TOLERANCE = 0.005
ADJUSTED_TOLERANCE = 0.01


def compare_symbol(symbol: str, interval: str, source_a: str = BASE_SOURCE,
                   source_b: str | None = None, store_reader=None) -> dict | None:
    """Per-symbol differences between two sources, or None when either lacks the symbol or
    the two share no period. Counts are over the shared period only."""
    read = store_reader or price_store.read_bars
    source_b = source_b or SECOND_SOURCE[quality.market_of(symbol)]
    raw = {s: read(symbol, interval, adjusted=False, source=s) for s in (source_a, source_b)}
    if raw[source_a].empty or raw[source_b].empty:
        return None
    start = max(df.index.min() for df in raw.values())
    end = min(df.index.max() for df in raw.values())
    if start > end:
        return None
    raw = {s: df[(df.index >= start) & (df.index <= end)] for s, df in raw.items()}
    a, b = raw[source_a], raw[source_b]
    common = a.index.intersection(b.index)
    adj = {s: read(symbol, interval, adjusted=True, source=s) for s in (source_a, source_b)}
    adj = {s: df[(df.index >= start) & (df.index <= end)] for s, df in adj.items()}
    adj_common = adj[source_a].index.intersection(adj[source_b].index)

    def differing(x: pd.DataFrame, y: pd.DataFrame, idx, tol: float) -> int:
        if len(idx) == 0:
            return 0
        rel = (x.loc[idx, "close"] / y.loc[idx, "close"] - 1).abs()
        return int((rel > tol).sum())

    def unmatched_big(x: pd.DataFrame, y: pd.DataFrame) -> int:
        flagged = x.index[x["big_move"]]
        other = y["big_move"].reindex(flagged).fillna(False).astype(bool)
        return int((~other).sum())

    row = {"symbol": symbol, "interval": interval, "start": start, "end": end,
           "common_bars": len(common),
           "raw_close_diff": differing(a, b, common, RAW_TOLERANCE),
           "adjusted_close_diff": differing(adj[source_a], adj[source_b], adj_common,
                                            ADJUSTED_TOLERANCE)}
    for name, x, y in ((source_a, a, b), (source_b, b, a)):
        row[f"{name}_only"] = len(x.index.difference(y.index))
        row[f"{name}_no_trade"] = int(x["no_trade"].sum())
        row[f"{name}_big_move"] = int(x["big_move"].sum())
        row[f"{name}_gap"] = int(x["gap_before"].sum())
        row[f"{name}_unmatched_big"] = unmatched_big(x, y)
    return row


def compare_all(symbols: list[str], intervals=price_store.INTERVALS, store_reader=None) -> pd.DataFrame:
    """One row per symbol and interval that both sources hold; adds a ``market`` column."""
    rows = []
    for interval in intervals:
        for symbol in symbols:
            market = quality.market_of(symbol)
            if market not in SECOND_SOURCE:
                continue
            row = compare_symbol(symbol, interval, store_reader=store_reader)
            if row:
                rows.append({"market": market, **row})
    return pd.DataFrame(rows)


def totals(detail: pd.DataFrame) -> pd.DataFrame:
    """Per market and interval sums, with the badness score of each source.

    A source's score is the bars it lacks (the other source's ``_only`` count) plus the big
    moves the other source flags that it does not (the other's ``_unmatched_big`` count)."""
    rows = []
    for (market, interval), g in detail.groupby(["market", "interval"]):
        second = SECOND_SOURCE[market]
        sums = g.drop(columns=["symbol", "market", "interval", "start", "end"]).sum()
        out = {"market": market, "interval": interval, "symbols": len(g), **sums.to_dict()}
        out[f"{BASE_SOURCE}_score"] = int(sums[f"{second}_only"] + sums[f"{second}_unmatched_big"])
        out[f"{second}_score"] = int(sums[f"{BASE_SOURCE}_only"] + sums[f"{BASE_SOURCE}_unmatched_big"])
        out["cleaner"] = second if out[f"{second}_score"] < out[f"{BASE_SOURCE}_score"] else BASE_SOURCE
        rows.append(out)
    return pd.DataFrame(rows)


def preferred_order(summary: pd.DataFrame) -> dict[str, tuple[str, ...]]:
    """Source order per market from the daily and hourly totals taken together; Yahoo is last
    as the fallback. A market with no comparison keeps Yahoo alone."""
    order = {"HK": (BASE_SOURCE,), "US": (BASE_SOURCE,), "OTHER": (BASE_SOURCE,)}
    for market, g in summary.groupby("market"):
        second = SECOND_SOURCE[market]
        base_score = g[f"{BASE_SOURCE}_score"].sum()
        second_score = g[f"{second}_score"].sum()
        order[market] = (second, BASE_SOURCE) if second_score < base_score else (BASE_SOURCE, second)
    return order


def report_markdown(detail: pd.DataFrame, summary: pd.DataFrame, date: str) -> str:
    fence = "```"
    return "\n".join([
        f"# Price source comparison, {date}", "", "## Totals per market", "",
        fence, summary.to_string(index=False), fence, "", "## Per symbol", "",
        fence, detail.to_string(index=False), fence, ""])
