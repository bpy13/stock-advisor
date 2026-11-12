# Decisions

What was decided, why, when, and whose call it was (Brian / Claude's default / builder check).
Change these only with a reason, and note the change here (mark reversed decisions as reversed
rather than deleting them). Nothing Brian didn't say is recorded as his decision.

## Scope

- 2026-10-27 (Brian): add a news monitoring module. Its purpose is to not lag behind ordinary
  market participants when news breaks.
- 2026-10-27 (Brian): backtest news against past data, and quantify its predictive value with
  a model such as regression.
- 2026-10-27 (Brian): prediction horizons are short: minute, hour and 1-day returns.
- 2026-10-27 (Brian): backtest as far back as the available stock data allows.
- 2026-10-27 (Brian): the news module is separate from the price-vs-own-history modules. It
  deals with market-moving events (new government policies, wars, security vulnerabilities,
  crashes). It finds similar past events, measures how markets reacted, and extrapolates to
  today's decisions to maximize profit or minimize loss. History goes as far back as the event
  and price data allow.
- 2026-10-27 (Brian): the aim is to beat ordinary investors, not professional trading
  algorithms.
- 2026-10-27 (Brian): score headlines with FinBERT.
- 2026-10-27 (Brian, accepted default): a news prediction only shows a warning beside the
  signal until the backtest proves it on held-out data for that horizon; then it may change
  the signal for that horizon.

## Data and secrets

- 2026-10-27 (Brian): include as many free news sources as possible.
- 2026-10-27 (Brian, accepted default): use only official feeds, APIs and filings; skip sites
  whose terms forbid scraping, and skip paywalled articles.
- 2026-10-27 (Brian): SEC EDGAR requests use Brian's personal email as the contact. It lives in
  the gitignored `.env`, never in committed files.

## Behaviour and rules

- 2026-10-27 (Brian): score headlines only; fetch and read the full article only when a
  headline is high impact.

- 2026-10-27 (Claude's default): the live EDGAR feed keeps only allowlisted companies
  (megacaps plus holdings); filings from thousands of small companies would drown the event
  signal.
- 2026-10-27 (Claude's default): items with date-only times (Wikipedia, pre-2000s EDGAR) are
  flagged with `time_precision="day"` and used only for the 1-day horizon, never for minute
  or hour reactions.

- 2026-10-27 (Brian): each suggested action also estimates how long it stays profitable
  (when similar past events' price paths usually peaked and reversed).
- 2026-10-27 (Brian): alerts go to Brian's phone via a Telegram bot.
- 2026-10-27 (Brian, accepted default): alert only on high-impact events that affect a holding,
  the Hang Seng or the S&P 500 with a predicted move of at least 1.5%; no quiet hours (24/7);
  the watcher runs on Brian's PC, started at login by a Windows task (cloud later).

- 2026-10-27 (Claude's default): add a `geopolitical_tension` category (diplomatic disputes,
  sanctions, US–China and cross-strait friction short of war); it counts as macro. Real
  headlines like "China condemns US designation…" fell into "other" without it.

- 2026-10-27 (Claude's default, Brian to confirm): a proven news action moves the price-based
  recommendation one step: "reduce" turns BUY→HOLD or HOLD→SELL; "add" turns SELL→HOLD or
  HOLD→BUY. The rationale gains a note. Unproven predictions never change it.

- 2026-10-29 (Brian, accepted recommendation, option A): the backtest saves its fitted news
  models to a file, and the watcher, CLI report and dashboard load that file instead of
  fitting. Fitting on the live store builds the all-pairs analog table (467k events, an
  estimated 30–60 min and several GB) and stopped the watcher's polling meanwhile. Rejected:
  fitting on a side thread (keeps the cost every 6 hours).

- 2026-10-30 (Brian): `period="max"` means as far back as yfinance covers (Task 6.2i). The
  backtest's README tables are replaced by "no valid backtest yet"; the reaction table is
  rebuilt; nothing is proven under 250 distinct trading days; the model fit waits for the
  rebuild.
- 2026-10-30 (Brian): the news module's goal is graded severity and per-stock sensitivity
  leading to quantitative buy/sell suggestions. Write up the "news → factor shock → stock
  sensitivity" design as a proposal for review (docs/proposals/2026-10-30-news-impact-design.md).
- 2026-10-30 (Brian): start with the factors oil, US rates, China/HK tech, US tech, cyber
  security and USD/CNY; add others (e.g. company announcements) only once these prove
  effective.
- 2026-10-30 (Brian): severity scoring may use the Claude API. A cost quote comes before any
  paid run.

## UI

- 2026-10-27 (Brian, Guardian key application): Guardian content is displayed only as the
  headline plus a link back to the Guardian. The stored trailText summary is used for scoring
  only and never shown in the CLI, dashboard or alerts.

- 2026-10-27 (Brian): news output appears in both the CLI report and the Streamlit dashboard.
- 2026-10-28 (Brian): GDELT items drop the sub-hour horizons (1m, 5m, 15m) and keep the hour
  and day horizons, because GDELT stamps articles per crawl batch, not per article.
- 2026-10-28 (Brian, accepted recommendation): keep the 169 GDELT items stored on 2026-10-27;
  no purge. Their 05:15 UTC stamps match GDELT's own batch stamps.

## Repository

- Remote: https://github.com/bpy13/stock-advisor.git (GitHub renamed it from stock_advisor;
  remote updated 2026-10-28).
## Orchestrator answers (2026-11-10)

- 2026-11-10 (Brian): the project needs replanning before a worker starts: "stock needs replanning on how to get better quality data, as well as considering the scope of other quant projects". Stock stays paused in the orchestrator.
- 2026-11-10 (Brian): replaces the 2026-10-27 one-step default above: "the decision should be combined, making use of both data to give best recommendation". How to combine the price and news data is for the replanning.

## Replanning (2026-11-10)

Brian's answers in the replanning session, word for word where quoted. Research behind them:
`docs/research/2026-11-10-quant-landscape.md`.

### Goal and order of work
- 2026-11-10 (Brian): the goal is to "establish portfolio analyzer, watch news and send Telegram
  alert accordingly".
- 2026-11-10 (Brian, accepted default): the portfolio analyzer and the news filter come first.
  The combined model follows as a tested research track, and the best proven model sets the
  BUY/HOLD/SELL label.
- 2026-11-10 (Brian, accepted default): survey open-source quant projects and borrow their data
  sources and methods, but keep this repo.
- 2026-11-10 (Brian, accepted default): close the 2026-10-27 news plan. Carry over the dashboard
  browser check, the scheduled-task check and the Telegram live test. Drop the reaction-table
  rebuild, the backtest rerun and the re-categorizing of old headlines.

### The model
- 2026-11-10 (Brian): whether one combined regression replaces the separate price rule and news
  model "should depends on test performance. In production (when sending alarm to telegram),
  always use the best model, combined or not".
- 2026-11-10 (Brian): "the signal strength and confidence should come from the regression (which
  uses the news as input). Waiting for price to change is already too late, ideally I want to
  catch the signal before that". So no alert rule waits for a price move to confirm the news.
- 2026-11-10 (Brian, accepted default): the 5-trading-day forecast sets the label; the 1-hour
  and 1-day forecasts show beside it.
- 2026-11-10 (Brian): "the hourly definitely need staying. Minute could be useful for future
  quant projects (need research)". The minute recorder keeps running.
- 2026-11-10 (Claude's default, builder check): every backtest measures the return from the
  first price Brian could have traded at after the news (the next bar, or the next market open),
  never from before the news.

### Milestone 3 test rules (2026-11-10, after `docs/research/2026-11-10-strategy-verification.md`)
- 2026-11-10 (Brian): "there are quantitative way to verify the strategies. Please conduct your
  researches properly". He also said finding signals takes "many rounds of testing for various
  strategies". So milestone 3 is a test bench and rounds of candidates, not one regression.
- 2026-11-10 (Brian, "default"): every signal goes through a ledger and five gates: a written
  reason; ranking power; money after costs; robustness; a hold-out opened once. Details in
  `docs/milestones.md`, milestone 3.
- 2026-11-10 (Brian): the pass mark is the strict one, a t-stat of 3: "strict is fine, as we
  don't plan to frequently trade due to trade cost. It should be able to capture news induced
  swing in the market". Claude's reading of the second sentence: news signals are a required
  candidate family and are tested in the first round, with the event study.
- 2026-11-10 (Brian, "similar with 2"): the Telegram alert bar is the strict one too. The past
  hit rate must beat a coin flip with 95% confidence on cases that do not overlap. This replaces
  "right at least 60% of the time in 30 or more past cases" in the entry below; the 2% predicted
  move after costs stays.
- 2026-11-10 (Brian): the past-year-winners signal "should be one of the many". No candidate is
  favoured. Brian's rule "hold last year's best stock" was researched (section 4a of the research
  file); its broad form, ranking every stock by its 12-month return, is the candidate.
- 2026-11-10 (Claude's defaults, Brian may change any): the gate numbers that Brian did not
  discuss one by one: deflated Sharpe ratio of 0.95, probability of backtest overfitting at most
  0.05, false finds capped at 5% per round, a two-year hold-out that must keep half the effect,
  a three-month live record before alerts, and proving the bench on the source papers' numbers.

### Alerts and recommendations
- 2026-11-10 (Brian): "the Telegram alert should only be sent when a clear signal for selling or
  buying certain stock is found, and the recommendation should be given based on the current
  portfolio (considering opportunity costs, risks, available cash, etc.)". News items, unusual
  moves and risk warnings go to the dashboard, not to Telegram (Claude's reading).
- 2026-11-10 (Brian): the alert bar "should take into account the opportunity cost (the trade
  cost). So basically the default". The default: send when the predicted move after Brian's
  trading costs is at least 2%, and forecasts that strong were right at least 60% of the time in
  30 or more past cases of the walk-forward test. Until a model has that record its signals
  show on the dashboard only, marked unproven. Replaces the 2026-10-27 alert rule (predicted
  move of at least 1.5% on high-impact events). The "60% in 30 cases" part was itself replaced
  later on 2026-11-10: see "Milestone 3 test rules" above.
- 2026-11-10 (Claude's default, Brian to confirm): position limits for a recommendation's
  amount: no stock above 25% of the portfolio (the existing rule), no trade under HK$10,000,
  sizes rounded to whole board lots; when cash is short the alert names the weakest holding to
  trim.

### Data
- 2026-11-10 (Brian): "free tier news data is sufficient, what we need is stock data for
  inference".
- 2026-11-10 (Brian, accepted default): a Futu (moomoo) account and a free Alpaca account serve
  as second price sources beside Yahoo. Brian opens the accounts and handles the login and the
  key; workers never see them.
- 2026-11-10 (Brian, accepted default): Claude Haiku classifies news stories (relevant or not,
  event type, new or repeat, severity), replacing FinBERT's tone as the filter, after a
  200-story sample and Brian's go on the measured cost. The API key stays Brian's.
- 2026-11-10 (Brian, "default for now"): the watchlist is the holdings, the Hang Seng Index
  members, the 100 largest US stocks and the main index funds, in a file Brian can edit. Markets:
  Hong Kong and the US only.
- 2026-11-10 (Brian, accepted default): Brian's broker offers no interface the tool could read,
  so Brian keeps the trade file and a cash figure by hand. The tool has a fee table per
  broker.
- 2026-11-10 (research finding, not a decision): HKEX's terms of use forbid scripted access to
  all its websites, so the 2026-10-27 rule (skip sites whose terms forbid it) keeps HKEX
  announcements, directors' dealings and Stock Connect files out.

### Accounts and approval
- 2026-11-10 (Brian): approved the four milestones in `docs/milestones.md` and the position
  limits above with an "ok" (the question said "ok" accepts them). His exact words name
  his accounts, so they are in `docs/private/decisions-private.md`.
- 2026-11-10 (Brian, accepted default): the account for new trades is decided at the start
  of milestone 4.
- Naming: "Futu" is the company, the account and the data interface. Earlier entries say
  "moomoo" for the same thing (moomoo is Futu's app name outside Hong Kong).
- 2026-11-10 (research finding, not a decision): Alpaca may refuse the sign-up (unconfirmed).
  If so, Futu serves the US bars.

### Builder check for milestone 1 (Claude's defaults, 2026-11-10; Brian may change any)
- "The 100 largest US stocks" means the S&P 100 members: a published list, not a ranking that
  changes daily.
- Anything that names a holding (reports, logs, comparison detail) is written under `data/`,
  which git ignores. Tracked files carry totals only. The watchlist file in git never lists
  the holdings; they join at run time.
- The price store appends raw bars and replaces adjusted bars whole on every refresh, because
  an adjusted history changes after each dividend.
- Hourly bars follow the trading session (Hong Kong from 09:30, the US from 09:30 New York
  time), the same for every source, so sources can be compared bar by bar.
- Quality flags: a daily move above 40% or an hourly move above 20% is flagged, not removed.
- The analyzer measures risk on weekly returns, because Hong Kong and US sessions do not
  overlap. Driver proxies are those of `docs/proposals/2026-10-30-news-impact-design.md`.
- The trade file records no cash and no dividends. So portfolio returns cover the invested
  holdings only and count dividends as reinvested; the dashboard says so.
- Accounts, cash and limits live in `data/accounts.json`. Fee tables are code, with the source
  page and date beside each rate.
- The old report and the news module keep reading prices the old way until milestone 3; the
  analyzer reads the new store.

### Brokers and data accounts in milestone 1
- 2026-11-10 (Brian): milestone 1 has fee tables for Hang Seng Bank and Futu, and uses Futu
  and Alpaca as price sources. Interactive Brokers waits for later: no fee table now. His
  exact words are in the private file.
- 2026-11-10 (Brian, by saying "ok" to phases 2, 3 and 4 and settling phase 1 with the line
  above): the milestone 1 plan `docs/plans/2026-11-10-price-data-and-analyzer.md` is approved.
- 2026-11-10 (Brian): "git ignore any private info". Anything that says where Brian's money or
  shares are, which accounts he holds, his cash, his holdings or his personal circumstances
  goes under `docs/private/` or `data/`; git ignores both. Tracked docs keep the tool's design
  only. The repo on GitHub is public.
- 2026-11-10 (Brian): the Alpaca keys are in `.env` (inbox, Task 2.7) (Brian, 2026-11-10: "done").
- 2026-11-11 (Brian): milestone 3's test bench adds a long-short version of gate 3 for pairs
  signals, reported apart from the buy-only results. Short sales go through moomoo (Futu), and
  the cost includes moomoo's interest on borrowed shares (inbox, pairs question) (Brian,
  2026-11-11: "then allow shorting via moomoo, taking the charges interest into account").

### Portfolio report check (2026-11-11)
- The analyzer's report on the real portfolio (plan 2026-11-10, Task 3.5) is accepted as right. (Brian, 2026-11-11: "looks about right")
- Futu: the account application must be redone (HKID rejected); Task 2.8 keeps waiting. (Brian, 2026-11-11: "they rejected my HKID, not sure why, had to redo and wait again")

### News tab speed (2026-11-11, Task 4.2b)
- The News tab as fixed is accepted: 15 to 25 s on the first open after a restart, 4 to 8 s later; no warm-up at start-up and no prediction-model fit for now. (Brian, 2026-11-11: "ok")
- 2026-11-12, Brian (default): Futu OpenD (GUI 10.12.7208) runs on this PC under his Futu 牛牛 login, at 127.0.0.1:11111; Task 2.8 may load Futu prices while it runs. (Brian, 2026-11-12: "logged in")
