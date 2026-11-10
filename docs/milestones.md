# Milestones

Approved by Brian on 2026-11-10 (replanning session). Plan for milestone 1:
`docs/plans/2026-11-10-price-data-and-analyzer.md`.

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

## 3. The regression and its honest test
Done when:
- One table has a row per stock per day and per hour, with price inputs, news inputs and slow
  signals (insider buying, short selling, momentum).
- Three models are tested for the 1-hour, 1-day and 5-day horizons: price only, news only, and
  combined. The test trains on earlier years and scores later ones, with a gap between them.
- Every return is measured from the first price Brian could have traded at after the news,
  with his trading cost subtracted. Results use medians and capped extremes, and t-stats
  corrected for overlapping periods.
- For each horizon the best model is chosen by its record on unseen years. A saved table shows
  how often forecasts of each strength were right.
- The report and dashboard show one label per stock from the 5-day forecast of the best model,
  with the hour and 1-day forecasts beside it, each marked proven or unproven.

## 4. Recommendations and Telegram alerts
Done when:
- Brian has chosen the account for new trades. Interactive Brokers gets a fee table first
  if he wants it compared.
- A recommendation names the stock, the direction, the amount and the account, and uses that
  account's fee table. The amount respects the
  cash, the position limits (no stock above 25%, no trade under HK$10,000, whole board lots:
  my default) and the trade's cost. When cash is short it names the weakest holding to trim.
- Telegram sends only when the predicted move after costs is at least 2%, and forecasts that
  strong were right at least 60% of the time in 30 or more past cases. Other signals show on
  the dashboard, marked unproven.
- The first real alert reaches Brian's phone.
- The pre-release review is done and its fixes shipped.

## Later (not scheduled)
- Graded severity and factor shocks (`docs/proposals/2026-10-30-news-impact-design.md`).
- Projects that use minute bars (news reaction speed, volatility from 5-minute bars).
- China A-shares through Stock Connect.
- Reading positions and cash from a Futu account automatically.
- Interactive Brokers: a fee table, and a third price source if Brian opens an account.
