# Inbox: questions for Brian (stock_advisor)

Workers add questions here; the orchestrator checks each against the source and sends Brian a card.
Brian's answers are copied here word for word, then into `docs/decisions.md`.

## Open

**Should a proven news prediction move the buy/sell/hold signal by one step?** (from docs, `docs/decisions.md` 2026-10-27 "Brian to confirm", plan Task 5.2)
- What it is: the report starts from a price-based signal (BUY, HOLD or SELL). Claude chose a default rule: when the news model has proven itself on held-out data for that horizon, a "reduce" prediction moves BUY to HOLD or HOLD to SELL, and an "add" prediction moves SELL to HOLD or HOLD to BUY. Unproven predictions never change the signal and only show a warning.
- Example: the price signal says BUY for a holding, and the news model predicts -2% over 1 day with a proven record. The report then shows HOLD with a note. Without the rule it would still show BUY.
- Why it matters: this decides how far the news model may override the price signal. A bigger or smaller step changes real recommendations once any prediction is proven.
- Options: **Default:** keep the one-step rule as written. Or change the step size, or let news only add a warning and never change the signal.

## Answered
