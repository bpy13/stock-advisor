"""Tests for stock_advisor.correlation using synthetic price series."""

import numpy as np
import pandas as pd

from stock_advisor.config import AnalysisConfig
from stock_advisor.correlation import (
    build_peer_map,
    compute_correlation_matrix,
    get_correlated_peers,
)


def _synthetic_close_prices(length: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(seed=42)
    index = pd.date_range("2023-01-01", periods=length, freq="D")

    shared_returns = rng.normal(0, 0.01, length)
    idiosyncratic = rng.normal(0, 0.01, length)

    # A and B track the same shared factor closely -> highly correlated.
    a_returns = shared_returns + rng.normal(0, 0.001, length)
    b_returns = shared_returns + rng.normal(0, 0.001, length)
    # C is driven by independent noise -> should not be strongly correlated.
    c_returns = idiosyncratic

    prices = pd.DataFrame(
        {
            "A": 100 * (1 + a_returns).cumprod(),
            "B": 100 * (1 + b_returns).cumprod(),
            "C": 100 * (1 + c_returns).cumprod(),
        },
        index=index,
    )
    return prices


def test_compute_correlation_matrix_shape_and_diagonal():
    prices = _synthetic_close_prices()
    matrix = compute_correlation_matrix(prices)

    assert list(matrix.columns) == ["A", "B", "C"]
    for symbol in matrix.columns:
        assert matrix.loc[symbol, symbol] == pytest_approx(1.0)


def pytest_approx(value, tol=1e-6):
    class _Approx:
        def __eq__(self, other):
            return abs(other - value) < tol

    return _Approx()


def test_get_correlated_peers_finds_strongly_correlated_pair():
    prices = _synthetic_close_prices()
    matrix = compute_correlation_matrix(prices)
    config = AnalysisConfig(correlation_threshold=0.5)

    peers = get_correlated_peers("A", matrix, config)

    assert any(peer.symbol == "B" for peer in peers)
    assert all(abs(peer.correlation) >= config.correlation_threshold for peer in peers)


def test_get_correlated_peers_unknown_symbol_returns_empty():
    prices = _synthetic_close_prices()
    matrix = compute_correlation_matrix(prices)

    assert get_correlated_peers("ZZZ", matrix) == []


def test_build_peer_map_covers_all_symbols():
    prices = _synthetic_close_prices()
    peer_map = build_peer_map(prices)

    assert set(peer_map.keys()) == {"A", "B", "C"}
