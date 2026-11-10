# Milestones

Approved by Brian on 2026-11-10 (replanning session). Plan for milestone 1:
`docs/plans/2026-11-10-price-data-and-analyzer.md`. Milestone 3 and the alert line of milestone 4
were revised the same day, on his answers about how signals are verified.

Workers build only toward the current milestone. Pending items that do not serve it wait.
When every "done when" line holds, the orchestrator sends Brian one card: the milestone is reached,
with the next one proposed for his approval. Lines marked "(my default)" came from Claude; Brian
accepted them with the milestones and may change them.

Purpose (Brian, 2026-11-10): a portfolio analyzer that watches the news and sends a Telegram
alert only when it finds a clear reason to buy or sell a named stock. A regression that uses
both price and news produces the signal's strength and confidence. The recommendation fits the
current portfolio: cash, risk, and the cost of the trade. Decisions: `docs/decisions.md`,
section "Replanning (2026-11-10)". Research: `docs/research/2026-11-10-quant-landscape.md`.

## Current: 1. Clean price data and the portfolio analyzer
Done when:
- **Watchlist.** One editable file lists the stocks the tool follows: the holdings, the Hang
  Seng Index members, the 100 largest US stocks and the main index funds.
- **Price store.** Daily bars for the watchlist are stored raw and adjusted, apart, against a
  trading calendar (lunch break, half days, holidays). Each bar carries flags: no trades that
  day, a move beyond a set limit, a gap. Hourly bars are stored the same way.
- **Second sources.** Futu serves Hong Kong bars (8 years hourly, 20 years daily) and Alpaca's
  free feed serves US bars (7 years hourly). If Alpaca refuses the sign-up,
  Futu serves the US bars too. A report compares each with Yahoo over a shared period and
  lists the differences. The store prefers the source the report shows is cleaner.
- **Portfolio inputs.** The trade file stays as it is. One settings file lists the accounts
  and the position limits. Each account has a broker, its cash in HKD and USD, and a fee
  table. Which accounts Brian holds stays out of git (`data/accounts.json`). Fee tables
  exist for Hang Seng Bank and Futu, so the tool gives the cost of any trade at each.
- **Analyzer.** The dashboard and the CLI report show, for the portfolio: value, return with
  and without the timing of deposits, deepest fall, yearly swing, groups of holdings that move
  together, and concentration. For each holding: its share of the portfolio's risk, and how far
  it follows the market and the six drivers Brian chose on 2026-10-30 (oil, US rates, China/HK
  tech, US tech, cyber security, USD/CNY).
- **Old plan closed.** The 2026-10-27 plan is marked closed. Its carry-overs are done: the
  dashboard checked in a real browser, the four scheduled tasks checked.
- The minute recorder keeps running; its stored size per stock per year is measured.
- Tests and `ruff check` pass; README, architecture and known-issues match.

## 2. News watch that filters
Done when:
- Each story is linked to the watchlist stocks or drivers it concerns, or dropped.
- Claude Haiku labels each linked story: relevant or not, event type, new or repeat, severity.
  A 200-story sample with its measured cost came first, and Brian approved the cost.
- A labelled history exists for the regression to learn from. Its one-time cost was quoted and
  approved before the run.
- New free sources feed the watch: US company filings by event type, US insider trades, US
  and Hong Kong short-selling files, and Hong Kong and China news feeds whose terms allow it.
- The dashboard News tab shows the labelled stories per holding. The old "high impact" flag
  is gone.

## 3. Signals, their honest test, and the regression
Revised on 2026-11-10 after the research in `docs/research/2026-11-10-strategy-verification.md`;
Brian's answers are in `docs/decisions.md`, "Milestone 3 test rules". A signal is one input that
may predict a stock's return, such as a kind of news or the past year's return.

Done when:
- **Table.** One table has a row per stock per day and per hour, with price inputs, news inputs
  and slow signals (insider buying, short selling, past returns).
- **Ledger.** One tracked file records every test of every signal variant before it runs: the
  signal, the reason for it, the horizon, the stocks, the date. Failures stay in it. The count
  of independent tries comes from it.
- **Test bench.** One command takes a signal through five gates and writes a report. A fail
  stops the signal.
  1. *Reason and plan.* A written reason and one planned test are in the ledger first.
  2. *Ranking power.* Each day, the rank correlation between the signal and the return that
     followed, on periods that do not overlap. Its mean must reach a t-stat of 3, with errors
     corrected for serial correlation. A news signal is tested with an event study instead,
     corrected for events that fall on the same day. Across a round of signals, false finds
     are also capped at 5% of the finds.
  3. *Money after costs.* Buying only: the top group against the whole watchlist, bought at
     the first price Brian could have traded at, minus the fee table's cost. Training and test
     periods never overlap. The Sharpe ratio, deflated by the ledger's count of tries, must
     reach 0.95.
  4. *Robustness.* The probability of backtest overfitting across the signal's variants is at
     most 0.05. The result is positive in both halves of the history, in each market, and at
     double the cost.
  5. *Hold-out.* The last two years stay unused until this gate and are opened once per
     signal. The effect keeps its sign and at least half its size.
- **The bench is proven first (my default).** Each statistic reproduces the worked numbers of
  its source paper. A random signal fails the gates; a planted one passes.
- **Many candidates, in rounds.** The rounds test many signals, none favoured: swings that
  news causes (by event type, severity and novelty), past-year winners, return to the average,
  insider buying, short selling, links between stocks, index changes, drift after results.
  News signals are in the first round. Each candidate ends in the ledger as passed or failed.
- **Regression.** The signals that pass feed one forecast per horizon (1 hour, 1 day, 5 days).
  Price only, news only and combined are compared on unseen years, and the best is used. A
  saved table shows how often forecasts of each strength were right.
- **Live record.** A signal's forecasts are stored daily for three months before any Telegram
  alert may use it.
- **Honest labels.** The report and dashboard show one label per stock from the 5-day forecast,
  with the hour and 1-day forecasts beside it, each marked proven or unproven. Every report
  states that the watchlist holds today's index members only, which flatters the past. "No
  signal proven yet" is a valid result: the dashboard then shows unproven forecasts and
  Telegram stays silent.

## 4. Recommendations and Telegram alerts
Done when:
- Brian has chosen the account for new trades. Interactive Brokers gets a fee table first
  if he wants it compared.
- A recommendation names the stock, the direction, the amount and the account, and uses that
  account's fee table. The amount respects the
  cash, the position limits (no stock above 25%, no trade under HK$10,000, whole board lots:
  my default) and the trade's cost. When cash is short it names the weakest holding to trim.
- Telegram sends only when three things hold. The predicted move after costs is at least 2%.
  The past hit rate of forecasts that strong beats a coin flip with 95% confidence, counted on
  cases that do not overlap (20 right of 30 passes, so does 60 of 100; 18 of 30 fails). The
  signal behind it passed milestone 3's gates and has its three-month live record. Other
  signals show on the dashboard, marked unproven. (Revised 2026-11-10; it replaces "60% right
  in 30 or more cases", which a coin matches 18% of the time.)
- The first real alert reaches Brian's phone.
- The pre-release review is done and its fixes shipped.

## Later (not scheduled)
- Graded severity and factor shocks (`docs/proposals/2026-10-30-news-impact-design.md`).
- Projects that use minute bars (news reaction speed, volatility from 5-minute bars).
- China A-shares through Stock Connect.
- Reading positions and cash from a Futu account automatically.
- Interactive Brokers: a fee table, and a third price source if Brian opens an account.
