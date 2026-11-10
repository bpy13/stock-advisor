"""Portfolio analysis: ``python -m stock_advisor.analyze_cli [--save]`` and ``... cost``.

The report names holdings, so ``--save`` writes under ``data/reports/`` (gitignored); never
commit it.
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

from stock_advisor import accounts as accounts_mod
from stock_advisor import fees, price_store
from stock_advisor.analyzer import PortfolioReport, build_portfolio_report
from stock_advisor.watchlist import load_watchlist

REPORTS_DIR = Path(__file__).resolve().parent.parent / "data" / "reports"


def _pct(x: float) -> str:
    return "n/a" if pd.isna(x) else f"{x:.1%}"


def format_report(rep: PortfolioReport) -> str:
    s = rep.summary
    fall = (f"{_pct(s.deepest_fall)} ({s.fall_start:%Y-%m-%d} to {s.fall_end:%Y-%m-%d})"
            if s.fall_start is not None else _pct(s.deepest_fall))
    lines = [
        "Portfolio (HKD)",
        f"  Value today:                   {s.value_today:,.0f} (cash {s.cash:,.0f})",
        f"  Return without deposit timing: {_pct(s.return_without_timing)}",
        f"  Return with deposit timing:    {_pct(s.return_with_timing)} a year",
        f"  Deepest fall:                  {fall}",
        f"  Yearly swing:                  {_pct(s.yearly_swing)}",
        f"  Three largest holdings:        {_pct(s.top3_weight)}",
        f"  Effective number of holdings:  {s.effective_holdings:.1f}",
    ]
    if not rep.cash_set:
        lines.append("  Cash is not set: edit data/accounts.json")
    if s.unpriced:
        lines.append(f"  No price in the store (valued at cost): {', '.join(s.unpriced)}")
    if rep.too_short:
        lines.append(f"  Under a year of history (no risk numbers): {', '.join(rep.too_short)}")
    lines += ["", "Per holding"]
    t = rep.table.copy()
    t["weight"] = t["weight"].map(_pct)
    t["risk_share"] = t["risk_share"].map(_pct)
    t["market_beta"] = t["market_beta"].map(lambda b: "n/a" if pd.isna(b) else f"{b:.2f}")
    t["group"] = t["group"].map(lambda g: "-" if pd.isna(g) else int(g))
    lines.append(t.fillna("").to_string())
    if rep.groups:
        lines += ["", "Groups that move together"]
        lines += [f"  {', '.join(g)}" for g in rep.groups]
    lines += ["", rep.caveat]
    return "\n".join(lines)


def _market_kind(symbol: str) -> tuple[str, str]:
    market = "HK" if symbol.upper().endswith(".HK") else "US"
    kind = next((i.kind for i in load_watchlist(include_holdings=False) if i.symbol == symbol), "stock")
    return market, "index_fund" if kind == "index_fund" else "stock"


def cost_report(symbol: str, amount: float, price: float | None = None) -> str:
    """Cost of buying, and of a round trip, at each broker. ``amount`` is the trade value."""
    market, kind = _market_kind(symbol)
    if price is None:
        bars = price_store.read_bars(symbol, "1d", adjusted=False)
        closes = bars["close"].dropna()
        price = float(closes.iloc[-1]) if not closes.empty else None
    if price is None:
        if market == "US":
            raise SystemExit(f"No price for {symbol} in the store; pass --price (US fees depend on shares).")
        price = 1.0  # Hong Kong fees depend on the trade's value only
    shares = amount / price
    out = []
    for broker in accounts_mod.BROKERS:
        buy = fees.trade_cost(broker, market, kind, price, shares, "buy")
        rt = fees.round_trip_pct(broker, market, kind, price, shares)
        if not out:
            out.append(f"Cost of a {amount:,.0f} {buy.currency} trade in {symbol}")
        out.append(f"  {broker}: buy {buy.total:,.2f} {buy.currency}; round trip {rt:.2f}%")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="analyze_cli")
    parser.add_argument("--save", action="store_true", help="also write data/reports/portfolio-<date>.md")
    sub = parser.add_subparsers(dest="cmd")
    c = sub.add_parser("cost", help="cost of a trade at each broker")
    c.add_argument("--symbol", required=True)
    c.add_argument("--amount", required=True, type=float)
    c.add_argument("--price", type=float, help="default: last close in the store")
    args = parser.parse_args(argv)
    if args.cmd == "cost":
        print(cost_report(args.symbol, args.amount, args.price))
        return 0
    text = format_report(build_portfolio_report())
    print(text)
    if args.save:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        path = REPORTS_DIR / f"portfolio-{date.today():%Y-%m-%d}.md"
        path.write_text(text + "\n", encoding="utf-8")
        print(f"\nSaved to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
