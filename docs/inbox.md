# Inbox: questions for Brian (stock_advisor)

Workers add questions here; the orchestrator checks each against the source and sends Brian a card.
Brian's answers are copied here word for word, then into `docs/decisions.md`.

## Open

**Is Futu OpenD running on this PC under your login?** (plan 2026-11-10, Task 2.8)
- What it is: Futu is the broker whose free interface gives 8 years of hourly Hong Kong prices. Its small program, Futu OpenD, must run on this PC and be logged in to your Futu account. The tool then asks it for prices; the tool never sees your password.
- Example: with OpenD running, the tool fetches hourly prices for Tencent back to 2018. Without it, Hong Kong prices come from Yahoo only (2 years of hourly bars, known errors).
- Why it matters: the comparison of price sources (Task 2.9) and the 8-year hourly history wait for this. Every other task carries on.
- Options: **Default:** you open the account and start OpenD when convenient, then answer "running". Or answer "skip Futu" and Hong Kong stays on Yahoo.
- Status (2026-11-10, orchestrator): Brian opened a Futu account; Futu shows "Account Application Under Review", opening expected in 1-2 business days. Not yet answered; Task 2.8 still waits.

**Do the numbers in your saved portfolio report look right?** (plan 2026-11-10, Task 3.5)
- What it is: the analyzer ran on your real trades and wrote a report to `data/reports/portfolio-2026-11-11.md` (not in git). It shows value, return, deepest fall, yearly swing, each holding's share of risk, groups and concentration. 19 of 22 holdings have prices; 3 have none and count at cost.
- Example: if the report shows a return of +40% but your own statement says +15%, tell us which number is wrong.
- Why it matters: only you know your true holdings and returns. The automatic checks (weights sum to 1, no empty values) cannot catch a wrong trade record or a wrong price. Nothing waits on your answer.
- Options: **Default:** "ok" (nothing looks wrong). Or name the number that looks wrong.

**Can you restart the dashboard and look at its Portfolio and News tabs?** (plan 2026-11-10, Task 4.2)
- What it is: the dashboard is the web page at http://localhost:8502. The copy now running started on 2026-10-31, so it lacks the new Portfolio tab. A restart loads the new code. The system refused the worker's attempt to stop that process.
- Example: in PowerShell, run `Stop-Process -Id (Get-NetTCPConnection -LocalPort 8502 -State Listen).OwningProcess`. The restart script starts the dashboard again within about 30 seconds. Then open http://localhost:8502 and click the Portfolio and News tabs.
- Why it matters: automatic tests passed, but nobody has seen the tabs in a real browser. The docs task (Task 4.4) waits for this.
- Options: **Default:** you restart it, look at both tabs and answer "ok" or name what looks wrong. Or answer "skip" and the task closes without a browser check.

## Answered

**Should milestone 3's test bench also test pairs trades, which buy one stock and sell its partner short?** (Brian's chat, 2026-11-11; `docs/milestones.md`, milestone 3)
- What it is: pairs trading watches two stocks that usually move together. When they drift apart, it buys the one that fell behind and sells the other short. Statistical arbitrage does the same across many stocks at once. Milestone 3's money test (gate 3) checks buying only: the top-ranked stocks against the whole watchlist. A short sale never enters it.
- Example: HSBC and Standard Chartered usually move together. One month HSBC falls 6% while Standard Chartered stays flat. A pairs trade buys HSBC and sells Standard Chartered short; it profits if the gap closes. The buy-only bench can test only "buy HSBC", which also carries the whole market's fall.
- Why it matters: every pairs study found tests both sides together; none tests buying only (`docs/research/2026-11-10-strategy-verification.md`, line 249). So a buy-only test may reject an idea that works as a pair. The same studies show profits after costs mostly shrank to 0.05% to 0.36% a month since the 2000s. Adding short sales means a cost of borrowing stock, and your brokers may not allow it (not checked).
- Options: **Default:** keep the bench buy-only; "links between stocks" and "return to the average" enter as buy-only signals, as written now. Or (b) add a long-short version of gate 3 for pairs signals only, with borrowing costs, reported apart from the buy-only results. Or (c) leave pairs to a later project and drop them from milestone 3.
- Brian (2026-11-11): "then allow shorting via moomoo, taking the charges interest into account" (option b, a long-short version of gate 3, with moomoo's interest on borrowed shares as the cost).

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
