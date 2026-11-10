"""Accounts (broker, cash, trade file) and position limits.

Brian's real accounts live in ``data/accounts.json`` (gitignored). When that file is
absent the tracked ``sample_data/accounts.json`` is read instead.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

BROKERS = ("hang_seng_bank", "futu")
CURRENCIES = ("HKD", "USD")

_ROOT = Path(__file__).resolve().parent.parent
REAL_PATH = _ROOT / "data" / "accounts.json"
SAMPLE_PATH = _ROOT / "sample_data" / "accounts.json"


@dataclass(frozen=True)
class Account:
    name: str
    broker: str
    cash: dict[str, float]
    trade_file: str | None


@dataclass(frozen=True)
class Limits:
    max_position_weight: float
    min_trade_hkd: float
    whole_board_lots: bool


def _parse_account(i: int, raw: dict) -> Account:
    where = f"accounts[{i}]"
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError(f"{where}.name must be a non-empty string")
    broker = raw.get("broker")
    if broker not in BROKERS:
        raise ValueError(f"{where}.broker {broker!r} is unknown; use one of {BROKERS}")
    cash_raw = raw.get("cash", {})
    if not isinstance(cash_raw, dict):
        raise ValueError(f"{where}.cash must be an object of currency to amount")
    cash: dict[str, float] = {}
    for cur, amount in cash_raw.items():
        if cur not in CURRENCIES:
            raise ValueError(f"{where}.cash currency {cur!r} is unknown; use {CURRENCIES}")
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ValueError(f"{where}.cash.{cur} must be a number")
        if amount < 0:
            raise ValueError(f"{where}.cash.{cur} must not be negative")
        cash[cur] = float(amount)
    trade_file = raw.get("trade_file")
    if trade_file is not None and not isinstance(trade_file, str):
        raise ValueError(f"{where}.trade_file must be a string or null")
    return Account(name=name, broker=broker, cash=cash, trade_file=trade_file)


def _parse_limits(raw: dict) -> Limits:
    weight = raw.get("max_position_weight")
    if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not 0 <= weight <= 1:
        raise ValueError("limits.max_position_weight must be a number from 0 to 1")
    min_trade = raw.get("min_trade_hkd")
    if isinstance(min_trade, bool) or not isinstance(min_trade, (int, float)) or min_trade < 0:
        raise ValueError("limits.min_trade_hkd must be a number, 0 or more")
    lots = raw.get("whole_board_lots")
    if not isinstance(lots, bool):
        raise ValueError("limits.whole_board_lots must be true or false")
    return Limits(float(weight), float(min_trade), lots)


def load_accounts(path: str | Path | None = None) -> tuple[list[Account], Limits]:
    """Read and validate the accounts file; return (accounts, limits)."""
    if path is None:
        path = REAL_PATH if REAL_PATH.exists() else SAMPLE_PATH
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    accounts = [_parse_account(i, a) for i, a in enumerate(data.get("accounts", []))]
    return accounts, _parse_limits(data.get("limits", {}))
