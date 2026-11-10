# Inbox: questions for Brian (stock_advisor)

Workers add questions here; the orchestrator checks each against the source and sends Brian a card.
Brian's answers are copied here word for word, then into `docs/decisions.md`.

## Open

**Is Futu OpenD running on this PC under your login?** (plan 2026-11-10, Task 2.8)
- What it is: Futu is the broker whose free interface gives 8 years of hourly Hong Kong prices. Its small program, Futu OpenD, must run on this PC and be logged in to your Futu account. The tool then asks it for prices; the tool never sees your password.
- Example: with OpenD running, the tool fetches hourly prices for Tencent back to 2018. Without it, Hong Kong prices come from Yahoo only (2 years of hourly bars, known errors).
- Why it matters: the comparison of price sources (Task 2.9) and the 8-year hourly history wait for this. Every other task carries on.
- Options: **Default:** you open the account and start OpenD when convenient, then answer "running". Or answer "skip Futu" and Hong Kong stays on Yahoo.

## Answered

**Are the two Alpaca keys in `.env`?** (plan 2026-11-10, Task 2.7)
- What it is: Alpaca is a US broker whose free account gives 7 years of hourly US prices. It issues two keys. They go in the file `.env` as `ALPACA_API_KEY` and `ALPACA_API_SECRET`. Workers never open that file.
- Example: with the keys, the tool fetches hourly prices for Apple back to 2019. Without them, US prices come from Yahoo only.
- Why it matters: the US half of the source comparison waits for this. Alpaca may refuse the sign-up (not confirmed); then Futu serves the US prices instead.
- Options: **Default:** create the free account, add the keys, answer "done". Or answer "Alpaca refused" and the worker switches the US prices to Futu.
- Brian (2026-11-10): "done" (the Default: free account created, keys added to `.env`).

**Should a proven news prediction move the buy/sell/hold signal by one step?** (from docs, `docs/decisions.md` 2026-10-27 "Brian to confirm", plan Task 5.2)
- What it is: the report starts from a price-based signal (BUY, HOLD or SELL). Claude chose a default rule: when the news model has proven itself on held-out data for that horizon, a "reduce" prediction moves BUY to HOLD or HOLD to SELL, and an "add" prediction moves SELL to HOLD or HOLD to BUY. Unproven predictions never change the signal and only show a warning.
- Example: the price signal says BUY for a holding, and the news model predicts -2% over 1 day with a proven record. The report then shows HOLD with a note. Without the rule it would still show BUY.
- Why it matters: this decides how far the news model may override the price signal. A bigger or smaller step changes real recommendations once any prediction is proven.
- Options: **Default:** keep the one-step rule as written. Or change the step size, or let news only add a warning and never change the signal.
- Card sent 2026-11-10, card 11
- Brian (2026-11-10): "the decision should be combined, making use of both data to give best recommendation". Not the Default (one-step rule): the replanning designs a combined recommendation.

**Approve stock's milestones, and start its worker?** (orchestrator, 2026-11-10)
- What it is: docs/milestones.md (draft) sets 3 goals: 1. news module finished and honestly backtested (what the open plan finishes); 2. graded severity and per-stock sensitivity (inferred); 3. proven predictions change the signal (inferred).
- Example: once approved, a worker builds the open plan tasks (9 unticked), starting by checking Tasks 6.2g, 6.2h and 6.2i, whose code is already committed.
- Why it matters: the project stays paused in the orchestrator until Brian approves. Task 5.4b (Telegram token) stays with Brian: workers never handle secrets.
- Options: **Default:** approve milestone 1 as written and unpause; milestones 2 and 3 stay drafts. Or edit the file first.
- Card sent 2026-11-10, card 10
- Brian (2026-11-10): "stock needs replanning on how to get better quality data, as well as considering the scope of other quant projects". Not the Default: stock stays paused; milestones get redrafted after the replanning.
