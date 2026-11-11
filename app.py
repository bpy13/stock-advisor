"""Interactive Stock Advisor app: browse the buy/sell/hold report and drill into
any symbol's price trend.

Run with: streamlit run app.py
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from stock_advisor.config import DEFAULT_CONFIG
from stock_advisor.market_data import fetch_close_prices, fetch_price_history
from stock_advisor.memory_guard import (
    DASHBOARD_DEFAULT_GB,
    DASHBOARD_LIMIT_ENV,
    limit_from_env,
    start_memory_guard,
)
from stock_advisor.report import generate_report
from stock_advisor.validation import (
    DEFAULT_METRICS,
    current_signal_table,
    evaluate_metrics,
    rank_metrics,
)

st.set_page_config(page_title="Stock Advisor", layout="wide")

# A runaway dashboard exits and run_dashboard.ps1 restarts it. Streamlit reruns this script on
# every interaction; the guard starts only once per process.
start_memory_guard("dashboard", limit_from_env(DASHBOARD_LIMIT_ENV, DASHBOARD_DEFAULT_GB))


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


# ---- News tab ---------------------------------------------------------------------------------
# Display rule (decisions.md): every source shows headline + link only, never the summary.

NEWS_TTL = 300  # seconds; the watcher stores new events every minute or so
HOURS_CHOICES = {"6 hours": 6, "24 hours": 24, "3 days": 72, "7 days": 168}
PRICE_FIELDS = ("1m", "1h", "1d")


@st.cache_data(ttl=NEWS_TTL, show_spinner="Analyzing recent news events...")
def _news_analyses(hours: float, high_impact_only: bool, limit: int):
    """Analyses of recent events. Opens the store for this call only (short busy timeout use,
    closed at once) so the backfill's writes are never blocked for long."""
    from stock_advisor.news import analysis as A
    from stock_advisor.news.collect import holdings_symbols
    from stock_advisor.news.reactions import default_price_loader

    targets = A.alert_targets(holdings_symbols())
    store = A.open_store()
    try:
        analyzer = A.NewsAnalyzer(store, targets, price_loader=default_price_loader)
        analyzer.refresh()
        analyses = analyzer.analyze_recent(hours, high_impact_only, limit)
        # SimilarEvent has no link, so look up each past event's lead item URL here.
        links = {}
        for a in analyses:
            for s in a.similar:
                if s.event_id not in links:
                    items = store.items_for_event(s.event_id)
                    lead = next((i.url for i in items if i.title == s.title and i.url), "")
                    links[s.event_id] = lead or next((i.url for i in items if i.url), "")
        return analyses, analyzer.history_events, links
    finally:
        store.close()


@st.cache_data(ttl=NEWS_TTL)
def _news_backtest_results() -> dict:
    from stock_advisor.news_backtest_cli import load_results

    return load_results().data


@st.cache_data(ttl=30)
def _backfill_status() -> dict:
    from stock_advisor.news.analysis import BACKFILL_STATUS_PATH

    try:
        return json.loads(BACKFILL_STATUS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _pct(value: float, signed: bool = True) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value * 100:+.2f}%" if signed else f"{value * 100:.2f}%"


def _link(title: str, url: str) -> str:
    """Markdown link for a headline; plain text when there is no URL."""
    safe = title.replace("[", "(").replace("]", ")")
    return f"[{safe}]({url})" if url else safe


def _forecast_table(outlooks) -> pd.DataFrame:
    rows = []
    for target, outlook in outlooks.items():
        for horizon, f in outlook.forecasts.items():
            rows.append({
                "Target": target,
                "Horizon": horizon,
                "Predicted": _pct(f.predicted),
                "Range (80%)": f"{_pct(f.low)} to {_pct(f.high)}" if f.available else "n/a",
                "Action": outlook.action if horizon == "1d" and outlook.has_prediction else "",
                "Window": outlook.window_text if horizon == "1d" else "",
                "Status": "proven" if f.proven else "⚠ unproven",
            })
    return pd.DataFrame(rows)


