# Requests: stock

Goal: answer Brian's requests that fit this project's scope, outside any milestone plan. Each request
becomes one task here, written by the orchestrator with Brian's words, and a worker builds it (repo
CLAUDE.md, docs/decisions.md and the project rules apply). Drafts (emails, answers, interview prep,
cheat sheets) are written to a file the task names; the orchestrator checks them and passes them on.

Constraints: as in docs/decisions.md and CLAUDE.md. A request outside the project's scope, or one
that needs a decision only Brian can make, goes to docs/inbox.md instead.

Acceptance: each task's "Done when" line.

## Tasks

- [x] **Task R1: carry over what the pinned session knew, before it retires** (sonnet) `[parallel-ok]`
  - Why: Brian is retiring the pinned sessions and handing new requests to the orchestrator's workers (Brian, 2026-11-26: "I'm not retiring the project, only the pinned session. Honestly it should cover all the currently pinned session except for hk-games marketing, and dating"). A worker sees only repo files, so what the session learned in chat must be written into the repo.
  - Source: the pinned session local_7ab67b27 "Stock"; transcripts are the .jsonl files in `C:\Users\brian\.claude\projects\C--Users-brian-OneDrive-Documents-workspace-repo-stock-advisor\` (each /clear starts a new file: read all of them, Brian's own messages first).
  - What: (1) Brian's rulings and preferences given only in chat go into docs/decisions.md as decisions, each ending `(Brian, <date>: "<his words>")`; (2) facts and how-tos the session learned (setup steps, how to run or restart a live service, where data lives, known pitfalls) go into CLAUDE.md or a docs file; (3) lines in CLAUDE.md or docs that are now stale or wrong are corrected (for example "not run by the orchestrator's workers" or "not registered": the project is now registered); (4) anything unfinished in the session becomes an entry in docs/open-items.md (or the inbox if only Brian can decide).
  - Done when: the commit lists each added decision and fact with its source date; nothing contradicts docs/decisions.md; `git diff --stat` touches only docs and CLAUDE.md; pushed. Report the count of rulings and facts added.
  - Notes: read only from the transcripts; never read `.env` or `secrets`; never copy tokens, keys, passwords, phone numbers or other people's names or messages into the repo; no code changes.

- [x] **Task R2: which market-position data can we get: order book depth, open interest, crowded positioning** (sonnet) `[parallel-ok]` (checkpoint)
  - Why: Brian, 2026-11-26, on what "market position" data the strategies should use: "I'm thinking of order book depth, open interest, or crowded positioning".
  - What: for the markets the tool covers, find for each of the three where the data comes from, whether it is free or what it costs, how far back it goes and how often it updates, and any terms that forbid our use. Order book depth: the data feed the project already holds (for example Futu OpenAPI levels) or exchange feeds. Open interest: HKEX stock options and futures, US options. Crowded positioning: SFC short positions (already stored), short interest, CFTC Commitments of Traders, fund holdings, insider trades (already stored). Fetch one real sample of each free source the project can already reach (read-only, no paid sign-up, no new key).
  - Done when: `docs/research/market-position-sources.md` has a table (data / source / cost / history / update frequency / sample fetched yes-no / terms) with links, a recommendation of which one or two to add first and what each would add to a strategy, and an inbox question to Brian: which to build (default: the recommended ones). Pushed. No code changes; no paid API or sign-up.

- [x] **Task R3: can we get Futu order book depth, and on what terms** (sonnet) `[parallel-ok]` (slot 1 only)
  - Why: Brian, 2026-11-26, after Task R2 left Futu order book depth unchecked (OpenD was not running): "what's up with Futu depth?", then "I mean can you check".
  - What: (1) from Futu's own OpenAPI documentation (with links): what order-book depth an account gets for HK and US stocks without paying (levels, delay), what quote right (for example HK LV2) full 10-level depth needs and its price, and how many stocks can be subscribed at once at each quota tier; (2) on this PC, read-only: whether OpenD is installed, where, and whether this repo already has Futu config or code (say which files); (3) if OpenD is already running and logged in, fetch one HK order book (for example 00700) with `get_order_book` and record how many levels came back. Do not start OpenD, log in, or type any password, passkey or code: if it is not running, say so and stop that step.
  - Done when: a "Futu order book depth" section is added to `docs/research/market-position-sources.md` with the free vs paid levels, the quota numbers, OpenD's state on this PC and the sample (or why none), and the R2 inbox question is updated with what it means for option (d). Pushed. No code changes, no purchase, no sign-up.

- [ ] **Task R4: collect HKEX stock-option open interest and CFTC positioning** (sonnet) `[parallel-ok]` (taken: slot 1, 2026-11-26 12:00)
  - Why: Brian, 2026-11-26, on Task R2's card: "go with the recommended route and discard Futu".
  - What: two new collectors in the project's existing source pattern (see how the SFC short positions and insider trades are stored, and `docs/research/market-position-sources.md` for URLs): (1) HKEX Stock Options Daily Market Report: per underlying stock, calls and puts open interest and volume per day, with a backfill as far back as the files go (say how far); (2) CFTC Commitments of Traders (Socrata JSON, no key): weekly speculator and commercial positions for the futures markets the tool already watches (say which), with history. Each runs on the existing schedule, skips days already stored, and is read-only toward the outside. Check HKEX's terms of use for scripted download first; if they forbid it, stop (1) and put it in the inbox.
  - Done when: tests for both parsers (failing first) pass with the full suite; a live run stores the latest HKEX day and the latest CFTC week (row counts given); the scheduled job runs them; docs (CLAUDE.md data list, decisions) updated; pushed. If a live service must pick up the change, restart it through its scheduled task and check its log. No paid API.

## Self-review
- Each task quotes Brian's request and has a Done when line.
