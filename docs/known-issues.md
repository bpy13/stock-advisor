# Known issues

Limits and traps we live with. A bug that will be fixed goes in `open-items.md` instead.

## Data limits

- **Date-only precision.** Wikipedia Current events and old EDGAR filings carry a date, not a
  time. They are stored with `time_precision="day"` and used only for the 1-day and longer
  horizons, never for minute or hour reactions.
- **Yahoo intraday depth.** 1-minute bars reach back about 30 days (7 days per request) and
  60-minute bars about 730 days. Older events get daily reactions only. The nightly recorder
  (`record_minutes.py`) builds our own minute history from the day it starts running.
- **2828.HK has a short history.** Yahoo has daily prices only from 2024-04-24, so its backtest
  sample is small.
- **GDELT.** It starts around 2017 and returns 429 under bursts, then locks the caller out for a
  minute or more. The backfill waits longer between calls, and only one GDELT caller may run at a
  time.
- **Guardian and NYT daily caps.** Both APIs allow 500 calls a day; we stop at 480. The full
  Guardian archive (from 1990) takes about a week of daily runs and the NYT archive about a day.
  The daily backfill task resumes where the last run stopped.
- **`yfinance` `Ticker.news` is broken.** Yahoo's endpoint answers 404, so the Yahoo adapter uses
  the `yf.Search` fallback. Search finds no headlines for 2800.HK and 3033.HK (they still have
  prices). Re-check after a yfinance upgrade.
- **Per-page download errors.** Some adapters log and skip a failed page, so history can have
  small gaps. The status file shows the last error per source.

## Sources we skipped

- **Google News RSS.** Its robots.txt has `Disallow: /` for every crawler.
- **HKEXnews.** The HKEX Terms of Use (section 5) forbid scripted access and data mining. So
  Hong Kong company filings are not collected, and HK company news comes only from Yahoo and
  RSS feeds. Written permission from HKEX would reopen this.
- Paywalled articles are never fetched. Sites whose terms forbid scraping are skipped.

## Approximations in the model

- **Reaction start.** An event outside trading hours starts at the next session's open. The 60m
  bars are hourly, so the 1h and 4h points are approximate. For daily data the cutoff between
  "before the close" and "after the close" is approximate.
- **Category thresholds are untuned.** The strong (0.50) and minimum (0.30) match thresholds and
  the seed phrases were set on a small sample. Some borderline headlines land in the wrong
  category.
- **The high-impact share is high.** About one event in five is flagged on the live sample,
  mostly lone headlines with strong tone, and financial_crisis is over-assigned. The alert rule
  adds a second filter (predicted move of at least 1.5%).
- **Syndicated copies** of one wire story inflate the source count of an event.
- **Small effects.** Most news is priced in within seconds, so many predictions will stay
  `unproven`. That is the honest result, not a bug.

## Running it

- **Task Scheduler restart.** Its "restart on failure" only covers a failed launch, not a crash
  while running. `scripts/run_watcher.ps1` loops and restarts the watcher after 60 s on a
  non-zero exit code. A clean exit (code 0) ends the loop.
- **The watcher only runs while you are logged in.** It starts at login and stops at logout.
- **SQLite still has one writer.** `news.db` uses WAL mode, so readers no longer block on the
  backfill's writes. Two writers still take turns: a writer waits up to 30 s for the lock, so
  a long write can make another writer fail with "database is locked". WAL adds `news.db-wal`
  and `news.db-shm` files beside the database. See `architecture.md`.
- **A cold `news_cli --collect`** can wait many minutes on GDELT rate-limit pauses. Watch mode
  runs GDELT on a side thread, so it does not stall.
- **HK holdings and EDGAR.** HK companies do not file 8-Ks, so HK holdings are not passed to
  EDGAR.
- **Console encoding.** Under `conda run` in Windows PowerShell 5.1, characters such as the
  warning sign can print as garbage. Running python directly prints them correctly.