def _similar_markdown(analysis, links: dict) -> str:
    """Markdown table (dataframes cannot show a different link text per row)."""
    # Keep the table narrow: the main indices and the first holdings only.
    targets = (list(analysis.outlooks) or list(analysis.similar[0].reactions))[:4]
    head = "| Date | Headline | Similarity | " + " | ".join(f"{t} 1d" for t in targets) + " |"
    sep = "|" + " --- |" * (3 + len(targets))
    rows = [
        f"| {s.started_at.strftime('%Y-%m-%d')} | {_link(s.title, links.get(s.event_id, '')).replace('|', '/')} "
        f"| {s.similarity:.2f} | " + " | ".join(_pct(s.reactions.get(t)) for t in targets) + " |"
        for s in analysis.similar
    ]
    return "\n".join([head, sep, *rows])


def _render_event(a, links: dict) -> None:
    flag = "HIGH IMPACT · " if a.high_impact else ""
    st.markdown(f"##### {flag}{_link(a.title, a.link)}")
    st.caption(
        f"{a.started_at.strftime('%Y-%m-%d %H:%M UTC')} · category: {a.category or 'n/a'} · "
        f"{a.n_items} items · sources: {', '.join(a.sources) or 'n/a'}"
    )
    if len(a.headlines) > 1:
        st.markdown("\n".join(f"- {_link(h.title, h.url)} ({h.source})" for h in a.headlines))
    for warning in a.warnings:
        st.warning(warning)

    st.markdown("**Similar past events**")
    if a.similar:
        st.markdown(_similar_markdown(a, links))
    else:
        st.caption("No similar past events yet (the backfill is still building history).")

    st.markdown("**Predicted moves**")
    forecasts = _forecast_table(a.outlooks)
    if forecasts.empty or all(not o.has_prediction for o in a.outlooks.values()):
        st.caption("Not enough similar events to predict yet.")
    else:
        st.dataframe(forecasts, use_container_width=True, hide_index=True)
        if any(not f.proven for o in a.outlooks.values() for f in o.forecasts.values()):
            st.caption("⚠ unproven: the backtest has not shown this prediction beats chance.")


def _render_backtest(results: dict) -> None:
    st.subheader("Backtest results")
    if not results.get("results"):
        st.info("The backtest has not run yet (no results.json). Run "
                "`python -m stock_advisor.news_backtest_cli` once the backfill has built history.")
        return
    st.caption(
        f"Generated {results.get('generated_at', 'n/a')} from {results.get('n_events', 0)} events "
        f"({str(results.get('first_event') or '')[:10]} to {str(results.get('last_event') or '')[:10]})."
    )
    table = pd.DataFrame(results["results"])
    columns = [c for c in ("target", "horizon", "n", "hit_rate", "mean_signed_return",
                           "t_stat", "proven") if c in table.columns]
    st.dataframe(table[columns], use_container_width=True, hide_index=True)
    window = results.get("window")
    if window:
        with st.expander("Profitable-window data"):
            st.json(window)


def _render_backfill(status: dict) -> None:
    st.subheader("Backfill progress")
    if not status:
        st.caption("No backfill status file found.")
        return
    st.caption(f"State: {status.get('state', 'n/a')} · updated {status.get('updated', 'n/a')}")
    rows = [{"Source": name, "Status": info.get("run_status", ""),
             "Items stored": info.get("items_stored", 0),
             "Cursor": str(info.get("cursor") or "")[:10],
             "Complete": info.get("complete", False), "Last error": info.get("last_error", "")}
            for name, info in status.get("sources", {}).items()]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ---- Portfolio tab ----------------------------------------------------------------------------


@st.cache_data(ttl=3600, show_spinner="Analyzing the portfolio...")
def _portfolio_report():
    from stock_advisor.analyzer import build_portfolio_report  # imported here: pulls in sklearn
    return build_portfolio_report()


