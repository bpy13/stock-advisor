# Board: stock_advisor

Milestone: `docs/milestones.md` (approved 2026-11-10; now: 1, clean price data and the portfolio
analyzer; milestone 1 reached 2026-11-17, milestone 2 news watch approved). Plan: `docs/plans/2026-11-10-price-data-and-analyzer.md` (approved 2026-11-10;
registered with the orchestrator). Questions for Brian go to `docs/inbox.md`, never here.

## Workers
- none (slot 2 finished the code of Task 5.2, 2026-11-17; its history run waits for slot 1). (slot 4 finished the code of Task 6.2, 2026-11-17; its history load waits for slot 1)
- none (slot 2 finished the code of Task 5.2c, Yahoo news, 2026-11-17: the adapter calls Search only and returned 94 stories live; the watcher log check waits for slot 1).

## Ready to build (once the plan is approved and registered)
- Task 1.1 (two new dependencies), Task 1.2 (watchlist file), Task 1.4 (accounts, cash, limits).
  Every other task names what it needs.

## Waiting on Brian
- Approve the plan.
- Open a Futu account and start Futu OpenD on this PC (Task 2.8).
- Create a free Alpaca account and put its two keys in `.env` (Task 2.7).
- Type the cash balances into `data/accounts.json` once Task 1.4 has created it.
- `scripts/run_rebuild_backtest.py` has an uncommitted change from 30 Oct: commit or discard.

## Done and carried over
- The 2026-10-27 news plan is closed (see its banner). Carried into the new plan: the scheduled
  tasks check (Task 4.1) and the dashboard browser check (Task 4.2). The Telegram live test
  moves to milestone 4.

