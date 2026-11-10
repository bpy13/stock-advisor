# Research 5: backtest design, acceptance gates and tools (facts only, gathered 2026-11-10)

Tags: [page] = I opened the page and read it there (WebFetch returns a small-model summary of the page, so wording is as relayed; PyPI data come from the PyPI JSON API). [snippet] = seen only in a search result or a secondary summary. [unconfirmed] = could not confirm. No verdicts. Earlier notes (research-quant-projects.md, research2-maths-toolbox.md) were read first; facts already there are not repeated except where needed (cross-references marked "earlier notes").

---
## 1. Acceptance gates on alpha platforms

### 1a. WorldQuant BRAIN
The official BRAIN documentation (support.worldquantbrain.com, platform.worldquantbrain.com) returned HTTP 403 / empty to my fetches. The numbers below come from third-party copies of the BRAIN documentation. Treat as "copy of docs", not official-page-read.
- Source A: GitHub copy of "BRAIN Alpha Test Requirements and Tips" https://github.com/JoshuaAnthony6/world-quant-brain-mcp/blob/main/docs/workflows/%E7%A4%BA%E4%BE%8B%E5%8F%82%E8%80%83%E6%96%87%E6%A1%A3_BRAIN_Alpha_Test_Requirements_and_Tips.md [page, but a third-party mirror]
- Source B: https://www.quantt.co.uk/resources/worldquant-brain (review site; says it also could not open live BRAIN docs and relies on a copy) [page]

| Test | Delay-1 | Delay-0 | Source / tag |
|---|---|---|---|
| Fitness | > 1 | > 1.3 | A [page]; B gives only delay-1 > 1.0 [page] |
| Sharpe | > 1.25 | > 2 | A [page]; B delay-1 1.25 [page] |
| Turnover | 1% to 70% | 1% to 70% | A [page]; A's overview section also cites "< 250%", which conflicts; B 1%-70% [page]; a search summary said another guide gave 10%-70% [snippet] |
| Weight concentration | max weight in any stock < 10%; "sufficient instruments" must get weight (no number) | same | A [page]; B [page] |
| Sub-universe Sharpe | >= 0.75 x sqrt(sub-universe size / alpha universe size) x alpha Sharpe (example TOP1000 inside TOP3000) | same | A [page]; B gives no formula [page]; formula also seen in search summaries [snippet] |
| Self-correlation | PnL correlation < 0.7 with own submitted alphas (4-year window); alternative: alpha Sharpe at least 10% above the correlated alpha | same | A [page]; B calls the 0.7 "community-sourced, unconfirmed" [page] |
| Production correlation | about 0.7 against production alphas, no detail | same | A [page] |
| ATOM (USA, delay 1) | last-2-year Sharpe > 1 (relaxed criteria instead of full IS ladder) | | A [page] |
| GLB alphas | also sub-geography Sharpe >= 1 (AMER, APAC, EMEA) | | A [page] |

- Fitness formula: Fitness = Sharpe x sqrt(|Returns| / max(Turnover, 0.125)). Turnover floored at 12.5%, so lower turnover does not raise fitness. A [page], B [page].
- Source B quotes the copied documentation as saying criteria "vary slightly depending on region and Delay" [page].
- Out-of-sample: A says alphas must pass in-sample tests before being submitted for out-of-sample testing; only submitted alphas count toward scoring; no OOS thresholds given [page]. IS ladder Sharpe test thresholds: not on A [page]; not found elsewhere [unconfirmed].
- Self-correlation measured on daily PnL changes, not cumulative PnL curves: stated by a third-party search summary [snippet]. A local tool using default 0.6 is that tool's own setting [snippet].
- IQC guidelines page https://www.worldquant.com/brain/iqc-guidelines/ [page]: alphas are scored only if they qualify for out-of-sample testing and are scored against other participants' alphas; team merged pool gets a correlation test (threshold not given); no Sharpe/fitness/turnover thresholds on that page; alphas that add deliberate "noise" to subvert scoring may be disqualified.

