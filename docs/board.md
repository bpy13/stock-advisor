# Board: stock_advisor

Milestone: `docs/milestones.md` (approved 2026-11-10; now: 1, clean price data and the portfolio
analyzer). Plan: `docs/plans/2026-11-10-price-data-and-analyzer.md` (waits for Brian's approval;
not yet in the orchestrator's registry). Questions for Brian go to `docs/inbox.md`, never here.

## Workers
- none (slot 3 finished Task 1.1; slot 2 finished Task 1.3, trading calendars, 396 tests pass)

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
