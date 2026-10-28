# Open items

As of 2026-10-27. Tick off, or move to `decisions.md` when settled. A bug that will be fixed goes
here; a limit or trap we live with goes in `known-issues.md`. Each item in one place only.

## Blockers

- GDELT timestamps still collapse: after the fix (b8af5fe) and the combined-query change
  (8bbdb94), all 169 stored GDELT items still share published_at 2026-10-27 05:15 UTC
  (checked 2026-10-27 20:20 HKT). The root cause was never confirmed live (GDELT returned 429
  on every probe). Until fixed, GDELT events can't be used for minute/hour reactions, and
  they group into misleading "05:15" events. Next step: capture a real artlist response
  outside rate-limit windows and compare `seendate` values with what is stored; also check
  whether the backfill and watcher calling GDELT at the same time makes the 429s worse.
- `conda run` on Windows strips `^` from arguments (cmd escape character), so
  `--targets ^HSI ^GSPC` became HSI/GSPC and prices failed to load in the end-to-end run.
  Use `^^HSI`, or call the env's python directly; consider accepting HSI/GSPC aliases.

## Waiting on the user

- Watcher (pid 19260) and dashboard (pid 24808) run outside their tasks: `Stop-ScheduledTask`
  marked the tasks Ready but left the processes, and Claude's safety check blocked
  `Stop-Process`. In PowerShell: `Stop-Process -Id 19260,24808; Start-ScheduledTask
  stock_advisor_news_watcher; Start-ScheduledTask stock_advisor_dashboard`.
- Real-browser check of the dashboard News tab (no browser tools in this session): the
  dashboard task serves it at http://localhost:8502; open it and check the News tab.

- Telegram bot token in `.env` as `TELEGRAM_BOT_TOKEN=` (create the bot with @BotFather, then
  send the bot one message). Task 5.4b (setup and phone test) waits for it.

- Guardian and NYT API keys in `.env` (`GUARDIAN_API_KEY`, `NYT_API_KEY`). Until then those
  two sources are built and tested from fixtures, but not backfilled.
  - NYT: done 2026-10-27 (live archive and Top Stories, real fixtures; old months use
    "Business Day", already covered). Archive months run up to ~14 MB each.
  - Guardian: done 2026-10-27 (live, real fixture, archive from 1990-02-08, limits 60/min and
    500/day).

- Google News RSS dropped: its robots.txt disallows /rss for every crawler. Brian may
  overrule the skip; the adapter would take about an hour to build.
- HKEXnews dropped: the HKEX Terms of Use (section 5) forbid scripted access and data mining.
  The helper read the terms through a summarising fetch, not the raw page. Brian could ask
  info@hkex.com.hk for written permission; until then HK filings are not collected.

- Confirm the one-step rule for proven news actions (decisions.md, 2026-10-27).
- (plan review 2026-10-28) If Task 6.2c finds GDELT stamps items per 15-minute crawl batch,
  should GDELT items drop the 1-minute horizon (keep hour and day)? Default: yes.
