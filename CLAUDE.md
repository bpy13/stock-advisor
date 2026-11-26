# Stock Advisor – notes for Claude

A personal research tool for one user (Brian). It produces buy/sell/hold signals for HK and US
stocks from price history, correlation and the user's own portfolio, via a CLI and a Streamlit
dashboard.

Read these before substantial changes:

- `docs/decisions.md` – what was decided and why (don't re-litigate without a reason)
- `docs/open-items.md` – pending work and questions waiting on the user
- `docs/plans/` – the latest plan
- `docs/architecture.md` – modules, data flow, where things live (once it exists)
- `docs/known-issues.md` – limits and traps found so far (once it exists)
- `README.md` – user-facing setup and commands

## Environment
- Conda env `stock_advisor` (python 3.12): `conda env create -f environment.yml`
  (pip-only alternative: `pip install -r requirements.txt`; install CPU torch first)
- Run: `conda run -n stock_advisor python -m stock_advisor.cli` (report),
  `streamlit run app.py` (dashboard), `python -m stock_advisor.validate_cli` (metric backtest),
  `python -m stock_advisor.news_cli` (news events; `--watch` to poll),
  `python -m stock_advisor.news_backtest_cli` (news backtest),
  `python scripts/backfill_news.py --status` (backfill progress),
  `python -m stock_advisor.prices_cli refresh|status|compare` (price store),
  `python -m stock_advisor.analyze_cli [--save]` and `analyze_cli cost --symbol S --amount N` (portfolio)
- Tests: `conda run -n stock_advisor python -m pytest -q`
- Lint: `conda run -n stock_advisor ruff check .` (config in `ruff.toml`)
- Secrets: copy `.env.example` to `.env` (gitignored)

## Project rules
- `data/` holds the user's real holdings (`data/transaction.csv`) and caches; it is gitignored.
  Never commit or print its contents.
- Tests use synthetic data only; no live network calls in tests.

## Conventions
- Market-position data: SFC short positions (`short_selling`) and CFTC weekly positions (`cot_positions`: S&P 500, Nasdaq-100, WTI crude, 10-year note) sit in the news store `data/cache/news/news.db`, loaded by the 02:00 backfill. HKEX option data is not fetched (terms forbid scripts).
- Remote data is cached on disk under `data/cache/` (see `market_data.py` for the pattern).

## Live services and workers (carried over 2026-11-26)
- The project is registered with the orchestrator; its workers build plan tasks from `docs/plans/`
  and take Brian's requests from `docs/plans/requests.md`. Questions for Brian go to `docs/inbox.md`.
- Four Windows scheduled tasks run on Brian's PC: `stock_advisor_news_watcher` and
  `stock_advisor_dashboard` (at login, port 8502), `stock_advisor_news_backfill` (02:00) and
  `stock_advisor_minute_recorder` (22:00). Commands are in README "Scheduled tasks".
- A running service keeps old code and old `.env` values until it restarts. A worker's command to
  stop a process is refused, so Brian stops it and the task restarts it in about 60 s.
- Futu OpenD must run on this PC (127.0.0.1:11111) for Hong Kong hourly prices. Check it with the
  real client, not `netstat`; see `docs/known-issues.md`.
- Never ask Brian to paste a token or key into chat; he edits `.env` himself.
- Memory: the watcher and dashboard exit above 8 GB and 10 GB (guard in `docs/known-issues.md`).
  A model fit never runs inside them; they load the saved `fitted.pkl`.
