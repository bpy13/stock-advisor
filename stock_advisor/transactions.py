"""Builds a Portfolio from a raw brokerage transaction history CSV."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Union

from .portfolio import Portfolio, Position


@dataclass(frozen=True)
class Transaction:
    """A single fill: positive quantity is a buy, negative is a sell."""

    trade_date: date
    name: str
    ticker: str
    currency: str
    price: float
    quantity: float


def normalize_transaction_ticker(ticker: str, currency: str) -> str:
    """Map a raw transaction ticker to the symbol Yahoo Finance expects.

    Hong Kong exchange codes are recorded as plain numbers (e.g. "00011") and
    need a zero-padded 4-digit ".HK" suffix (e.g. "0011.HK"). Everything else
    (US tickers, bonds, commodities) is passed through unchanged, upper-cased.
    """
    raw = ticker.strip().upper()
    if raw.isdigit() and currency.strip().upper() == "HKD":
        return f"{int(raw):04d}.HK"
    return raw


def load_transactions(path: Union[str, Path]) -> List[Transaction]:
    """Parse a transaction CSV with a `#`-prefixed header row.

    Expected columns: date,name,ticker,currency,price,quantity
    Dates are `dd-mm-yyyy`; quantity is signed (negative = sell).
    """
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        lines = handle.readlines()
    if not lines:
        return []

    header = lines[0].lstrip("#").strip().split(",")
    reader = csv.DictReader(lines[1:], fieldnames=header)

    transactions = []
    for row in reader:
        if not row.get("date"):
            continue
        transactions.append(
            Transaction(
                trade_date=datetime.strptime(row["date"].strip(), "%d-%m-%Y").date(),
                name=row["name"].strip(),
                ticker=row["ticker"].strip(),
                currency=row["currency"].strip(),
                price=float(row["price"]),
                quantity=float(row["quantity"]),
            )
        )
    return transactions


def build_portfolio_from_transactions(path: Union[str, Path], cash: float = 0.0) -> Portfolio:
    """Aggregate a transaction history into current net positions.

    Uses the average-cost method: buys add shares and cost at the fill price;
    sells reduce shares while leaving the average cost per remaining share
    unchanged. Positions fully closed out (net shares <= 0) are omitted.
    """
    transactions = sorted(load_transactions(path), key=lambda txn: txn.trade_date)

    shares: Dict[str, float] = {}
    total_cost: Dict[str, float] = {}

    for txn in transactions:
        symbol = normalize_transaction_ticker(txn.ticker, txn.currency)
        held = shares.get(symbol, 0.0)
        cost = total_cost.get(symbol, 0.0)

        if txn.quantity >= 0:
            shares[symbol] = held + txn.quantity
            total_cost[symbol] = cost + txn.quantity * txn.price
        else:
            sold = min(-txn.quantity, held)
            avg_cost = cost / held if held else 0.0
            shares[symbol] = held - sold
            total_cost[symbol] = cost - sold * avg_cost

    positions = {
        symbol: Position(symbol=symbol, shares=remaining, cost_basis=total_cost[symbol] / remaining)
        for symbol, remaining in shares.items()
        if remaining > 0
    }
    return Portfolio(positions=positions, cash=cash)
