# Milestones

DRAFT, waiting for Brian's approval (orchestrator card)

Workers build only toward the current milestone. Pending items that do not serve it wait.
When every "done when" line holds, the orchestrator sends Brian one card: the milestone is reached,
with the next one proposed for his approval. Lines marked "(inferred)" come from me, not from the
docs; Brian should check them.

Purpose (decisions.md, 2026-10-27): a news module that spots market-moving events early, finds
similar past events, measures how markets reacted, and suggests actions, so Brian does not lag
ordinary investors.

## Current: 1. News module finished and honestly backtested
What the open plan (`docs/plans/2026-10-27-news-event-module.md`) finishes.
Done when:
- The reaction table is rebuilt with full price history (`period="max"`, decisions 2026-10-30) and
  the backtest has run on it. `results.json` shows the distinct trading days behind each result
  (nothing is "proven" under 250 days). Plan Tasks 6.2i and 6.2f.
- The live watcher and dashboard load the saved fitted models and the memory guard, and their logs
  show "Model ready" with fitted pairs above 0 (Tasks 6.2g, 6.2h; the code is committed, the live
  restart is not checked).
- The four scheduled tasks are Ready or Running, and one full live pass (collect, score, news_cli)
  plus `python -m stock_advisor.cli` shows real values in the news column (Task 6.2).
- The dashboard News tab is checked in a real browser (open item "Waiting on the user").
- Open fixes done: GDELT timestamps re-checked on fresh data (6.2c); old rows re-categorized (6.2e).
- Telegram: the first real alert reaches Brian's phone (Task 5.4b, the token and test message
  already done; the first real alert needs predictions).
- The pre-release review is done and fixes shipped; tests and `ruff check` pass; docs match
  (Task 6.3). Tasks 5.4b and 6.2f may stay open per the plan.

## 2. Graded severity and per-stock sensitivity (inferred)
From decisions 2026-10-30 (Brian) and the proposal `docs/proposals/2026-10-30-news-impact-design.md`,
which is still only a proposal for Brian's review.
Done when:
- Brian has reviewed the proposal and decided what to build (inferred: this is the gate).
- Each high-impact event gets a graded severity and factor shocks, for the six agreed factors:
  oil, US rates, China/HK tech, US tech, cyber security, USD/CNY (decisions 2026-10-30).
- Each holding has a measured sensitivity to those factors from daily prices (proposal step B,
  inferred as a done-when line).
- The report and dashboard show a quantitative buy/sell suggestion from severity and sensitivity.
- Any paid Claude API run for severity had a cost quote first (decisions 2026-10-30).

## 3. Proven predictions change the signal (inferred)
Done when:
- At least one target and horizon passes the "proven" bar on held-out data (250 or more distinct
  trading days, decisions 2026-10-30), or the backtest honestly shows none do and Brian accepts
  that (inferred).
- A proven news action moves the price-based recommendation one step, as decided (2026-10-27, pending
  Brian's confirmation); unproven predictions still show only a warning.
- Category thresholds and the high-impact rule are revisited using the backtest (open items).
