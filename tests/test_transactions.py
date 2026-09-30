"""Tests for stock_advisor.transactions."""

import pytest

from stock_advisor.transactions import (
    build_portfolio_from_transactions,
    load_transactions,
    normalize_transaction_ticker,
)


def _write_csv(tmp_path, rows):
    path = tmp_path / "transaction.csv"
    header = "#date,name,ticker,currency,price,quantity\n"
    body = "\n".join(rows)
    path.write_text(header + body + "\n", encoding="utf-8")
    return path


def test_normalize_transaction_ticker_hk_numeric_gets_padded_and_suffixed():
    assert normalize_transaction_ticker("00011", "HKD") == "0011.HK"
    assert normalize_transaction_ticker("1", "HKD") == "0001.HK"


def test_normalize_transaction_ticker_us_ticker_passthrough():
    assert normalize_transaction_ticker("aapl", "USD") == "AAPL"


def test_normalize_transaction_ticker_non_hkd_numeric_passthrough():
    # e.g. a bond code that happens to be numeric but isn't HKD-denominated.
    assert normalize_transaction_ticker("123", "USD") == "123"


def test_load_transactions_parses_rows(tmp_path):
    path = _write_csv(
        tmp_path,
        [
            "11-03-2019,Hang Seng Bank,00011,HKD,188.3,100",
            "03-05-2024,Nvidia,NVDA,USD,850,10",
        ],
    )
    transactions = load_transactions(path)

    assert len(transactions) == 2
    assert transactions[0].ticker == "00011"
    assert transactions[0].quantity == 100
    assert transactions[1].trade_date.isoformat() == "2024-05-03"


def test_build_portfolio_from_transactions_aggregates_multiple_buys(tmp_path):
    path = _write_csv(
        tmp_path,
        [
            "01-01-2024,Apple,AAPL,USD,100,10",
            "02-01-2024,Apple,AAPL,USD,200,10",
        ],
    )
    portfolio = build_portfolio_from_transactions(path)

    position = portfolio.positions["AAPL"]
    assert position.shares == 20
    assert position.cost_basis == pytest.approx(150.0)


def test_build_portfolio_from_transactions_sell_keeps_average_cost(tmp_path):
    path = _write_csv(
        tmp_path,
        [
            "01-01-2024,Apple,AAPL,USD,100,10",
            "02-01-2024,Apple,AAPL,USD,200,10",
            "03-01-2024,Apple,AAPL,USD,999,-5",
        ],
    )
    portfolio = build_portfolio_from_transactions(path)

    position = portfolio.positions["AAPL"]
    assert position.shares == 15
    assert position.cost_basis == pytest.approx(150.0)


def test_build_portfolio_from_transactions_drops_fully_closed_positions(tmp_path):
    path = _write_csv(
        tmp_path,
        [
            "01-01-2024,Apple,AAPL,USD,100,10",
            "02-01-2024,Apple,AAPL,USD,150,-10",
        ],
    )
    portfolio = build_portfolio_from_transactions(path)

    assert "AAPL" not in portfolio.positions


def test_build_portfolio_from_transactions_normalizes_hk_ticker(tmp_path):
    path = _write_csv(tmp_path, ["11-03-2019,Hang Seng Bank,00011,HKD,188.3,100"])
    portfolio = build_portfolio_from_transactions(path, cash=500.0)

    assert "0011.HK" in portfolio.positions
    assert portfolio.cash == 500.0


def test_build_portfolio_from_transactions_processes_out_of_order_rows(tmp_path):
    # Later trade date listed first in the file; aggregation must sort by date.
    path = _write_csv(
        tmp_path,
        [
            "03-01-2024,Apple,AAPL,USD,999,-5",
            "01-01-2024,Apple,AAPL,USD,100,10",
            "02-01-2024,Apple,AAPL,USD,200,10",
        ],
    )
    portfolio = build_portfolio_from_transactions(path)

    position = portfolio.positions["AAPL"]
    assert position.shares == 15
    assert position.cost_basis == pytest.approx(150.0)
