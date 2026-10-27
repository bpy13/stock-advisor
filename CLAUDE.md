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
  `python scripts/backfill_news.py --status` (backfill progress)
- Tests: `conda run -n stock_advisor python -m pytest -q`
- Lint: `conda run -n stock_advisor ruff check .` (config in `ruff.toml`)
- Secrets: copy `.env.example` to `.env` (gitignored)

## Project rules
- `data/` holds the user's real holdings (`data/transaction.csv`) and caches; it is gitignored.
  Never commit or print its contents.
- Tests use synthetic data only; no live network calls in tests.

## Conventions
- Remote data is cached on disk under `data/cache/` (see `market_data.py` for the pattern).
