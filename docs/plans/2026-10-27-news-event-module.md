# Plan: news event module (2026-10-27)

## Goal
A separate news module that spots market-moving events as they break (new government
policies, wars, security vulnerabilities, crashes), finds similar past events, measures how
markets reacted to them, and turns that into a predicted move and a suggested action today.
The aim is to react before ordinary investors do, not to compete with professional algorithms.

## Approach
1. Collect headlines from as many free sources as possible: long-history archives for the
   backtest, fast feeds for live monitoring. Store them in one local SQLite file.
2. Score every headline with FinBERT (tone) and a small local sentence-embedding model
   (meaning). Classify into event categories, group headlines about the same story into one
   event, and fetch the full article only for high-impact events.
3. Measure each past event's market reaction (1 minute, 1 hour, 1 day where price data exists)
   for the Hang Seng, the S&P 500, sector proxies and the user's holdings.
4. Predict today's reaction from similar past events (nearest neighbours by meaning) plus a
   regression on event features. Validate walk-forward (train on earlier years, test on later).
5. Show today's events, similar past events, predicted moves and a suggested action in the CLI
   and the Streamlit dashboard. A live watcher polls the fastest sources every minute.
6. A nightly recorder saves 1-minute prices so minute-level history grows from now on.

## Constraints (verbatim from docs/decisions.md)
- 2026-10-27 (Brian): add a news monitoring module. Its purpose is to not lag behind ordinary
  market participants when news breaks.
- 2026-10-27 (Brian): backtest news against past data, and quantify its predictive value with
  a model such as regression.
- 2026-10-27 (Brian): prediction horizons are short: minute, hour and 1-day returns.
- 2026-10-27 (Brian): backtest as far back as the available stock data allows.
- 2026-10-27 (Brian): the news module is separate from the price-vs-own-history modules. It
  deals with market-moving events (new government policies, wars, security vulnerabilities,
  crashes). It finds similar past events, measures how markets reacted, and extrapolates to
  today's decisions to maximize profit or minimize loss. History goes as far back as the event
  and price data allow.
- 2026-10-27 (Brian): the aim is to beat ordinary investors, not professional trading
  algorithms.
- 2026-10-27 (Brian): score headlines with FinBERT.
- 2026-10-27 (Brian, accepted default): a news prediction only shows a warning beside the
  signal until the backtest proves it on held-out data for that horizon; then it may change
  the signal for that horizon.
- 2026-10-27 (Brian): include as many free news sources as possible.
- 2026-10-27 (Brian, accepted default): use only official feeds, APIs and filings; skip sites
  whose terms forbid scraping, and skip paywalled articles.
- 2026-10-27 (Brian): SEC EDGAR requests use Brian's personal email as the contact. It lives in
  the gitignored `.env`, never in committed files.
- 2026-10-27 (Brian): score headlines only; fetch and read the full article only when a
  headline is high impact.
- 2026-10-27 (Brian): news output appears in both the CLI report and the Streamlit dashboard.
- 2026-10-27 (Brian, accepted default): add a nightly minute-price recorder (Windows scheduled
  task); include the Guardian and NYT archive APIs (free keys in `.env`); predict the Hang
  Seng, the S&P 500, main sectors and each holding.

## Acceptance criteria
- A1. One conda env `stock_advisor` runs the full test suite and `ruff check`.
- A2. Every source adapter returns normalized headlines, is tested against a saved sample
  response (no network in tests), and has been run once live (or its blocker is recorded).
- A3. Intraday prices (1m, 60m) are fetched and cached; the minute recorder runs as a
  scheduled task and appends a day of bars.
- A4. Headlines get FinBERT tone, an embedding, an event category and an event cluster;
  high-impact events get their article body fetched (non-paywalled only).
- A5. A backfill has filled the store with history from each long-history source, as far back
  as each allows, and the reaction table covers every event with available prices.
- A6. `python -m stock_advisor.news_backtest_cli` prints, per target and horizon, out-of-sample
  hit rate, t-stat, sample size and a `proven` flag, from a walk-forward test.
- A7. `python -m stock_advisor.news_cli` shows current events, similar past events, predicted
  moves and suggested actions; `--watch` keeps polling. The CLI report gains a news column;
  the dashboard gains a News tab. Unproven predictions show as warnings only.
- A8. README, `docs/architecture.md` and `docs/known-issues.md` describe the module, sources,
  limits and commands.
- A9. (added 2026-10-27) Each suggested action carries an estimated profitable window (e.g.
  "exit within 1–3 days"), derived from the price paths of similar past events.
- A10. (added 2026-10-27) Qualifying alerts reach Brian's phone via a Telegram bot; the
  watcher starts at Windows login.

## Shared resources (never use in parallel)
- Conda env `stock_advisor`: one install at a time. Only Phase 0 installs packages; a later
  task needing a package reports it instead of installing.
- `data/cache/news/news.db` (the real store): tests always use `tmp_path`. Only the backfill
  and live runs write to it, one at a time.
