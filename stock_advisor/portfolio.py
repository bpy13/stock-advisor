"""Loads a user's stock portfolio (holdings) from JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Union

from .market_data import normalize_symbol

_REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_TRANSACTIONS_PATH = _REPO_ROOT / "data" / "transaction.csv"
DATA_PORTFOLIO_PATH = _REPO_ROOT / "data" / "portfolio.json"
SAMPLE_PORTFOLIO_PATH = _REPO_ROOT / "sample_data" / "portfolio.json"


@dataclass(frozen=True)
class Position:
    """A single portfolio holding."""

    symbol: str
    shares: float
    cost_basis: float  # average purchase price per share


@dataclass(frozen=True)
class Portfolio:
    """A collection of positions plus uninvested cash."""

    positions: Dict[str, Position]
    cash: float = 0.0

    def market_value(self, current_prices: Dict[str, float]) -> float:
        """Total portfolio value (holdings at current price + cash)."""
        holdings_value = sum(
            position.shares * current_prices.get(position.symbol, position.cost_basis)
            for position in self.positions.values()
        )
        return holdings_value + self.cash

    def position_weight(self, symbol: str, current_prices: Dict[str, float]) -> float:
        """Fraction of total portfolio value held in `symbol` (0.0 if not held)."""
        total_value = self.market_value(current_prices)
        if total_value <= 0:
            return 0.0
        position = self.positions.get(normalize_symbol(symbol))
        if position is None:
            return 0.0
        price = current_prices.get(position.symbol, position.cost_basis)
        return (position.shares * price) / total_value


def resolve_portfolio_path(explicit_path: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """Pick which portfolio source file to load.

    An explicit path always wins. Otherwise prefer the real, gitignored
    `data/transaction.csv` (raw fills, aggregated into positions) over
    `data/portfolio.json` (a plain snapshot), and fall back to the tracked
    `sample_data/portfolio.json` demo if neither real file exists. Returns
    None if nothing is available. Callers should dispatch on `.suffix` to
    pick between `load_portfolio` (JSON) and `build_portfolio_from_transactions`
    (CSV).
    """
    if explicit_path is not None:
        return Path(explicit_path)
    if DATA_TRANSACTIONS_PATH.exists():
        return DATA_TRANSACTIONS_PATH
    if DATA_PORTFOLIO_PATH.exists():
        return DATA_PORTFOLIO_PATH
    if SAMPLE_PORTFOLIO_PATH.exists():
        return SAMPLE_PORTFOLIO_PATH
    return None


def load_portfolio(path: Union[str, Path]) -> Portfolio:
    """Load a portfolio from a JSON file.

    Expected schema:
        {
          "cash": 1000.0,
          "positions": [
            {"symbol": "AAPL", "shares": 10, "cost_basis": 150.0}
          ]
        }
    """
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    positions = {}
    for entry in raw.get("positions", []):
        symbol = normalize_symbol(entry["symbol"])
        positions[symbol] = Position(
            symbol=symbol,
            shares=float(entry["shares"]),
            cost_basis=float(entry.get("cost_basis", 0.0)),
        )

    return Portfolio(positions=positions, cash=float(raw.get("cash", 0.0)))
