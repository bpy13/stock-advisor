# Open-source quant projects: facts (gathered 2026-11-10)

Method: GitHub README pages via WebFetch (summaries by a small model, so quotes are as relayed), GitHub REST API (pushed_at, stars, latest release), and a few docs/source files. Anything not seen on a live page is marked "unconfirmed". No verdicts.

## Maintenance snapshot (GitHub API, 2026-11-10)
| Project | Stars | License | Last push (pushed_at) | Latest release |
|---|---|---|---|---|
| microsoft/qlib | 50.2k | MIT | 2026-11-04 | v0.9.8, 2026-10-08 |
| openbq-org/OpenBB (was OpenBB-finance/OpenBB) | 75.3k | README: Apache-2.0; API spdx "NOASSERTION" | 2026-11-10 | tag "ODP", 2026-09-30 |
| polakowo/vectorbt | 9.8k | "Apache 2.0 with Commons Clause" (API: NOASSERTION) | 2026-11-08 | v1.2.0, 2026-10-19 |
| stefan-jansen/zipline-reloaded | 2.0k | Apache-2.0 | 2026-11-02 | 3.2.1, 2026-10-25 |
| QuantConnect/Lean | 22.5k | Apache-2.0 | 2026-11-09 | GitHub "latest release" is v2.4.0.1 from 2017 (tags list v2.4.0.x; releases not used); unconfirmed current version |
| AI4Finance-Foundation/FinRL | 17.0k | MIT (name/logo trademarked) | 2026-11-03 | v0.3.8, 2026-03-20 |
| mementum/backtrader | 23.7k | GPL-3.0 | 2024-08-19 | none on GitHub releases; latest tag 1.9.78.123 listed by API order unclear (unconfirmed) |
| stefan-jansen/alphalens-reloaded | 685 | Apache-2.0 | 2026-10-26 | 0.5.1, 2026-10-26 |
| stefan-jansen/pyfolio-reloaded | 623 | Apache-2.0 | 2026-11-02 | 0.10.2, 2026-11-02 |
| skfolio/skfolio | 2.6k | BSD-3-Clause | 2026-11-08 | v1.12.8, 2026-11-08 |
| PyPortfolio/PyPortfolioOpt | 6.2k | MIT | 2026-07-07 | v1.6.0, 2026-02-26 |
| hudson-and-thames/mlfinlab (GitHub) | 5.0k | NOASSERTION | 2023-10-02 | none |
| AI4Finance-Foundation/FinGPT | 21.5k | MIT | 2026-10-25 | v1.0.0, 2026-04-08 |

Sources: https://api.github.com/repos/<owner>/<repo> and /releases/latest for each.