- `data/cache/prices/` (price cache): tests use `tmp_path` / monkeypatched `CACHE_DIR`.
- Streamlit port 8502 (changed 2026-10-28, plan review: hk-estate holds 8501): the
  `stock_advisor_dashboard` task owns it; Phase 6 checks open it, never start a second server.
- `requirements.txt`, `environment.yml`, `stock_advisor/config.py`, `README.md`: one task per
  phase at most; named in that task.

## Phase 0 – Environment (sonnet)

- [x] **Task 0.1: project conda env**
  - Files: create `environment.yml` (python 3.12, pinned versions); modify `requirements.txt`
    (minimum ranges); create `.env.example` (keys with empty values: `SEC_CONTACT_EMAIL`,
    `GUARDIAN_API_KEY`, `NYT_API_KEY`); add `ruff` config to a new `ruff.toml`.
  - Done when: `conda run -n stock_advisor python -m pytest -q` passes the existing tests and
    `conda run -n stock_advisor ruff check .` exits 0 (fix or configure existing lint hits).
  - Notes: packages to add: `torch` (CPU build), `transformers`, `sentence-transformers`,
    `feedparser`, `requests`, `beautifulsoup4`, `lxml`, `trafilatura`, `statsmodels`,
    `scikit-learn`, `python-dotenv`, `ruff`. Update CLAUDE.md Environment lines to the env.

## Phase 1 – News sources (sonnet)

- [x] **Task 1.1: news models, store and settings**
  - Files: create `stock_advisor/news/__init__.py`, `stock_advisor/news/models.py`,
    `stock_advisor/news/store.py`, `stock_advisor/news/settings.py`,
    `stock_advisor/news/sources/__init__.py`; test `tests/news/test_store.py`.
  - Done when: `pytest tests/news/test_store.py` passes: insert, de-duplicate by id, query by
    time range and source, update scores.
  - Notes: `NewsItem` dataclass: `id` (sha1 of source+url, or source+title+published_at when
    no url), `source`, `published_at` (tz-aware UTC), `title`, `url`, `summary`, `symbols`
    (list), `language`, `body` (optional). Store: SQLite at `data/cache/news/news.db`, path
    overridable. Tables `items`, `scores` (item_id, tone_pos, tone_neg, tone_neu, tone,
    category, embedding BLOB, event_id, high_impact), `events`. `settings.py` loads `.env` via
    python-dotenv. Each adapter exposes `fetch_recent() -> list[NewsItem]` and, if it has
    history, `fetch_range(start, end) -> Iterator[NewsItem]`. Adapters set a descriptive
    User-Agent and sleep between requests to respect published rate limits.

Tasks 1.2–1.10 are `[parallel-ok]` (each touches only its own adapter, test and fixture). Each:
probe the live endpoint first (read robots.txt and terms; quote them in the report if they
forbid access, then skip that source), save one real response as a fixture under
`tests/fixtures/news/<source>/`, test parsing from the fixture, then run it live once and
report the item count and the earliest date reachable.

- [x] **Task 1.2: Wikipedia Current events** `[parallel-ok]` — `sources/wikipedia_events.py`.
  History via the MediaWiki API, one page per day ("Portal:Current events/<YYYY Month D>"),
  each bullet becomes an item. Report the earliest year with daily pages.
- [x] **Task 1.3: GDELT** `[parallel-ok]` — `sources/gdelt.py`. DOC 2.0 API (artlist,
  English, market/policy/war/cyber queries) for recent items; report the history the API
  actually allows.
- [x] **Task 1.4: Guardian Open Platform** `[parallel-ok]` — `sources/guardian.py`. Sections
  business, world, technology, politics, us-news; date-range paging; key from `GUARDIAN_API_KEY`.
  Missing key: adapter logs one warning and returns nothing; live run waits for the key.
- [x] **Task 1.5: NYT Archive API** `[parallel-ok]` — `sources/nyt.py`. One call per month;
  keep sections Business, World, Technology, U.S., Front Page; key from `NYT_API_KEY`; respect
  12 s between calls. Missing key: as in 1.4.
- [-] **Task 1.6: Google News RSS** `[parallel-ok]` — SKIPPED 2026-10-27: news.google.com
  robots.txt has `User-agent: *` / `Disallow: /` with no Allow for /rss, so the "skip sites
  that forbid access" decision applies. Any later task that lists Google News drops it. — `sources/google_news.py`. Topic and
  search feeds (en-US and en-HK); `fetch_range` uses `after:`/`before:` search operators per
  week; report how many results one query returns and how far back it works.
- [x] **Task 1.7: yfinance news** `[parallel-ok]` — `sources/yahoo.py`. Per-symbol headlines
  for indices, sector proxies and holdings.
- [-] **Task 1.8: HKEXnews** `[parallel-ok]` — SKIPPED 2026-10-27: the HKEX Terms of Use
  (section 5) forbid "programmatic, scripted or other mechanical means" of access and data
  mining. HK company news comes from yfinance and RSS feeds instead. Reopen only with written
  permission from HKEX. — `sources/hkex.py`. Latest listed-company
  announcements (live) and title search by date range (history); map stock codes to Yahoo
  `NNNN.HK` symbols with `market_data.normalize_symbol`.
