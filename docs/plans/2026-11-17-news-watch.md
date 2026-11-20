# Plan: news watch that filters (2026-11-17)

Milestone 2 of `docs/milestones.md`. Written for workers who have not seen the planning chat.
Status: approved (Brian, 2026-11-17: "approve").

## Goal
Every stored news story is either linked to the watchlist stocks or drivers it concerns, or
dropped. Claude Haiku labels each linked story (relevant or not, event type, new or repeat,
severity). New free sources feed the watch. A labelled history exists for milestone 3's
regression. The dashboard News tab shows the labelled stories per holding, and the old "high
impact" flag is gone. No signal, forecast or alert is built here.

## Approach
1. A linker maps a story to watchlist symbols and drivers from a names file (company names,
   short names, tickers, driver keywords). A story with no link is marked dropped, not deleted.
2. A labeller sends one linked story to Claude Haiku and stores four labels. Every call's
   tokens and price are recorded, and a monthly ceiling stops paid calls.
3. A 200-story sample runs first. Its measured cost and its labels go to Brian. Nothing larger
   runs before his go.
4. Source adapters are added beside the existing ones: US filings by event type for every US
   watchlist stock, US insider trades, short-selling files, and Hong Kong and China feeds
   whose terms allow it. These do not wait for the sample.
5. After Brian's go: the watcher labels new linked stories, and the stored history is labelled
   once through the job queue after a separate quote.
6. The News tab shows labels per holding. `high_impact` is removed everywhere.

## Constraints (verbatim from `docs/decisions.md`)
- 2026-10-30 (Brian): severity scoring may use the Claude API. A cost quote comes before any
  paid run.
- 2026-11-10 (Brian, accepted default): Claude Haiku classifies news stories (relevant or not,
  event type, new or repeat, severity), replacing FinBERT's tone as the filter, after a
  200-story sample and Brian's go on the measured cost. The API key stays Brian's.
- 2026-11-10 (research finding, not a decision): HKEX's terms of use forbid scripted access to
  all its websites, so the 2026-10-27 rule (skip sites whose terms forbid it) keeps HKEX
  announcements, directors' dealings and Stock Connect files out.
- (Brian): "free tier news data is sufficient, what we need is stock data for inference".
- 2026-11-17, Brian: milestone 2 is approved as written; the 200-story sample with its
  measured cost still needs his approval before any larger paid run. (Brian, 2026-11-17: "yes")
- Standing allowance (orchestrator skill): paid API calls with a key the project holds, up to
  US$10 per task, estimate first and real cost on the board after.

## Acceptance criteria (the milestone's "done when" lines)
- A. Each story is linked to the watchlist stocks or drivers it concerns, or dropped. (Tasks 5.1, 5.2)
- B. Haiku labels each linked story; the 200-story sample with its measured cost came first and
  Brian approved the cost. (Tasks 5.3, 5.4, 5.5, 7.1)
- C. A labelled history exists; its one-time cost was quoted and approved before the run.
  (Tasks 7.2, 7.3)
- D. New free sources feed the watch: US filings by event type, US insider trades, US and Hong
  Kong short-selling files, Hong Kong and China feeds whose terms allow it. (Tasks 6.1 to 6.4)
- E. The News tab shows the labelled stories per holding; "high impact" is gone. (Tasks 8.1, 8.2)

## Facts a worker needs (checked 2026-11-17)
- News code: `stock_advisor/news/` (adapters in `news/sources/`, all on `PoliteSession`;
  collector `news/collect.py`; store `news/store.py`; ids and dedupe `news/models.py`).
- Store: SQLite `data/cache/news/news.db` (about 6 GB, WAL, ONE writer, waits up to 30 s);
  table `items` has `symbols` (JSON), filled today only by the Yahoo and EDGAR adapters.
- Watchlist: `config/watchlist.csv` (`symbol,market,kind,name`), loaded by
  `stock_advisor/watchlist.py`; holdings join at run time. The six drivers are its rows of
  kind `driver` and are defined in `stock_advisor/risk.py`.
