# Board: stock_advisor

Milestone: `docs/milestones.md` (approved 2026-11-10; now: 1, clean price data and the portfolio
analyzer). Plan: `docs/plans/2026-11-10-price-data-and-analyzer.md` (waits for Brian's approval;
not yet in the orchestrator's registry). Questions for Brian go to `docs/inbox.md`, never here.

## Workers
- none (slot 1 finished Task 2.5; slot 3 finished Tasks 1.1, 1.5 and 2.2; slot 2 finished Tasks 1.3 and 2.1; slot 4 finished Task 1.4, accounts, cash and limits; copy of sample to data/accounts.json still to do in the main folder)

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
