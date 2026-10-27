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

## UI

- 2026-10-27 (Brian, Guardian key application): Guardian content is displayed only as the
  headline plus a link back to the Guardian. The stored trailText summary is used for scoring
  only and never shown in the CLI, dashboard or alerts.

- 2026-10-27 (Brian): news output appears in both the CLI report and the Streamlit dashboard.

## Repository

- Remote: https://github.com/bpy13/stock_advisor (existing).
