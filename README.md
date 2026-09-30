# Stock Advisor

Produces a buy/sell/hold report for a list of stocks based purely on **relative
valuation vs. their own historical price**, with cross-stock correlation context
and portfolio-aware adjustments. Price data comes from Yahoo Finance via
[`yfinance`](https://pypi.org/project/yfinance/).

This is a self-contained repo — all code, tests, and sample data live under this
folder.

## How the signal works

For each symbol:

1. **Valuation** ([stock_advisor/price_analysis.py](stock_advisor/price_analysis.py)):
   compute the current price's z-score and percentile rank against its trailing
   history (default: last 252 trading days), plus 20/50/200-day moving averages.
   - Price far **below** its historical mean → `BUY` (cheap).
   - Price far **above** its historical mean → `SELL` (expensive).
   - Otherwise → `HOLD`.
2. **Correlation** ([stock_advisor/correlation.py](stock_advisor/correlation.py)):
   compute pairwise return correlations across the requested symbols (rolling
   90-day window) and surface each symbol's most correlated peers, since equity
   markets move together and a single-stock dip may just be a sector-wide move.
3. **Portfolio adjustment** ([stock_advisor/recommendation.py](stock_advisor/recommendation.py)):
   if a portfolio file is supplied, `BUY` signals are downgraded to `HOLD` when
   the position is already over-concentrated (default: >25% of portfolio value),
   and `SELL` signals are downgraded to `HOLD` when there's no existing position
   to sell.

## Usage

```bash
pip install -r requirements.txt

python -m stock_advisor.cli AAPL MSFT GOOG NVDA --portfolio sample_data/portfolio.json
```

Portfolio file format (see [sample_data/portfolio.json](sample_data/portfolio.json)):

```json
{
  "cash": 2500.0,
  "positions": [
    {"symbol": "AAPL", "shares": 10, "cost_basis": 150.0}
  ]
}
```

## Project layout

```
stock_advisor/
  market_data.py       Yahoo Finance loading (yfinance)
  price_analysis.py    z-score / percentile-rank valuation vs. own history
  correlation.py        return correlation across requested symbols
  portfolio.py          load user holdings from JSON
  recommendation.py     combine valuation + correlation + portfolio -> action
  report.py             orchestrates the pipeline into a report DataFrame
  cli.py                command-line entrypoint
tests/                  unit tests (synthetic data, no network calls)
sample_data/            example portfolio.json
```

## Tests

```bash
pytest
```

Tests use synthetic price data (no live network calls to Yahoo Finance).
