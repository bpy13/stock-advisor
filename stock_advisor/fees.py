"""Per-trade cost of a buy or sell at each broker in ``accounts.BROKERS``.

Counted: broker commission and platform fee, Hong Kong stamp duty and levies, US regulatory
fees. Not counted (not per-trade costs of the order itself): currency conversion, the price
spread, and Hang Seng Bank's monthly custody fee (see ``HSB_CUSTODY_FEE_HKD_MONTHLY``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .accounts import BROKERS

# --- Rates. Each was read from the broker's or regulator's own fee page on 2026-11-10. ---
# HKEX / SFC / AFRC: stamp duty 0.1% a side (stocks only), rounded up to a whole HK$.
HK_STAMP_DUTY = 0.001
# SFC levy + AFRC levy + HKEX trading fee, combined, a side (stocks and funds).
HK_LEVIES_AND_TRADING_FEE = 0.000085
# SEC Section 31 fee, sales only (sec.gov fee rate advisory); FINRA TAF per share, sales only.
US_SEC_FEE = 0.0000206
US_FINRA_PER_SHARE = 0.000195
US_FINRA_MIN = 0.01

# Hang Seng Bank securities fee schedule.
HSB_HK_RATE = 0.0025
HSB_HK_MIN_HKD = 100.0
HSB_US_PER_SHARE = 0.015
HSB_US_MIN_USD = 15.0
HSB_CUSTODY_FEE_HKD_MONTHLY = 25.0  # not per trade; exposed for callers that want it
# Futu fee page.
FUTU_HK_PLATFORM_HKD = 15.0  # per order; HK commission is 0
FUTU_US_COMMISSION_PER_SHARE = 0.0049
FUTU_US_COMMISSION_MIN_USD = 0.99
FUTU_US_PLATFORM_PER_SHARE = 0.005
FUTU_US_PLATFORM_MIN_USD = 1.0

_CURRENCY = {"HK": "HKD", "US": "USD"}


@dataclass(frozen=True)
class TradeCost:
    total: float
    currency: str
    lines: tuple[tuple[str, float], ...]  # (label, amount)


def trade_cost(broker: str, market: str, kind: str, price: float, shares: float, side: str) -> TradeCost:
    """Cost of one order. ``side`` is "buy" or "sell"; ``kind`` is "stock" or "index_fund"."""
    if broker not in BROKERS:
        raise ValueError(f"unknown broker {broker!r}; expected one of {BROKERS}")
    if market not in _CURRENCY:
        raise ValueError(f"unknown market {market!r}; expected HK or US")
    if side not in ("buy", "sell"):
        raise ValueError(f"unknown side {side!r}; expected buy or sell")
    value = price * shares
    lines: list[tuple[str, float]] = []
    if market == "HK":
        if broker == "hang_seng_bank":
            lines.append(("commission", max(value * HSB_HK_RATE, HSB_HK_MIN_HKD)))
        else:
            lines.append(("platform fee", FUTU_HK_PLATFORM_HKD))
        if kind == "stock":
            lines.append(("stamp duty", float(math.ceil(value * HK_STAMP_DUTY))))
        lines.append(("levies and trading fee", value * HK_LEVIES_AND_TRADING_FEE))
    else:
        if broker == "hang_seng_bank":
            lines.append(("commission", max(shares * HSB_US_PER_SHARE, HSB_US_MIN_USD)))
        else:
            lines.append(("commission", max(shares * FUTU_US_COMMISSION_PER_SHARE, FUTU_US_COMMISSION_MIN_USD)))
            lines.append(("platform fee", max(shares * FUTU_US_PLATFORM_PER_SHARE, FUTU_US_PLATFORM_MIN_USD)))
        if side == "sell":
            lines.append(("SEC fee", value * US_SEC_FEE))
            # Hang Seng Bank's schedule lists only the SEC fee.
            if broker == "futu":
                lines.append(("FINRA fee", max(shares * US_FINRA_PER_SHARE, US_FINRA_MIN)))
    return TradeCost(sum(a for _, a in lines), _CURRENCY[market], tuple(lines))


def round_trip_pct(broker: str, market: str, kind: str, price: float, shares: float) -> float:
    """Buy plus sell cost as a percentage of the trade's value (1.22 means 1.22%)."""
    both = trade_cost(broker, market, kind, price, shares, "buy").total + trade_cost(
        broker, market, kind, price, shares, "sell"
    ).total
    return both / (price * shares) * 100