### 1b. Numerai (docs.numer.ai)
- CORR calculation [page] https://docs.numer.ai/numerai-tournament/scoring/correlation-corr : (1) gauss-rank the predictions (rank, scale to (0,1), inverse normal CDF); (2) centre the target; (3) raise each series to power 1.5 keeping sign (stated reason: gives more weight to the tails because the fund tends to trade only extreme predictions); (4) Pearson correlation of the two. Only prediction ranks matter.
- MMC [page] https://docs.numer.ai/numerai-tournament/scoring/meta-model-contribution-mmc : covariance of the model's predictions, after neutralising them to the Meta Model, with the target. Steps: normalise predictions, normalise Meta Model, neutralise submission to Meta Model, covariance with target. BMC is the analogue against the stake-weighted benchmark models.
- FNC [page] https://docs.numer.ai/numerai-tournament/scoring/feature-neutral-correlation : correlation with target after neutralising predictions to the features (remove linear projection onto features, rescale to unit std, then Spearman with target). Stated reason: features are inconsistent individually, so heavy linear exposure to them is expected to do poorly. Website shows FNCv3 (neutralised to the "medium" subset of V3 features).
- Payout [page] https://docs.numer.ai/numerai-tournament/scoring : from round 1393 (projected to open 2026-11-06) Classic payouts planned on NCORR (neutralised CORR vs Jupiter target) and NMMC; payout = 8 x NCORR + 32 x NMMC over 60 scoring days; page does not say whether weights are normalised. Earlier rounds keep old payout config. The page says FNC is informational, not used for payout.
- Eras [page] https://docs.numer.ai/numerai-tournament/data : an era groups rows from one point in time (in v6 the column is `date`). Page advice: treat each era, not each row, as one data point; many metrics are scored per era (mean correlation per era). Targets can cover overlapping future periods, so take care with cross-validation (it points to a forum post on era-wise time-series CV). Features' predictive power is "inconsistent over time".
- A separate "era-wise scoring" page (…/scoring/era-wise-scoring) returned 404; an explicit "stated reason for eras" beyond the above: [unconfirmed].
- Eras became weekly (from monthly) and now overlap, per a forum post in a search result [snippet] https://forum.numer.ai/t/super-massive-data-release-deep-dive . Rounds are 20 live market days for the main score [snippet].

### 1c. Quantopian contest criteria (archived)
Source: Quantopian lecture notebook copy https://notebook.community/quantopian/research_public/notebooks/tutorials/5_contest_lesson_11/notebook [page] (undated; a 2019-era version per a search summary [snippet]).
- Position concentration: 98th percentile of max single position <= 5%; max <= 10%.
- Gross leverage: min >= 0.7; 2nd pct >= 0.8; 98th pct <= 1.1; max <= 1.2.
- Turnover (63-day rolling mean, daily): min >= 3%; 2nd pct >= 5%; 98th pct <= 65%; max <= 80%.
- Net exposure (absolute): 98th pct <= 10%; max <= 20%.
- Beta to SPY (absolute, 126-day rolling): 98th pct <= 0.3; max <= 0.4.
- Sector exposure (63-day rolling mean, absolute, 11 sectors): 98th pct <= 0.20; max <= 0.25.
- Style exposure (absolute, 5 styles): 98th pct <= 0.40; max <= 0.50.
- Trading universe QTradableStocksUS: >= 90% of investment minimum; 2nd pct >= 95%.
- Positive cumulative return required; more than 504 trading days of backtest needed to be scored.
- Score: each day's return divided by trailing 63-day annualised volatility (floored at 2%); final score is the cumulative sum, from the 442nd rolling value on. The page lists no Sharpe constraint.
- Forum posts (quantopian-archive.netlify.app) say max position concentration was cut from 10% to 5% and that Sortino replaced Calmar in the score; sources conflict [snippet]. Original rulebook not found [unconfirmed].

### 1d. QuantConnect Alpha / backtest statistics
- The QuantConnect docs page for backtest results returned 404 [unconfirmed]. PSR definition/threshold in the official docs: [unconfirmed].
- Forum thread https://www.quantconnect.com/forum/discussion/11497/ [page]: a user states Alpha-market rules include "> 80% PSR"; no staff member confirms the number; staff (Derek Melchin) say they aim for an average of 10 trades per month, rejected an alpha with 3 orders in 5 years, and say minute resolution "will be required" for fill modelling.
- Search summaries [snippet]: PSR benchmark Sharpe fixed at 1.0 (Jared Broad); 5-year backtest for Alpha Streams submission (Derek Melchin); Sharpe uses risk-free rate 0; staff are reviewing criteria and they have changed over time.

