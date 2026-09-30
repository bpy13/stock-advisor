"""Loads historical stock price data from Yahoo Finance."""

from __future__ import annotations

from typing import Dict, Iterable, List

import pandas as pd
import yfinance as yf


def normalize_symbol(symbol: str) -> str:
    """Normalize a raw user-supplied ticker string for Yahoo Finance lookups."""
    normalized = str(symbol).strip().upper()
    if not normalized:
        raise ValueError("A stock symbol is required.")
    return normalized


def fetch_price_history(
    symbols: Iterable[str],
    period: str = "2y",
    interval: str = "1d",
) -> Dict[str, pd.DataFrame]:
    """Fetch OHLCV history for each symbol individually.

    Returns a dict mapping the normalized symbol to its history DataFrame.
    Symbols with no data are omitted, since a delisted/invalid ticker should
    not silently zero out the analysis for the rest of the batch.
    """
    result: Dict[str, pd.DataFrame] = {}
    for raw_symbol in symbols:
        symbol = normalize_symbol(raw_symbol)
        ticker = yf.Ticker(symbol)
        history = ticker.history(period=period, interval=interval, auto_adjust=False)
        if history.empty:
            continue
        result[symbol] = history
    return result


def fetch_close_prices(
    symbols: Iterable[str],
    period: str = "2y",
    interval: str = "1d",
) -> pd.DataFrame:
    """Fetch adjusted-close price history for a batch of symbols.

    Returns a single DataFrame indexed by date, one column per symbol,
    forward-filled to align trading calendars across exchanges.
    """
    histories = fetch_price_history(symbols, period=period, interval=interval)
    if not histories:
        raise ValueError("No Yahoo Finance data found for any requested symbol.")

    closes = {symbol: history["Close"] for symbol, history in histories.items()}
    frame = pd.DataFrame(closes).sort_index()
    return frame.ffill().dropna(how="all")


def missing_symbols(requested: Iterable[str], fetched: Dict[str, pd.DataFrame]) -> List[str]:
    """Return normalized symbols that were requested but had no data returned."""
    requested_normalized = {normalize_symbol(symbol) for symbol in requested}
    return sorted(requested_normalized - set(fetched.keys()))
