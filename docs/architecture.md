# Architecture

Two independent parts share the price cache and the CLI report:

1. The price-vs-own-history advisor (`market_data`, `price_analysis`, `indicators`,
   `validation`, `correlation`, `portfolio`, `transactions`, `recommendation`, `report`, `cli`).
2. The news event module (`stock_advisor/news/` plus two CLIs), described here.

## News data flow

```
sources -> store -> scoring -> categories -> events -> reactions -> model + window
        -> analysis -> news_cli / report column / dashboard News tab / notify (Telegram)
```

| Step | Module | What it does |
|---|---|---|
| Sources | `news/sources/*.py` | One adapter per source. Each has `name`, `fetch_recent()` and, if it has history, `fetch_range(start, end)`. All HTTP goes through `PoliteSession` (descriptive User-Agent, minimum gap, retry on 429 and 5xx). Adapters: `wikipedia_events`, `edgar`, `gdelt`, `guardian`, `nyt`, `yahoo`, `rss_feeds`. |
| Collect | `news/collect.py` | Runs adapters, stores items, keeps backfill cursors and per-source daily call budgets (Guardian and NYT 480 a day). One failing source logs and the rest continue. |
| Store | `news/store.py`, `news/models.py`, `news/settings.py` | SQLite file; ids are a hash of source plus URL, so repeats are ignored. `settings.py` reads secrets from `.env`. |
| Scoring | `news/scoring.py` | FinBERT tone (`ProsusAI/finbert`, tone = p_pos - p_neg) and a sentence embedding (`all-MiniLM-L6-v2`). Models load lazily, run on the CPU in batches of 64. |
| Categories | `news/categories.py` | Nearest seed-phrase centroid by embedding, with keyword overrides where the match is weak. Categories include trade_tariffs, monetary_policy, war_conflict, cyber_security, financial_crisis, geopolitical_tension, company_results and other. |
| Events | `news/events.py`, `news/article.py` | Clusters headlines into events (cosine similarity 0.60 to the event centroid, 12 h window, 48 h maximum span). High impact means a macro category with strong tone or three or more sources. `article.py` fetches the body of high-impact events, skipping paywalled domains and honouring robots.txt. |
| Reactions | `news/reactions.py` | Cumulative return paths per event and target: 1m, 5m, 15m, 1h, 4h and the 1st, 2nd, 3rd, 5th and 10th close. Uses 1m bars, then 60m bars, then daily bars. Missing data is NaN. Stocks also get a market-adjusted return. |
| Model | `news/model.py` | For each target and horizon: similarity-weighted mean reaction of the 20 most similar earlier events, plus a ridge regression on category, tone, source count, high-impact flag and 20-day volatility. Uses only earlier events. |
| Window | `news/window.py` | From the paths of similar earlier events, the median and quartiles of the peak time, shown as "exit within X-Y". |
| Backtest | `news_backtest_cli.py` | Walk-forward by calendar year. Writes `results.json`. A target and horizon is `proven` when n >= 30, abs(t) >= 2 and hit rate > 0.5. |
| Analysis | `news/analysis.py` | Shared layer that returns data and prints nothing: `NewsAnalyzer`, `process_new` (score, categorize, cluster), and the watcher's source groups. |
| Output | `news_cli.py`, `report.py`, `app.py`, `news/notify.py` | CLI text, a `news` column in the report, the dashboard News tab, Telegram alerts. |

Rules the output layers keep: unproven predictions only warn; Guardian items show the headline
and link only, never the stored summary.

## Tables in `news.db`

| Table | Content |
|---|---|
| `items` | one row per headline: id, source, `published_at` (UTC text), title, url, summary, symbols, language, body, `time_precision` (`exact` or `day`) |
| `scores` | per item: tone values, category, embedding (BLOB), `event_id`, `high_impact` |
| `events` | per event: start time, category, title, item and source counts, `high_impact` |
| `api_calls` | calls made per source and UTC day (daily caps) |
| `backfill_cursor` | how far each source's backfill has got |
| `sent_alerts` | event ids already alerted or suppressed, so no event is alerted twice |

## Files and caches (all under `data/cache/`, gitignored)

| Path | Content |
|---|---|
| `prices/<symbol>.parquet` | daily bars, fresh for 12 hours |
| `prices_intraday/<interval>/<symbol>.parquet` | 1m and 60m bars, merged over time; `recorder_log.txt` |
| `news/news.db` | the store above |
| `news/model/reactions.parquet` | reaction table cache; new events are added on each backtest run |
| `news/model/results.json` | backtest results read by the CLI, report and dashboard |
| `news/backfill_status.json`, `backfill.lock`, `backfill_log.txt` | backfill progress, lock, log |
| `news/watcher_log.txt` | watcher output |

## Scheduled tasks (Windows Task Scheduler)

| Task | Trigger | Runs |
|---|---|---|
| `stock_advisor_minute_recorder` | daily 22:00, runs a missed run at next login | `scripts/record_minutes.py` |
| `stock_advisor_news_backfill` | daily 02:00, no time limit | `scripts/backfill_news.py` |
| `stock_advisor_news_watcher` | at login, no time limit | `scripts/run_watcher.ps1`, which runs `news_cli --watch` in a loop |

Each register script finds the conda env's python at registration time and replaces an existing
task of the same name.

## Watcher

`news_cli --watch` polls EDGAR, RSS (without CISA) and yfinance headlines every 60 s. CISA,
Guardian, NYT and GDELT run every 15 min; GDELT runs on a side thread and is skipped while the
backfill is using it. New items are scored and clustered, the model refreshes every 6 hours, and
only new high-impact events print and go to the Telegram notifier. The notifier alerts when a
target has a predicted 1-day move of at least 1.5%, at most 10 alerts an hour (rest recorded as
suppressed), and never logs the bot token.

## Concurrency

SQLite allows one writer at a time. The backfill, the watcher and interactive commands share
`news.db`:

- `NewsStore` connects with a 30 s timeout and `analysis.open_store` sets `busy_timeout` to
  30 s, so a reader or writer waits instead of failing at once.
- `news_backtest_cli` opens the store read-only (`mode=ro`).
- The backfill takes `backfill.lock` (holds its pid; a lock left by a dead process is replaced),
  so a second backfill exits at once. The scheduled task also uses `MultipleInstances IgnoreNew`.
- The watcher reads `backfill_status.json` only. It never takes the lock.
- Never run two GDELT callers at once: GDELT locks out for a minute or more after a burst.
- `NewsStore` sets `PRAGMA journal_mode=WAL` on connect (the mode persists in the file). Readers
  run while a writer holds a transaction. Writers still take turns. The `-wal` and `-shm` side
  files sit next to `news.db`; copy all three together when taking a backup.
