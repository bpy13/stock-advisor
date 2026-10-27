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


NO_NEWS = "—"  # shown when a symbol has no current news event
NEWS_LOOKBACK_HOURS = 24

# A proven news action moves the price-based action one step; an unproven one never does.
_PROVEN_STEP = {
    "reduce": {"BUY": "HOLD", "HOLD": "SELL"},
    "add": {"SELL": "HOLD", "HOLD": "BUY"},
}


def _signed_pct(fraction: float) -> str:
    return f"{fraction * 100:+.1f}%".replace("-", "−")


def news_outlooks(
    symbols: list[str], analyzer=None, hours: float = NEWS_LOOKBACK_HOURS
) -> dict[str, tuple[str, object]]:
    """Strongest recent news outlook per symbol: {symbol: (category, TargetOutlook)}.

    Never raises: a missing store, a missing model or any news-module error gives {}, so the
    report still prints. With no `analyzer`, the real store is opened and closed here.
    """
    store = None
    try:
        if analyzer is None:
            from .news.analysis import NewsAnalyzer, open_store
            from .news.settings import DEFAULT_DB_PATH

            if not Path(DEFAULT_DB_PATH).exists():
                return {}
            store = open_store()
            analyzer = NewsAnalyzer(store, symbols)
        best: dict[str, tuple[str, object]] = {}
        for analysis in analyzer.analyze_recent(hours=hours):
            for symbol, outlook in analysis.outlooks.items():
                move = outlook.predicted_action_move
                if move != move:  # NaN: no prediction for this symbol
                    continue
                if symbol not in best or abs(move) > abs(best[symbol][1].predicted_action_move):
                    best[symbol] = (analysis.category or "news", outlook)
        return best
    except Exception as exc:  # the news column must never break the report
        print(f"Note: news column unavailable ({type(exc).__name__}).")
        return {}
    finally:
        if store is not None:
            try:
                store.close()
            except Exception:
                pass


def format_news_cell(category: str, outlook) -> str:
    """e.g. "⚠ war_conflict: −2.1% 1d (unproven)" or "war_conflict: −2.1% 1d (proven: reduce)"."""
    text = f"{category}: {_signed_pct(outlook.predicted_action_move)} 1d"
    if outlook.action_proven:
        return f"{text} (proven: {outlook.action})"
    return f"⚠ {text} (unproven)"


def apply_news_actions(action: str, outlook) -> str:
    """Shift the action one step on a proven news prediction; unproven predictions never do."""
    if outlook is None or not outlook.action_proven:
        return action
    return _PROVEN_STEP.get(outlook.action, {}).get(action, action)


def generate_report(
    symbols: Optional[Iterable[str]] = None,
    portfolio_path: Optional[Union[str, Path]] = None,
    config: AnalysisConfig = DEFAULT_CONFIG,
    include_news: bool = True,
    news_analyzer=None,
) -> pd.DataFrame:
    """Fetch data, run the full analysis pipeline, and return a report DataFrame.

    If `symbols` is omitted, the analysis universe defaults to the resolved
    portfolio's holdings (see `resolve_portfolio_path`), or to
    `DEFAULT_HK_UNIVERSE` if no portfolio is available either.

    `include_news` adds a `news` column from the news module (`news_analyzer` overrides the
    real one in tests); the column holds "—" when there is nothing to show.
    """
    requested, portfolio = resolve_symbols_and_portfolio(symbols, portfolio_path)

    close_prices = fetch_close_prices(requested, period=config.period, interval=config.interval)

    skipped = missing_symbols(requested, {c: close_prices[c] for c in close_prices.columns})
    if skipped:
        print(f"Warning: no data found for {', '.join(skipped)}; skipping.")

    valuations = analyze_valuations(close_prices, config)
    peer_map = build_peer_map(close_prices, config)
    current_prices = {symbol: metrics.current_price for symbol, metrics in valuations.items()}

    news = news_outlooks(list(valuations), news_analyzer) if include_news else {}

    rows = []
    for symbol, valuation in valuations.items():
        recommendation: Recommendation = build_recommendation(
            valuation=valuation,
            peers=peer_map.get(symbol, []),
            portfolio=portfolio,
            current_prices=current_prices,
            config=config,
        )
        category, outlook = news.get(symbol, (None, None))
        action = apply_news_actions(recommendation.action, outlook)
        rationale = recommendation.rationale
        if action != recommendation.action:
            rationale += (
                f" News: proven {outlook.action} prediction moves "
                f"{recommendation.action} to {action}."
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
                "recommendation": action,
                "shares_held": recommendation.shares_held,
                "portfolio_weight": round(recommendation.position_weight, 4),
                "rationale": rationale,
            }
        )
        if include_news:
            rows[-1]["news"] = (
                NO_NEWS if outlook is None else format_news_cell(category, outlook)
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
    if "news" in report.columns:
        display_columns.append("news")
    table = report[display_columns].to_string()
    rationale_lines = "\n".join(
        f"- {symbol}: {row.rationale}" for symbol, row in report.iterrows()
    )
    return f"{table}\n\nRationale:\n{rationale_lines}"
