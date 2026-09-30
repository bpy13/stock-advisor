"""Interactive Stock Advisor app: browse the buy/sell/hold report and drill into
any symbol's price trend.

Run with: streamlit run app.py
"""

from __future__ import annotations

from dataclasses import replace
from typing import Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from stock_advisor.config import DEFAULT_CONFIG
from stock_advisor.market_data import fetch_close_prices, fetch_price_history
from stock_advisor.report import generate_report
from stock_advisor.validation import (
    DEFAULT_METRICS,
    current_signal_table,
    evaluate_metrics,
    rank_metrics,
)

st.set_page_config(page_title="Stock Advisor", layout="wide")


@st.cache_data(ttl=900, show_spinner="Fetching data and analyzing...")
def _run_report(
    symbols_key: Optional[Tuple[str, ...]], portfolio_path: str, period: str
) -> pd.DataFrame:
    symbols = list(symbols_key) if symbols_key else None
    config = replace(DEFAULT_CONFIG, period=period)
    return generate_report(symbols=symbols, portfolio_path=portfolio_path or None, config=config)


@st.cache_data(ttl=900, show_spinner="Loading price history...")
def _load_closes(symbol: str, period: str) -> pd.Series:
    history = fetch_price_history([symbol], period=period)[symbol]
    return history["Close"]


@st.cache_data(ttl=900, show_spinner="Loading price history for comparison...")
def _load_close_prices(symbols_key: Tuple[str, ...], period: str) -> pd.DataFrame:
    return fetch_close_prices(list(symbols_key), period=period)


@st.cache_data(ttl=900, show_spinner="Backtesting metrics against realized forward returns...")
def _backtest_metrics(
    symbols_key: Tuple[str, ...], period: str, forward_window: int, metric_names: Tuple[str, ...]
) -> pd.DataFrame:
    close_prices = _load_close_prices(symbols_key, period)
    metrics = [m for m in DEFAULT_METRICS if m.name in metric_names]
    return evaluate_metrics(close_prices, metrics=metrics, forward_window=forward_window)


st.title("Stock Advisor")

with st.sidebar:
    st.header("Settings")
    symbols_input = st.text_input(
        "Symbols (comma-separated, blank = auto)",
        help=(
            "Blank defaults to your portfolio's holdings (data/transaction.csv or "
            "data/portfolio.json), or the HK universe if no portfolio is found."
        ),
    )
    portfolio_path = st.text_input("Portfolio file (blank = auto-detect)")
    period = st.selectbox("History period", ["6mo", "1y", "2y", "5y"], index=2)
    if st.button("Run report", type="primary"):
        st.cache_data.clear()

symbols_key = tuple(s.strip().upper() for s in symbols_input.split(",") if s.strip()) or None

try:
    report = _run_report(symbols_key, portfolio_path, period)
except Exception as exc:  # surface fetch/validation errors in the UI instead of crashing
    st.error(f"Failed to generate report: {exc}")
    st.stop()

st.subheader("Report")
st.dataframe(report.drop(columns=["rationale"]), use_container_width=True)

st.subheader("Price trend")
selected_symbol = st.selectbox("Symbol", options=list(report.index))

if selected_symbol:
    closes = _load_closes(selected_symbol, period)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=closes.index, y=closes, name="Close"))
    for window, label in ((20, "20D MA"), (50, "50D MA"), (200, "200D MA")):
        fig.add_trace(go.Scatter(x=closes.index, y=closes.rolling(window).mean(), name=label))
    fig.update_layout(height=500, xaxis_title="Date", yaxis_title="Price", legend_title="")
    st.plotly_chart(fig, use_container_width=True)

    row = report.loc[selected_symbol]
    col1, col2, col3 = st.columns(3)
    col1.metric("Recommendation", row["recommendation"])
    col2.metric("Z-score", f"{row['zscore']:+.2f}")
    col3.metric("Percentile", f"{row['percentile_rank']:.0f}th")
    st.caption(row["rationale"])

st.subheader("Compare methods")
st.caption(
    "See what each valuation method says about the same stocks right now, and "
    "whether that method has actually predicted forward returns historically."
)

metric_names = [m.name for m in DEFAULT_METRICS]
selected_metric_names = st.multiselect("Metrics to compare", metric_names, default=metric_names)
chosen_metrics = [m for m in DEFAULT_METRICS if m.name in selected_metric_names]

if chosen_metrics:
    symbols_key = tuple(report.index)
    close_prices = _load_close_prices(symbols_key, period)

    st.markdown("**Current signal per symbol, per method**")
    current_table = current_signal_table(close_prices, metrics=chosen_metrics)
    st.dataframe(current_table.round(4), use_container_width=True)

    st.markdown("**Backtested historical edge** (does each method actually predict forward returns?)")
    col1, col2 = st.columns(2)
    forward_window = col1.slider("Forward window (trading days)", 5, 60, 20, step=5)
    backtest_period = col2.selectbox("Backtest history length", ["2y", "5y", "10y"], index=1)

    summary = _backtest_metrics(
        symbols_key, backtest_period, forward_window, tuple(selected_metric_names)
    )
    ranked = rank_metrics(summary)
    st.dataframe(ranked.round(4), use_container_width=True)
    st.caption(
        "`good_indicator` = enough BUY/SELL samples, a correctly-signed spread, and "
        "|t-stat| >= 2 (a rule-of-thumb bar for \"probably not just noise\")."
    )
else:
    st.info("Select at least one metric above to compare.")
