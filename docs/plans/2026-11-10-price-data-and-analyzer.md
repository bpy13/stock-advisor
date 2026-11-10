# Plan: clean price data and the portfolio analyzer (2026-11-10)

Milestone 1 of `docs/milestones.md`. Written for workers who have not seen the planning chat.

## Goal
The tool holds clean daily and hourly prices for a fixed watchlist, from two sources per
market, and shows Brian an analysis of his portfolio: value, return, risk, concentration and
what each holding is exposed to. No forecast and no alert is built here; milestones 2 to 4
build those on top of this data.

## Approach
1. A watchlist file names what the tool follows. Holdings join it at run time, never in git.
2. A price store keeps bars per source: raw bars are appended, adjusted bars are replaced
   whole on each refresh (an adjusted history changes after every dividend). A trading
   calendar says which sessions should exist, and each bar carries quality flags.
3. Three sources feed the store: Yahoo (exists), Futu for Hong Kong, Alpaca for the US. A
   comparison report says which source is cleaner per market; the store then prefers it.
4. An accounts file holds each account's broker and cash, and the position limits. A fee
   module prices any trade at Hang Seng Bank and at Futu.
5. An analyzer computes the portfolio numbers from the trade file and the store. The CLI and
   a new dashboard tab show them.

## Constraints (verbatim from `docs/decisions.md`, section "Replanning (2026-11-10)")
- (Brian): the goal is to "establish portfolio analyzer, watch news and send Telegram alert
  accordingly".
- (Brian): "free tier news data is sufficient, what we need is stock data for inference".
- (Brian): "the hourly definitely need staying. Minute could be useful for future quant
  projects (need research)". The minute recorder keeps running.
- (Brian, accepted default): a Futu account and a free Alpaca account serve as second price
  sources beside Yahoo. Brian opens the accounts and handles the login and the key; workers
  never see them.
- (Brian, "default for now"): the watchlist is the holdings, the Hang Seng Index members, the
  100 largest US stocks and the main index funds, in a file Brian can edit. Markets: Hong Kong
  and the US only.
- (Brian, accepted default): Brian's broker offers no interface the tool could read, so Brian
  keeps the trade file and a cash figure by hand.
- (Brian): milestone 1 has fee tables for Hang Seng Bank and Futu; Interactive Brokers waits
  for later.
- (Brian): "git ignore any private info". The GitHub repo is public. Which accounts Brian
  holds, his cash, his holdings and anything personal stay in `data/` and `docs/private/`,
  which git ignores.
- 2026-10-27 rule, still in force: use official feeds and APIs only; skip sites whose terms
  forbid scripted access (all HKEX websites) and paywalled pages.

## Rules for every task
- **Private data.** `data/` holds Brian's real holdings. Never print, log to the console,
  commit or quote: a holding's symbol, a share count, a cash figure, a portfolio value. Live
  checks print aggregates only (counts, sums of weights, pass or fail). Any report that names
  holdings goes under `data/reports/` (gitignored). Tests use synthetic data and no network.
- **Secrets.** Never open, print or edit `.env`. Code reads it through
  `stock_advisor/news/settings.py` (`load_env`, `get_setting`). A task that needs a key or a
  login Brian has not provided stays `(waiting: inbox)`.
- **Python.** Use `C:\Users\brian\miniconda3\envs\stock_advisor\python.exe` directly, not
  `conda run` (it strips `^` from arguments). Scripts over one line go in a file.
- **Where live tasks run.** `data/`, `.env` and `docs/private/` exist only in the main
  project folder, never in a worker's git worktree. Tasks 2.5 to 2.9, 3.5, 4.1 and 4.2 use
  real data: run them only from the main project folder (slot 1). A worker in a worktree
  leaves them and takes another task. No task needs `docs/private/`.
- **Tests and lint.** While editing: the task's own test files. Before each commit:
  `...\python.exe -m pytest -q` (all pass) and `...\python.exe -m ruff check .` (no findings).
- **Files.** Touch only the files the task lists. `scripts/run_rebuild_backtest.py` has an
  uncommitted change that is not yours: never stage, edit or revert it. Stage named files
  only, never `git add -A`.
- **Docs.** Tasks do not edit `README.md`, `docs/architecture.md`, `docs/known-issues.md` or
  `docs/open-items.md`; Task 4.4 does. Write findings worth keeping on a `Result:` line under
  your task in this file.