- [x] **Task 1.9: SEC EDGAR** `[parallel-ok]` — `sources/edgar.py`. Latest 8-K Atom feed
  (live) and full-text/submissions APIs (history); User-Agent `stock_advisor <email>` with the
  email from `SEC_CONTACT_EMAIL`; at most 10 requests per second.
- [x] **Task 1.10: public RSS feeds** `[parallel-ok]` — `sources/rss_feeds.py`. A list of
  feed URLs in the module (Yahoo Finance, Nasdaq, RTHK business, SCMP business, CNBC, BBC
  business, MarketWatch, Investing.com); keep only feeds that load and allow access.
- [x] **Task 1.11: collector CLI**
  - Files: create `stock_advisor/news/collect.py`; test `tests/news/test_collect.py`.
  - Done when: test passes with fake adapters; `python -m stock_advisor.news.collect --recent`
    run live stores items from every working source and prints a count per source.
  - Notes: `--recent` calls every adapter's `fetch_recent`; `--backfill --source X --start
    YYYY-MM-DD` runs `fetch_range` and resumes from the latest stored date for that source.
    One failing source logs and continues. Also (decisions 2026-10-27): add
    `time_precision` ("exact" | "day") to `NewsItem` and the `items` table (default "exact";
    Wikipedia and EDGAR items without an acceptance time set "day"); the live EDGAR feed
    is filtered to the allowlist plus holdings. Daily caps: a per-source daily call budget
    (Guardian 480, NYT 480 — both APIs allow 500/day) counted in the store; on reaching it,
    or on a 429/403 rate-limit response, the backfill for that source stops cleanly and
    resumes from the last stored date on the next run.

- [x] **Task 1.12: NYT Top Stories for live polling** (added 2026-10-27; after 1.11)
  - Files: modify `stock_advisor/news/sources/nyt.py`, `tests/news/test_nyt.py`; fixture
    under `tests/fixtures/news/nyt/`.
  - Done when: tests pass; `fetch_recent` uses the Top Stories API (sections home, business,
    world, technology, us) instead of the current-month archive, run live once with the key;
    the Archive API stays for `fetch_range`. Also run the Task 1.5 live month check and tick
    1.5 if it passes.
  - Notes: same `NYT_API_KEY`; respect NYT's per-minute and per-day limits.

## Phase 2 – Intraday prices and minute recorder (sonnet)

- [x] **Task 2.1: intraday price fetch with cache** `[parallel-ok]`
  - Files: modify `stock_advisor/market_data.py`; test `tests/test_market_data.py`.
  - Done when: new tests pass: `fetch_intraday(symbol, interval)` for `1m` and `60m` reads
    and merges a parquet cache at `data/cache/prices_intraday/<interval>/<symbol>.parquet`.
  - Notes: Yahoo limits: 1m about the last 30 days (7 days per request), 60m about 730 days.
    Fetch in allowed chunks; timestamps stored tz-aware UTC.
- [x] **Task 2.2: target list** `[parallel-ok]`
  - Files: modify `stock_advisor/config.py`; test `tests/test_config.py` (create).
  - Done when: test passes; each symbol was confirmed live to return daily data from Yahoo.
  - Notes: `NEWS_TARGETS`: `^HSI`, `^GSPC`, US sector ETFs (XLK, XLF, XLE, XLV, XLI, XLY,
    XLP, XLU, XLB, XLRE, XLC), HK proxies (2800.HK, 3033.HK, 2828.HK), plus holdings at run
    time. Drop any that fail the live check and report them.
- [x] **Task 2.3: minute recorder and scheduled task** (after 2.1, 2.2)
  - Files: create `scripts/record_minutes.py`, `scripts/register_recorder_task.ps1`.
  - Done when: `python scripts/record_minutes.py` run live appends today's 1m bars for every
    target and prints rows added; re-running adds 0 duplicates.
  - Notes: the `.ps1` registers a Windows scheduled task `stock_advisor_minute_recorder`
    running daily at 22:00 local with the env's python. The coordinator runs it in Phase 6.

## Phase 3 – Scoring, categories and events (sonnet, 3.3 fable)

- [x] **Task 3.1: FinBERT tone and embeddings**
  - Files: create `stock_advisor/news/scoring.py`; test `tests/news/test_scoring.py`.
  - Done when: unit tests pass with a fake model; a live check scores 5 real headlines and the
    tones look right ("Stocks crash as..." negative).
  - Notes: FinBERT `ProsusAI/finbert` (tone = p_pos − p_neg); embeddings
    `sentence-transformers/all-MiniLM-L6-v2`. Batch size 64, CPU. Models load lazily once;
    tests never download models. `score_pending(store)` scores unscored items in batches.
- [x] **Task 3.2: event categories**
  - Files: create `stock_advisor/news/categories.py`; test `tests/news/test_categories.py`.
  - Done when: tests pass on 30 hand-written headlines (at least 2 per category) with ≥ 80%
    correct.
  - Notes: categories: trade_tariffs, monetary_policy, fiscal_regulation, war_conflict,
    terrorism, pandemic_health, cyber_security, natural_disaster, financial_crisis,
    election_politics, energy_commodities, company_results, company_corporate_action, other.
    Method: nearest seed-phrase centroid by embedding, keyword overrides where the centroid
    is weak.
- [x] **Task 3.3: event clustering and high-impact rule** (fable) — final values: cosine 0.60
  to the event centroid, 12 h window, 48 h max span (979 real headlines → 769 events).
  - Files: create `stock_advisor/news/events.py`, `stock_advisor/news/article.py`; tests
    `tests/news/test_events.py`, `tests/news/test_article.py`.
  - Done when: tests pass: headlines about one story within a time window merge into one
    event; unrelated ones don't; high-impact events get a body via `article.fetch_body`
    (paywalled domains skipped by a domain list) and are re-scored on title + first 2,000
    characters.
  - Notes: event = cluster by cosine similarity and time window (start: 0.75 and 6 hours;
    tune on real data and record final values). High impact when the category is macro
    (everything except company_* and other) and (|tone| ≥ 0.6 or ≥ 3 distinct sources in the
    cluster), or a later backtest shows the category moves markets. Event time = earliest
    headline time.

## Phase 4 – Backfill, reactions and model (fable for 4.3, 4.4)

- [x] **Task 4.1: backfill job** (sonnet)
  - Files: create `scripts/backfill_news.py`.
  - Done when: started in the background, writing progress to
    `data/cache/news/backfill_status.json`; the check command
    `python scripts/backfill_news.py --status` prints per-source date reached and item count.
  - Notes: runs sources one after another (Wikipedia, EDGAR, GDELT, then
    Guardian and NYT once keys exist), then scoring and clustering. Resumable. Expected to
    take hours; the helper hands back once it is running. Depth: as far back as each source
    goes (Guardian from 1990-02, ~3,450 calls ≈ 7 days at the daily cap; NYT from 1990,
    ~440 calls ≈ 1 day). Add `scripts/register_backfill_task.ps1`: a daily Windows task that
    reruns the backfill until every source reports complete; the coordinator registers it.
    EDGAR's cursor advances only per completed quarter (its index is not in date order).
- [x] **Task 4.2: reaction table** (sonnet)
  - Files: create `stock_advisor/news/reactions.py`; test `tests/news/test_reactions.py`.
  - Done when: tests pass on synthetic prices: for an event at time t, the cumulative return
    path from the last price at or before t to t+1m, 5m, 15m, 1h, 4h and the 1st, 2nd, 3rd,
    5th and 10th close after t; events outside trading hours use the next session's open as
    the start; missing data gives NaN, not 0; `time_precision="day"` items get only the
    daily horizons.
  - Notes: uses 1m bars where cached, 60m bars within ~730 days, daily otherwise. Stocks also
    get a market-adjusted return (minus the matching index return: ^HSI for .HK, ^GSPC else).
    The 1m, 1h and 1-day points are the headline horizons; the full path feeds Task 4.5.
- [x] **Task 4.3: analog and regression model** (fable)
  - Files: create `stock_advisor/news/model.py`; test `tests/news/test_model.py`.
  - Done when: tests pass on synthetic events with a planted effect (model finds it) and with
    pure noise (model reports not proven).
  - Notes: features: category one-hot, tone, cluster source count, high_impact, analog
    prediction (similarity-weighted mean reaction of the k=20 most similar earlier events),
    pre-event 20-day volatility of the target. Ridge regression per target and horizon.
    Predictions must use only events before the event being predicted (no look-ahead).
- [x] **Task 4.4: walk-forward backtest CLI** (fable) — live run on the real store found 0
  scored events (backfill not yet scored); full live run waits for the backfill.
  - Files: create `stock_advisor/news_backtest_cli.py`; test `tests/news/test_backtest.py`.
  - Done when: test passes; run live on the backfilled store, it prints per target and
    horizon: n, out-of-sample hit rate, mean return when following the predicted sign, Welch
    t-stat, `proven`; results saved to `data/cache/news/model/results.json`.
  - Notes: expanding window by year. `proven` = n ≥ 30 out-of-sample events, |t| ≥ 2 and hit
    rate > 0.5, matching the bar in `validation.py`.
- [x] **Task 4.5: profitable-window estimate** (fable; after 4.2, 4.3) — live window output
  waits for the backfill (synthetic CLI run checked)
  - Files: create `stock_advisor/news/window.py`; test `tests/news/test_window.py`; add a
    window section to `news_backtest_cli.py` output.
  - Done when: tests pass on synthetic paths (a planted peak at day 2 gives a window ending
    near day 2; a path that never reverses gives "no reversal within 10 days"); the live
    backtest prints, per target, how often following the window beat holding to day 10.
  - Notes: from the k most similar earlier events' cumulative paths (signed by the predicted
    direction), estimate the peak time (median and interquartile range across analogs) and
    express the window as "exit within <p25>–<p75>". No look-ahead. Output feeds 5.1 and 5.4.

## Phase 5 – Live monitor and output (sonnet)

- [x] **Task 5.1: news CLI and watcher**
  - Files: create `stock_advisor/news_cli.py`; test `tests/news/test_news_cli.py`.
  - Done when: test passes with fake store/model; live run prints current events (last 24 h by
    default), top 5 similar past events each, predicted move per target and horizon with a
    range, a suggested action and its profitable window (Task 4.5); `--watch` polls EDGAR,
    RSS and yfinance every 60 s (CISA feed at most every 15 min), Guardian, NYT and GDELT
    every 15 min (GDELT locks out for a minute or more after bursts; never run two GDELT
    callers at once), and prints only new high-impact events.
  - Notes: action rule: predicted 1-day move ≤ −1.5% → "reduce", ≥ +1.5% → "add", else
    "hold". Shown as a warning ("⚠ unproven") unless `proven` for that target and horizon.
    Thresholds live in `config.py` as `NEWS_ACTION_THRESHOLD_PCT`. Guardian items display
    as headline + link only, never the summary (applies to 5.1–5.4).
- [x] **Task 5.2: CLI report news column**
  - Files: modify `stock_advisor/report.py`, `stock_advisor/cli.py`; test
    `tests/test_report.py`.
  - Done when: tests pass; live `python -m stock_advisor.cli` shows a `news` column per
    holding (e.g. "⚠ war_conflict: −2.1% 1d (unproven)") and is unchanged when no events.
  - Notes: proven predictions may change the action per the decision; unproven never do.
- [x] **Task 5.3: dashboard News tab**
  - Files: modify `app.py`.
  - Done when: `streamlit run app.py` in the background on 8501 loads; the News tab shows
    events, similar past events, predicted moves and backtest results; checked in a real
    browser; server stopped by port afterwards.
- [x] **Task 5.4: Telegram alerts** (built in 2bffd2b; split 2026-10-28, plan review: the
  phone test is Task 5.4b, so this task can be ticked without the token)
  - Files: create `stock_advisor/news/notify.py`; test `tests/news/test_notify.py`; hook
    into `news_cli.py --watch`; add `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` to `.env.example`.
  - Done when: tests pass with a mocked Telegram API (the coordinator reruns
    `tests/news/test_notify.py`); `python -m stock_advisor.news.notify --setup` finds the chat
    id from the bot's latest update and saves it to `.env`; `--test` sends one message; with
    no token both commands say so and exit without a request.
- [ ] **Task 5.4b: Telegram live test** (added 2026-10-28, plan review; waiting on Brian)
  - Blocked until `.env` has a non-empty `TELEGRAM_BOT_TOKEN` (absent on 2026-10-28). Does not
    block 6.2 or 6.3; if still blocked at 6.3, the wrap-up leaves it in open-items.
  - Done when: `--setup` saves `TELEGRAM_CHAT_ID` to `.env`; `--test` delivers one message that
    Brian confirms on his phone; the running watcher picks up the token (restart the
    `stock_advisor_news_watcher` task) and the sent-alert table records the first real alert.
  - Progress 2026-10-28: bot @brian_stock_advisor_bot; `--setup` saved the chat id (private
    chat); `--test` delivered and Brian confirmed it on his phone; the watcher restarted at
    23:07 HKT without the "alerts are off" warning. Open: the first real alert, which needs
    predictions (after the backfill and 6.2f).
  - Notes: Telegram Bot API `sendMessage` only (plus `getUpdates` once at setup). Alert rule
    (decision): high-impact event affecting a holding, ^HSI or ^GSPC with a predicted move
    ≥ 1.5%; 24/7. Message: event headline + link, category, target, predicted move per
    horizon, action, window, "⚠ unproven" when applicable. Never alert the same event twice
    (record sent event ids in the store). The token never appears in logs.
- [x] **Task 5.5: watcher autostart**
  - Files: create `scripts/register_watcher_task.ps1`.
  - Done when: the script registers a Windows scheduled task `stock_advisor_news_watcher`
    that runs `news_cli --watch` at user login and restarts on failure. The coordinator runs
    it in Phase 6.

## Phase 6 – Docs, scheduled task, end-to-end check

- [x] **Task 6.1: docs** `[parallel-ok]` (sonnet)
  - Files: modify `README.md`; create `docs/architecture.md`, `docs/known-issues.md`.
  - Done when: each command in the README runs as written.
Tasks 6.2a–6.2e (added 2026-10-28, plan review) fix the blockers the Phase 5 live run found,
before the end-to-end check. 6.2a and 6.2b are `[parallel-ok]` (disjoint files). 6.2c–6.2e
write to or diagnose the real store: one at a time, never while
`data/cache/news/backfill.lock` exists, and with a copy of `news.db` taken first.

- [x] **Task 6.2a: index aliases without `^`** (added 2026-10-28, plan review) `[parallel-ok]`
  (sonnet) — a3be264; HSI/GSPC map to ^HSI/^GSPC and load 1d and 60m prices (checked live)
  - Files: modify `stock_advisor/config.py` (one `normalize_target` helper), `news_cli.py`,
    `news_backtest_cli.py`, `stock_advisor/news/analysis.py` (`NewsAnalyzer` targets),
    `README.md`; test `tests/test_config.py`.
  - Done when: tests pass; a `NEWS_TARGETS` key given without its `^` (`HSI`, `GSPC`) maps
    back to `^HSI`/`^GSPC` wherever targets are read from the command line; live
    `conda run -n stock_advisor python -m stock_advisor.news_cli --targets ^HSI ^GSPC` loads
    prices; the README says `conda run` strips `^` (cmd escape) and gives `^^HSI` or the env's
    python as the way round it.
- [x] **Task 6.2b: news.db in WAL mode** (added 2026-10-28, plan review) `[parallel-ok]`
  (sonnet) — 4e9cf8a; the real file switched at 12:03 HKT while the watcher ran (not stopped
  first); afterwards journal_mode=wal, quick_check ok, counts intact; `--status` works with the
  watcher and backfill running
  - Files: modify `stock_advisor/news/store.py`; test `tests/news/test_store.py`; update the
    "SQLite has one writer" entry in `docs/known-issues.md` and `docs/architecture.md`.
  - Done when: `NewsStore` runs `PRAGMA journal_mode=WAL` on connect (the real file reports
    `delete` on 2026-10-28; the mode persists in the file once set); a test shows a second
    connection reads while the first holds an open write; the first real connect happens with
    the watcher and dashboard tasks stopped (`Stop-ScheduledTask`, then start them again), and
    `--status` plus one `news_cli` run succeed while the watcher runs.
  - Notes: why now: the watcher, dashboard and daily backfill all hold the file at once since
    Brian registered the tasks; `delete` mode blocks every reader during a write.
- [ ] **Task 6.2c: GDELT timestamps, verified on fresh data** (added 2026-10-28, plan review)
  (sonnet)
  - Facts on 2026-10-28 (read-only count): 169 GDELT items, one distinct `published_at`
    (2026-10-27T05:15Z), all stored by the pre-fix code (b8af5fe landed 18:08 HKT);
    `add_items` is `INSERT OR IGNORE`, so a refetch never re-stamps them; no GDELT item has
    been stored since, although the watcher has polled GDELT every 15 min since 00:42 HKT. So
    the fix is untested, not disproven, and live GDELT collection currently adds nothing.
  - Files: `stock_advisor/news/sources/gdelt.py`, `tests/news/test_gdelt.py` (one real
    artlist response saved under `tests/fixtures/news/gdelt/`), maybe
    `stock_advisor/news/collect.py`; a scratchpad script for the one-off purge.
  - Done when: (1) the watcher log explains the 0 items in 11 h (429 on every poll, an
    exception, or `gdelt_busy` stuck true) and that cause is fixed; (2) one real artlist call
    made outside a lockout is saved as a fixture and its `seendate` values are compared with
    what `_to_items` stores; (3) after the fix, a live `fetch_recent` stores items with more
    than one distinct `published_at` (read-only `COUNT(DISTINCT published_at)`); (4) the 169
    old items, their scores and their event memberships are deleted (backup first) so no
    "05:15" events remain; the GDELT backfill cursor is left alone.
  - Progress 2026-10-28 (173e3d8): (1) done: GDELT's DOC API itself had nothing newer than
    2026-10-27T05:15Z (index stalled upstream); fetch_recent now logs the newest seendate.
    (2) done: real 72 h fixture, 250 articles with only 3 distinct seendates. (3) open until
    GDELT publishes newer batches. (4) dropped (Brian, 2026-10-28: no purge): 126 of the 169
    stored items appear in the real response with the same 05:15 stamp, so they are correct.
  - Notes: if GDELT really stamps `seendate` per 15-minute crawl batch, minute reactions for
    GDELT items are not possible: record that in known-issues and ask Brian whether GDELT
    items keep the 1-minute horizon (decision, not a default).
- [x] **Task 6.2d: backfill stop diagnosis and crash logging** (added 2026-10-28, plan
  review) (coordinator diagnoses; sonnet for the code) — cf242e3 (crash state, progress lines,
  faulthandler, `--process-only`); the old log has no trace after 03:25, so the cause stays
  unknown (open-items); backfill task restarted 12:05 HKT, `--status` shows it running
  - Facts on 2026-10-28: the 02:00 task's run (started 02:00:02 HKT) stopped at 07:57 HKT in
    state "scoring" with 543,624 items unscored. The lock file is gone, so `main()`'s
    `finally` ran: an exception escaped `run()` (a finished run writes "stopped" or
    "complete"). The traceback went to the headless console and is lost; the task reports
    result 0. Nothing runs until 02:00 tomorrow.
  - Files: `scripts/backfill_news.py`; test `tests/test_backfill.py`.
  - Done when: `main()` logs an exception from `run()` with `logger.exception` and writes
    state `crashed: <ExceptionType>` to the status file before releasing the lock (test with
    a fake `run` that raises); the coordinator reads the tail of
    `data/cache/news/backfill_log.txt` (summarize the cause, never quote data); the backfill
    is restarted (`Start-ScheduledTask stock_advisor_news_backfill`) and `--status` shows it
    running; the cause is fixed or recorded in open-items.
  - Notes: suspects: "database is locked" from the watcher or dashboard writing while
    scoring (6.2b helps) or memory in FinBERT batches. (OneDrive sync is off, so not OneDrive.)
- [ ] **Task 6.2e: re-categorize items scored before the single-stock fix** (added
  2026-10-28, plan review) (sonnet)
  - Files: create `scripts/recategorize_news.py` (reuses `categories.py`; add a store query
    for all categorized rows beside `items_awaiting_category`); test with a `tmp_path` store.
  - Done when: a dry run prints old→new category counts; the real run (backup first, never
    while the backfill lock exists) updates only changed rows with `store.set_category`, then
    recomputes `high_impact` for the affected events; `--status` item and event counts are
    unchanged.
  - Progress 2026-10-28: script in 8e2ce23; real dry run (28 s): 27 of 383,946 rows change,
    in 22 events. Real run waits for the backfill lock to clear.
  - Notes: the first backfill run (18:55–23:24 HKT on 2026-10-27) categorized with the rules
    before 0fbfdf1 (19:53 HKT); `scores` has no categorized-at column, so recompute every
    categorized row and write only the differences.
- [ ] **Task 6.2: scheduled tasks check and end-to-end run** (coordinator; after 6.2a–6.2e)
  - (plan review 2026-10-28) Brian registered all four tasks. Observed: `minute_recorder`
    Ready (first run 22:00 HKT), `news_backfill` Ready (daily 02:00), `news_watcher` Running
    since 00:42, `dashboard` Running on 8502. Registering is done; this task verifies.
  - Done when: `Get-ScheduledTask -TaskName stock_advisor_*` output quoted in the report
    (recorder Ready, watcher Running); one full live pass (collect → score → news_cli, run
    with the env's python, not `conda run`) completes and its output is quoted;
    `python -m stock_advisor.news_backtest_cli` run on the store as it stands (about 380k
    scored items and 312k events on 2026-10-28) writes `data/cache/news/model/results.json`
    (absent on 2026-10-28) and its summary is quoted; `python -m stock_advisor.cli` shows
    real values in the news column; the dashboard News tab at http://localhost:8502 is
    checked in a real browser (or stays in open-items as waiting on Brian when the session
    has no browser tool); after 22:00 HKT, `Get-ScheduledTaskInfo stock_advisor_minute_recorder`
    shows LastTaskResult 0 and the 1m cache gained today's bars (or this check goes to
    open-items for the next session).
  - Progress 2026-10-29: the backtest on the store as it stood finished at 05:10 HKT (started
    12:25 the day before): results.json covers 321,373 events, 37 targets, 10 horizons; 271
    target/horizon results, 0 proven; 99 pairs skipped (too few reactions); 6 market-moving
    category rows; no window section. The watcher loads results.json only when it starts.
  - Notes: the backfill needs several more daily runs (Guardian cursor 2002, NYT 2010,
    Wikipedia 2010, GDELT stalled; scoring lags fetching). Do not wait for it: 6.2f is the
    rerun.
- [ ] **Task 6.2g: live code loads the backtest's fitted models** (added 2026-10-29; Brian
  approved option A, decisions.md) (sonnet; before the watcher's next refit if possible)
  - Why: since reactions.parquet exists (2026-10-29 03:54), each `NewsAnalyzer.refresh` fits
    and so builds `EventLibrary.candidates()` for all ~467k events; the watcher stops polling
    for that time (see open-items, "Watcher memory").
  - Files: `stock_advisor/news_backtest_cli.py` (save the fitted models beside results.json,
    e.g. `data/cache/news/model/fitted.pkl`, with the library size and generated_at),
    `stock_advisor/news/model.py` (save/load helpers; a `NewsModel` that predicts from loaded
    fits plus the one-row analog search), `stock_advisor/news/analysis.py` (`refresh` loads
    the file and never calls `fit`; no file means no predictions, as today); tests in
    `tests/news/test_model.py`, `tests/news/test_analysis.py`, the backtest CLI test file.
  - Done when: tests pass, including one showing `refresh` never calls `fit` or
    `candidates()`; a save/load round trip gives the same predictions as the in-memory model;
    the real backtest's models are saved without rerunning the whole backtest (add a
    `--fit-only` path that fits on the cached reactions, or note its run time if it is long);
    a real `NewsAnalyzer.refresh` on the store takes about a minute and analyzing 10 recent
    events gives non-n/a predictions where pairs were fitted; the watcher is restarted (Brian
    stops it by process id: `Stop-Process`, the task restarts it in 60 s) and its log shows
    "Model ready" with fitted pairs > 0 and cycles every ~1–2 minutes.
  - Notes: the fitted ridge models are small (coefficients, alpha, vol_fill, residuals);
    pickle is fine for a local cache file. The analog features still use the live library,
    so new events get analogs from up-to-date history.
- [ ] **Task 6.2h: memory guard for the watcher and dashboard** (added 2026-10-29; Brian:
  "fix the memory leak issue so it doesn't happen again") (sonnet)
  - Why: on 2026-10-29 the old-code watcher reached 21.4 GB and the dashboard 17.9 GB (both
    fitting on refresh, fixed by 6.2g); RAM fell to 0.9 GB free. Nothing stops a future bug
    from doing the same. Both wrapper scripts (`run_watcher.ps1`, `run_dashboard.ps1`) already
    restart their process after any exit, so a process that exits itself above a limit is
    restarted cleanly.
  - Files: new `stock_advisor/memory_guard.py` (own private bytes via ctypes
    `GetProcessMemoryInfo` on Windows, no new dependency; a daemon thread checking every 15 s;
    a warning in the log at 75% of the limit; above the limit an error line with the size,
    then `os._exit` with a fixed non-zero code; started at most once per process; limit from
    an env var, defaults 8 GB watcher, 10 GB dashboard), `stock_advisor/news_cli.py` (start it
    in `--watch` mode), `app.py` (start it once per process: Streamlit reruns the script),
    `tests/test_memory_guard.py`; docs: known-issues (the limits, and that they must rise if
    the store roughly doubles), architecture, README.
  - Done when: tests pass (the guard exits above the limit, warns at 75%, starts once, with a
    fake memory reader and fake exit); a real run of the guard with a tiny limit in a scratch
    script exits with the code and logs the line; the watcher and dashboard are restarted on
    the new code (Brian stops them by process id) and their logs show the guard started.
  - Notes: the new-code dashboard still reached 18 GB after 6.2g. The cause was
    `read_reactions` loading all 119M rows of reactions.parquet (almost all without a
    return). It now streams the file and keeps only known rows of the live targets: a real
    refresh peaks at 3.3 GB (was 10–14 GB). `refresh` also drops the old model first.
- [ ] **Task 6.2i: data fixes before any real backtest** (added 2026-10-30; Brian approved
  questions 1, 3 and 4 of the reaction-table review) (sonnet, then a long job)
  - Why: valid reactions covered only 22–27 Oct 2026 (3–4 trading days). News covers
    1990–2002 and 2026; cached daily prices started in 2006 because `period="max"` is cut to
    20 years in market_data.py; empty reaction rows are never rebuilt. The README's backtest
    tables (485f4d4) measured those few days, not news effects.
  - Files: `stock_advisor/market_data.py` ("max" = all of yfinance's history, and an older
    cut cache is refetched once), `stock_advisor/news/model.py` and
    `stock_advisor/news_backtest_cli.py` (MIN_PROVEN_DAYS = 250 distinct trading days of
    out-of-sample events for "proven", and the same for market-moving categories; the day
    count printed and saved in results.json), README.md (the backtest tables replaced by "no
    valid backtest yet" and why); tests.
  - Code part done in a2065f1 (^GSPC now from 1927, ^HSI from 1986, checked live).
  - Before the rebuild (added 2026-10-30): the rebuild would hold ~117M rows as Python
    objects (estimated 25+ GB). reactions.parquet keeps only rows with a return; a small
    `reactions_tried.parquet` records the (event, target) pairs already built; the build runs
    one target at a time and appends to the files; the backtest reads the table compactly.
  - Then: `news_backtest_cli --rebuild-reactions` run alone in the background, with the
    memory guard; its run time and day counts recorded.
  - Done when: tests pass; a real `fetch_price_history(["^GSPC"], period="max")` starts in
    1927 or the first year yfinance has; the rebuilt table has 1-day reactions for 1990–2002
    events; the backtest summary shows the day counts.
- [ ] **Task 6.2f: rerun the backtest after the backfill completes** (added 2026-10-28, plan
  review; waiting on time, probably a later session)
  - Done when: `--status` shows every source complete (or capped with the limit recorded) and
    0 to score, categorize and cluster; `news_backtest_cli --rebuild-reactions` rerun (the
    cache predates the GDELT "batch" precision of 16bfaa6) and `results.json`
    replaced; the `proven` flags, the market-moving categories and the window section are
    quoted; the category thresholds and high-impact rule open items are revisited with them.
- [ ] **Task 6.3: pre-release review, fixes, wrap-up, ship** (coordinator; after 6.2.
  5.4b and 6.2f may stay open: the wrap-up lists them in open-items, they do not block the
  ship)

## Self-review
- A1→0.1; A2→1.1–1.11; A3→2.1–2.3, 6.2; A4→3.1–3.3; A5→4.1, 4.2; A6→4.3, 4.4;
  A7→5.1–5.3; A8→6.1; A9→4.2, 4.5, 5.1; A10→5.4, 5.4b, 5.5, 6.2. (2026-10-28, plan
  review) Phase 5 live-run blockers→6.2a–6.2e; A5/A6 on the full history→6.2f.
- Parallel groups touch disjoint files; `config.py` only in 2.2 (Phase 2) and read-only
  afterwards except 5.1 adding one constant (Phase 5, serial with 5.2/5.3? 5.1–5.3 run in
  sequence because 5.2 and 5.3 use 5.1's functions).
- Long job: the backfill (4.1) runs in the background while 4.2–4.4 are built.
