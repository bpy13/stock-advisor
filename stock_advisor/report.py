"""Orchestrates data loading + analysis into a single buy/sell/hold report."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Union

import pandas as pd

from .config import DEFAULT_CONFIG, DEFAULT_HK_UNIVERSE, AnalysisConfig
from .correlation import build_peer_map
from .market_data import fetch_close_prices, missing_symbols
from .portfolio import Portfolio, load_portfolio, resolve_portfolio_path
from .price_analysis import analyze_valuations
from .recommendation import Recommendation, build_recommendation
from .transactions import build_portfolio_from_transactions


def resolve_symbols_and_portfolio(
    symbols: Optional[Iterable[str]] = None,
    portfolio_path: Optional[Union[str, Path]] = None,
) -> tuple[list[str], Optional[Portfolio]]:
    """Resolve the (symbols-to-analyze, portfolio) pair shared by the report and
    the metric-validation CLI.

    If `symbols` is omitted, defaults to the resolved portfolio's holdings, or
    to `DEFAULT_HK_UNIVERSE` if no portfolio is available either.
    """
    resolved_portfolio_path = resolve_portfolio_path(portfolio_path)
    portfolio: Optional[Portfolio] = None
    if resolved_portfolio_path is not None:
        if resolved_portfolio_path.suffix.lower() == ".csv":
            portfolio = build_portfolio_from_transactions(resolved_portfolio_path)
        else:
            portfolio = load_portfolio(resolved_portfolio_path)

    if symbols is not None:
        requested = list(symbols)
    elif portfolio is not None and portfolio.positions:
        requested = list(portfolio.positions.keys())
    else:
        requested = list(DEFAULT_HK_UNIVERSE)

    return requested, portfolio


def generate_report(
    symbols: Optional[Iterable[str]] = None,
    portfolio_path: Optional[Union[str, Path]] = None,
    config: AnalysisConfig = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """Fetch data, run the full analysis pipeline, and return a report DataFrame.

    If `symbols` is omitted, the analysis universe defaults to the resolved
    portfolio's holdings (see `resolve_portfolio_path`), or to
    `DEFAULT_HK_UNIVERSE` if no portfolio is available either.
    """
    requested, portfolio = resolve_symbols_and_portfolio(symbols, portfolio_path)

    close_prices = fetch_close_prices(requested, period=config.period, interval=config.interval)

    skipped = missing_symbols(requested, {c: close_prices[c] for c in close_prices.columns})
    if skipped:
        print(f"Warning: no data found for {', '.join(skipped)}; skipping.")

    valuations = analyze_valuations(close_prices, config)
    peer_map = build_peer_map(close_prices, config)
    current_prices = {symbol: metrics.current_price for symbol, metrics in valuations.items()}

    rows = []
    for symbol, valuation in valuations.items():
        recommendation: Recommendation = build_recommendation(
            valuation=valuation,
            peers=peer_map.get(symbol, []),
            portfolio=portfolio,
            current_prices=current_prices,
            config=config,
        )
        rows.append(
            {
                "symbol": symbol,
                "current_price": round(valuation.current_price, 2),
                "ma_20": None if valuation.ma_short is None else round(valuation.ma_short, 2),
                "ma_50": None if valuation.ma_medium is None else round(valuation.ma_medium, 2),
                "ma_200": None if valuation.ma_long is None else round(valuation.ma_long, 2),
                "pct_from_ma_200": (
                    None
                    if valuation.pct_from_ma_long is None
                    else round(valuation.pct_from_ma_long, 2)
                ),
                "zscore": round(valuation.zscore, 2),
                "percentile_rank": round(valuation.percentile_rank, 1),
                "raw_signal": recommendation.raw_signal,
                "recommendation": recommendation.action,
                "shares_held": recommendation.shares_held,
                "portfolio_weight": round(recommendation.position_weight, 4),
                "rationale": recommendation.rationale,
            }
        )

    report = pd.DataFrame(rows).set_index("symbol")
    return report.sort_values("zscore")


def format_report(report: pd.DataFrame) -> str:
    """Render a report DataFrame as a human-readable text table."""
    display_columns = [
        "current_price",
        "ma_20",
        "ma_50",
        "ma_200",
        "zscore",
        "percentile_rank",
        "recommendation",
        "portfolio_weight",
    ]
    table = report[display_columns].to_string()
    rationale_lines = "\n".join(
        f"- {symbol}: {row.rationale}" for symbol, row in report.iterrows()
    )
    return f"{table}\n\nRationale:\n{rationale_lines}"
