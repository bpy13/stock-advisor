"""The list of stocks and series the tool follows.

`config/watchlist.csv` is tracked and Brian edits it. The user's holdings join the list at run
time only; they are never written to the file (the repo is public).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

WATCHLIST_PATH = Path(__file__).resolve().parent.parent / "config" / "watchlist.csv"
MARKETS = ("HK", "US", "OTHER")
KINDS = ("stock", "index_fund", "index", "driver", "fx", "holding")


@dataclass(frozen=True)
class WatchItem:
    symbol: str
    market: str  # "HK" | "US" | "OTHER"
    kind: str  # one of KINDS
    name: str


def _holding_symbols() -> list[str]:
    # Imported here: report pulls in the whole analysis stack.
    from .report import resolve_symbols_and_portfolio

    symbols, _ = resolve_symbols_and_portfolio()
    return symbols


def _read_file(path: Path) -> list[WatchItem]:
    lines = path.read_text(encoding="utf-8").splitlines()
    items: list[WatchItem] = []
    seen: dict[str, int] = {}
    # Keep original line numbers so errors point at the line Brian sees in his editor.
    body = [(n, line) for n, line in enumerate(lines, start=1) if line.strip() and not line.startswith("#")]
    rows = list(csv.reader(line for _, line in body))
    if not rows or [c.strip() for c in rows[0]] != ["symbol", "market", "kind", "name"]:
        raise ValueError(f"{path.name}: header must be symbol,market,kind,name")
    for (lineno, _), row in zip(body[1:], rows[1:]):
        if len(row) != 4:
            raise ValueError(f"{path.name} line {lineno}: expected 4 columns, got {len(row)}")
        symbol, market, kind, name = (c.strip() for c in row)
        if not symbol:
            raise ValueError(f"{path.name} line {lineno}: empty symbol")
        if market not in MARKETS:
            raise ValueError(f"{path.name} line {lineno}: unknown market {market!r}")
        if kind not in KINDS:
            raise ValueError(f"{path.name} line {lineno}: unknown kind {kind!r}")
        if symbol in seen:
            raise ValueError(f"{path.name} line {lineno}: duplicate symbol {symbol} (first on line {seen[symbol]})")
        seen[symbol] = lineno
        items.append(WatchItem(symbol, market, kind, name))
    return items


def load_watchlist(
    include_holdings: bool = True, path: Optional[Union[str, Path]] = None
) -> list[WatchItem]:
    """Return the file's rows, plus current holdings the file does not list (kind "holding")."""
    items = _read_file(Path(path) if path else WATCHLIST_PATH)
    if include_holdings:
        listed = {i.symbol for i in items}
        for symbol in _holding_symbols():
            symbol = symbol.strip().upper()
            if symbol and symbol not in listed:
                listed.add(symbol)
                market = "HK" if symbol.endswith(".HK") else "US"
                items.append(WatchItem(symbol, market, "holding", symbol))
    return items