- **Shared resources.** The conda env (only Task 1.1 installs into it). Port 8502 (the live
  dashboard: never stop it by task name; Task 4.2 restarts it by process id). `news.db` is not
  used by this plan. No task here is CPU-heavy, so none goes through the job queue; a task
  that turns out to need more than a few minutes of full CPU uses
  `bot-stream\tools\queue\hkq.ps1` (lane `cpu`).
- **Old code stays.** `market_data.py`, the report and the news module keep working as they
  are. The analyzer and the new CLIs read the store. Milestone 3 retires the old paths.

## Acceptance criteria (the milestone's "done when", with the tasks that deliver each)
| Criterion | Tasks |
|---|---|
| Watchlist file | 1.2 |
| Price store: daily and hourly, raw and adjusted apart, calendar, flags | 1.3, 2.1, 2.2, 2.5 |
| Second sources and the comparison report; the store prefers the cleaner one | 2.3, 2.4, 2.7, 2.8, 2.9 |
| Portfolio inputs: accounts, cash, limits, two fee tables | 1.4, 1.5 |
| Analyzer on the dashboard and the CLI | 3.1 to 3.5 |
| Old plan closed; dashboard checked in a real browser; four scheduled tasks checked | done 2026-11-10 (plan closed); 4.1, 4.2 |
| Minute recorder keeps running; stored size measured | 2.6 |
| Tests and `ruff check` pass; docs match | every task; 4.3, 4.4 |

## Interfaces fixed by this plan
```python
# stock_advisor/watchlist.py
@dataclass(frozen=True)
class WatchItem: symbol: str; market: str; kind: str; name: str
#   market: "HK" | "US" | "OTHER"   kind: "stock" | "index_fund" | "index" | "driver" | "fx" | "holding"
def load_watchlist(include_holdings: bool = True) -> list[WatchItem]

# stock_advisor/calendars.py
def sessions(market: str, start, end) -> pd.DatetimeIndex            # session dates, tz-naive
def hourly_bar_starts(market: str, session_date) -> list[pd.Timestamp]  # UTC bar starts

# stock_advisor/price_store.py     files: data/cache/store/<source>/<interval>/<raw|adjusted>/<symbol>.parquet
SOURCES = ("yahoo", "futu", "alpaca");  INTERVALS = ("1d", "60m")
def write_bars(source, interval, symbol, raw: pd.DataFrame, adjusted: pd.DataFrame | None) -> None
def read_bars(symbol, interval="1d", adjusted=True, source=None, start=None, end=None) -> pd.DataFrame
#   columns: open, high, low, close, volume, no_trade, big_move, gap_before
#   index: "1d" = session date (tz-naive); "60m" = bar start, UTC.  source=None = preferred source.
def status() -> pd.DataFrame      # per source, interval, market: symbols, first and last bar, flag counts

# stock_advisor/price_sources/<yahoo|futu|alpaca>.py   each:
def fetch(symbol: str, interval: str, start, end) -> tuple[pd.DataFrame, pd.DataFrame | None]  # raw, adjusted

# stock_advisor/accounts.py
@dataclass(frozen=True)
class Account: name: str; broker: str; cash: dict[str, float]; trade_file: str | None
@dataclass(frozen=True)
class Limits: max_position_weight: float; min_trade_hkd: float; whole_board_lots: bool
BROKERS = ("hang_seng_bank", "futu")
def load_accounts(path=None) -> tuple[list[Account], Limits]

# stock_advisor/fees.py   (imports BROKERS from accounts)
def trade_cost(broker, market, kind, price, shares, side) -> TradeCost   # .total, .currency, .lines
def round_trip_pct(broker, market, kind, price, shares) -> float
```

## Phase 1 – Foundations (sonnet)

- [x] **Task 1.1: add the two new dependencies**
  - Result: installed exchange_calendars 4.13.2 and futu-api 10.12.7208; import OK, pip check clean, 389 tests pass, ruff clean.
  - Files: modify `environment.yml`, `requirements.txt`.
  - Add `exchange_calendars` (trading calendars) and `futu-api` (the only client for Futu's
    local gateway), pinned to the versions pip resolves. Install both into the existing env
    with `...\python.exe -m pip install`. Do not recreate the env.
  - Done when: `...\python.exe -c "import exchange_calendars, futu"` exits 0 (run it from a
    script file); the full test suite passes as before.
  - Notes: if either package fails to install or breaks a pinned package (pandas 3.1,
    numpy 2.5), do not downgrade anything. For calendars try `pandas_market_calendars`
    instead. For Futu, write the error on a `Result:` line and post an inbox question.