- `high_impact` today: computed in `news/events.py`; stored in `scores.high_impact` and
  `events.high_impact`; used in `model.py`, `notify.py`, `library_snapshot.py`,
  `scripts/recategorize_news.py`, `backfill_news.py`; shown in `app.py` (the "High-impact only"
  checkbox and the "HIGH IMPACT" prefix).
- No Claude code, SDK or key name exists in the repo yet.
- Dashboard: Streamlit, `app.py`, News tab `_render_news_tab`, port 8502.
- The watcher (`news_cli --watch`, started at logon) and the 02:00 backfill task write
  `news.db`. A live program runs the old code: a task that changes the watcher restarts it
  through its scheduled task (never as the worker's own child) and reads `watcher_log.txt`.
- Tests: `conda run -n stock_advisor python -m pytest -q`; lint: `conda run -n stock_advisor
  ruff check .`. CI runs Python 3.12 with `-m "not slow"`, without torch or transformers: new
  tests must pass there, so every Claude call in a test goes through a fake client.
- A worker's checkout has an empty `data/`; the real data is in
  `C:\Users\brian\OneDrive\Documents\workspace\repo\stock_advisor\data`. Read it from there;
  write `news.db` only through the store's own functions and never while a test runs.
- Prices read on 2026-11-10 (`docs/research/2026-11-10-quant-landscape.md`): Haiku 5.5 US$0.10
  in and US$0.50 out per million tokens, batch jobs half. Task 5.3 reads the current price
  page again and records it. Model id `claude-haiku-5-5`.

## Shared resources
`news.db` (one writer), `backfill.lock`, port 8502, GDELT (one caller at a time), the SEC's
fair-access limit (10 requests a second, contact e-mail from `.env`), Futu OpenD on 11111 (not
used here). Two tasks marked `[parallel-ok]` never edit the same file; schema changes go only
through Task 5.2's migration and the task that names its own new table.

## Phase 5 – Linking and the sample (sonnet)

- [x] **Task 5.1: the names file and the linker** (opus) `[parallel-ok]`
  - Result (slot 1, 2026-11-17): 1,109 alias rows for 205 symbols and the six drivers; 96 tests pass (64 linked headlines, 21 traps); 614 tests pass in all, ruff clean. Linking takes about 3.5 ms a story on the busy PC (a prefix-tree regex; the flat one took 10 ms). No `hans` rows were written: the working agreement forbids writing Simplified Chinese; the linker accepts them if Brian adds some. Weak names ("Apple", "Meta", "小米") need a cue word or another alias; numeric HK codes link only after "HKEX:" or as "(00700)".
  - Files: create `config/aliases.csv` (`symbol,alias,kind`: full name, short name, ticker
    forms such as "0700.HK", "700 HK", "Tencent", "騰訊"; driver keywords for the six drivers),
    `stock_advisor/news/link.py`, `tests/test_news_link.py`; a script
    `scripts/build_aliases.py` that drafts the file from `config/watchlist.csv`.
  - Done when: tests pass on a fixture of at least 60 hand-written headlines: each expected
    symbol or driver is found, and 20 trap headlines link to nothing ("Apple harvest", "Meta
    analysis", a bank named in a street address). `link(title, summary, body)` returns symbols,
    drivers and the matched text. Matching is on word boundaries; a ticker of one or two
    letters links only with "$" or an exchange prefix. Chinese aliases are Traditional as used
    in Hong Kong; a Simplified alias is added only as a second row marked `kind=hans`.
  - Notes: holdings join at run time as in `watchlist.py`; nothing about the holdings is
    written to a tracked file.

- [ ] **Task 5.2: links stored for every story** (slot 1 only) (code done by slot 2 on 2026-11-17; left: the history run through jobq and the watcher restart, both in the main folder) (waiting: link history job 276 (254 failed 2026-11-20 on "database is locked" beside job 199; queued again as 276 after 199) in the cpu queue (was 200; moved behind mahjong job 253 on 2026-11-19, not started before); watcher poll not yet confirmed) — needs: Task 5.1
  - Files: modify `stock_advisor/news/store.py` (migration: `items.drivers` JSON,
    `items.link_state` = linked / dropped, `items.linked_at`), `news/collect.py` (new stories
    are linked on insert; the Yahoo and EDGAR symbols are kept and merged),
    `scripts/link_history.py` (links the stored history in batches, resumable by id);
    `tests/test_news_store_links.py`.
  - Done when: tests pass; the history run goes through `jobq.ps1` in the cpu lane and its log
    ends with counts: stories total, linked, dropped, and linked per symbol for the 20 symbols
    with the most stories. A report `data/reports/news-links-<date>.md` holds those counts and
    30 random linked and 30 random dropped headlines for a reading check. The watcher is
    restarted through its scheduled task and `watcher_log.txt` shows a poll without an error.
  - Notes: a dropped story stays in `items`; nothing is deleted.
  - Status (slot 1, 2026-11-17 15:15): history run queued as job 200, re-added as job 254 on 2026-11-19 (cpu lane, script `data/cache/news/link_history_job.ps1`, runs `scripts/link_history.py`; resumable). Check: `jobq.ps1 status`, `jobq.ps1 log 200`; the log must end with counts, and `data/reports/news-links-<date>.md` must exist. Watcher: started through task `stock_advisor_news_watcher` at 15:09 (new code, python pid 7792); after 4 minutes `watcher_log.txt` had no new line (python at 1 s CPU, log still ends 2026-11-11 00:46). Left: read `watcher_log.txt` for a poll without an error (restart the task if still silent), then tick. Jobs 199 and 200 sat queued behind other cpu jobs.
  - Status (slot 2, 2026-11-17): code and 5 tests done (store migration and `add_items(items, linker)`, `collect.py` and `scripts/backfill_news.py` link on insert, `scripts/link_history.py` with report). Left for slot 1 in the main folder (real news.db and the scheduled tasks): pull main, then `jobq.ps1 add -Lane cpu -Script <job.ps1>` running `python scripts/link_history.py` (resumable; log ends with counts; report `data/reports/news-links-<date>.md`); restart the watcher through its scheduled task and check `watcher_log.txt` shows a poll without an error; then tick.

- [x] **Task 5.2b: the news watcher polls again, and stays up** (opus) (slot 1 only) `[parallel-ok]`
  - Symptom (orchestrator, 2026-11-17 15:20, read from the files): `data/cache/news/watcher_log.txt` was last written on 2026-11-11 00:46 (its last lines are GDELT 429 retries), so the watcher has logged nothing for six days. Slot 1 restarted the scheduled task `stock_advisor_news_watcher` at 15:06 for Task 5.2: python pid 7792 (started 15:09:19) had used 1.4 s of CPU after five minutes and the log is still silent. The task runs at Task Scheduler priority 7 (below-normal CPU, low disk priority).
  - Lead, not proven: gym-coach Task 14e found the same picture today (a priority-7 logon task stuck in heavy imports on a busy PC; fixed by logging before the heavy imports and registering the task at priority 4). Prove the cause here before changing code: where is the process stuck now, and why did the log stop on 11 Nov (a hang inside the GDELT wait, a dead process with the wrapper loop gone, or the task not started after a reboot).
  - Files: `scripts/run_watcher.ps1`, `scripts/register_watcher_task.ps1`, `stock_advisor/news_cli.py` and the watcher loop as the cause requires; tests for any logic change (failing test first).
  - Done when: the cause is written here in one paragraph with its evidence; the watcher writes a "starting" line before its heavy imports and one line per poll (stories fetched per source), so silence always means stuck; a stuck or dead watcher is restarted without a person (say how); the scheduled task is registered again and restarted through Task Scheduler (never as your own child) and `watcher_log.txt` shows two polls in a row without an error within 15 minutes, checked by you after the restart; tests and ruff pass. If the restart or the re-register is refused by the permission check, write the exact commands under this task, mark it as waiting on Brian's restart in the usual form, and end blocked.
  - Cause (slot 1, 2026-11-17): two separate faults. (1) On 11 Nov the watcher died with its wrapper and nothing restarted it. Evidence: the log's last line is 00:46:43 (a GDELT retry on the side thread); the main loop's once-a-minute "cycle:" lines stop at 00:44:44 too; there is no "watcher exited" wrapper line and no memory-guard line; `news.db` holds no rss or gdelt story after 10 Nov UTC, so polling stopped, not only logging. No reboot since 31 Oct, and the task started a new instance at 15:06 under IgnoreNew, so no old instance was running (orchestrator, from the earlier worker's commands: no stop or kill before that start). The task only started at logon, so six days passed. Why the tree ended is not provable now (Task Scheduler history is off). (2) The 15:06 start was starved, not hung: at priority 7 (below normal) beside two CPU queue jobs, python used under 6 s of CPU in 18 minutes and took 6.5 minutes to its first log line. Also found: `Stop-ScheduledTask` kills only the outer conhost; the wrapper, cmd and python kept running.
  - Result (slot 1, 2026-11-17): `run_watcher.ps1` writes a "wrapper: starting" line before python starts, and kills and restarts a watcher whose log has not grown for 30 minutes (checked through an open handle each minute; smoke-tested with a hanging fake and a 1-minute limit: killed and restarted). A dead wrapper is restarted by the task's new 15-minute repeat (IgnoreNew makes it a no-op while one runs). Task priority 4. Each poll logs "cycle: ... fetched edgar 1, yahoo 0, rss 284" (and "slow poll: ... fetched ..."); new test `test_watch_logs_one_line_per_poll_with_stories_fetched_per_source`. Re-registered and restarted through Task Scheduler at 15:34 (the old tree killed with taskkill); python reached its first line in 2 s; polls at 15:37:31 and 15:40:01 without a cycle error. Yahoo still fails per symbol (since 3 Nov; see `docs/open-items.md`), so each poll takes about 2.5 minutes. 640 tests pass, ruff clean.

- [x] **Task 5.2c: Yahoo news returns stories again, or is switched off cleanly** (done 2026-11-17: Brian restarted the watcher at 16:14 (Brian: "done"); orchestrator read watcher_log.txt: polls at 16:16:17 and 16:17:44 both show "yahoo 184", no YFDataException line after the restart) (opus) `[parallel-ok]` (slot 1 only) (code done by slot 2 on 2026-11-17; left: the live watcher check in the main folder) (was waiting on Brian's restart of the watcher) — needs: Task 5.2b
  - Symptom (found by slot 1 in Task 5.2b, 2026-11-17, from `data/cache/news/watcher_log.txt`): every Yahoo symbol logs "Yahoo news for X failed (YFDataException)"; the same lines appear since 3 Nov (per-day counts in `docs/open-items.md`; 10,000 to 19,000 a day on 7-10 Nov); each poll fetches "yahoo 0" and takes about 2.5 minutes instead of 60 seconds. So Yahoo news has returned nothing for two weeks.
  - What: prove the cause first (a changed Yahoo endpoint or cookie, the installed yfinance version, a rate limit or block on this address); reproduce it in a failing test with a recorded response. Then either make the fetch work again within Yahoo's terms as `docs/decisions.md` reads them, or, if it cannot work, switch the Yahoo news source off by a setting, with one log line per poll and no per-symbol retries, and say in `docs/known-issues.md` what is lost (which symbols had no other source).
  - Files: `stock_advisor/news/sources/` (the Yahoo source), its tests, `docs/known-issues.md`; the main folder is not needed for the code, only for the live check.
  - Done when: the cause is written here with its evidence; tests pass and ruff is clean; the live watcher log (slot 1 reads it after the watcher is restarted through its scheduled task) shows either "yahoo N" with N above 0 in two polls, or no Yahoo failure lines and a poll time back near 60 seconds. If the live check needs the main folder and you are not slot 1, leave that last step for slot 1 in the usual form.
  - Cause (slot 2, 2026-11-17, checked): yfinance 1.7.0's `Ticker.news` posts to `finance.yahoo.com/xhr/ncp`, which answers HTTP 404 with an HTML page (4,567 bytes) that contains "Will be right back". yfinance's `get_news` treats that text as "Yahoo is down" and raises YFDataException (`yfinance/base.py` line 618). The adapter called `Ticker.news` first and fell back to `yf.Search` only on an empty list, so the exception skipped Search for every symbol. Inferred: before 3 Nov the 404 page lacked that text, so yfinance returned an empty list and the fallback ran. Not a block or rate limit: `yf.Search` from this PC returned 18 to 20 stories each for AAPL, MSFT, NVDA, XLK, XLF, XLE, ^HSI and ^GSPC. Not a yfinance upgrade: 1.7.0 installed 27 Oct, unchanged.
  - Fix (slot 2): the adapter calls `yf.Search` only (one request per symbol instead of two failing ones plus crumb retries). Recorded response: `tests/fixtures/news/yahoo/ncp_404.html`; `tests/news/test_yahoo.py` shows yfinance raising on it, and the old adapter failed the new test with the watcher's exact log line. Tests and ruff pass. Live run of `YahooNewsSource().fetch_recent()` from this worktree, twice: "yahoo 94" in 11.5 s and in 6.0 s. Lost: Search finds no headlines for Hong Kong tickers (0700.HK, 0005.HK, 9988.HK, 2800.HK, 3033.HK all 0), written in `docs/known-issues.md`.
  - Left for slot 1: after the watcher restarts through its scheduled task on the new code, read `data/cache/news/watcher_log.txt`. Expect "yahoo N" with N above 0 in two polls and no "Yahoo news for X failed (YFDataException)" lines. Then tick this task.
  - Slot 1, 2026-11-17 15:57: the watcher (python pid 13040, started 15:34) still runs the old code; its log shows "Yahoo news for X failed (YFDataException)" at 15:56. The wrapper restarts only a dead or quiet watcher, so it will not load the fix by itself. Slot 1's restart was refused by the permission check; the orchestrator asked Brian.
  - Brian's restart (PowerShell): `Stop-ScheduledTask -TaskName stock_advisor_news_watcher`, then `Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'news_cli --watch|run_watcher.ps1' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }`, then `Start-ScheduledTask -TaskName stock_advisor_news_watcher`.
  - Then a slot-1 run reads the log: `Get-Content data\cache\news\watcher_log.txt -Tail 200 | Select-String 'yahoo|cycle'`, expects "yahoo N" above 0 in two polls and no YFDataException lines, and ticks the task.

- [x] **Task 5.3: the labeller, with cost recording and a ceiling** (opus) `[parallel-ok]`
  - Files: create `stock_advisor/news/label.py`, `tests/test_news_label.py`; modify
    `news/store.py` (new table `labels`: item id, relevant, event_type, novelty, severity,
    model, prompt version, tokens in and out, cost in US$, labelled_at; new table `llm_calls`
    is not needed if `api_calls` can hold tokens and cost: say which was chosen),
    `requirements.txt` (`anthropic`), `.env.example` (`ANTHROPIC_API_KEY=`, name only).
  - Done when: tests pass with a fake client: one story in gives one stored label row with
    tokens and cost; a malformed answer is retried once and then stored as `error`, never
    guessed; a month's cost at the ceiling (setting, default US$10) stops every paid call and
    says so in the log; a story already labelled with the same prompt version is not sent
    again. The label is requested as structured output: `relevant` yes/no; `event_type` one of
    a fixed list (results, guidance, deal, regulation, legal, management, product, macro,
    rating, capital, other); `novelty` new/repeat; `severity` 1 to 3. The prompt holds the
    story's title, summary, the linked symbols and their names, nothing about Brian's holdings.
  - Notes: read the current Claude API price page and the SDK's structured-output docs first;
    record the price read and its date in the module and in `docs/decisions.md`'s research
    notes via the hand-back (do not edit `docs/decisions.md`). No real API call in this task.
  - Hand-back (slot 2, 2026-11-17): price page read 2026-11-17 (platform.claude.com/docs/en/about-claude/pricing):
    Haiku 5.5 US$0.10 in, US$0.50 out per million tokens up to 100,000-token prompts (batch
    US$0.05 and US$0.25); recorded in `label.py`. For `docs/decisions.md` research notes.
    Chosen: no `llm_calls` table and `api_calls` unchanged; each `labels` row holds its own
    tokens and cost (a retry included), and the month's spend is their sum. Ceiling setting:
    `LABEL_MONTHLY_CEILING_USD` in `.env` (default 10). A story with an `error` row is not
    sent again under the same prompt version. Requests use structured output
    (`output_config.format` json_schema) with thinking off; the request shape is checked only
    against the installed SDK (anthropic 2.9.0), so Task 5.5's first real call is its first live test.

- [x] **Task 5.4: Brian's API key is in `.env`** (checkpoint) (slot 1 only) — needs: Task 5.3
  - Result (slot 1, 2026-11-17): checked `ANTHROPIC_API_KEY` in the main folder's `.env`: non-empty (True). Value not printed.
  - Done when: `ANTHROPIC_API_KEY` is set in
    `C:\Users\brian\OneDrive\Documents\workspace\repo\stock_advisor\.env` by Brian. The worker
    checks only that the name has a non-empty value (`python -c` printing True/False), never
    prints, copies or logs the value, and posts the question to `docs/inbox.md` if it is empty.
  - Notes: Brian (2026-11-17): "done" (he put the key in). The orchestrator found one non-empty `ANTHROPIC_API_KEY` line in that file on 2026-11-17 by counting lines, without reading the value; the worker repeats the check and ticks.

- [ ] **Task 5.5: the 200-story sample and its measured cost** (checkpoint) (slot 1 only) — needs: Task 5.2, Task 5.4
  - Files: create `scripts/label_sample.py`; report `data/reports/label-sample-<date>.md` and
    a copy of its text (no holdings) in `docs/study-results/label-sample.md`.
  - Done when: an estimate is written on the board first (200 stories at the measured mean
    length; it must be under US$1, else stop and ask). Then 200 linked stories are labelled:
    100 from the last 30 days and 100 spread over the history, across sources, fixed seed. The
    report holds: the real cost and tokens; cost per story; the cost per month of live
    labelling at the last 30 days' linked-story rate; the cost of labelling the whole linked
    history, plain and as a batch job; the label counts; 40 stories with their labels for
    Brian to read; how many of the 200 Haiku called not relevant. The question "approve this
    cost and these labels?" goes to `docs/inbox.md`; the task is marked waiting.
  - Notes: Brian's approval covers Tasks 7.1 and 7.2. If the labels read wrong, the prompt
    changes and the sample is repeated (another US$1 at most) before he is asked again.

## Phase 6 – New free sources (sonnet)
Each task reads the source's terms of use and robots.txt first and writes what it found into
its hand-back for `docs/decisions.md`. A source whose terms forbid scripted access is not
built: the task records that in `docs/known-issues.md` and is ticked with that result. Every
adapter uses `PoliteSession`, stores through `news/store.py` or its own table named below, is
linked by Task 5.1's linker where it carries a company, and has tests on saved fixtures (no
network in tests).

- [x] **Task 6.1: US filings by event type for every US watchlist stock** `[parallel-ok]` (slot 1 only)
  - Result (slot 1, 2026-11-17): live fetch of 2026-11-13: 101 US tickers, 100 CIKs (the log lists the one without); 5 filings stored with item numbers (e.g. AMT 1.01/2.03/9.01, GS 5.03), none from the old 10 tickers; 3.7 s, inside the SEC limit.
  - Status (slot 3, 2026-11-17): code and tests done (new column `items.event_items` JSON, added by one idempotent ALTER in `NewsStore._migrate`, orchestrator-approved; Task 5.2 must keep it when it adds its own columns; `NewsItem.event_items`; allowlist = US watchlist stocks + holdings + old 10). Left for slot 1 (needs `.env` SEC_CONTACT_EMAIL): `python scripts/check_edgar_day.py <past weekday>`, read that tickers without a CIK are logged and filings exceed the old 10-ticker count; then tick.
  - Files: modify `stock_advisor/news/sources/edgar.py`, `news/collect.py` (the allowlist
    becomes every US watchlist symbol with a CIK), tests.
  - Done when: tests pass: an 8-K is stored with its item numbers (for example 2.02 results,
    5.02 officer change, 1.01 material agreement) as `event_items`; the CIK map covers every
    US watchlist stock or lists the ones without a CIK in the log. A live fetch of one day
    stores filings for more than the old 10-ticker list, inside the SEC's request limit.

- [ ] **Task 6.2: US insider trades (Form 4)** `[parallel-ok]` (slot 1 only) (waiting: history job 199 in the cpu queue)
  - Status (slot 1, 2026-11-17 15:05): live day 2026-11-13 loaded 43 rows; the rerun added 0 (no duplicates). History load queued as job 199 (cpu lane, script `data/cache/news/insider_history_job.ps1`, runs `scripts/load_insider.py --history`). Check: `jobq.ps1 status`, `jobq.ps1 log 199`; the log must end with `rows per trade year`. Then tick. The live day is not yet wired into the watcher or backfill task. Run the script with PYTHONPATH set to the repo.
  - Status (slot 4, 2026-11-17): code and 12 tests done in 5719ddd (`insider.py`, `scripts/load_insider.py`, table `insider_trades` created by `InsiderTrades`; 508 tests pass, ruff clean). Left to do in the main folder (needs .env and the real news.db): `python scripts/load_insider.py --history` through jobq (cpu lane), then `--day <date>`; check the log ends with rows per year and a rerun adds no duplicate; then tick. The live day is not yet wired into the watcher or backfill task.
  - Files: create `stock_advisor/news/sources/insider.py`, `tests/test_insider.py`; new table
    `insider_trades` (symbol, filer, role, trade date, filed date, code, shares, price, value,
    10b5-1 flag, accession number unique).
  - Done when: tests pass on saved Form 4 XML (a purchase, a sale, an option exercise, an
    amended filing that replaces its original). The SEC insider data sets from 2006 load the
    history for the US watchlist through `jobq.ps1` (cpu lane) and the log ends with rows per
    year; the live feed adds one day's filings without a duplicate.

- [x] **Task 6.3: short-selling files, US and Hong Kong** `[parallel-ok]`
  - Files: create `stock_advisor/news/sources/short_selling.py`, `tests/test_short_selling.py`;
    new table `short_selling` (symbol, date, source, short volume or position, total volume
    where given).
  - Done when: FINRA's terms are read and recorded; if allowed, the daily short-volume files
    and the twice-monthly short-interest files load for the US watchlist. The SFC weekly
    short-position CSVs from 2012 load for the Hong Kong watchlist (terms already read: personal
    use allowed). Tests pass on saved files, including a week the SFC published late. A
    scheduled fetch is added to the existing backfill task, not a new scheduled task.

- [x] **Task 6.4: Hong Kong and China feeds whose terms allow it** `[parallel-ok]`
  - Files: modify `stock_advisor/news/sources/rss_feeds.py`, its tests, `docs/known-issues.md`.
  - Done when: the terms of news.gov.hk, the SFC's RSS, the Census and Statistics Department
    and CNA are read; the allowed ones are added and one live poll stores stories from each.
    The Investing.com and SCMP terms (open item) are read: a feed whose terms forbid automated
    access is removed and its stored stories are kept. The file's comment lists every rejected
    feed with the reason. HKEX stays out. A feed in Chinese is stored as published; a
    Simplified source is not converted.

## Phase 7 – Live labelling and the history (sonnet)

- [ ] **Task 7.1: the watcher labels new linked stories** — needs: Task 5.5
  - Files: modify `stock_advisor/news_cli.py` / `news/collect.py`, tests.
  - Done when: tests pass (fake client): a new linked story is labelled within one slow-poll
    cycle; a dropped story is never sent; at the monthly ceiling the watcher keeps collecting
    and linking and logs once that labelling stopped. The watcher is restarted through its
    scheduled task; after one hour `watcher_log.txt` shows labelled stories and no error, and
    the month's cost so far is written on the board.

- [ ] **Task 7.2: the history quote** (checkpoint) — needs: Task 5.5, Task 6.1
  - Done when: `data/reports/label-history-quote-<date>.md` states: linked stories in the
    history per year and source; the cost of labelling all of them as a batch job at the
    sample's measured tokens per story; two cheaper cuts (the last 8 years only; one story per
    event group from `news/events.py`); the run time. The question with the three prices goes
    to `docs/inbox.md`; the task is marked waiting. Nothing paid runs in this task.

- [ ] **Task 7.3: the labelled history** — needs: Task 7.2
  - Files: create `scripts/label_history.py` (batch API, resumable by batch id, stops at the
    approved amount plus 10 %), tests with a fake client.
  - Done when: the cut Brian approved is labelled through `jobq.ps1` (cpu lane); the log ends
    with stories labelled, errors, and the real cost against the quote; the real cost is on the
    board. A rerun sends nothing already labelled.
  - Notes: the approved amount is this task's spending limit and replaces the US$10 allowance
    for this one task only, in Brian's words from the inbox answer.

## Phase 8 – Dashboard, removal, close (sonnet)

- [ ] **Task 8.1: the News tab shows labelled stories per holding** — needs: Task 7.1
  - Files: modify `app.py` (`_render_news_tab` and its helpers), tests.
  - Done when: the tab lists, per holding and per driver, the linked stories with event type,
    new or repeat, and severity, newest first, with filters for severity and event type; not
    relevant stories are hidden by default. The "High-impact only" checkbox and the "HIGH
    IMPACT" prefix are gone. Checked in a real browser on port 8502 with a screenshot in the
    hand-back; first open after a restart stays within the accepted 15 to 25 s.

- [ ] **Task 8.2: `high_impact` removed everywhere** (opus) — needs: Task 7.3, Task 8.1
  - Files: modify `news/events.py`, `model.py`, `notify.py`, `library_snapshot.py`,
    `scripts/recategorize_news.py`, `backfill_news.py`, their tests; a migration that leaves
    the old columns unread (no column or row is dropped from `news.db`).
  - Done when: `grep -ri "high.impact" --include=*.py .` finds nothing outside the migration
    note; where the flag was an input (`model.py`) or a gate (`notify.py`), label severity 3
    and relevant takes its place, and stories without a label count as not severe; tests and
    ruff pass; the watcher and the dashboard are restarted through their scheduled tasks and
    their logs show no error.
  - Notes: no alert rule is tuned here; milestone 4 owns the alert conditions.

- [ ] **Task 8.3: docs** — needs: Task 8.2, Task 6.1, Task 6.2, Task 6.3, Task 6.4
  - Done when: README, `docs/architecture.md` and `docs/known-issues.md` match the code (the
    linker, the labeller and its ceiling, each new source and its terms, the tables added).

- [ ] **Task 8.4: end-of-run review** (fable: end-of-run review) — needs: Task 8.3
  - Done when: the review of this plan's commit range is in `docs/reviews/`; plain bugs are
    fixed and verified; judgment calls are in `docs/open-items.md`; the milestone's five lines
    are checked one by one and the milestone card question is in `docs/inbox.md`.

## Self-review
Criteria A to E each map to tasks above. Every task has a "done when". `news.db` has one
writer: Tasks 5.2, 6.2, 6.3 and 7.3 write through the store and queue their long runs in the
cpu lane, one at a time. Brian is needed three times: the key (5.4), the sample (5.5) and the
history quote (7.2); Phase 6 and Task 5.1 to 5.3 never wait on him.
