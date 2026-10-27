"""Default configuration values for stock-advisor analysis."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisConfig:
    """Tunable thresholds and windows used across the analysis pipeline."""

    # History window fetched from Yahoo Finance.
    period: str = "2y"
    interval: str = "1d"

    # Moving-average windows (trading days) reported alongside valuation metrics.
    short_ma_window: int = 20
    medium_ma_window: int = 50
    long_ma_window: int = 200

    # Lookback window used for z-score / percentile-rank valuation.
    valuation_lookback: int = 252

    # Z-score thresholds: price this many std-devs from its historical mean.
    buy_zscore: float = -1.0
    sell_zscore: float = 1.0

    # Percentile-rank thresholds (0-100) of current price within lookback history.
    buy_percentile: float = 20.0
    sell_percentile: float = 80.0

    # Rolling window (trading days) used to compute return correlations.
    correlation_window: int = 90

    # Absolute correlation above which two symbols are considered "correlated peers".
    correlation_threshold: float = 0.6

    # Max number of correlated peers to surface per symbol in the report.
    max_peers_reported: int = 3

    # Portfolio concentration guardrail: fraction of portfolio value a single
    # position may represent before BUY signals are downgraded to HOLD.
    max_position_weight: float = 0.25


DEFAULT_CONFIG = AnalysisConfig()

# Yahoo Finance has no bulk "list all HK tickers" endpoint, so this is a curated
# proxy for "all HK stocks": the Hang Seng Index constituents, in Yahoo's
# "NNNN.HK" ticker format. Used as the analysis universe when no symbols and no
# portfolio are supplied.
DEFAULT_HK_UNIVERSE: tuple[str, ...] = (
    "0001.HK", "0002.HK", "0003.HK", "0005.HK", "0006.HK", "0011.HK", "0012.HK",
    "0016.HK", "0017.HK", "0027.HK", "0066.HK", "0101.HK", "0175.HK", "0241.HK",
    "0267.HK", "0288.HK", "0316.HK", "0322.HK", "0386.HK", "0388.HK", "0669.HK",
    "0688.HK", "0700.HK", "0762.HK", "0823.HK", "0857.HK", "0868.HK", "0881.HK",
    "0883.HK", "0939.HK", "0941.HK", "0968.HK", "0981.HK", "0992.HK", "1038.HK",
    "1044.HK", "1088.HK", "1093.HK", "1109.HK", "1113.HK", "1177.HK", "1211.HK",
    "1299.HK", "1378.HK", "1398.HK", "1810.HK", "1876.HK", "1928.HK", "1929.HK",
    "1997.HK", "2007.HK", "2018.HK", "2020.HK", "2269.HK", "2313.HK", "2318.HK",
    "2319.HK", "2331.HK", "2359.HK", "2382.HK", "2388.HK", "2628.HK", "2688.HK",
    "3690.HK", "3968.HK", "3988.HK", "6098.HK", "6690.HK", "6862.HK", "9618.HK",
    "9633.HK", "9888.HK", "9901.HK", "9961.HK", "9988.HK", "9999.HK",
)

# Price/news targets tracked besides the user's holdings. kind is "index" or "sector".
# Every symbol was confirmed live to return daily Yahoo data on 2026-10-27.
NEWS_TARGETS: dict[str, dict[str, str]] = {
    "^HSI": {"label": "Hang Seng Index", "kind": "index"},
    "^GSPC": {"label": "S&P 500", "kind": "index"},
    "XLK": {"label": "US technology", "kind": "sector"},
    "XLF": {"label": "US financials", "kind": "sector"},
    "XLE": {"label": "US energy", "kind": "sector"},
    "XLV": {"label": "US health care", "kind": "sector"},
    "XLI": {"label": "US industrials", "kind": "sector"},
    "XLY": {"label": "US consumer discretionary", "kind": "sector"},
    "XLP": {"label": "US consumer staples", "kind": "sector"},
    "XLU": {"label": "US utilities", "kind": "sector"},
    "XLB": {"label": "US materials", "kind": "sector"},
    "XLRE": {"label": "US real estate", "kind": "sector"},
    "XLC": {"label": "US communication services", "kind": "sector"},
    # HK proxies: prices work, but Yahoo returns few headlines for them.
    "2800.HK": {"label": "Tracker Fund of Hong Kong", "kind": "index"},
    "3033.HK": {"label": "CSOP Hang Seng TECH ETF", "kind": "sector"},
    "2828.HK": {"label": "Hang Seng China Enterprises ETF", "kind": "index"},
}


def news_targets(holdings: Iterable[str]) -> list[str]:
    """Return the fixed targets followed by holdings (upper-cased, de-duplicated)."""
    result = list(NEWS_TARGETS)
    seen = set(result)
    for symbol in holdings:
        normalized = symbol.strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def MARKET_INDEX_FOR(symbol: str) -> str:  # noqa: N802 - name fixed by the plan
    """Return the benchmark index for a symbol: ^HSI for .HK tickers, else ^GSPC."""
    return "^HSI" if symbol.strip().upper().endswith(".HK") else "^GSPC"
