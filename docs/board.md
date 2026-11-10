# Board: stock_advisor

Milestone: `docs/milestones.md` (draft; now: 1, news module finished). Plan:
`docs/plans/2026-10-27-news-event-module.md`. Questions for Brian go to `docs/inbox.md`, never here.

## Workers
- none

## Ready to build
Open plan tasks a worker could start now (the plan has 9 open tasks):
- **Task 6.2i: data fixes before any real backtest.** The code part is committed (a2065f1, ff60fd5,
  4b4d34d); the plan box is unticked. Left: the rebuild-and-backtest long job (memory guard, run alone
  in the background, queue lane cpu) and recording its run time and day counts. A worker checks
  first. Note: `scripts/run_rebuild_backtest.py` has uncommitted changes in the working tree.
- **Task 6.2g and Task 6.2h: tick the boxes.** The code is committed (97acc98, 444b022). The live
  check needs the watcher and dashboard restarted by process id (inferred: Brian or the orchestrator
  in an attended session, since the plan says Brian stops them).
- **Task 6.2e: re-categorize old rows.** Script exists (8e2ce23); the real run needs a backup first and
  no `backfill.lock` (plan).
- **Task 6.2c: GDELT timestamps on fresh data.** Items (1), (2) and (4) are done or dropped; only (3)
  is open and waits on GDELT publishing newer batches (the plan says so).
- **Task 6.2: scheduled tasks check and end-to-end run.** After the fixes above.
- **Task 6.2f: rerun the backtest after the backfill completes.** Waits on time (backfill status).
- **Task 6.3: pre-release review, fixes, wrap-up, ship.** Last; 5.4b and 6.2f may stay open.

## Waiting on Brian
- **Task 5.4b (Telegram).** Workers never handle secrets, so the Telegram token in `.env` waits on
  Brian. Progress: token, chat id and the phone test are already done (plan, 2026-10-28). Only the
  first real alert is open, and it needs predictions.
- Real-browser check of the dashboard News tab at http://localhost:8502 (open items, "Waiting on
  the user").
- Confirm the one-step rule for proven news actions (`docs/inbox.md`).
- Review the news-impact design proposal (`docs/proposals/2026-10-30-news-impact-design.md`) before
  milestone 2 work starts.

## Done and carried over
- Phases 0 to 5 (except 5.4b) and Tasks 6.1, 6.2a, 6.2b, 6.2d are ticked in the plan.