- (plan review 2026-10-28) OneDrive syncs `data\` (news.db is 1.5 GB, written all day). This
  may slow or break the backfill. Default: exclude `data\` from OneDrive sync (Brian's setting).

## Pending work

- CLI report news column (Task 5.2): the live run showed "—" for every holding, because no
  predictions exist before the backfill and backtest. Re-check once results.json exists. The
  report fits the news model on every run; cache it if that gets slow. Under `conda run`,
  "—" prints as mojibake in PowerShell 5.1 (console code page); direct python is fine.

- yfinance `Ticker.news` returns nothing (Yahoo's endpoint answers 404); the Yahoo adapter
  uses the `yf.Search` fallback. Re-check after a yfinance upgrade. Search finds no headlines
  for 2800.HK and 3033.HK; Task 2.2 decides whether they stay as price targets (they still
  have prices; only headlines are missing).
- RSS feeds (Task 1.10): 12 feeds kept on robots.txt grounds. Still to do: read the
  Investing.com and SCMP terms for bans on automated feed access; check whether Dow Jones
  terms allow MarketWatch feeds; find working Yahoo, Nasdaq and US Treasury feed URLs. Poll
  CISA (5.7 MB per fetch) at most every 15 minutes.

- News event module: see `docs/plans/2026-10-27-news-event-module.md`.

- GDELT returns 429 under a full 10-query pass (one query gave up in the live run). The
  watcher polls it every 15 min; the Phase 4 backfill needs longer waits.
- EDGAR live feed gave 0 allowlisted 8-Ks in one poll. Judge the allowlist after several
  days of polling. HK holdings are not passed to EDGAR (HK companies don't file 8-Ks).
- EDGAR `fetch_range` reads quarterly indexes in form-type order, so an interrupted
  mid-quarter backfill could skip filings; Task 4.1 must keep EDGAR's cursor per quarter.

- Yahoo has 2828.HK daily prices only from 2024-04-24 (the ETF listed in 2003), so its
  backtest sample is short. Goes into known-issues in Phase 6.

- Category thresholds (0.50 strong / 0.30 minimum) and seeds are untuned on real data. Known
  borderline: "Society for Hong Kong Studies to disband" → geopolitical_tension. Revisit after
  the backfill, using which categories the backtest shows actually move prices.

- Events (Task 3.3): 19% of events are high impact on the live sample, mostly lone headlines
  with strong tone; financial_crisis is over-assigned. Alerts still filter on a predicted move
  of at least 1.5%; tighten the rule with the `market_moving` hook once the backtest shows
  which categories move prices. Syndicated GDELT copies inflate source counts. `events.py`
  runs its own SQL; store methods to add later: event_members, pending query, event-context
  query, batch save.
- Cluster parameters chosen on real data: similarity ≥ 0.60, 12 h window (same day for
  date-only items), events span at most 48 h. The plan's 0.75 merged too little.

- Backfill (Task 4.1): the daily 02:00 task runs it; the 2026-10-28 run stopped at 07:57 HKT
  while scoring, with no trace; cause unknown. Since cf242e3 a crash writes `crashed: <type>`
  to the status file and a traceback to backfill_log.txt; read them after the next stop.
  `news_cli` took over 5 minutes to print on the full store (2026-10-28). Check:
  `conda run -n stock_advisor python scripts\backfill_news.py --status`. Sources take
  30-minute turns; Guardian and NYT stop at 480 calls a day; GDELT history from 2017 needs
  ~2 calls per day-window, so it takes a day or more. Wikipedia, NYT and EDGAR adapters
  swallow some per-page download errors, so history may have gaps: check the status file's
  last-error column after the first full pass. `fetch_high_impact_bodies` has no retry cap.
- CPU is shared with other projects' long jobs (hk-estate backfill, holdem benchmark), so
  FinBERT scoring of the backfill runs slower than the measured 24 headlines/s.
- Full live backtest (Task 4.4) and window check (Task 4.5) wait for the backfill to score
  and cluster events; rerun `python -m stock_advisor.news_backtest_cli` then.

- Watcher (Task 5.1): WAL mode is now Task 6.2b; store.py connects with a 30 s timeout. A cold
  `news_cli --collect` can block on GDELT 429 waits for many minutes (watch mode runs GDELT
  on a side thread, so it doesn't stall). The watcher log (data\cache\news\watcher_log.txt,
  gitignored) lists holdings symbols.

- Dashboard News tab (Task 5.3) was checked with Streamlit's AppTest and an HTTP health
  check, not a real browser: the coordinator checks it in a browser in Phase 6. The forecast
  table and "⚠ unproven" badge are untested on real data until predictions exist.
  `SimilarEvent` should carry a URL (app.py looks links up itself for now).

- Re-categorize rows categorized before commit 0fbfdf1: now Task 6.2e (use
  `store.set_category`, not `update_scores`, which resets high_impact).

## Later

- NYT business/world RSS feeds need no key and could join the RSS adapter. (Top Stories is
  now Task 1.12.)
- "Public attention" signal from the NYT Most Popular API: when a market story reaches
  most-viewed, ordinary investors have caught on. No history in the API, so it must be
  recorded for months before it can be backtested.
