# Requests: stock

Goal: answer Brian's requests that fit this project's scope, outside any milestone plan. Each request
becomes one task here, written by the orchestrator with Brian's words, and a worker builds it (repo
CLAUDE.md, docs/decisions.md and the project rules apply). Drafts (emails, answers, interview prep,
cheat sheets) are written to a file the task names; the orchestrator checks them and passes them on.

Constraints: as in docs/decisions.md and CLAUDE.md. A request outside the project's scope, or one
that needs a decision only Brian can make, goes to docs/inbox.md instead.

Acceptance: each task's "Done when" line.

## Tasks

- [ ] **Task R1: carry over what the pinned session knew, before it retires** (sonnet) `[parallel-ok]`
  - Why: Brian is retiring the pinned sessions and handing new requests to the orchestrator's workers (Brian, 2026-11-26: "I'm not retiring the project, only the pinned session. Honestly it should cover all the currently pinned session except for hk-games marketing, and dating"). A worker sees only repo files, so what the session learned in chat must be written into the repo.
  - Source: the pinned session local_7ab67b27 "Stock"; transcripts are the .jsonl files in `C:\Users\brian\.claude\projects\C--Users-brian-OneDrive-Documents-workspace-repo-stock-advisor\` (each /clear starts a new file: read all of them, Brian's own messages first).
  - What: (1) Brian's rulings and preferences given only in chat go into docs/decisions.md as decisions, each ending `(Brian, <date>: "<his words>")`; (2) facts and how-tos the session learned (setup steps, how to run or restart a live service, where data lives, known pitfalls) go into CLAUDE.md or a docs file; (3) lines in CLAUDE.md or docs that are now stale or wrong are corrected (for example "not run by the orchestrator's workers" or "not registered": the project is now registered); (4) anything unfinished in the session becomes an entry in docs/open-items.md (or the inbox if only Brian can decide).
  - Done when: the commit lists each added decision and fact with its source date; nothing contradicts docs/decisions.md; `git diff --stat` touches only docs and CLAUDE.md; pushed. Report the count of rulings and facts added.
  - Notes: read only from the transcripts; never read `.env` or `secrets`; never copy tokens, keys, passwords, phone numbers or other people's names or messages into the repo; no code changes.

## Self-review
- Each task quotes Brian's request and has a Done when line.
