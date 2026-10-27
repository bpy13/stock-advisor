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
- Streamlit port 8501: Phase 5 only.
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
- [ ] **Task 3.3: event clustering and high-impact rule** (fable)
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

- [ ] **Task 4.1: backfill job** (sonnet)
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
- [ ] **Task 4.2: reaction table** (sonnet)
  - Files: create `stock_advisor/news/reactions.py`; test `tests/news/test_reactions.py`.
  - Done when: tests pass on synthetic prices: for an event at time t, the cumulative return
    path from the last price at or before t to t+1m, 5m, 15m, 1h, 4h and the 1st, 2nd, 3rd,
    5th and 10th close after t; events outside trading hours use the next session's open as
    the start; missing data gives NaN, not 0; `time_precision="day"` items get only the
    daily horizons.
  - Notes: uses 1m bars where cached, 60m bars within ~730 days, daily otherwise. Stocks also
    get a market-adjusted return (minus the matching index return: ^HSI for .HK, ^GSPC else).
    The 1m, 1h and 1-day points are the headline horizons; the full path feeds Task 4.5.
- [ ] **Task 4.3: analog and regression model** (fable)
  - Files: create `stock_advisor/news/model.py`; test `tests/news/test_model.py`.
  - Done when: tests pass on synthetic events with a planted effect (model finds it) and with
    pure noise (model reports not proven).
  - Notes: features: category one-hot, tone, cluster source count, high_impact, analog
    prediction (similarity-weighted mean reaction of the k=20 most similar earlier events),
    pre-event 20-day volatility of the target. Ridge regression per target and horizon.
    Predictions must use only events before the event being predicted (no look-ahead).
- [ ] **Task 4.4: walk-forward backtest CLI** (fable)
  - Files: create `stock_advisor/news_backtest_cli.py`; test `tests/news/test_backtest.py`.
  - Done when: test passes; run live on the backfilled store, it prints per target and
    horizon: n, out-of-sample hit rate, mean return when following the predicted sign, Welch
    t-stat, `proven`; results saved to `data/cache/news/model/results.json`.
  - Notes: expanding window by year. `proven` = n ≥ 30 out-of-sample events, |t| ≥ 2 and hit
    rate > 0.5, matching the bar in `validation.py`.
- [ ] **Task 4.5: profitable-window estimate** (fable; after 4.2, 4.3)
  - Files: create `stock_advisor/news/window.py`; test `tests/news/test_window.py`; add a
    window section to `news_backtest_cli.py` output.
  - Done when: tests pass on synthetic paths (a planted peak at day 2 gives a window ending
    near day 2; a path that never reverses gives "no reversal within 10 days"); the live
    backtest prints, per target, how often following the window beat holding to day 10.
  - Notes: from the k most similar earlier events' cumulative paths (signed by the predicted
    direction), estimate the peak time (median and interquartile range across analogs) and
    express the window as "exit within <p25>–<p75>". No look-ahead. Output feeds 5.1 and 5.4.

## Phase 5 – Live monitor and output (sonnet)

- [ ] **Task 5.1: news CLI and watcher**
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
- [ ] **Task 5.2: CLI report news column**
  - Files: modify `stock_advisor/report.py`, `stock_advisor/cli.py`; test
    `tests/test_report.py`.
  - Done when: tests pass; live `python -m stock_advisor.cli` shows a `news` column per
    holding (e.g. "⚠ war_conflict: −2.1% 1d (unproven)") and is unchanged when no events.
  - Notes: proven predictions may change the action per the decision; unproven never do.
- [ ] **Task 5.3: dashboard News tab**
  - Files: modify `app.py`.
  - Done when: `streamlit run app.py` in the background on 8501 loads; the News tab shows
    events, similar past events, predicted moves and backtest results; checked in a real
    browser; server stopped by port afterwards.
- [ ] **Task 5.4: Telegram alerts**
  - Files: create `stock_advisor/news/notify.py`; test `tests/news/test_notify.py`; hook
    into `news_cli.py --watch`; add `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` to `.env.example`.
  - Done when: tests pass with a mocked Telegram API; `python -m stock_advisor.news.notify
    --setup` finds the chat id from the bot's latest update and saves it to `.env`;
    `--test` delivers one message that Brian confirms on his phone.
  - Notes: Telegram Bot API `sendMessage` only (plus `getUpdates` once at setup). Alert rule
    (decision): high-impact event affecting a holding, ^HSI or ^GSPC with a predicted move
    ≥ 1.5%; 24/7. Message: event headline + link, category, target, predicted move per
    horizon, action, window, "⚠ unproven" when applicable. Never alert the same event twice
    (record sent event ids in the store). The token never appears in logs.
- [ ] **Task 5.5: watcher autostart**
  - Files: create `scripts/register_watcher_task.ps1`.
  - Done when: the script registers a Windows scheduled task `stock_advisor_news_watcher`
    that runs `news_cli --watch` at user login and restarts on failure. The coordinator runs
    it in Phase 6.

## Phase 6 – Docs, scheduled task, end-to-end check

- [ ] **Task 6.1: docs** `[parallel-ok]` (sonnet)
  - Files: modify `README.md`; create `docs/architecture.md`, `docs/known-issues.md`.
  - Done when: each command in the README runs as written.
- [ ] **Task 6.2: register recorder and end-to-end run** (coordinator)
  - Done when: `Get-ScheduledTask stock_advisor_minute_recorder` and
    `Get-ScheduledTask stock_advisor_news_watcher` show both Ready; one full live pass
    (collect → score → news_cli) completes and its output is quoted in the report.
- [ ] **Task 6.3: pre-release review, fixes, wrap-up, ship** (coordinator)

## Self-review
- A1→0.1; A2→1.1–1.11; A3→2.1–2.3, 6.2; A4→3.1–3.3; A5→4.1, 4.2; A6→4.3, 4.4;
  A7→5.1–5.3; A8→6.1; A9→4.2, 4.5, 5.1; A10→5.4, 5.5, 6.2.
- Parallel groups touch disjoint files; `config.py` only in 2.2 (Phase 2) and read-only
  afterwards except 5.1 adding one constant (Phase 5, serial with 5.2/5.3? 5.1–5.3 run in
  sequence because 5.2 and 5.3 use 5.1's functions).
- Long job: the backfill (4.1) runs in the background while 4.2–4.4 are built.
