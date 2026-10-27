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

## Data and secrets

- 2026-10-27 (Brian): include as many free news sources as possible.
- 2026-10-27 (Brian, accepted default): use only official feeds, APIs and filings; skip sites
  whose terms forbid scraping, and skip paywalled articles.
- 2026-10-27 (Brian, accepted default): SEC EDGAR requires a contact email in requests; Brian
  supplies the address to use. No address is sent without his say.

## Behaviour and rules

- 2026-10-27 (Brian): score headlines only; fetch and read the full article only when a
  headline is high impact.

## UI

- 2026-10-27 (Brian): news output appears in both the CLI report and the Streamlit dashboard.

## Repository

- Remote: https://github.com/bpy13/stock_advisor (existing).
