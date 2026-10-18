# Stock Advisor

Produces a buy/sell/hold report for a list of stocks based purely on **relative
valuation vs. their own historical price**, with cross-stock correlation context
and portfolio-aware adjustments. Price data comes from Yahoo Finance via
[`yfinance`](https://pypi.org/project/yfinance/).

This is a self-contained repo — all code, tests, and sample data live under this
folder.

## Local price cache

Daily OHLCV history fetched from Yahoo Finance is cached to disk under
`data/cache/prices/` (gitignored) as one parquet file per symbol. A cache is
considered fresh for 12 hours (`CACHE_TTL_HOURS` in
[stock_advisor/market_data.py](stock_advisor/market_data.py)); after that, only
new bars since the last cached date are re-fetched and merged in, rather than
re-downloading the full history. Pass `use_cache=False` to
`fetch_price_history`/`fetch_close_prices` to bypass it entirely.

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

# analyze specific tickers
python -m stock_advisor.cli AAPL MSFT GOOG NVDA --portfolio sample_data/portfolio.json

# or omit tickers entirely: defaults to your resolved portfolio's holdings,
# or a curated Hang Seng Index universe if no portfolio is available
python -m stock_advisor.cli
```

### Interactive app

For a persistent, browsable way to study the market instead of one-off CLI
runs, launch the Streamlit app ([app.py](app.py)):

```bash
streamlit run app.py
```

This opens a local web page where you can adjust symbols/portfolio/period in
the sidebar, view the same report as a sortable table, then pick any symbol
from a dropdown to see its close price over the chosen period plotted with
20/50/200-day moving averages (e.g. select `1398.HK` to see its 1-year trend).

Portfolio file format (see [sample_data/portfolio.json](sample_data/portfolio.json)):

```json
{
  "cash": 2500.0,
  "positions": [
    {"symbol": "AAPL", "shares": 10, "cost_basis": 150.0}
  ]
}
```

### Using your real portfolio

Drop your real data into `data/` (gitignored, so it's never committed). Two
formats are supported, checked in this order:

1. `data/transaction.csv` — a raw brokerage transaction history:

   ```
   #date,name,ticker,currency,price,quantity
   11-03-2019,Hang Seng Bank,00011,HKD,188.3,100
   03-05-2024,Nvidia,NVDA,USD,850,10
   ```

   Dates are `dd-mm-yyyy`; `quantity` is signed (negative = sell). Numeric
   HK tickers with currency `HKD` are converted to Yahoo's `NNNN.HK` format
   automatically. Transactions are aggregated into net positions using the
   average-cost method (sells reduce shares but leave the average cost per
   remaining share unchanged); fully closed-out positions are dropped.

2. `data/portfolio.json` — a plain positions snapshot (see schema above).

If neither exists, the tracked `sample_data/portfolio.json` is used as a demo
fallback. Pass `--portfolio <path>` to override with either a `.csv` or
`.json` file explicitly.

### Choosing which stocks get analyzed

- Symbols passed on the command line always win.
- Otherwise, if a portfolio is resolved (see above) and it holds positions,
  those holdings are analyzed.
- Otherwise, the analysis falls back to `DEFAULT_HK_UNIVERSE` in
  [stock_advisor/config.py](stock_advisor/config.py) — a curated list of Hang
  Seng Index constituents. Yahoo Finance has no bulk "list every HK ticker"
  endpoint, so this list is a practical stand-in for "all HK stocks", not
  literally exhaustive.

## Which metrics are actually good indicators?

The report's valuation signal (z-score + percentile rank vs. own history) is
one hypothesis among several plausible ones. [stock_advisor/indicators.py](stock_advisor/indicators.py)
implements a wider range of candidate metrics as full historical time series
(not just a single current snapshot):

- `zscore_252d`, `percentile_rank_252d` — the metrics the report itself uses
- `pct_from_ma_200d` — percent above/below the 200-day moving average
- `rsi_14d` — Wilder's Relative Strength Index (classic oversold/overbought)
- `bollinger_percent_b_20d` — position within the 20-day Bollinger Bands
- `momentum_60d` — trailing 60-day return (tests the opposite, trend-following hypothesis)
- `distance_from_52w_high` — percent below the trailing 252-day high

[stock_advisor/validation.py](stock_advisor/validation.py) backtests each one:
for every historical day it computes the metric's BUY/SELL/HOLD signal using
only data available up to that day, then measures the forward N-day return
that was *actually* realized afterward (pooled across all requested symbols).
A metric is flagged as a genuine indicator only if it has enough BUY/SELL
samples, BUY signals really did outperform SELL signals going forward
(positive spread), and that spread clears a statistical-significance bar
(Welch's t-stat, default |t| >= 2).

Run it with:

```bash
python -m stock_advisor.validate_cli --period 5y --forward-window 20
# or against specific symbols:
python -m stock_advisor.validate_cli 0700.HK 9988.HK AAPL MSFT --period 5y
```

This prints a ranked table (sample sizes, average forward return per signal
class, spread, t-stat, and a `good_indicator` flag) so you can see which
metrics have real predictive power on your symbols vs. which just look
plausible but don't actually beat noise.

## Project layout

```
app.py                  Streamlit interactive app (report + per-symbol trend charts)
stock_advisor/
  market_data.py       Yahoo Finance loading (yfinance), with a local disk cache
  price_analysis.py    z-score / percentile-rank valuation vs. own history
  indicators.py         wider range of time-series metrics (RSI, Bollinger, momentum, ...)
  validation.py          backtests each metric against realized forward returns
  correlation.py        return correlation across requested symbols
  portfolio.py          load/aggregate user holdings; portfolio JSON schema
  transactions.py        parse transaction-history CSV into net positions
  recommendation.py     combine valuation + correlation + portfolio -> action
  report.py             orchestrates the pipeline into a report DataFrame
  cli.py                command-line entrypoint
  validate_cli.py        metric-backtesting command-line entrypoint
tests/                  unit tests (synthetic data, no network calls)
sample_data/            example portfolio.json
```

## Tests

```bash
pytest
```

Tests use synthetic price data (no live network calls to Yahoo Finance).

## License

MIT; see [LICENSE](LICENSE).
