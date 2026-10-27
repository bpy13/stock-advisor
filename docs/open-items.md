# Open items

As of 2026-10-27. Tick off, or move to `decisions.md` when settled. A bug that will be fixed goes
here; a limit or trap we live with goes in `known-issues.md`. Each item in one place only.

## Blockers

## Waiting on the user

- Guardian and NYT API keys in `.env` (`GUARDIAN_API_KEY`, `NYT_API_KEY`). Until then those
  two sources are built and tested from fixtures, but not backfilled.
  - NYT: done 2026-10-27 (live archive and Top Stories, real fixtures; old months use
    "Business Day", already covered). Archive months run up to ~14 MB each.
  - Guardian: done 2026-10-27 (live, real fixture, archive from 1990-02-08, limits 60/min and
    500/day).

- Google News RSS dropped: its robots.txt disallows /rss for every crawler. Brian may
  overrule the skip; the adapter would take about an hour to build.
- HKEXnews dropped: the HKEX Terms of Use (section 5) forbid scripted access and data mining.
  The helper read the terms through a summarising fetch, not the raw page. Brian could ask
  info@hkex.com.hk for written permission; until then HK filings are not collected.

## Pending work

- yfinance `Ticker.news` returns nothing (Yahoo's endpoint answers 404); the Yahoo adapter
  uses the `yf.Search` fallback. Re-check after a yfinance upgrade. Search finds no headlines
  for 2800.HK and 3033.HK; Task 2.2 decides whether they stay as price targets (they still
  have prices; only headlines are missing).
- RSS feeds (Task 1.10): 12 feeds kept on robots.txt grounds. Still to do: read the
  Investing.com and SCMP terms for bans on automated feed access; check whether Dow Jones
  terms allow MarketWatch feeds; find working Yahoo, Nasdaq and US Treasury feed URLs. Poll
  CISA (5.7 MB per fetch) at most every 15 minutes.

- News event module: see `docs/plans/2026-10-27-news-event-module.md`.

- GDELT: all 168 live items share one published_at (2026-10-27 05:15 UTC), so the time
  parsing is wrong. Fix dispatched with Phase 2.
- GDELT returns 429 under a full 10-query pass (one query gave up in the live run). The
  watcher polls it every 15 min; the Phase 4 backfill needs longer waits.
- EDGAR live feed gave 0 allowlisted 8-Ks in one poll. Judge the allowlist after several
  days of polling. HK holdings are not passed to EDGAR (HK companies don't file 8-Ks).
- EDGAR `fetch_range` reads quarterly indexes in form-type order, so an interrupted
  mid-quarter backfill could skip filings; Task 4.1 must keep EDGAR's cursor per quarter.

- Yahoo has 2828.HK daily prices only from 2024-04-24 (the ETF listed in 2003), so its
  backtest sample is short. Goes into known-issues in Phase 6.

## Later

- NYT business/world RSS feeds need no key and could join the RSS adapter. (Top Stories is
  now Task 1.12.)
- "Public attention" signal from the NYT Most Popular API: when a market story reaches
  most-viewed, ordinary investors have caught on. No history in the API, so it must be
  recorded for months before it can be backtested.
