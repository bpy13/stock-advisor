"""CLI for backtesting valuation metrics: python -m stock_advisor.validate_cli [SYMBOLS...]

Determines which metrics (besides plain moving averages) actually predict
forward returns, using historical data, rather than just looking plausible.
"""

from __future__ import annotations

import argparse

import pandas as pd

from .market_data import fetch_close_prices
from .report import resolve_symbols_and_portfolio
from .validation import DEFAULT_METRICS, evaluate_metrics, rank_metrics


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Backtest each valuation metric's BUY/SELL signal against realized "
            "forward returns, and report which ones show a genuine edge."
        )
    )
    parser.add_argument(
        "symbols",
        nargs="*",
        help="Symbols to backtest over. If omitted, defaults like the report CLI (portfolio/HK universe).",
    )
    parser.add_argument("--portfolio", default=None, help="Path to a portfolio JSON/CSV file.")
    parser.add_argument(
        "--period",
        default="5y",
        help="History window to backtest over; longer = more samples (default: %(default)s).",
    )
    parser.add_argument(
        "--forward-window",
        type=int,
        default=20,
        help="Trading days ahead to measure the forward return over (default: %(default)s).",
    )
    parser.add_argument(
        "--min-t-stat",
        type=float,
        default=2.0,
        help="Minimum |t-stat| for a metric to be flagged as a genuine indicator (default: %(default)s).",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    symbols, _portfolio = resolve_symbols_and_portfolio(args.symbols or None, args.portfolio)
    close_prices = fetch_close_prices(symbols, period=args.period)

    summary = evaluate_metrics(close_prices, DEFAULT_METRICS, forward_window=args.forward_window)
    ranked = rank_metrics(summary, min_abs_t_stat=args.min_t_stat)

    pd.set_option("display.width", 160)
    print(ranked.round(4).to_string())


if __name__ == "__main__":
    main()
