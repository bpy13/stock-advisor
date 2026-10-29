# Stock Advisor

[![CI](https://github.com/bpy13/stock-advisor/actions/workflows/ci.yml/badge.svg)](https://github.com/bpy13/stock-advisor/actions/workflows/ci.yml)

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

## News event module

A separate module that watches the news for market-moving events (new government policies,
wars, security vulnerabilities, crashes). For each event it:

1. finds similar past events (nearest neighbours by meaning of the headlines);
2. measures how markets reacted to them (1 minute, 1 hour and 1 day, plus a path out to 10 days);
3. predicts today's move for `^HSI`, `^GSPC`, sector funds and your holdings at the 1-minute,
   1-hour and 1-day horizons, with an 80% range;
4. suggests an action (reduce, add or hold) and a profitable window, such as "exit within 1-3 days";
5. sends a Telegram alert for high-impact events that need attention.

Headlines are scored for tone with FinBERT and for meaning with a small sentence-embedding model,
both running on the CPU. Headlines about one story merge into one event. Full articles are
fetched only for high-impact events.

**Honest caveat.** News effects on prices are small, and professionals price most of them in
within seconds. The aim is to beat ordinary investors who read the news late, not trading
algorithms. A walk-forward backtest decides whether each prediction is worth trusting. This is a
personal research tool and not financial advice.

### Sources

| Source | Status | History reach | Notes |
|---|---|---|---|
| Wikipedia Current events | kept | 2002-04 onward | Date only, no time of day |
| SEC EDGAR 8-K filings | kept | 1994 onward | Date only for old filings; live feed limited to an allowlist plus your US holdings |
| GDELT | kept | about 2017 onward | Strict rate limits |
| Guardian Open Platform | kept | 1990-02 onward | Free key; 500 calls a day; headline and link only |
| New York Times Archive and Top Stories | kept | 1990 onward | Free key; 500 calls a day |
| Yahoo Finance headlines (yfinance) | kept | recent only | Per symbol, through the Search fallback |
| Public RSS feeds (12) | kept | recent only | RTHK, SCMP, BBC, Investing.com, HKFP, Federal Reserve, HKMA, CISA, USGS earthquakes |
| Google News RSS | skipped | n/a | Its robots.txt disallows `/rss` for every crawler |
| HKEXnews | skipped | n/a | HKEX Terms of Use (section 5) forbid scripted access and data mining |

The rule: use only official feeds, APIs and filings. Skip sites whose terms forbid scraping and
skip paywalled articles.

### Setup

```powershell
conda env create -f environment.yml          # python 3.12 env "stock_advisor"
Copy-Item .env.example .env                  # then fill in the keys below
```

`.env` is gitignored. Never commit it. Keys:

| Key | What it is | How to get it |
|---|---|---|
| `SEC_CONTACT_EMAIL` | contact address EDGAR requires in the User-Agent | your own email |
| `GUARDIAN_API_KEY` | Guardian Open Platform | register for a free developer key at open-platform.theguardian.com |
| `NYT_API_KEY` | NYT Archive and Top Stories | create an app at developer.nytimes.com, enable the Archive API and the Top Stories API |
| `TELEGRAM_BOT_TOKEN` | your alert bot | message @BotFather in Telegram, send `/newbot` |
| `TELEGRAM_CHAT_ID` | where alerts go | filled in by `notify --setup` |
| `TELEGRAM_MAX_ALERTS_PER_HOUR` | optional, default 10 | a number |

A source whose key is missing logs one warning and returns nothing. Telegram setup:

```powershell
# 1. put TELEGRAM_BOT_TOKEN in .env, 2. send your bot one message in Telegram, then:
conda run -n stock_advisor python -m stock_advisor.news.notify --setup   # saves TELEGRAM_CHAT_ID
conda run -n stock_advisor python -m stock_advisor.news.notify --test    # sends one test message
```

### Commands

Run all of these from the repo root. Prefix with `conda run -n stock_advisor` (or activate the env).

Note: `conda run` passes arguments through `cmd`, which strips `^`, so `--targets ^HSI` arrives
as `HSI`. The CLIs map `HSI` and `GSPC` back to `^HSI` and `^GSPC`. You can also write `^^HSI`
or call the env's own `python.exe` directly.

```powershell
# Collect headlines now (every source's latest items)
python -m stock_advisor.news.collect --recent
python -m stock_advisor.news.collect --backfill --source guardian --start 2020-01-01

# Build history: all long-history sources, then score, categorize and cluster. Resumable.
python scripts/backfill_news.py                 # runs for hours; one at a time (lock file)
python scripts/backfill_news.py --status        # progress per source
python scripts/backfill_news.py --max-minutes 90
# Re-apply the current category rules to stored items (back up news.db first; needs the lock)
python scripts/recategorize_news.py --dry-run   # old -> new category counts, writes nothing
python scripts/recategorize_news.py             # update changed rows and their events

# Current events, similar past events, predicted moves, actions
python -m stock_advisor.news_cli                # one-shot, last 24 h from the store
python -m stock_advisor.news_cli --collect      # fetch and score first
python -m stock_advisor.news_cli --watch        # keep polling; prints new high-impact events
python -m stock_advisor.news_cli --watch --no-alerts   # watch without Telegram

# Walk-forward backtest; saves data/cache/news/model/results.json and fitted.pkl
# (the models the watcher, report and dashboard load; they never fit themselves)
python -m stock_advisor.news_backtest_cli
# Refit and save only fitted.pkl from the cached reactions (no backtest; results.json unchanged)
python -m stock_advisor.news_backtest_cli --fit-only

# Record today's 1-minute and 60-minute bars (Yahoo keeps 1m for only ~30 days); no options
python scripts/record_minutes.py
```

Predictions also appear as a `news` column in `python -m stock_advisor.cli` and in the **News** tab
of `streamlit run app.py`.

### Scheduled tasks (Windows)

Four scripts register Windows scheduled tasks. Each replaces its task if you run it again.
All run headless (`conhost.exe --headless`, no window) and need no administrator rights.

| Script | Task name | When |
|---|---|---|
| `scripts\register_dashboard_task.ps1` | `stock_advisor_dashboard` | at login, `streamlit run app.py` on fixed port 8502 (hk-estate holds 8501), restarted if it stops |
| `scripts\register_recorder_task.ps1` | `stock_advisor_minute_recorder` | daily 22:00, saves minute bars |
| `scripts\register_backfill_task.ps1` | `stock_advisor_news_backfill` | daily 02:00, continues the backfill |
| `scripts\register_watcher_task.ps1` | `stock_advisor_news_watcher` | at login, runs `news_cli --watch`, logs to `data\cache\news\watcher_log.txt` |

```powershell
powershell -File scripts\register_watcher_task.ps1
Start-ScheduledTask -TaskName stock_advisor_news_watcher
Get-ScheduledTask stock_advisor_news_watcher
# remove a task
Unregister-ScheduledTask -TaskName stock_advisor_news_watcher -Confirm:$false
```

Memory guard: the watcher and the dashboard exit (code 86) when they use more private memory than
a limit, and their wrapper scripts restart them. Set the limit in GB with
`STOCK_ADVISOR_WATCHER_MEMORY_GB` (default 8) and `STOCK_ADVISOR_DASHBOARD_MEMORY_GB`
(default 10), in the environment or `.env`.

### How to read the output

- **Predicted move**: for each target, 1m, 1h and 1d returns with an 80% range, for example
  `1d -1.20% (80% range -3.00% to +0.60%)`.
- **`⚠ unproven`**: the backtest has not shown, on held-out later years, that this target and
  horizon beats chance. Treat the number as a note, not a signal. It never changes the
  price-based recommendation.
- **Proven rule**: a target and horizon is proven when it has at least 30 out-of-sample events,
  an absolute Welch t-stat of at least 2 and a hit rate above 50%. A proven "reduce" or "add"
  moves the price-based recommendation one step (default awaiting your confirmation, see
  `docs/decisions.md`).
- **Action**: predicted 1-day move at or below -1.5% says reduce; at or above +1.5% says add;
  otherwise hold. The threshold is `NEWS_ACTION_THRESHOLD_PCT` in `stock_advisor/config.py`.
- **Window**: "exit within 1-3 days" comes from when similar past events' price paths peaked.
  "no reversal within 10 days" means the move had not reversed in the history.
- **`n/a`**: too little history to predict. Run the backfill and the backtest first.

More detail: [docs/architecture.md](docs/architecture.md) and
[docs/known-issues.md](docs/known-issues.md).

## Backtest results

Latest news-model run: 2026-10-29 05:10 HKT (`generated_at` 2026-10-28T21:10:37Z in
`results.json`). It covered 321,373 news events from 1990-01-01 to 2026-10-28, 37 targets
(16 index and sector targets plus the portfolio's holdings, not listed here) and 10 horizons
from 1 minute to 10 days.

**Out of sample, nothing is proven yet.** The walk-forward test scored 271 target/horizon
pairs (99 more were skipped for too few price reactions). Every pair had 0 out-of-sample
events, so none meets the proven rule (n >= 30, |t| >= 2, hit rate > 50%). The news history
backfill is still running; the backtest is rerun once it has filled in older years.

**In-sample category screen** from the same run: Hang Seng Index, 1-day reaction after an
event, categories with at least 30 events (means and t-stats rounded):

| Event category | Events | Mean 1-day return | t-stat | Passes \|t\| >= 2? |
|---|---:|---:|---:|:---:|
| company_corporate_action | 71 | +0.285% | +6.70 | yes |
| company_results | 108 | +0.194% | +4.73 | yes |
| election_politics | 78 | -0.213% | -3.82 | yes |
| energy_commodities | 45 | +0.075% | +0.95 | no |
| financial_crisis | 55 | -0.002% | -0.03 | no |
| war_conflict | 34 | -0.005% | -0.05 | no |
| other | 442 | +0.001% | +0.03 | no |

Takeaway: three categories clear |t| >= 2 in sample, but the screen tests 15 categories
across 37 targets and 8 horizons with no out-of-sample confirmation, so they are leads to
test, not signals to trade. The S&P 500 1-day rows are left out on purpose: every category
there, including "other", shows about +0.5% a day with t above 9. That pattern points to a
data problem in that reaction series, not a news effect.

Reproduce (needs the news backfill first; writes `data/cache/news/model/results.json`):

```powershell
python -m stock_advisor.news_backtest_cli
```

The price-indicator backtest (`python -m stock_advisor.validate_cli`) prints its table and
saves no results file, so no numbers from it are listed here.

## Project layout

```
app.py                  Streamlit interactive app (report + News tab + per-symbol trend charts)
scripts/
  backfill_news.py       resumable news history backfill (+ --status)
  record_minutes.py      daily 1m and 60m price recorder
  register_*_task.ps1    register the scheduled tasks; run_watcher.ps1 is the watcher's wrapper
docs/                    architecture.md, known-issues.md, decisions.md, open-items.md, plans/
stock_advisor/
  news/                  news module: sources/, store, scoring, categories, events, reactions,
                         model, window, analysis, collect, notify
  news_cli.py            current events, predictions, --watch
  news_backtest_cli.py   walk-forward backtest of the news model
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
