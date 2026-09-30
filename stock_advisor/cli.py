"""Command-line entrypoint: python -m stock_advisor.cli [SYMBOLS...] [options]"""

from __future__ import annotations

import argparse

from .config import DEFAULT_CONFIG
from .report import format_report, generate_report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Report whether each given stock looks cheap or expensive relative to "
            "its own trading history, optionally adjusted for an existing portfolio."
        )
    )
    parser.add_argument(
        "symbols",
        nargs="*",
        help=(
            "Ticker symbols to analyze, e.g. AAPL MSFT. If omitted, defaults to the "
            "resolved portfolio's holdings (see --portfolio), or to a curated list "
            "of Hang Seng Index constituents if no portfolio is available either."
        ),
    )
    parser.add_argument(
        "--portfolio",
        default=None,
        help=(
            "Path to a portfolio JSON file or a transaction-history CSV. If "
            "omitted, data/transaction.csv is used when present, then "
            "data/portfolio.json, then sample_data/portfolio.json."
        ),
    )
    parser.add_argument(
        "--period",
        default=DEFAULT_CONFIG.period,
        help="Yahoo Finance history period, e.g. 1y, 2y, 5y (default: %(default)s)",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    config = DEFAULT_CONFIG
    if args.period != config.period:
        from dataclasses import replace

        config = replace(config, period=args.period)

    report = generate_report(
        args.symbols or None, portfolio_path=args.portfolio, config=config
    )
    print(format_report(report))


if __name__ == "__main__":
    main()
