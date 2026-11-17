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

- [ ] **Task 5.1: the names file and the linker** (opus) `[parallel-ok]` (taken: slot 1, 2026-11-17 13:08)
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

- [ ] **Task 5.2: links stored for every story** — needs: Task 5.1
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

- [ ] **Task 5.3: the labeller, with cost recording and a ceiling** (opus) `[parallel-ok]` (taken: slot 2, 2026-11-17 12:10)
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

- [ ] **Task 5.4: Brian's API key is in `.env`** (checkpoint) (slot 1 only) — needs: Task 5.3
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

- [ ] **Task 6.1: US filings by event type for every US watchlist stock** `[parallel-ok]`
  - Files: modify `stock_advisor/news/sources/edgar.py`, `news/collect.py` (the allowlist
    becomes every US watchlist symbol with a CIK), tests.
  - Done when: tests pass: an 8-K is stored with its item numbers (for example 2.02 results,
    5.02 officer change, 1.01 material agreement) as `event_items`; the CIK map covers every
    US watchlist stock or lists the ones without a CIK in the log. A live fetch of one day
    stores filings for more than the old 10-ticker list, inside the SEC's request limit.

- [ ] **Task 6.2: US insider trades (Form 4)** `[parallel-ok]`
  - Files: create `stock_advisor/news/sources/insider.py`, `tests/test_insider.py`; new table
    `insider_trades` (symbol, filer, role, trade date, filed date, code, shares, price, value,
    10b5-1 flag, accession number unique).
  - Done when: tests pass on saved Form 4 XML (a purchase, a sale, an option exercise, an
    amended filing that replaces its original). The SEC insider data sets from 2006 load the
    history for the US watchlist through `jobq.ps1` (cpu lane) and the log ends with rows per
    year; the live feed adds one day's filings without a duplicate.

- [ ] **Task 6.3: short-selling files, US and Hong Kong** `[parallel-ok]` (taken: slot 5, 2026-11-17 12:00)
  - Files: create `stock_advisor/news/sources/short_selling.py`, `tests/test_short_selling.py`;
    new table `short_selling` (symbol, date, source, short volume or position, total volume
    where given).
  - Done when: FINRA's terms are read and recorded; if allowed, the daily short-volume files
    and the twice-monthly short-interest files load for the US watchlist. The SFC weekly
    short-position CSVs from 2012 load for the Hong Kong watchlist (terms already read: personal
    use allowed). Tests pass on saved files, including a week the SFC published late. A
    scheduled fetch is added to the existing backfill task, not a new scheduled task.

- [ ] **Task 6.4: Hong Kong and China feeds whose terms allow it** `[parallel-ok]`
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