@st.cache_data(ttl=3600)
def _trade_cost_text(symbol: str, amount: float) -> str:
    from stock_advisor.analyze_cli import cost_report
    return cost_report(symbol, amount)


def _render_portfolio_tab() -> None:
    try:
        rep = _portfolio_report()
    except Exception as exc:  # a missing store or accounts file must not break the other tabs
        st.error(f"Could not build the portfolio analysis: {exc}")
        return
    s = rep.summary
    st.subheader("Portfolio (HKD)")
    cols = st.columns(4)
    cols[0].metric("Value today", f"{s.value_today:,.0f}")
    cols[1].metric("Return, no deposit timing", _pct(s.return_without_timing))
    cols[2].metric("Return with timing (a year)", _pct(s.return_with_timing))
    cols[3].metric("Deepest fall", _pct(s.deepest_fall, signed=False))
    cols = st.columns(4)
    cols[0].metric("Yearly swing", _pct(s.yearly_swing, signed=False))
    cols[1].metric("Three largest holdings", _pct(s.top3_weight, signed=False))
    cols[2].metric("Effective holdings", f"{s.effective_holdings:.1f}")
    cols[3].metric("Cash", f"{s.cash:,.0f}")
    if not rep.cash_set:
        st.info("Cash is not set: edit data/accounts.json")
    if s.value_series is not None and not s.value_series.empty:
        fig = go.Figure(go.Scatter(x=s.value_series.index, y=s.value_series.values, name="Value"))
        if s.fall_start is not None and s.fall_end is not None:
            fig.add_vrect(x0=s.fall_start, x1=s.fall_end, fillcolor="red", opacity=0.15,
                          line_width=0, annotation_text="deepest fall")
        fig.update_layout(title="Value of the holdings", height=350, margin=dict(t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)
    if s.unpriced:
        st.warning(f"No price in the store (valued at cost): {', '.join(s.unpriced)}")
    if rep.too_short:
        st.warning(f"Under a year of history (no risk numbers): {', '.join(rep.too_short)}")
    st.subheader("Per holding")
    st.dataframe(rep.table, use_container_width=True)
    if rep.groups:
        st.subheader("Groups that move together")
        for group in rep.groups:
            st.write(", ".join(group))
    st.caption(rep.caveat)
    st.subheader("Cost of a trade")
    c1, c2 = st.columns(2)
    symbol = c1.text_input("Symbol", "0005.HK", key="cost_symbol").strip().upper()
    amount = c2.number_input("Amount (value of the trade)", min_value=1.0, value=20000.0, step=1000.0)
    if symbol:
        try:
            st.code(_trade_cost_text(symbol, float(amount)))
        except (Exception, SystemExit) as exc:  # cost_report exits when a US price is missing
            st.error(f"Could not price the trade: {exc}")


def _render_news_tab() -> None:
    st.subheader("Recent news events")
    col1, col2, col3 = st.columns([2, 2, 1])
    window_label = col1.selectbox("Time window", list(HOURS_CHOICES), index=1)
    high_only = col2.checkbox("High-impact only", value=False)
    max_events = col3.number_input("Max events", 1, 50, 10)
    try:
        analyses, history, links = _news_analyses(
            HOURS_CHOICES[window_label], high_only, int(max_events))
    except Exception as exc:  # a locked or missing store must not break the other tabs
        st.error(f"Could not load news events: {exc}")
        analyses, history, links = [], 0, {}
    st.caption(f"{len(analyses)} events shown; model built from {history} past events.")
    if not analyses:
        st.info("No events in this window.")
    for analysis in analyses:
        with st.container(border=True):
            _render_event(analysis, links)
    _render_backtest(_news_backtest_results())
    _render_backfill(_backfill_status())


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

tab_report, tab_portfolio, tab_news = st.tabs(["Report", "Portfolio", "News"])

# The Portfolio and News tabs render before the report so a failed report (st.stop below)
# cannot hide them.
with tab_portfolio:
    _render_portfolio_tab()

with tab_news:
    _render_news_tab()

with tab_report:
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