### 1e. Kaggle Jane Street and Optiver
Kaggle evaluation pages did not render through WebFetch (title only), so formulas come from third-party write-ups.
- Jane Street Market Prediction (2020-21) [page, blog] https://bullettech.github.io/BulletTech/Main_Course/Machine_Learning/2021-09-02-Kaggle-janestreet : p_i = sum over trades j of weight_ij x resp_ij x action_ij (daily profit); t = (sum p_i / sqrt(sum p_i^2)) x sqrt(250/|i|); utility u = min(max(t,0),6) x sum p_i. The page does not define |i| (number of days, by usual reading; [unconfirmed]).
- Jane Street Real-Time Market Data Forecasting (2024-25): sample-weighted zero-mean R2 on responder_6; zero-mean means the denominator uses squared y rather than deviations from the mean (a blog says Jane Street replaced the test-set mean with zero) [snippet] (search results: https://anilkeshwani.github.io/garden/Clippings/Jane-Street-Real-Time-Market-Data-Forecasting--Kaggle , https://aifin-hkust.github.io/project3/project3.JS_forecast.pdf ). Exact formula text: [unconfirmed] (extraction garbled).
- Optiver Realized Volatility Prediction: RMSPE = sqrt((1/n) sum ((y - yhat)/y)^2) [snippet]; target is realised volatility over a 10-minute window [snippet].
- Optiver Trading at the Close: mean absolute error of target move in basis points [snippet]; official page [unconfirmed].

---
## 2. Factor-analysis and report tools

| Tool | Latest release (PyPI) | Licence | pandas / numpy / Python constraints (PyPI metadata) |
|---|---|---|---|
| alphalens-reloaded | 0.5.1, 2026-10-26 [page] | Apache-2.0 | pandas >=1.5.0,<4.0 (Python <3.15); numpy >=1.26 on 3.12+; Python >=3.11,<3.16 [page] |
| quantstats | 0.0.86, 2026-09-27 [page] | Apache-2.0 | pandas >=2.0.0 (no upper bound), numpy >=1.24, Python >=3.10; README says pandas >=1.5, metadata says >=2.0 [page] |
| empyrical-reloaded | 0.7.2, 2026-11-02 [page] | Apache-2.0 | pandas >=2.2.2 on Python 3.12+ (no upper bound), numpy >=1.26 on 3.12+, scipy, bottleneck, pytz, peewee<3.17.4; Python >=3.11 [page] |
| pyfolio-reloaded | 0.10.2, 2026-11-02 [page] | Apache-2.0 | pandas <3.2, >=1.5.0; numpy <3; needs empyrical-reloaded >=0.5.11, seaborn, matplotlib, scikit-learn; Python >=3.11,<3.16 [page] |
| pyqlib (Qlib) | 0.9.7, 2025-08-15 on PyPI [page]; GitHub v0.9.8 2026-10-08 (earlier notes) | MIT (classifier) | pandas >=0.24 (unpinned upper), numpy unpinned; wheels listed for Python 3.8-3.12 only; Python >=3.8 [page] |

Sources: https://pypi.org/pypi/<name>/json for each (read 2026-11-10).
- Maintenance status text (earlier notes, GitHub): alphalens-reloaded and pyfolio-reloaded in maintenance mode, successor "ML4T Diagnostic".
- Alphalens tear sheet content, from source code https://raw.githubusercontent.com/stefan-jansen/alphalens-reloaded/main/src/alphalens/tears.py and plotting.py [page]:
  - Full tear sheet = quantile statistics table + returns tear sheet + information tear sheet + turnover tear sheet.
  - Information tear sheet: IC table, IC time series, IC histogram, IC Q-Q plot, per forward-return period; monthly IC heatmap when by_group is False; IC by group when by_group True. No IC decay and no autocorrelation there.
  - IC table columns: IC Mean, IC Std, Risk-Adjusted IC (mean/std), t-stat(IC) (one-sample t-test vs 0), p-value(IC), IC Skew, IC Kurtosis.
  - Turnover tear sheet: quantile turnover table and factor rank autocorrelation, per period; top/bottom quantile turnover plots.
  - Returns: quantile returns (bar, violin, cumulative by quantile) per docs index https://alphalens.ml4trading.io/ [page]. IC decay as a named report: not found [unconfirmed]; the docs index says IC decay "Not mentioned" [page]. (IC per several forward periods gives a decay-like view; that is an inference.)
  - Quantile stats table: min, max, mean, std, count, count % per quantile.
- Overlap handling in alphalens: earlier notes (not corrected for overlap).
- Qlib analysis https://qlib.readthedocs.io/en/latest/component/report.html [page]: IC (daily Pearson), rank_ic (Spearman), monthly IC, IC Q-Q; group returns (5 groups of 20% by score rank; long-short Group1 minus Group5; long-average); prediction-score autocorrelation (to judge turnover); risk analysis (std, annualised return, information ratio, max drawdown, each with and without cost); accumulated metrics are sums, not compounded. ICIR is not defined on the page [page].
- quantstats metrics list: earlier notes (research2 section F).

---
## 3. Backtest engines

| Engine | Licence | Latest release | pandas support (metadata) | Commission / slippage model |
|---|---|---|---|---|
| vectorbt (open) | Apache 2.0 with Commons Clause ("fair-code"); PyPI licence field empty, LICENSE.md present [page] | 1.2.0, 2026-10-19 [page] | pandas >=3.0.3,<4.0; numpy >=2.4.6; Python >=3.11,<3.15 [page] | `fees` (e.g. 0.001) and `slippage` (e.g. 0.001) arguments in Portfolio.from_signals/from_orders; slippage units, `fixed_fees`, and default `price` not shown in what I read [page, partial]; docs promote PRO features (execution records, contract multipliers) [page] |
| backtesting.py | AGPL-3.0 [page] | 0.6.6, 2026-07-22 [page] | pandas >=0.25.0 (no upper bound), numpy >=1.17, bokeh >=3 [page] | `commission` = fraction, (fixed, relative) tuple, or callable func(order_size, price); applied at entry and exit; `spread` constant fraction of price charged once; default market order fills at next bar's open, `trade_on_close=True` fills at current close [page https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html] |
| backtrader | GPLv3+ [page] | 1.9.78.123, 2023-04-19 [page]; GitHub last push 2024-08-19 (earlier notes) | no pandas pin (requires_dist lists only matplotlib extra) [page] | commission as percentage (if margin unset) or fixed per contract (if margin set); `commission=0.005` = 0.5% example; slippage on a separate page I did not open [page https://www.backtrader.com/docu/commission-schemes/commission-schemes/] |
| zipline-reloaded | Apache-2.0 [page] | 3.2.1, 2026-10-25 [page] | pandas >=1.5.3,<3.0 (so NOT pandas 3); numpy >=2.1 on 3.13; Python >=3.11,<3.15 [page] | slippage: FixedSlippage (spread default 0; buys at close + half spread), VolumeShareSlippage (volume_limit 0.025, price_impact 0.1, impact quadratic in volume share); commission: PerShare default $0.001/share, PerTrade default 0, PerDollar default 0.0015 [page https://zipline.ml4trading.io/api-reference.html]. FixedBasisPointsSlippage details and next-bar execution: not visible [unconfirmed] |
| bt (pmorissette) | MIT [page] | 1.4.1, 2026-10-10 [page] | requires ffn >=1.1.2; own deps list no pandas pin [page] | commission/slippage docs page I fetched was an empty outline [unconfirmed] |
| LEAN | Apache-2.0 (earlier notes) | GitHub "latest release" 2017; current version [unconfirmed] (earlier notes) | n/a (C# core, Python via pythonnet) | Default slippage NullSlippageModel (zero); VolumeShareSlippageModel; custom models return per-share slippage in price units [page https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/slippage/key-concepts]. Fee models per brokerage; Interactive Brokers equities model "$0.005/share, $1 minimum, 0.5% maximum"; page lists no HK/HKEX fee model [page https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/transaction-fees/supported-models] |

Hong Kong specifics:
- LEAN source Market.cs defines `HKFE` ("Hong Kong Exchange", code 25) but no `HKG`/`SEHK` market [page https://raw.githubusercontent.com/QuantConnect/Lean/master/Common/Market.cs]. Earlier notes: a forum thread says HK equities not supported.
- No HK stamp duty or per-stock lot-size support found in any of vectorbt, backtesting.py, backtrader, zipline-reloaded, bt, LEAN docs I read [unconfirmed beyond the pages named]. backtesting.py allows a callable commission, which can carry any formula [page]. Board lot size is set by the issuer, e.g. 100 shares Tencent, 500 BYD Auto [snippet]. HKEX fee rates: earlier notes (research2 section C; stamp duty 0.1% per side, trading fee 0.00565%, SFC levy 0.0027%). Settlement fee 0.002% (min HKD2, max HKD100) [snippet from a broker/HKEX search result].
- Pandas 3 summary from metadata above: vectorbt requires pandas >=3; zipline-reloaded requires <3; others have no upper cap or cap at <4.

---
## 4. Cross-validation tooling for time series

- scikit-learn TimeSeriesSplit [page] https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html : params n_splits (default 5), max_train_size, test_size (default n_samples // (n_splits+1)), gap (default 0; "number of samples to exclude from the end of each train set before the test set"). Example 12 samples, test_size=2, gap=2: fold 0 train [0-3], test [6,7]. Expanding window unless max_train_size is set. Latest scikit-learn 1.9.1 (earlier notes).
- skfolio 1.12.8, 2026-11-08, BSD-3; pandas >=2.1, scikit-learn >=1.6, Python >=3.10 [page PyPI]. 
  - `WalkForward` [page https://skfolio.org/generated/skfolio.model_selection.WalkForward.html]: test_size, train_size (int, DateOffset or timedelta), freq (calendar schedule, needs DatetimeIndex), purged_size (default 0: observations removed from end of training before test; doc says use >=1 to model execution delay for daily data), expand_train (default False = rolling), reduce_test (default False).
  - `CombinatorialPurgedCV(n_folds=10, n_test_folds=8, purged_size=0, embargo_size=0)` [page]: n_folds >= 3; n_test_folds >= 2; properties n_splits, n_test_paths, recombined_paths. (Earlier notes list n_test_folds=2 in a README example; the API page default is 8.)
  - CPCV paths formula, from Lopez de Prado paper [page, local text of GARP PDF https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf]: N groups, k test groups: splits = C(N,k); paths phi[N,k] = k/N x C(N,k); example N=6, k=2 gives 15 splits and 5 paths. Yields a distribution of Sharpe ratios.
- mlfinlab (Hudson & Thames): repo LICENSE.txt is the proprietary "ArbitrageLab Business License Agreement" (internal business use only, no redistribution, no reverse engineering) [page https://raw.githubusercontent.com/hudson-and-thames/mlfinlab/master/LICENSE.txt]. Public repo holds docs only, source behind paid tiers [snippet]; PyPI lookup 404 for current page in my earlier-notes attempt; Snyk says no PyPI release in 12 months (undated) [snippet]. Earlier notes: GBP 100 + VAT per user per month for Business tier.
- Free alternatives:
  - purgedcv 0.1.12, 2026-11-08, MIT, Python >=3.11, numpy >=1.24, pandas >=2.0, scikit-learn >=1.3 [page PyPI]. GitHub eslazarev/purged-cross-validation: splitters WalkForwardSplit (n_splits, test_size, window expanding/sliding, train_size), PurgedKFold (embargo, embargo_observations or embargo_fraction), PurgedGroupKFold, CombinatorialPurgedCV (n_splits N, n_test_groups K), CombinatoriallySymmetricCV; label timing via prediction_times/evaluation_times and purge_horizon; also probabilistic and deflated Sharpe, PBO, min backtest length, min_track_record_length; MIT; 63 stars, 162 commits, 1 open issue; no last-commit date shown [page]. Version 0.0.x early-stage per search summary [snippet] but PyPI now shows 0.1.12.
  - mlfinpy 0.1.2, 2024-10-09, MIT; pandas >=2.2.3,<3.0; numpy <1.27 (so not numpy 2); Python >=3.11 [page PyPI]. Appears unmaintained since Oct 2024 (inference from date).
  - timeseriescv 0.2, 2018-09-07, MIT [page PyPI]. Not maintained since 2018 (inference from date).
- arch 8.0.0, 2025-10-21, NCSA licence; numpy <3, pandas >=1.4, scipy >=1.8, statsmodels >=0.13; Python >=3.10 [page PyPI]. Docs https://arch.readthedocs.io/en/latest/ [page]:
  - Time-series bootstraps: StationaryBootstrap(block_size, ...) (Politis-Romano 1994; exponential block lengths, block_size is the mean), CircularBlockBootstrap, MovingBlockBootstrap (docs don't recommend: end observations under-sampled); `optimal_block_length(x)` helper exists.
  - SPA (arch.bootstrap.SPA): White/Hansen test; args benchmark losses (T), models losses (T x k), block_size (default sqrt(T)), reps (default 1000), bootstrap (default stationary), studentize (default True), nested (default False); three p-values (upper, consistent, lower). Refs Hansen 2005, White 2000. The null is not stated on the page.
  - StepM: size = FWER (default 0.05); same args as SPA; `superior_models`; ref Romano & Wolf 2005.
  - MCS: Model Confidence Set (Hansen, Lunde, Nason 2011); args losses (T x k), size, block_size (default sqrt(T)), method 'R' (default) or 'max', reps 1000, bootstrap stationary; outputs included, excluded, pvalues.
  - All take losses (lower is better), so a return series must be turned into a loss (e.g. negative return) by the caller [inference].

---
## 5. Backtest realism checklists, with source per item

### 5a. "The Seven Sins of Quantitative Investing" (Wang, Luo, Alvarez; Deutsche Bank DB Quant Handbook Part II, 8 Sept 2014 [snippet]). Original PDF (columbia.edu link) returned 404; list read from a textbook summary https://portfoliooptimizationbook.com/book/8.2-seven-sins.html [page, secondary]
1. Survivorship bias: include bankrupt, delisted, acquired companies; use comprehensive databases such as CRSP; do not drop stocks for missing values.
2. Look-ahead bias: check timestamps, release dates and backfill corrections; align returns with weights (using w_t with r_t of the same period is wrong).
3. Storytelling bias: inventing an explanation after seeing a pattern; antidote more data and statistical testing.
4. Overfitting and data snooping: avoid fine-tuning, run sensitivity analysis, validate on new data (paper trading or live).
5. Turnover and transaction costs: include costs and slippage; the example uses 60 bps fee with daily rebalancing; control turnover or rebalancing frequency.
6. Outliers: robust estimation, winsorise or truncate; example removes hourly crypto returns above 5%.
7. Asymmetric patterns and shorting costs: shorting is not free or always available; borrow costs spiked in 2008; test against easy-to-borrow names.

### 5b. Lopez de Prado, "The 10 Reasons Most Machine Learning Funds Fail" (SSRN 3104816; GARP copy, text extracted locally) [page]
Titles: #1 Sisyphus paradigm (research assembly line vs lone PM), #2 research through backtesting, #3 chronological sampling, #4 integer differentiation, #5 fixed-time horizon labelling, #6 learning side and size simultaneously, #7 weighting of non-IID samples (average uniqueness weights), #8 cross-validation leakage (purging), #9 walk-forward (or historical) backtesting, #10 backtest overfitting.
- #9 text: walk-forward tests a single historical path; results depend on the sequence of data (fitting on reversed sequence often underperforms); early decisions use little data; says walk-forward is as easy to overfit as walk-backward. Solution: CPCV (formulas in section 4).
- #10 text: expected maximum of I iid standard normals ~ (1-gamma) Z^-1[1-1/I] + gamma Z^-1[1-1/(I e)] <= sqrt(2 ln I); without the number of trials one cannot compute FWER, FDR or PBO. Solution: Deflated Sharpe Ratio.
- CXO Advisory summary: 20 walk-forward backtests repeated on the same data likely yield one useless strategy at a naive 95% confidence level [snippet].

### 5c. Bailey, Borwein, Lopez de Prado, Zhu (2014/2015, Notices AMS): about 45 configurations on a 5-year sample can give an in-sample annualised Sharpe of 1 with true OOS Sharpe 0; defines Minimum Backtest Length [snippet] (search summaries; an R translation reproduces N=45 -> about 5 years).

### 5d. Ernest Chan (via third-party summaries only; his blog/book not opened) [snippet]
Look-ahead bias (use lagged data; compare position files from full vs truncated data to detect it), data-snooping (keep models simple, few parameters), survivorship (use a database that includes Enron-type delisted names), stock splits and dividend adjustment, primary vs consolidated prices, linearity. Sources: https://josephchenhk.github.io/ernest-p-chan-winning-strategies-and-their-rationale-1 , https://www.benzinga.com/markets/13/05/3582742/backtesting-pitfalls (403 on fetch). Chan's own text: [unconfirmed].

### 5e. CFA Institute refresher "Backtesting and Simulation" [page] https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/backtesting-and-simulation
Rolling-window (walk-forward) backtest approximates real investing; behavioural pitfalls survivorship and look-ahead; historical scenario analysis (recession, inflation) for structural breaks; negative skew and fat tails mean backtests may understate downside; historical simulation by bootstrap, Monte Carlo needs a distribution choice (multivariate normal misses skew and fat tails); sensitivity analysis. Data snooping not in the excerpt [page]. Study-guide material adds: use point-in-time data, specialised vendors for corporate actions and delistings [snippet].

### 5f. Items for which I found no primary text
- Point-in-time index membership, execution at next bar, half-spread and square-root market impact models, borrow limits, corporate-action handling: appear as tool features (backtesting.py next-bar fill and spread; zipline FixedSlippage half-spread and VolumeShare quadratic impact; Qlib exchange costs in earlier notes) but I did not find a primary checklist document listing them [unconfirmed as a checklist]. Square-root impact formula source: [unconfirmed].
- QuantConnect/Quantopian lecture-note checklists: [unconfirmed] (not opened).

---
## 6. Counting and logging trials
- Deflated Sharpe, from the Lopez de Prado paper text [page, local extract of GARP PDF]: PSR[SR*] = Z[((SR - SR*) sqrt(T-1)) / sqrt(1 - skew x SR + ((kurt-1)/4) SR^2)]; DSR is PSR with SR* = sqrt(V[SR_n]) x ((1-gamma) Z^-1[1-1/N] + gamma Z^-1[1-1/(N e)]), where V is the variance of Sharpe estimates across trials and N the number of independent trials; Sharpe in original (non-annualised) frequency.
- Original DSR paper (Bailey & Lopez de Prado; davidhbailey.com/dhbpapers/deflated-sharpe.pdf), text extracted locally [page]: N must be the number of independent trials; with M dependent trials estimate implied independent trials N_hat from average correlation rho: N_hat = rho + (1 - rho) M (eq. 9, interpolating between rho=1 giving 1 and rho=0 giving M); weighted average correlation defined by a quadratic form; mentions Fisher transform refinement. Examples in the text: an investor may allocate after N=46 independent trials, or N=88 with other assumptions. It states the optimal number of trials idea ("best so far") and that investment theory, not computation, should guide trial count.
- What to count, from a search summary of practitioner pages (luxalgo, quantt) [snippet]: total distinct variants considered, including discarded ones, manual tweaks, parameter values, universe definitions, cost assumptions, start dates; pre-registration suggested as fix; one author's 275 correlated backtests had best Sharpe 0.50 vs 0.92 expected if independent [snippet]. "Log every run automatically" is the summariser's inference, not a source statement.
- MLflow tracking [page] https://mlflow.org/docs/latest/ml/tracking/ : log_param, log_metric, runs (metadata, start/end times, artifacts), experiments group runs, `MlflowClient.search_runs()` returns runs; the page has no run-count function and no DSR link (counting by list length is my inference; max_results caps it).
- Published research-log template that feeds DSR's N: not found [unconfirmed]. purgedcv (section 4) ships deflated Sharpe, PBO and min_track_record_length functions that take trial inputs [page].

---
## 7. Walk-forward analysis and CPCV evidence
- Pardo WFE: Pardo's book (Wiley 2008) not opened [unconfirmed]. Backtrex blog https://backtrex.com/en/blog/walk-forward-efficiency-ratio-thresholds [page, secondary]: WFE = (net OOS / net IS) x 100; bands <30% severe overfitting, 30-50% marginal, 50-70% acceptable ("Pardo threshold"), 70-100% good, >100% check period selection; recommends OOS win rate >60%; window split 3:1 (75/25) standard, 4:1 for scarce data, 2:1 conservative; minimum 30 trades per OOS window; at least 5 iterations, 8-12 more stable; prefers rolling windows for FX/index markets with changing regimes. The page itself flags several claims as unsourced.
- Other definitions: annualised OOS / annualised IS profit (ProRealCode forum, quantammsim docs, which also use Sharpe-based WFE and cite Pardo 2008 for WFE > 0.5) [snippet]; threshold of 0.5 attributed to Pardo by several blogs [snippet]. Two runs can share 60% WFE with very different OOS variance [snippet].
- Anchored vs rolling: skfolio WalkForward `expand_train` False = rolling fixed window, True = anchored/expanding [page]; purgedcv `window` "expanding" or "sliding" [page]; Lopez de Prado criticises early WF decisions using little data (section 5b).
- Arian, Norouzi Mobarekeh, Seco (2024), Knowledge-Based Systems, DOI 10.1016/j.knosys.2024.112477 (SSRN 4778909). The publisher/SSRN pages returned 403 or a redirect stub, so I did not read the abstract on its page. From a search-result summary [snippet]: CPCV had lower Probability of Backtest Overfitting and better Deflated Sharpe test statistic than K-Fold, Purged K-Fold and Walk-Forward; walk-forward showed weaker false-discovery prevention, more temporal variability and weaker stationarity; Bagged CPCV and Adaptive CPCV proposed; synthetic environment used Heston, Merton jump diffusion and drift-burst processes; K-Fold vs Purged K-Fold performance comparable.

---
## 8. Free data for honest tests
- S&P 500 membership history: github.com/fja05680/sp500 [page], MIT licence; files: historical components and changes 1996 to present (point-in-time snapshots), changes since 2019, ticker start/end dates; original historical list came from a download tied to Clenow's "Trading Evolved", later changes from Wikipedia plus manual research; updated every couple of months; index count not always 500 (494 on 2001-01-16), author suggests starting at 2001; no company names; does not provide prices for delisted names (README names Norgate and eoddata as paid options); no accuracy guarantee. S&P 100 history: [unconfirmed] (not found).
- Wikipedia list of S&P 500 companies [page]: current table with "date added" and a link to "Historical components of the S&P 500"; a selected-changes table: not seen in the part I read [unconfirmed]. Licence is generally CC BY-SA [unconfirmed on page].
- Hang Seng Index history: no free consolidated point-in-time file found. Hang Seng Indexes publishes quarterly review announcements with constituent appendices (www.hsi.com.hk), e.g. one 2024 review with 82 constituents unchanged, and a Feb 2026 change list (index at 90 members) [snippet]; the HSI index-details page returned no usable content and its data terms: [unconfirmed]. Third-party sites show current or dated snapshots only [snippet]. I did not scrape HKEX.
- Delisted US stocks: vendor pages only [snippet]: EODHD (delisted symbols with EOD prices), Sharadar (EOD prices include delisted, from 1998), Norgate (delisted securities and historical index constituents), QuantRocket (included in licence), MarketParquet (free daily sample, full archive USD 79 one-time). All paid or limited; no free full source found. Yahoo via yfinance: Apache-2.0 library, 1.8.0; its description says Yahoo data is for personal use and to check Yahoo's terms [page PyPI]. fja05680 README says Yahoo only gives current symbols [page].
- Ken French factors: earlier notes (research2 section B): Asia Pacific ex Japan, Japan, Developed ex US, Emerging files; no HK-only file; AQR datasets list no HK-specific file. Nothing new re-checked.
- Earnings dates: SEC EDGAR [page] https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data : free, max 10 requests/second, declare a User-Agent with name and contact email, data.sec.gov JSON APIs (submissions, XBRL facts), daily/full index files by form type and filing date; so 8-K filing timestamps are available (that 8-K Item 2.02 marks earnings is background, [unconfirmed here]). Vendor/free earnings calendar APIs and HK results dates: [unconfirmed]. HKEX board-meeting notices are on HKEX sites, which I did not scrape.

---
## Could not confirm
- Official WorldQuant BRAIN documentation pages (403): IS ladder Sharpe test, out-of-sample test thresholds, current self-correlation rules; all thresholds above come from mirrors/reviews.
- Numerai: an explicit statement of why eras exist (era-wise-scoring page 404); TC definition; era length today beyond forum snippet.
- Quantopian: original official rulebook and the exact final scoring (Sortino/Calmar) text.
- QuantConnect: official Alpha criteria page and official PSR threshold (only an unconfirmed forum claim of 80%); official backtest statistics page (404).
- Kaggle: official evaluation pages for Jane Street (both) and Optiver (both) did not render; formulas from blogs; exact weighted zero-mean R2 text; |i| definition.
- Alphalens: whether any report shows "IC decay" by name; alphalens period defaults (not read).
- Qlib: ICIR definition; Qlib pandas 2/3 compatibility beyond unpinned metadata; PyPI lags GitHub (0.9.7 vs 0.9.8).
- Backtest engines: vectorbt slippage units and default price; bt commission/slippage docs; zipline FixedBasisPointsSlippage and next-bar rule; backtrader slippage page; LEAN current version and any HK support; HK stamp duty/lot-size support in any engine.
- Whether mlfinlab was ever re-released on PyPI under a new licence (PyPI page not read); mlfinlab GitHub archived status.
- Pardo's book text (WFE 50% threshold, 3:1 split are from secondary sources).
- Arian/Norouzi/Seco paper: full text and abstract not read on a primary page.
- Original Seven Sins PDF (404); Chan's own checklist; QuantConnect/Quantopian lecture-note checklists; primary source for square-root market impact, borrow limits, corporate-action checklists.
- Any published research-log template that feeds DSR's N.
- S&P 100 membership history; Hang Seng Indexes consolidated history and terms of use; Wikipedia selected-changes table coverage and licence text; free full delisted US price source; earnings-date free sources for US and HK.