## Microsoft Qlib - https://github.com/microsoft/qlib
- What: "Qlib is an AI-oriented Quant investment platform that aims to use AI tech to empower Quant Research." Pipeline: data, model training, backtest. Linked to RD-Agent.
- Data: official dataset "disabled temporarily"; community source suggested; default collector uses Yahoo Finance ("might not be perfect"). Examples use China (`region cn`); US also listed. Hong Kong: not mentioned (unconfirmed for HK). Intraday: 1-minute data and high-frequency examples exist.
- Alpha158 (source: https://github.com/microsoft/qlib/blob/main/qlib/contrib/data/loader.py): kbar 9 features (KMID, KLEN, KMID2, KUP, KUP2, KLOW, KLOW2, KSFT, KSFT2); price: OPEN/HIGH/LOW/VWAP divided by close (window 0); volume ratios optional; rolling default windows [5,10,20,30,60] with operators ROC, MA, STD, BETA, RSQR, RESI, MAX, MIN, QTLU, QTLD, RANK, RSV, IMAX, IMIN, IMXD, CORR, CORD, CNTP, CNTN, CNTD, SUMP, SUMN, SUMD, VMA, VSTD, WVMA, VSUMP, VSUMN, VSUMD. Total count of 158 not stated on the page fetched.
- Alpha360: 6 fields (CLOSE, OPEN, HIGH, LOW, VWAP, VOLUME) x 60 days = 360; prices divided by latest close, volume by latest volume.
- Label (handler.py): `"Ref($close, -2)/Ref($close, -1) - 1"` (return from t+1 close to t+2 close, i.e. next-day return with one day delay). Learn processors: DropnaLabel, CSZScoreNorm on label (cross-sectional z-score per day). Alpha360 inference processors: ProcessInf, ZScoreNorm, Fillna.
- Models: XGBoost, LightGBM, CatBoost, MLP, LSTM, GRU, ALSTM, GATs, TFT, TabNet, Transformer, Localformer, TRA, TCN, HIST; RL for order execution (TWAP, PPO, OPDS); rolling retraining and DDG-DA mentioned for market adaptation.
- Backtest: `qrun`; TopkDropoutStrategy (docs https://qlib.readthedocs.io/en/latest/component/strategy.html): holds Topk stocks, drops worst-ranked held, buys best unheld; "turnover is roughly 2 x Drop / K"; uses only score ordering. Costs in example `exchange_kwargs`: open_cost 0.0005, close_cost 0.0015, min_cost 5, limit_threshold 0.095, deal_price close (units not defined on page).
- Metrics (https://qlib.readthedocs.io/en/latest/component/report.html): IC = per-day Pearson correlation of label and score; Rank IC = Spearman; monthly IC; IC distribution and Q-Q plot; risk analysis on excess return with and without cost: std, annualized return, information ratio, max drawdown. ICIR: not defined on that page (unconfirmed).
- Validation: time-based segments (train/valid/test) per README examples; purged/embargoed CV: not found. Rolling retraining mentioned in README, not described on the report page.
- Signal combination: strategy docs say nothing about ensembling; input is a single `score` column, "prediction scores are not rescaled by Qlib". Ensembling across models: unconfirmed.
- News/sentiment: none on README.

## OpenBB - https://github.com/OpenBB-finance/OpenBB (redirects to openbq-org/OpenBB)
- What: "the open-source toolset that helps data engineers integrate proprietary, licensed, and public data sources"; exposes Python, Workspace, Excel, MCP servers, REST. A data aggregation layer, not a backtester ("No backtesting feature is described").
- License: README "Distributed under the Apache License, Version 2.0."
- Data: many providers behind `obb.equity.price.historical`; docs say historical price supports 9 providers (https://docs.openbb.co/odp/python/faqs/data_providers). HK: third-party write-up says China/HK relies mainly on Yahoo Finance with insufficient depth; OpenBB blog says China domestic coverage needs custom extensions (AKShare, Tushare, TdxQuant community extensions): https://openbb.co/blog/extending-openbb-for-a-share-and-hong-kong-stock-analysis-with-akshare-and-tushare/ . Intraday intervals 1m..1d seen only on a third-party mirror (unconfirmed officially). HK news via yfinance/FMP: unconfirmed.
- News: `obb.news.company` requires openbb-news plus a provider extension (nasdaq or tmx) per search result of official V4 docs.

## vectorbt - https://github.com/polakowo/vectorbt
- What: "Trading research at scale"; NumPy/Numba vectorised backtesting, parameter sweeps (10,000 combinations example, `fees=0.001`).
- License: "fair-code", Apache 2.0 with Commons Clause (commercial sale of products primarily this software restricted).
- Data: built-in `vbt.YFData.download` (Yahoo). More integrations are PRO.
- Validation: "Walk-forward optimization" listed under robustness testing; splitters and cross-validation tutorial are PRO features (community edition not described).
- Metrics: Total Return, Max Drawdown, Win Rate, Profit Factor, Expectancy, Sharpe, Sortino, Calmar, Omega; QuantStats integration. Costs: fees; "Total Fees Paid" in stats; slippage in PRO docs.
- Maintenance: active (push 2026-11-08, v1.2.0 2026-10-19). Open edition vs vectorbt PRO split.

## zipline-reloaded - https://github.com/stefan-jansen/zipline-reloaded
- Event-driven backtester from Quantopian. Quote: maintainers "continue to maintain Zipline Reloaded for bug, security and compatibility fixes", new feature work moved to ML4T Backtest (maintenance mode).
- Data: Quandl bundle via NASDAQ Data Link (API key needed); custom bundles possible (unconfirmed on page). HK/intraday: not on README.
- Output as pandas DataFrames for pyfolio-reloaded. Costs/slippage: not on README (zipline has commission/slippage models: unconfirmed here).

## QuantConnect LEAN - https://github.com/QuantConnect/Lean
- "an event-driven, professional-caliber algorithmic trading platform"; Python and C#; LEAN CLI for backtest, `lean optimize`, research, live via Docker.
- Walk-forward: docs describe it as "the practice of periodically adjusting the logic or parameters of a strategy", scheduled with `train` (https://www.quantconnect.com/docs/v2/writing-algorithms/optimization/walk-forward-optimization).
- HK: a QuantConnect forum thread says HK equities not supported; workaround is IB data via toolbox downloader plus custom data (https://www.quantconnect.com/forum/discussion/14580/backtesting-with-ib-data-for-hong-kong-stock-exchange-equities/); thread date unclear, so current status unconfirmed.
- News: Tiingo News Feed dataset, 10,000 US equities, from Jan 2014, second frequency, 120+ providers (https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/tiingo/tiingo-news-feed). Doc example scores sentiment by keyword dictionary. US only.
- Fee/slippage models: not on README (unconfirmed).

## FinRL - https://github.com/AI4Finance-Foundation/FinRL
- Financial deep reinforcement learning; layers "Market Environments", "DRL Agents", "Financial Applications"; train-test-trade. README points to FinRL-X for production.
- Data sources table: US (Yahoo, Alpaca, IEXCloud, WRDS...), mainland China (Akshare, Baostock, Tushare, JoinQuant, RiceQuant), crypto, Taiwan Sinopac; no Hong Kong provider listed.
- Features: MACD, Bollinger upper/lower, RSI-30, DX-30, 30/60 SMA; tutorial adds VIX and turbulence index.
- Models: A2C, DDPG, PPO, TD3, SAC (Stable Baselines 3); ElegantRL, RLlib referenced.
- Backtest: out-of-sample trade period compared with MVO and DJIA; specific metrics not named on README. Sentiment: not in FinRL itself; links to FinGPT.

## backtrader - https://github.com/mementum/backtrader
- "Python Backtesting library for trading strategies"; GPL-3.0; feeds from csv, pandas, blaze, IB, Visual Chart, Oanda; "Flexible definition of commission schemes", slippage, bracket orders; analyzers "TimeReturn, Sharpe Ratio, SQN"; pyfolio integration marked deprecated.
- Last push 2024-08-19 (API); README does not state maintenance status.

## alphalens-reloaded - https://github.com/stefan-jansen/alphalens-reloaded
- Factor analysis: returns, IC, turnover, grouped analysis; `get_clean_factor_and_forward_returns(..., quantiles=5, ...)`. Maintenance mode; "Our new development focuses on ML4T Diagnostic."
- Source (performance.py, https://github.com/stefan-jansen/alphalens-reloaded/blob/main/src/alphalens/performance.py), as relayed: IC is `stats.spearmanr(forward_return, factor)` per date (rank IC); quantile mean-return std error = std / sqrt(count) with dates treated as independent; no t-stat computed; "The code doesn't adjust for overlapping forward-return windows". Alphalens does not compute ICIR in that file (unconfirmed elsewhere; the tear sheet reports IC mean, std, risk-adjusted IC per its docs, unconfirmed).

## pyfolio-reloaded - https://github.com/stefan-jansen/pyfolio-reloaded
- Tear sheets of performance and risk from returns, positions, transactions; "Pyfolio Reloaded is in minimal maintenance"; successor ML4T Diagnostic. Apache-2.0.

## skfolio - https://github.com/skfolio/skfolio ; PyPortfolioOpt
- skfolio: "Python library for portfolio optimization, factor model construction, and risk management built on scikit-learn." BSD-3-Clause. Validation: `WalkForward(train_size=252, test_size=60)`, `CombinatorialPurgedCV(n_folds=10, n_test_folds=2)`. CPCV docs (https://skfolio.org/generated/skfolio.model_selection.CombinatorialPurgedCV.html): purging is "removing from the training set all observations whose labels overlapped in time" with test; embargoing "removing from the training set all observations that immediately follow an observation" in the test set; params `purged_size` (default 0), `embargo_size` (default 0). Metrics: Sharpe, Sortino, Calmar, CVaR, drawdown, Ulcer, etc. `transaction_costs` per-asset in optimisation, also management fees. Ensemble: stacking optimization. It optimises portfolio weights, not stock return forecasts.
- PyPortfolioOpt: MIT, 6.2k stars, v1.6.0 2026-02-26. Mean-variance, Black-Litterman, HRP; README not fetched (unconfirmed details).

## mlfinlab / AFML methods
- mlfinlab (Hudson & Thames): https://hudsonthames.org/mlfinlab/ presents it as a paid product: Business GBP 100 + VAT per user per month. Page lists Triple-Barrier, Meta-Labeling, Trend Scanning, feature importance, cross-validation, sampling, sequential bootstrap. Page does not name purged k-fold, embargo or sample weights (they exist in the AFML book; unconfirmed on this page). GitHub repo last push 2023-10-02, license NOASSERTION.
- Open-source implementations of purge/embargo seen: skfolio (above). Others (e.g. sklearn-style PurgedKFold in other libraries): not checked, unconfirmed.

## FinGPT - https://github.com/AI4Finance-Foundation/FinGPT
- Open-source financial LLMs, 5-layer framework (data sources, data engineering, LoRA fine-tuning, tasks, apps). MIT. Quote: "Nothing herein is financial advice, and NOT a recommendation to trade real money."
- Sentiment models: v3.3 (Llama2-13B), v3.2 (Llama2-7B), v3.1 (ChatGLM2-6B), LoRA; weighted F1 on FPB, FiQA-SA, TFNS, NWGI; v3.3 FPB 0.882 as relayed. Sentiment training set 76.8K rows.
- FinGPT-Forecaster: input ticker, date, weeks of news, optional basic financials; output next-week price movement prediction; "currently trained on US market data (DOW 30)". How sentiment becomes a feature: not explained on README. News provider: not named. HK: not mentioned. Last dated "What's New" item Nov 2023 (README), but repo pushed 2026-10-25.

## Projects combining news sentiment and price features (from a web search, not deeply verified)
- parth1899/financial-sentiment-analysis-and-stock-forecasting-platform: FinBERT labels + LSTM, yfinance; hackathon project, last push Mar 2025.
- jguhit/Erdos-2024-DL-Newsworthy: headline sentiment, 15 stocks, ~5 years, 15-minute bars (Stock News API, Alpaca); model unconfirmed.
- Papers: FinBERT-LSTM https://arxiv.org/abs/2407.16150 (also 2211.07392; news weighted by category plus prior week's prices); Zeng & Jiang https://arxiv.org/html/2306.02136v3 (average FinBERT probabilities per ticker per day, yfinance); Ruan & Jiang, Mathematics 2025 https://mdpi.com/2227-7390/13/17/2747 (FinBERT + technical indicators into XGBoost, SHAP ranks FinBERT features high); Lee & Anderl, Frontiers AI 2025 (content sentiment more effective than headline sentiment; energy sector).
- Search summary: no widely used mature library found that combines them; QuantConnect Tiingo example uses keyword-dictionary sentiment.

## Overlapping forward returns: standard inference practices
- Newey-West HAC: from search results, "Newey and West (1987)" is the preferred choice in finance literature for long-horizon regressions (NBER w27410 https://nber.org/system/files/working_papers/w27410/w27410.pdf; course note https://www3.nd.edu/~nmark/FinancialEconometrics/2022Course/CourseNotes/Prepared_Day9.pdf). Caveat in those sources: can over-reject in finite samples with persistent regressors.
- statsmodels `get_robustcov_results` cov_type 'HAC' with required `maxlags`, kernels bartlett (default) or uniform; page does not mention Newey-West by name or overlap (https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.RegressionResults.get_robustcov_results.html). Common rule for maxlags (h-1 for horizon h): unconfirmed, not on page.
- Scaled t-statistic: Valkanov (2003), Hjalmarsson (2011) divide OLS t by sqrt(horizon); Fed paper https://www.federalreserve.gov/Pubs/ifdp/2006/853/ifdp853.htm ; another paper cautions it can overestimate the standard error.
- Non-overlapping sampling: keep every h-th observation, optionally average over the h starting offsets (arXiv 2604.07870).
- Hodrick (1992) / Hansen-Hodrick SEs: named only as citations; details unconfirmed.
- Purging/embargo (AFML): defined in skfolio docs above. López de Prado average-uniqueness sample weights: no live page confirmed (search found nothing).
- Library behaviour: Qlib computes daily cross-sectional IC with a 1-day-ahead label (no multi-day overlap in its default label); alphalens computes per-date Spearman IC and, per its source as relayed, does not correct for overlap and treats dates as independent in quantile standard errors.
- Not checked: Fama-MacBeth implementations (linearmodels), Qlib ICIR definition, alphalens docs on `periods`.
