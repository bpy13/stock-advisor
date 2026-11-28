# Telegram spec: stock_advisor

## Purpose and direction
- Phone alerts for high-impact news events that move a holding, ^HSI or ^GSPC by a predicted 1.5% or more in one day.
- Direction: **send-only**. It never reads incoming messages. Its only `getUpdates` use is `--setup`, which reads the latest update once to learn the chat id (it does not clear updates).
- Bot code: `stock_advisor/news/notify.py` (`TelegramClient`, `TelegramNotifier`, `format_alert`, `build_notifier`, `main`); settings `stock_advisor/news/settings.py`; dedup table `sent_alerts` in `stock_advisor/news/store.py`; hook in `stock_advisor/news_cli.py` (`--watch`, `--no-alerts`).
- Entry points: `python -m stock_advisor.news_cli --watch` (alerts); `python -m stock_advisor.news.notify --setup | --test`.

## Who may message it
Not applicable: send-only.
- Recipient: one chat, setting `TELEGRAM_CHAT_ID`; token `TELEGRAM_BOT_TOKEN`; hourly cap `TELEGRAM_MAX_ALERTS_PER_HOUR` (default 10). Read from the environment then `.env` (`settings.get_setting`); `.env` is read only at process start, so a change needs a watcher restart.
- Language: English.

## Commands
Not applicable: send-only.

## Free-text intents
Not applicable: send-only.

## App-specific rules
- Alert only when the event is high-impact and at least one target has a predicted 1-day move >= `NEWS_ACTION_THRESHOLD_PCT` (1.5%) (decision 2026-10-27; stricter bar 2026-11-10, Brian, `docs/decisions.md`).
- Only the headline and link are sent, never an item summary (Guardian terms).
- One alert per event ever (`sent_alerts`); a failed send is not recorded, so a later batch retries it.
- Hourly cap: over the cap the event is recorded `suppressed` (never sent later) and one "N more alerts suppressed" message follows.
- Brian's research-inbox shares never go to Telegram (Task 9.2, d0c5b70, 2026-11-26).
- Never log exception text: only exception type or HTTP status (token in URL).
- Plain text, no markup, cut to 4096 characters; per-target lines are dropped from the end first; "unproven" prefix when a forecast is not proven.

## Messages the bot sends unasked
| When | What | To whom |
|---|---|---|
| Watcher finds a new qualifying event (24/7) | category, headline, link, sources, per-target forecast lines (`format_alert`) | the one chat |
| More than the hourly cap in one batch | "N more alerts suppressed (limit M per hour). Run news_cli to see them." | same chat |
| `--test` (manual) | one fixed test sentence | same chat |

## Schedule and process
- Long-running watcher `news_cli --watch` (feeds about every 15 min, a cycle log line about every minute). Scheduled task `stock_advisor_news_watcher` (`scripts/register_watcher_task.ps1`): at logon plus a 15-minute repeat, IgnoreNew, priority 4, restart 5 times at 2 min; runs `conhost.exe --headless` then `scripts/run_watcher.ps1`.
- `run_watcher.ps1` loops: restarts after a non-zero exit (60 s), kills and restarts when its log is quiet for 30 min; the memory guard exits at 8 GB (code 86).
- Restart: Brian types the stop command (a worker's kill command is refused by Claude Code's check); the wrapper then the task restart it in about 60 s (`docs/known-issues.md`, 2026-10-28, 2026-11-11). `register_watcher_task.ps1` prints the stop recipe (the wrapper tree must be killed too, seen 2026-11-17). No `tools\restart-*.ps1`.
- Offset and outbox: not applicable: send-only. Dedup state is `sent_alerts`; no outbox.
- Runs only while Brian is logged in (`docs/known-issues.md`).

## Logging
- `data\cache\news\watcher_log.txt` (wrapper lines plus watcher stdout and stderr). Telegram lines: one warning when off, "Telegram <method> returned HTTP <status>" or "failed (<ExceptionType>)". There is no per-alert log line; the record of a sent alert is its `sent_alerts` row. No token or secret logged.

## Network
- `requests.post`, timeout 15 s, no retries, any exception returns failure. SSL EOF is not handled specially; a failed alert is retried only by the next watcher batch (it stays unrecorded).

## Cost
- Claude calls per message: 0 on the Telegram path. (Claude labelling of stories lives separately in `stock_advisor/news/label.py`, with cost columns in the `labels` table; not part of Telegram.) Ledger and ceiling for Telegram: none needed.

## Gaps against the skill's rules
- Rules 1–5 (understanding messages): not applicable, send-only.
- Rule 6, local record of message, reply and branch: no per-alert log line (only `sent_alerts` rows); add one line per sent or suppressed alert (event id, no secrets).
- Rules 10–11, kept connection and send retries: none; add a short retry with backoff in `TelegramClient._call`.
- Rule 12, persisted offset and outbox: none. Offset: not applicable. Retry happens only implicitly via the unrecorded-event rule.
- Rule 16, restart script, then check the log: scheduled-task based (met), but the stop step is Brian typing; no restart script that then checks the log.
- Rule 18, cost ledger and ceiling: not applicable on this path.
- Rule 19, no test messages to real people: met. `tests/conftest.py` fixture `_no_real_telegram` blanks token and chat id; `tests/news/test_notify.py` fakes `post`.
- Note: the live phone test (Task 5.4b, 072e46a, 2026-10-28) was done by Brian; "first real alert waits on a proven model" (`docs/known-issues.md`).

## Lessons from history
- Tests must blank Telegram settings so no test alerts the phone (613adc0, 2026-10-27).
- Task Scheduler restart-on-failure covers only a failed launch, not a crash; add a wrapper loop (5790dcf, 2026-10-27).
- The watcher died on 2026-11-11 and nothing restarted it for six days: add a 15-min repeat trigger with IgnoreNew, plus a quiet-log kill (66fa1e3, Task 5.2b, 2026-11-17).
- Priority 7 starved watcher start-up for 20+ min: use priority 4 (66fa1e3, 2026-11-17).
- Stop-ScheduledTask ends only the outer conhost; kill the wrapper tree too (register_watcher_task.ps1, 2026-11-17).
- A worker's kill command is refused, so Brian types the stop; `.env` is read only at start (known-issues, 2026-10-28 and 2026-11-11).
- Telegram keeps updates 24 h and only for messages sent to that bot itself (known-issues, 2026-10-28).
- Alert bar is strict: only a clear buy or sell signal, with opportunity cost; other news goes to the dashboard (Brian, 2026-11-10).
- Memory guard restarts the watcher above 8 GB (444b022, 2026-10-29).