- [x] **Task 1.2: the watchlist file** `[parallel-ok]`
  - Files: create `config/watchlist.csv`, `stock_advisor/watchlist.py`,
    `tests/test_watchlist.py`.
  - `config/watchlist.csv` (tracked, Brian edits it): columns `symbol,market,kind,name`,
    Yahoo-style symbols. Rows: the Hang Seng Index members (start from
    `config.DEFAULT_HK_UNIVERSE`; check it against the constituent table on the English
    Wikipedia page "Hang Seng Index" and add or remove to match; write the page's revision
    date in a `#` comment line at the top); the S&P 100 members from the Wikipedia page
    "S&P 100" (this plan's reading of "the 100 largest US stocks"); index funds `2800.HK`,
    `2828.HK`, `3033.HK`, `SPY`, `QQQ` and the eleven sector funds in `config.NEWS_TARGETS`;
    indexes `^HSI`, `^GSPC`, `^NDX`; drivers `CL=F`, `^TNX`, `KWEB`, `HACK`, `CNY=X`; fx
    `HKD=X`.
  - `load_watchlist(include_holdings=True)` reads the file (skipping `#` lines) and adds the
    current holdings from `report.resolve_symbols_and_portfolio()` with kind `holding` when
    the file does not list them. A holding the file lists keeps the file's kind. Holdings
    are never written to the file.
  - Done when: `pytest -q tests/test_watchlist.py` passes (covers: comment lines, duplicate
    symbols rejected with the line number, holdings merged, unknown kind rejected); a script
    prints the row count per market and kind (expect HK stocks 75 to 95, US stocks 99 to 102).
  - Notes: read Wikipedia through its REST API with a descriptive User-Agent, once, by hand
    for this task; no code in the repo fetches it.
  - Result: 215 rows. HK stock 85, US stock 101, HK index fund 3, US index fund 13, indexes 3, drivers 5, fx 1. The HSI Wikipedia table lists 85 members although its text says 88. Six of the old DEFAULT_HK_UNIVERSE symbols are no longer in the table (0011, 0017, 2007, 2018, 6098, 9901). US share classes use Yahoo form (BRK-B).

- [x] **Task 1.3: trading calendars** — needs: Task 1.1
  - Result: calendars.py wraps XHKG/XNYS; bar starts filtered by real close; 7 tests pass.
  - Files: create `stock_advisor/calendars.py`, `tests/test_calendars.py`.
  - Wrap `exchange_calendars` (`XHKG` for market HK, `XNYS` for US). `sessions()` returns
    the session dates. `hourly_bar_starts()` returns the canonical hourly bars of a session,
    as UTC starts: HK 09:30, 10:30, 11:30, 13:00, 14:00, 15:00 Hong Kong time (a half day
    ends with the 11:30 bar); US 09:30 to 15:30 New York time, seven bars, the last one 30
    minutes (an early close at 13:00 ends with the 12:30 bar).
  - Done when: `pytest -q tests/test_calendars.py` passes. Tests pin known dates: 2025-12-24
    is a Hong Kong half day (3 bars); 2025-01-29 is a Hong Kong holiday (no session);
    2025-11-28 is a US early close (4 bars); a US summer and a US winter date give different
    UTC starts.
  - Notes: typhoon closures are not in the library. Do not model them: a typhoon day shows
    up as a `gap_before` flag, which is correct.

- [x] **Task 1.4: accounts, cash and limits** `[parallel-ok]`
  - Result: accounts.py, sample_data/accounts.json, 8 tests pass. Copy of sample to data/accounts.json not made (worktree has no data/); do it in the main folder.
  - Files: create `stock_advisor/accounts.py`, `sample_data/accounts.json`,
    `tests/test_accounts.py`.
  - File format (JSON), as in the sample: `{"accounts": [{"name": "example", "broker":
    "futu", "cash": {"HKD": 0, "USD": 0}, "trade_file": "data/transaction.csv"}],
    "limits": {"max_position_weight": 0.25, "min_trade_hkd": 10000,
    "whole_board_lots": true}}`. An account may have `"trade_file": null`. Brian's real
    accounts go only in `data/accounts.json`; never put them in the sample or in a test.
  - `load_accounts()` reads `data/accounts.json`, else `sample_data/accounts.json`. It
    rejects an unknown broker (not in `BROKERS`), negative cash, an unknown currency (only HKD and USD), and a
    weight outside 0 to 1, each with a message naming the field.
  - Done when: `pytest -q tests/test_accounts.py` passes. In the main project
    folder only: if `data/accounts.json` does not exist, copy the sample there (it is
    gitignored) so Brian has a file to fill in.
  - Notes: do not read or print an existing `data/accounts.json`.

- [x] **Task 1.5: fee tables for two brokers** — needs: Task 1.4
  - Result: fees.py; all worked totals match (HK 243.40/717.00/73.40/247.00, fund 203.40/33.40, US 30.05/4.04); round trip 1.217% HSB, 0.367% Futu for HK$20,000.
  - Files: create `stock_advisor/fees.py`, `tests/test_fees.py`.
  - The rates below were read from each broker's and regulator's own fee page on
    2026-11-10. Put each rate in one table at the top of the module
    with its source page and date in a comment. Cover market HK (kind `stock` pays stamp
    duty 0.1% a side, rounded up to a whole dollar; `index_fund` pays none; both pay the
    0.0085% levies and trading fee a side) and market US (SEC fee 0.00206% and FINRA fee
    US$0.000195 a share, minimum US$0.01, on sales). Brokers: Hang Seng Bank (HK 0.25%,
    minimum HK$100; US US$0.015 a share, minimum US$15); Futu (HK commission 0, platform fee
    HK$15 an order; US US$0.0049 a share minimum US$0.99, plus platform US$0.005 a share
    minimum US$1). Brian set Interactive Brokers aside for later (2026-11-10): build no
    table for it. Its rates are kept outside git for milestone 4.
  - Write the tests first, from these worked totals. A buy and a
    sell of HK$20,000 and of HK$100,000 of one HK stock must total: Hang Seng Bank 243.40
    and 717.00; Futu 73.40 and 247.00. The same for an
    HK index fund: 203.40 and 33.40 (HK$20,000). US, 25 shares at US$100, both sides:
    Hang Seng Bank 30.05 (its schedule lists only the SEC fee, so charge no FINRA fee
    there); Futu 4.04. Allow 0.01 for rounding.
  - Done when: `pytest -q tests/test_fees.py` passes.
  - Notes: currency conversion cost, the price spread and Hang Seng Bank's HK$25 monthly
    custody fee are not per-trade costs: expose the custody fee as a constant, leave the
    others out and say so in the module docstring.

## Phase 2 – The price store (sonnet)

- [x] **Task 2.1: store and quality flags** — needs: Task 1.3
  - Result: price_store.py and quality.py built; market derived from the symbol name; 13 tests pass, ruff clean.
  - Files: create `stock_advisor/price_store.py`, `stock_advisor/quality.py`,
    `tests/test_price_store.py`, `tests/test_quality.py`.
  - `write_bars` merges new raw bars into the stored raw file (new rows win on a duplicate
    index) and replaces the adjusted file whole. It then recomputes the flags and stores
    them in the raw file. `read_bars(adjusted=True)` returns adjusted prices with the raw
    file's flags; a source with no adjusted file returns raw prices.
  - `quality.flag_bars(bars, market, interval, tradable)`: `no_trade` = volume is 0 or
    missing (only when `tradable`, which is true for kinds stock, index_fund and holding);
    `big_move` = absolute close-to-close change above 40% (daily) or 20% (hourly);
    `gap_before` = number of calendar sessions (daily) or canonical bars (hourly) missing
    between the previous bar and this one. Symbols of market `OTHER` (futures, yields, fx)
    get `gap_before` 0.
  - Preferred source: `PREFERRED_SOURCES = {"HK": ("yahoo",), "US": ("yahoo",), "OTHER":
    ("yahoo",)}` in `price_store.py`; `read_bars(source=None)` returns the first source in
    the tuple that has the symbol. Task 2.9 changes the tuples.
  - Done when: both test files pass. Tests cover: append then re-append the same bars
    (no duplicates); an adjusted file replaced by a rescaled one (old values gone); each
    flag on a hand-made series; a daily series with one missing session; reading a symbol
    held by the second source only.
  - Notes: file names replace `.` and `^` and `=` with `_`. The store root comes from one
    module constant so tests point it at `tmp_path`.

- [ ] **Task 2.2: Yahoo into the store, and the prices CLI** — needs: Task 1.2, Task 2.1 (taken: slot 3, 2026-11-10 12:00)
  - Files: create `stock_advisor/price_sources/__init__.py`,
    `stock_advisor/price_sources/yahoo.py`, `stock_advisor/prices_cli.py`,
    `tests/test_price_source_yahoo.py`, `tests/test_prices_cli.py`.
  - `yahoo.fetch`: daily = one `yf.Ticker(symbol).history(period="max", interval="1d",
    auto_adjust=False, repair=True)` call; raw = Open/High/Low/Close/Volume, adjusted = the
    same bars scaled by `Adj Close / Close`. Hourly = `interval="60m"` for the last 729
    days, regular session only, re-indexed to the canonical bar starts of Task 1.3 (drop
    bars that match no canonical start and count them). Yahoo's hourly bars have no adjusted
    form: return `None`. Hourly bars exist only for markets HK and US.
  - `python -m stock_advisor.prices_cli refresh [--source yahoo] [--interval 1d|60m]
    [--limit N]` walks the watchlist with at least 0.5 s between calls, continues after a
    failed symbol, and prints one summary line (symbols done, failed, bars added). `status`
    prints `price_store.status()` grouped by market, without symbols.
  - Done when: the two test files pass (yfinance is faked); `prices_cli refresh --source
    yahoo --interval 1d --limit 5` then `prices_cli status` run for real and show 5 symbols
    with a first bar before 2010.
  - Notes: sources register in a dict in `price_sources/__init__.py`; Tasks 2.3 and 2.4
    each add one line there, in separate commits.

- [ ] **Task 2.3: Alpaca source (code and tests)** — needs: Task 2.2
  - Files: create `stock_advisor/price_sources/alpaca.py`,
    `tests/test_price_source_alpaca.py`, `tests/fixtures/alpaca_bars.json`; modify
    `stock_advisor/price_sources/__init__.py`, `.env.example` (add blank
    `ALPACA_API_KEY=` and `ALPACA_API_SECRET=` with a one-line comment).
  - Use `requests` against `https://data.alpaca.markets/v2/stocks/bars` (headers
    `APCA-API-KEY-ID`, `APCA-API-SECRET-KEY`; follow `next_page_token`). Daily:
    `timeframe=1Day`, once with `adjustment=raw` and once with `adjustment=all`. Hourly:
    fetch `timeframe=30Min` and build the canonical US bars of Task 1.3 from them (open of
    the first half hour, close of the last, high, low, summed volume); regular session only.
    Try `feed=sip` first; on a 403 or 422 that names the subscription, use `feed=iex` and
    remember the choice for the run. Only market US symbols of kind stock, index_fund or
    holding; skip the rest.
  - Done when: the test file passes (HTTP faked: paging, the feed fallback, the 30-minute
    to hourly build, a missing key gives a clear error that names the two variables).

- [ ] **Task 2.4: Futu source (code and tests)** — needs: Task 1.1, Task 2.3
  - Files: create `stock_advisor/price_sources/futu.py`, `tests/test_price_source_futu.py`;
    modify `stock_advisor/price_sources/__init__.py`.
  - Connect `futu.OpenQuoteContext(host="127.0.0.1", port=11111)`; the gateway (Futu OpenD)
    runs on Brian's PC under his login, so the code holds no credential. If the port is
    closed, raise one clear error ("Futu OpenD is not running") that `prices_cli refresh`
    reports and survives. Use `request_history_kline` with `KLType.K_DAY` and
    `KLType.K_60M`, `AuType.NONE` for raw and `AuType.QFQ` for adjusted, paging on
    `page_req_key`, at most 60 requests in 30 seconds. Map `0005.HK` to `HK.00005`.
    Re-index hourly bars to the canonical HK bar starts (Futu labels a bar by its end time,
    in Hong Kong time: Task 2.8 verifies this on real data).
  - Quota: the lowest account tier allows history for 100 different stocks in a rolling
    period. Fetch in this order: holdings, index funds, then the Hang Seng Index members.
    Before fetching, call `get_history_kl_quota`; stop when none is left and report how many
    symbols wait.
  - Done when: the test file passes with a fake quote context (paging, the rate limit, the
    symbol mapping, bar-end to bar-start, the quota stop, the closed-port error).
  - Notes: needs Task 2.3 only because both edit `price_sources/__init__.py`.

- [ ] **Task 2.5: first full Yahoo load** — needs: Task 2.2
  - Files: none (a live run).
  - Run `prices_cli refresh --source yahoo --interval 1d`, then `--interval 60m`, for the
    whole watchlist, in the background, logging to `data/cache/store/refresh_log.txt`.
  - Done when: `prices_cli status` shows, for Yahoo daily, at least 95% of the watchlist
    symbols; write on the `Result:` line the symbol counts, failed count, total flag counts
    per market and the store's size on disk (no symbols).

- [ ] **Task 2.6: nightly refresh, and the minute recorder's size** — needs: Task 2.5
  - Files: modify `scripts/record_minutes.py`, `tests/` file that covers it (create
    `tests/test_record_minutes.py` if none exists).
  - After the script's existing 1-minute and 60-minute recording (unchanged), it runs the
    store refresh for every source, daily then hourly, each source in its own try block so
    one failure does not stop the rest, and adds one line per source to the recorder log.
    The scheduled task `stock_advisor_minute_recorder` already runs this script at 22:00;
    do not re-register it.
  - Measure the minute recorder's stored size: bytes and rows under
    `data/cache/prices_intraday/1m/`, days covered, and the size per stock per year this
    implies. Write the numbers on the `Result:` line.
  - Done when: the test passes (sources faked: one raises, the others still run); one real
    run of the script ends with exit code 0 and the log shows a line per source.

- [ ] **Task 2.7: Alpaca live load** — needs: Task 2.3, Task 2.5
  - Waits for Brian to create a free Alpaca account and put the two keys in `.env`
    (`docs/inbox.md`). If Brian reports that Alpaca refused the sign-up,
    this task instead extends the Futu source to US symbols (`US.AAPL`) and Task 2.8 loads
    them; note that the Futu quota then has to cover about 215 stocks.
  - Run `prices_cli refresh --source alpaca` for daily and hourly bars.
  - Done when: `prices_cli status` shows Alpaca daily and hourly bars for at least 95% of
    the US stocks and funds; the `Result:` line says which feed answered (sip or iex) and
    the first hourly bar's date.

- [ ] **Task 2.8: Futu live load** (waiting: inbox) — needs: Task 2.4, Task 2.5
  - Waits for Brian to open a Futu account and start Futu OpenD on this PC (`docs/inbox.md`).
  - First verify the bar labelling on one liquid stock and one recent full day: print the
    day's hourly `time_key` values and volumes (a Hang Seng Index member, not a holding) and
    fix the mapping if Futu's layout differs from Task 2.4's assumption. Then run
    `prices_cli refresh --source futu` for daily and hourly bars.
  - Done when: `prices_cli status` shows Futu bars for every symbol the quota allowed, with
    hourly bars reaching back at least 7 years for a stock listed that long; the `Result:`
    line gives the quota left and the number of symbols still waiting.

- [ ] **Task 2.9: comparison report and the preferred source** (checkpoint) — needs: Task 2.7, Task 2.8
  - Files: create `stock_advisor/price_compare.py`, `tests/test_price_compare.py`; modify
    `stock_advisor/prices_cli.py` (add `compare`), `stock_advisor/price_store.py`
    (`PREFERRED_SOURCES`).
  - For each market and interval, over the period both sources cover, per symbol: bars in
    one source only; bars where the closes differ by more than 0.5% (raw) and 1% (adjusted);
    `no_trade`, `big_move` and `gap_before` counts per source; big moves one source has and
    the other does not. `prices_cli compare` writes the per-symbol detail to
    `data/reports/price-comparison-<date>.md` and prints the per-market totals.
  - The cleaner source for a market and interval is the one with fewer missing bars plus
    unmatched big moves. Set `PREFERRED_SOURCES` accordingly, Yahoo last as the fallback.
  - Checkpoint: post the per-market totals and the chosen order to `docs/inbox.md` as a
    question with the chosen order as the default. Nothing waits on the answer.
  - Done when: the test file passes (two hand-made sources with known differences); the
    real run's per-market totals are on the `Result:` line.

## Phase 3 – The portfolio analyzer (sonnet)

Method choices below are fixed by this plan. Returns for risk work are weekly (Friday close
to Friday close) because Hong Kong and US sessions do not overlap; daily returns would
understate how much the two move together.

- [ ] **Task 3.1: value, return and concentration** — needs: Task 1.4, Task 2.1
  - Files: create `stock_advisor/analyzer.py`, `tests/test_analyzer.py`.
  - Inputs: the trades of every account that has a `trade_file` (`transactions.
    load_transactions`), daily bars from `price_store.read_bars`, the cash in the accounts
    file, `HKD=X` for USD to HKD.
  - Outputs (one dataclass, `PortfolioSummary`, all money in HKD): value today (holdings
    plus cash); a daily value series of the holdings since the first trade; **return
    without the timing of deposits** = the chained daily return of the holdings, each day's
    return being the value-weighted adjusted-price return of what was held at the previous
    close; **return with the timing** = the yearly rate that sets the trades' cash flows and
    today's value to zero (scipy root finding); deepest fall of the chained index, with its
    start and end dates; yearly swing = standard deviation of daily returns × √252; weights;
    the three largest weights summed; effective number of holdings = 1 / Σ weight².
  - A holding with no price in the store is valued at cost, listed in
    `summary.unpriced`, and left out of the return series.
  - Done when: the test file passes. Write tests first with hand-checked numbers: two
    stocks, three trades, a known price path; a sale to zero; a USD holding converted; an
    unpriced holding.
  - Notes: the trade file records no cash and no dividends. So the returns cover the
    invested holdings only, and dividends count as reinvested. Say this in the docstring;
    the CLI and the dashboard repeat it in one line.

- [ ] **Task 3.2: groups, risk shares and exposures** `[parallel-ok]` — needs: Task 2.1
  - Files: create `stock_advisor/risk.py`, `tests/test_risk.py`.
  - `weekly_returns(symbols, years=3)` from adjusted daily bars; a symbol with under 52
    weeks is reported as too short and left out.
  - `groups(returns)`: average-linkage clustering (scipy) on distance 1 − correlation, cut
    at 0.5; returns lists of symbols.
  - `risk_shares(returns, weights)`: covariance by `sklearn.covariance.LedoitWolf`; share
    of holding i = weight_i × (Σ·weight)_i / (weightᵀ·Σ·weight). Shares sum to 1.
  - `exposures(returns, symbol)`: the market is `^HSI` for `.HK` symbols, `^GSPC`
    otherwise. Market beta = regression of the holding on its market. For each of the six
    drivers (oil `CL=F`, US rates `^TNX` as the weekly change in yield, China/HK tech
    `KWEB`, US tech `^NDX`, cyber security `HACK`, USD/CNY `CNY=X`), regress the holding on
    the market and the driver together (statsmodels OLS with HAC errors, 4 lags) and report
    the driver's coefficient and t-value. Mark a coefficient "clear" when |t| ≥ 2.
  - Done when: the test file passes on synthetic series with planted structure: two
    perfectly co-moving stocks land in one group; risk shares sum to 1 and a stock with
    twice the swing gets the larger share; a planted driver beta of 0.5 is recovered within
    0.1; a driver with no link gives |t| < 2 in a seeded test.

- [ ] **Task 3.3: the analyzer CLI** — needs: Task 1.5, Task 3.1, Task 3.2
  - Files: create `stock_advisor/analyze_cli.py`, `tests/test_analyze_cli.py`; add
    `build_portfolio_report()` to `stock_advisor/analyzer.py` (the one function the CLI and
    the dashboard both call).
  - `python -m stock_advisor.analyze_cli` prints the portfolio block, the per-holding table
    (weight, risk share, group, market beta, clear driver exposures) and the caveat line.
    `--save` also writes it to `data/reports/portfolio-<date>.md`.
    `python -m stock_advisor.analyze_cli cost --symbol 0005.HK --amount 20000` prints the
    cost of buying and of a round trip at each broker in `BROKERS`. The amount is the
    trade's value as given (no rounding to board lots here; milestone 4 adds that).
  - Done when: the test file passes (store and accounts faked); the `cost` command run for
    real prints 1.22% (Hang Seng Bank) and 0.37% (Futu) for the example above.

- [ ] **Task 3.4: the dashboard Portfolio tab** — needs: Task 3.3
  - Files: modify `app.py`; create or extend `tests/test_app_portfolio.py`.
  - Add a third tab "Portfolio" (tabs become Report, Portfolio, News) that renders
    `build_portfolio_report()`: headline numbers as metrics, the value and deepest-fall
    chart, the per-holding table, the groups, the caveat line, and a small "cost of a trade"
    form (symbol, amount) showing each broker. Cash of 0 in every account shows the
    note "Cash is not set: edit data/accounts.json". Cache the report for an hour
    (`st.cache_data`), cleared by the existing "Run report" button. A failure inside the
    tab shows `st.error` and must not hide the other tabs (render it the way the News tab is
    rendered before the report).
  - Done when: the Streamlit `AppTest` test passes with a faked report (tab renders, the
    cash note appears, an exception shows an error and the News tab still renders).

- [ ] **Task 3.5: the analyzer on the real portfolio** (checkpoint) — needs: Task 2.5, Task 3.4
  - Files: none (a live run).
  - Run `analyze_cli --save` on the real data. Check and print pass or fail only: weights
    sum to 1 (±0.001); risk shares sum to 1; no NaN in the headline numbers; every holding
    is priced, too short, or listed as unpriced; the run takes under 60 seconds.
  - Checkpoint: post one inbox question asking Brian to read the saved report (give its
    path) and say whether any number looks wrong. Nothing waits on the answer.
  - Done when: all checks pass; the `Result:` line gives the counts (holdings priced, too
    short, unpriced) and the run time.

## Phase 4 – Carry-overs and finish (sonnet; the review on opus)

- [ ] **Task 4.1: check the four scheduled tasks** — needs: Task 2.6
  - Files: none.
  - Done when: `Get-ScheduledTask -TaskName stock_advisor_*` shows the watcher, dashboard
    and backfill Running or Ready and the recorder Ready; after a 22:00 run,
    `Get-ScheduledTaskInfo stock_advisor_minute_recorder` shows `LastTaskResult` 0 and the
    recorder log has that night's line per source. Quote the states on the `Result:` line.
    If the 22:00 run has not happened yet, leave the task open and take another.

- [ ] **Task 4.2: the dashboard in a real browser** — needs: Task 3.5
  - Files: none.
  - Restart the dashboard so it loads the new code: find the process listening on port 8502
    (`Get-NetTCPConnection -LocalPort 8502`), stop that process id, and let
    `scripts/run_dashboard.ps1` restart it (or start the task again; a second start may be
    needed, see `docs/open-items.md`).
  - Done when: http://localhost:8502 answers 200 and the Portfolio and News tabs are seen
    rendering in a real browser. A worker without a browser tool does the restart and the
    200 check, then posts an inbox question asking Brian to open the page and look at both
    tabs, and marks this task as waiting on the inbox until he answers.

- [ ] **Task 4.3: review and fixes** (opus) — needs: Task 2.9, Task 3.5, Task 4.1
  - Run the `routine-reviewer` agent over this plan's commits (from the commit that added
    this file to `HEAD`) and the main paths they touch. Fix plain bugs inside this plan's
    scope, verifying each; record judgment calls in `docs/open-items.md`.
  - Done when: the review's findings are each fixed or recorded; tests and lint pass.

- [ ] **Task 4.4: docs and wrap-up** — needs: Task 4.2, Task 4.3
  - Files: modify `README.md`, `docs/architecture.md`, `docs/known-issues.md`,
    `docs/open-items.md`, `docs/board.md`, `CLAUDE.md` (run commands).
  - Move every `Result:` finding worth keeping into the right doc: the store layout and
    the three sources in architecture; the new commands in README and CLAUDE.md; limits
    found (Futu quota, Alpaca feed, Yahoo hourly depth, typhoon days, returns without cash
    or dividends) in known-issues. Remove open items this plan settled.
  - Done when: each acceptance criterion in the table above is checked against the repo and
    marked there; `git status` shows nothing of this plan uncommitted; the worker ends
    with the milestone-reached card for Brian (`docs/inbox.md`), proposing milestone 2.