## Results
- Task R2 (market-position sources) done by slot 1, 2026-11-26: HKEX stock-option open interest, CFTC and Yahoo option samples fetched; Futu order book not sampled (OpenD down); recommendation and inbox question written; docs only; cost US$0.
- Task R1 (carry over the pinned session) done by slot 1, 2026-11-26: 6 rulings added to decisions.md, 6 facts to known-issues.md, 7 lines to CLAUDE.md, 3 items to open-items.md, 1 question to the inbox; stale board header fixed; docs only; cost US$0.
- Task 9.2 (Brian's shares off the alert path) done by slot 2, 2026-11-26: `_recent_unscored` skips source `research_inbox`, so no score, event or Telegram; 2 new tests fail without the fix and pass with it; 641 tests pass, ruff clean; cost US$0.
- Task 9.1 (research-inbox source) done by slot 1, 2026-11-26: reads local items.jsonl, `stock` tag only; 5 new tests pass, 644 tests pass, ruff clean; no network; cost US$0. Tasks 9.2 and 9.3 follow.
- Task 6.2 (insider trades) done by slot 1, 2026-11-25: history job 199 loaded 2006 to 2026q1 (log ends with rows per year); 12 tests pass; live day 13 Nov added 43 rows, rerun 0 (17 Nov); a repeat today timed out; cost US$0.
- Task 5.2c (Yahoo news) waiting on Brian, slot 1, 2026-11-17: slot 2's fix is on main, but the watcher still runs the old code (log shows YFDataException at 15:56). Slot 1's watcher restart was refused; the orchestrator asked Brian to restart it (commands under the task). 9 Yahoo tests pass, ruff clean; cost US$0.
- Task 5.2b (news watcher polls again) done by slot 1, 2026-11-17: the watcher and its wrapper died on 11 Nov and nothing restarted them; the restart at 15:06 was starved at low priority. Now: task priority 4, a 15-minute repeat restarts a dead wrapper, the wrapper restarts a watcher quiet for 30 minutes, and each poll logs stories per source. Polls at 15:37 and 15:40 without a cycle error; Yahoo news fails since 3 Nov (open-items). 640 tests pass, ruff clean; cost US$0.
- Task 5.2 (links stored) part done by slot 1, 2026-11-17: history run queued as job 200 (cpu lane), watcher restarted through its task (first poll not yet seen); plan marked waiting; cost US$0.
- Task 6.2 (insider trades) part done by slot 1, 2026-11-17: live day 13 Nov stored 43 rows, rerun 0; history load queued as job 199 (cpu lane), plan marked waiting; cost US$0.
- Task 5.2 (links stored for every story) code done by slot 2, 2026-11-17: 5 new tests pass; the history run and the watcher restart wait for slot 1. No paid calls, cost US$0.
- Task 5.1 (names file and news linker) done by slot 1, 2026-11-17: 1,109 aliases for 205 symbols and 6 drivers; 96 linker tests pass (64 headlines, 21 traps); 614 tests pass in all, ruff clean; about 3.5 ms a story. Task 5.2 can start.
- Task 5.4 (API key check) done by slot 1, 2026-11-17: `ANTHROPIC_API_KEY` is non-empty in `.env`; value not read or printed; cost US$0.
- Task 5.3 (Haiku labeller, cost per label, monthly ceiling) done by slot 2, 2026-11-17: 18 tests pass with a fake client; no real API call, cost US$0; 534 tests pass after merging main, ruff clean.
- Task 1.2 (watchlist file) done by slot 1, 2026-11-10: 215 rows, 85 HK and 101 US stocks.
- Task 2.1 (price store and quality flags) done by slot 2, 2026-11-10.
- Task 3.1 (value, return and concentration) done by slot 5, 2026-11-10: analyzer.py with 6 hand-checked tests.
- Task 1.5 (fee tables) done by slot 3, 2026-11-10: all worked totals match; round trip for HK$20,000 is 1.22% at Hang Seng Bank and 0.37% at Futu; 422 tests pass.
- Task 2.2 (Yahoo into the store, prices CLI) done by slot 3, 2026-11-10: real run of 5 Hong Kong symbols gave 27,336 daily bars from 2000-01-03; tests and ruff pass.
- Task 2.5 (first full Yahoo load) done by slot 1, 2026-11-10: daily 215/215 symbols, hourly 208 (3 failed), 144 MB; HK hourly grid mismatch noted on the plan.
- Task 2.3 (Alpaca source) done by slot 2, 2026-11-10: 6 tests pass with faked HTTP; no live call yet (Task 2.7).
- Task 3.2 (groups, risk shares, exposures) done by slot 4, 2026-11-10: 5 tests pass.
- Task 2.4 (Futu source) done by slot 2, 2026-11-10: 7 tests pass with a fake quote context; no live call yet (Task 2.8).
- Task 2.6 (nightly refresh code) partly done by slot 2, 2026-11-11: recorder script refreshes every source with one log line each, test passes; the live run and the 1m size measurement wait for slot 1 in the main folder.
- Task 2.6 (nightly refresh, minute size) done by slot 1, 2026-11-11: live run exit 0, one log line per source; 1m store about 2.1 MB per stock per year; Alpaca ignores `.env` keys (bug noted on Task 2.7).
- Task 3.3 (analyzer CLI) done by slot 4, 2026-11-11: cost command gives 1.22% and 0.37%; 471 tests pass; built from slot 3's salvaged draft.
- Task 2.7 (Alpaca live load) done by slot 1, 2026-11-11: sip feed; daily and hourly 117 of 117 US symbols, first bar 2016-01-04; 473 tests pass.
- Task 3.4 (dashboard Portfolio tab) done by slot 1, 2026-11-11: 3 AppTest tests pass; 476 tests pass, ruff clean; browser check is Task 4.2.
- Task 3.5 (analyzer on the real portfolio) done by slot 1, 2026-11-11: 22 holdings (19 priced, 3 unpriced), all checks pass, run 56 s; Brian to read the saved report (inbox).
- Task 4.2 (dashboard in a browser) waiting on Brian, slot 1, 2026-11-11: port 8502 answers 200 but runs the old code from 2026-10-31; the restart was refused, so Brian restarts it and views the tabs (inbox).
- Task 2.8 (Futu live load) done by slot 1, 2026-11-12: 89 of 89 HK symbols daily (from 2006) and hourly (from 2018-11-06); bar labelling is end-time as assumed; quota 211 of 300 left; 484 tests pass.
- Task 4.2b (News tab speed) done by slot 1, 2026-11-11: library snapshot, one search per event, sparse outcomes; memory 3.5 GB (was 12 GB); repeat open 4-8 s, first open 15-25 s; dashboard restart is Brian's (inbox).
- Task 2.9 (comparison report) done by slot 1, 2026-11-12: code by slot 2; real run: HK hourly Futu 4 vs Yahoo 129,311 missing, US hourly Alpaca 1 vs Yahoo 2,283, HK daily Yahoo 80 vs Futu 961; PREFERRED_SOURCES now HK futu, US alpaca; 488 tests pass; per-interval question in inbox.
- Task 2.10 (preferred source per market and interval) done by slot 1, 2026-11-16: HK daily reads Yahoo (0005.HK from 2000-01-03), HK hourly reads Futu (from 2018-11-06), US unchanged; 489 tests pass, ruff clean.
- Task 4.1a (minute recorder hang) done by slot 1, 2026-11-16: an unclosed Futu connection kept the 12 Nov run alive after its work; fixed, with time limits and hourly fetches from the last bar. Real run via the task: result 0 in 39 minutes (was 9 hours); 13 Nov minute bars recovered; 494 tests pass.
- Task 4.3 (review and fixes) done by slot 1, 2026-11-17: 14 findings; 7 fixed with tests, 7 judgment calls in open-items; 498 tests pass, ruff clean.
- Task 4.1 (four scheduled tasks) done by slot 1, 2026-11-16: dashboard Running, others Ready; recorder 22:00 run result 0 with a log line per source.
- Task 4.4 (docs and wrap-up) done by slot 1, 2026-11-16: README, architecture, known-issues, CLAUDE.md updated; every milestone 1 criterion checked; milestone-reached card in the inbox.
- Task 6.3 (short-selling files) done by slot 5, 2026-11-17: SFC weekly short positions load into `short_selling` (live check: 528 rows for 89 HK symbols from 1 Oct 2026; full history loads at the next 02:00 backfill); FINRA not built (its terms forbid scraping), recorded in known-issues; 6 new tests pass.
- Task 6.1 (EDGAR filings by event type) done by slot 3 (code) and slot 1 (live check), 2026-11-17: 13 Nov fetch gave 101 tickers, 100 CIKs, 5 filings with item numbers, 3.7 s; cost US$0.
- Task 6.4 (Hong Kong and China feeds) done by slot 4, 2026-11-17: added news.gov.hk Finance, SFC Press Releases and Circulars, CNA Finance and Cross-Strait (live poll stored 72 stories); removed SCMP and Investing.com on their terms; Census and Statistics has no RSS feed; tests pass.
- Task R3 (Futu order book depth) done by slot 1, 2026-11-26: docs read; HK 10 levels need paid LV2 card, US 60 levels free in promotion; OpenD installed, not running, no sample.
