# Research 2: maths toolbox for a portfolio analyzer (facts only)

Gathered 2026-11-10. Status tags: **[opened]** = I opened the page this session and the fact is from it. **[background]** = standard knowledge I did not re-open (reference link given; treat as unconfirmed). **[unconfirmed]** = I could not open or verify it.
Fetch failures this session: SSRN, Taylor and Francis (Lo 2002), Wikipedia pages for Brinson, Deflated Sharpe, HAR, forecast-combination puzzle returned 404/403; IBKR campus returned 403; Morningstar and gov.hk stamp page returned empty.

Library data (version, upload date, license) come from the PyPI JSON API (https://pypi.org/pypi/<name>/json), read 2026-11-10 **[opened]**. License text is as PyPI reports it.

| Library | Latest version | Upload date | License (PyPI) |
|---|---|---|---|
| quantstats | 0.0.86 | 2026-09-27 | Apache-2.0 |
| pyfolio-reloaded | 0.10.2 | 2026-11-02 | Apache-2.0 |
| empyrical-reloaded | 0.7.2 | 2026-11-02 | Apache-2.0 |
| riskfolio-lib | 7.4.1 | 2026-11-04 | BSD 3-clause |
| skfolio | 1.12.8 | 2026-11-08 | BSD |
| pyportfolioopt | 1.6.0 | 2026-02-26 | MIT |
| ffn | 1.4.1 | 2026-10-10 | MIT |
| bt | 1.4.1 | 2026-10-10 | MIT |
| arch | 8.0.0 | 2025-10-21 | NCSA |
| statsmodels | 0.15.0 | 2026-08-27 | BSD-3-Clause |
| scikit-learn | 1.9.1 | 2026-09-10 | BSD-3-Clause |
| scipy | 1.18.1 | 2026-08-21 | BSD |
| hmmlearn | 0.3.3 | 2024-10-31 | not shown by PyPI field |
| pykalman | 0.11.2 | 2026-01-31 | BSD |
| pandas-datareader | 0.11.1 | 2026-06-24 | BSD-3-Clause |
| xgboost | 3.4.1 | 2026-08-15 | Apache-2.0 |
| lightgbm | 4.7.0 | 2026-07-18 | not shown by PyPI field |
| transformers | 5.22.2 | 2026-11-06 | Apache 2.0 |
| sentence-transformers | 6.2.0 | 2026-10-21 | Apache-2.0 |
| pyfinance | 2.0.2 | 2026-04-19 | MIT |
| pmdarima | 2.1.1 | 2025-11-17 | MIT |
| ruptures | 1.1.10 | 2025-09-10 | BSD-2-Clause |
| vectorbt | 1.2.0 | 2026-10-19 | not shown by PyPI field |
| lifelines | 0.30.3 | 2026-03-05 | MIT |
| mlfinlab | PyPI lookup failed | - | unconfirmed |

PyPI pages: https://pypi.org/project/quantstats/ , https://pypi.org/project/skfolio/ , https://pypi.org/project/riskfolio-lib/ , https://pypi.org/project/pyportfolioopt/ , https://pypi.org/project/arch/ , https://pypi.org/project/statsmodels/ , https://pypi.org/project/scikit-learn/ (same pattern for the rest).

---
## A. Performance measurement

- **Simple vs log return** [background]: simple R = P1/P0 - 1; log r = ln(P1/P0). Log returns add over time; simple returns add across assets. Ref: https://en.wikipedia.org/wiki/Rate_of_return . Library: empyrical-reloaded / quantstats (above).
- **Time-weighted return (TWR)** [opened]: split the period at each external flow and compound sub-period growth; flow timing does not affect it. Formula given: 1+R = (M1-C1)/M0 x ... x (Mn-Cn)/Mn-1. Wikipedia says it judges activity under the manager's control. https://en.wikipedia.org/wiki/Time-weighted_return
- **Money-weighted return / IRR** [opened]: the rate r that discounts all external flows plus ending value to the starting value; solved numerically; reflects flow size and timing; "commonly used" for private equity. Same page. Python: scipy.optimize (root finding), numpy-financial [background, not checked].
- **Annualization and Sharpe** [opened, partly]: Sharpe ratio = E[Ra - Rb]/sigma of excess return (Sharpe 1966, revised 1994). Wikipedia lists criticisms: fat tails/skew, smoothing of illiquid prices, and that rules of thumb ("above 1 acceptable") lack a clear source; diversified indexes typically below 1 annualized. https://en.wikipedia.org/wiki/Sharpe_ratio . Common annualization: mean x 252 and sigma x sqrt(252) for daily data [background].
- **Lo 2002** [background; page returned 403]: "The Statistics of Sharpe Ratios", Financial Analysts Journal 58(4). Known content: the sqrt(q) annualization rule holds only for i.i.d. returns; serial correlation changes it; gives a standard error for the Sharpe estimate. https://www.tandfonline.com/doi/abs/10.2469/faj.v58.n4.2453 . Wikipedia only says estimator accuracy depends on return statistics (opened).
- **Sortino** [opened]: like Roy's ratio; target return in numerator, downside deviation in denominator. Wikipedia Sharpe page above.
- **Calmar / max drawdown / duration** [opened]: drawdown = decline from running peak; MDD = largest; drawdown duration = peak-to-peak time; Calmar, Sterling and Burke ratios use drawdown as the risk term. Pitfall: max duration can differ from the duration of the max drawdown; MDD optimization is non-convex. Page notes several "citation needed" tags. https://en.wikipedia.org/wiki/Maximum_drawdown . Calmar formula (annual return / |MDD|, usually 36 months) [background].
- **Information ratio, tracking error** [background]: IR = mean(Rp - Rb)/std(Rp - Rb); tracking error = std(Rp - Rb). Both appear on Portfolio Visualizer's summary (opened, F below). quantstats lists `information_ratio` (opened, F).
- **Hit rate, payoff ratio** [background]: share of winning periods; average win / average loss. quantstats lists `win_rate`, `tail_ratio`, `kelly_criterion` (opened).
- **Alpha, beta (CAPM regression)** [background]: regress Rp - Rf on Rb - Rf; slope = beta, intercept = alpha. empyrical's `alpha_beta` returns both (opened, https://github.com/stefan-jansen/empyrical-reloaded). Reference: Sharpe 1964, J. Finance. Needs about 2-3 years of weekly/daily data to be stable [background].
- **Brinson attribution** [background; Wikipedia page 404]: allocation, selection and interaction effects vs a benchmark by sector. Refs: Brinson, Hood, Beebower 1986 (Financial Analysts Journal); Brinson and Fachler 1985. Search link: https://www.google.com/search?q=Brinson+Hood+Beebower+1986 . Python: no maintained dedicated library confirmed (unconfirmed).
- **Multi-currency / HKD-USD peg** [background]: HKD trades in a linked-exchange-rate band of 7.75-7.85 per USD via the HKMA. https://www.hkma.gov.hk/eng/key-functions/monetary-stability/linked-exchange-rate-system/ (not opened; unconfirmed). Practical note: convert USD stocks at daily FX, report USD return and HKD return; FX effect is small while the peg holds [background].
- **Libraries**: empyrical-reloaded https://github.com/stefan-jansen/empyrical-reloaded (Apache-2.0, 2026-11-02); quantstats https://github.com/ranaroussi/quantstats (Apache-2.0, 2026-09-27); pyfolio-reloaded (Apache-2.0, 2026-11-02).

## B. Risk

- **Rolling volatility, EWMA (RiskMetrics lambda 0.94)** [background]: EWMA variance s2_t = lambda s2_(t-1) + (1-lambda) r2_(t-1); lambda 0.94 daily, 0.97 monthly in RiskMetrics Technical Document (JP Morgan 1996). The Wikipedia VaR page does not mention EWMA or 0.94 (opened, negative finding). Library: pandas `ewm`; arch.
- **GARCH(1,1)** [opened]: sigma2_t = omega + alpha e2_(t-1) + beta sigma2_(t-1). Engle 1982 (Econometrica) introduced ARCH; Bollerslev 1986 (J. Econometrics) GARCH. https://en.wikipedia.org/wiki/Autoregressive_conditional_heteroskedasticity . Library: arch https://github.com/bashtage/arch (NCSA, 8.0.0, 2025-10-21). Sample size guidance: not on the page (several hundred to 1,000+ daily observations is common [background]).
- **Realized volatility / HAR-RV (Corsi 2009)** [background; Wikipedia page 404]: RV = sum of squared intraday returns; HAR regresses next-day RV on daily, weekly (5d), monthly (22d) RV averages. Ref: Corsi, "A Simple Approximate Long-Memory Model of Realized Volatility", J. Financial Econometrics 7(2), 2009. DOI https://doi.org/10.1093/jjfinec/nbp001 . Needs intraday bars (e.g. 5-minute). Library: statsmodels OLS (no dedicated HAR package confirmed).
- **Value at Risk** [opened]: loss that is not exceeded at a stated probability over a horizon; methods: parametric (variance-covariance, delta-gamma), nonparametric (historical, resampled), Monte Carlo. Criticisms: silent on tail size, not subadditive. A 2011 McKinsey survey of 18 institutions: 75% historical simulation, 15% Monte Carlo (as quoted by Wikipedia). https://en.wikipedia.org/wiki/Value_at_risk
- **Expected shortfall / CVaR** [opened]: ES_a = (1/a) integral of VaR_g from 0 to a; coherent, unlike VaR; always at least VaR; Rockafellar-Uryasev turns ES minimization into a linear program. https://en.wikipedia.org/wiki/Expected_shortfall . Basel 97.5% not on page (unconfirmed). quantstats has `value_at_risk`, `conditional_value_at_risk` (opened).
- **Covariance: sample vs Ledoit-Wolf** [opened]: shrunk = (1-a) S + a (Tr S / p) I. Sample eigenvalues are spread too widely; with few samples relative to features the matrix can be singular or not invertible. Ref: Ledoit and Wolf 2004, J. Multivariate Analysis 88(2) 365-411. https://scikit-learn.org/stable/modules/covariance.html . Library: scikit-learn `LedoitWolf` (BSD-3, 1.9.1, 2026-09-10); PyPortfolioOpt offers Ledoit-Wolf with three targets and Oracle Approximating Shrinkage (opened, https://github.com/robertmartin8/PyPortfolioOpt). Arithmetic [background]: 50 stocks need 50 x 51/2 = 1,275 covariance entries; n daily observations below 50 give a singular matrix.
- **Exponentially weighted covariance** [opened for existence]: PyPortfolioOpt lists "exponential covariance" (same README).
- **Correlation breakdown in crises** [background]: correlations rise in sell-offs. Ref: Longin and Solnik 2001, "Extreme Correlation of International Equity Markets", J. Finance. https://doi.org/10.1111/0022-1082.00340 (unconfirmed).
- **Concentration** [background]: Herfindahl H = sum of w_i^2, effective N = 1/H; diversification ratio = (sum w_i s_i)/s_p (Choueifaty and Coignard 2008, J. Portfolio Management 34(4), cited on https://en.wikipedia.org/wiki/Risk_parity , opened). Effective number of bets (Meucci 2009, "Managing Diversification", Risk) [background, unconfirmed link].
- **Risk contribution (marginal/component)** [opened]: sigma(w) = sqrt(w'Sw); contribution_i = w_i (Sw)_i / sigma(w); contributions sum to total by Euler's theorem. https://en.wikipedia.org/wiki/Risk_parity . Portfolio Visualizer shows "Risk Decomposition" (opened, F). Riskfolio-Lib computes per-asset and per-factor risk contribution (opened, F).
- **Factor exposure: Fama-French** [background for the factor definitions; opened for the data]: Fama and French 1993 (3 factor, J. Financial Economics 33), 2015 (5 factor, JFE 116). Ken French data library lists Asia Pacific ex Japan, Japan, and Developed ex US files: 3 Factors, 5 Factors, Momentum, each with Daily version; no Hong Kong-specific file; page states no date, latest table month is September 2026. https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html (opened). The fetch summary said no "global" file listed; Developed and Emerging files exist (opened, summary).
- **AQR data** [opened]: datasets listed are QMJ, BAB (equity factors monthly and daily), Value and Momentum Everywhere, Momentum Indices, "Devil in HML's Details" (monthly, daily). The page named no Hong Kong or Asia Pacific ex Japan file; BAB and HML Devil cover the U.S. and "23 international equity markets" (markets not named on page; per-country files unconfirmed). https://www.aqr.com/Insights/Datasets
- **Downloading factors in Python**: pandas-datareader (BSD-3, 0.11.1, 2026-06-24) and empyrical's `get_fama_french` (needs pandas-datareader) (opened, empyrical README).
- **Stress tests / scenario analysis** [background]: reprice the book under historical shocks (e.g. 2008, 2020) or hypothetical shocks. Portfolio Visualizer shows "Historical Market Stress Periods" such as COVID-19 (opened, F). skfolio has "Synthetic Data (stress testing and factor stress testing)" prior (opened, F).
- **PCA of returns** [background]: eigen-decompose the correlation matrix; first component is usually "market". Library: scikit-learn PCA. Not opened.
- Libraries: skfolio https://github.com/skfolio/skfolio ; Riskfolio-Lib https://riskfolio-lib.readthedocs.io/ ; arch ; scikit-learn.

## C. Portfolio construction and sizing

- **Markowitz mean-variance** [background]: minimize w'Sw s.t. w'mu = target. Ref: Markowitz 1952, J. Finance 7(1). Instability: sensitive to mu errors (Michaud 1989, "The Markowitz Optimization Enigma" [background]). Libraries: PyPortfolioOpt (MIT), Riskfolio-Lib, skfolio.
- **Minimum variance** [opened]: PyPortfolioOpt objective "minimum volatility" (README above).
- **Risk parity / ERC** [opened]: each asset contributes sigma(w)/N; unique solution via convex optimization; refs Maillard, Roncalli, Teiletche 2008; Qian 2005; Spinu 2013; Griveau-Billion et al. arXiv:1311.4057. https://en.wikipedia.org/wiki/Risk_parity . Riskfolio-Lib supports risk parity with 22 convex measures; skfolio has `RiskBudgeting` (opened, F).
- **HRP** [background for paper; opened for implementations]: Lopez de Prado 2016, "Building Diversified Portfolios that Outperform Out of Sample", J. Portfolio Management 42(4); SSRN 2708678 (SSRN fetch blocked). Clusters assets, recursive bisection, no covariance inversion. Implemented in PyPortfolioOpt, Riskfolio-Lib (HRP and HERC), skfolio (HRP, HERC, Schur, NCO) (opened).
- **Black-Litterman** [opened]: developed at Goldman Sachs 1990; start from equilibrium-implied returns, adjust by investor views with stated confidence. Refs: Black and Litterman 1991 (J. Fixed Income), 1992 (Financial Analysts Journal 48(5)); Meucci 2010 "The Black-Litterman Approach: Original Model and Extensions"; He and Litterman 2002. https://en.wikipedia.org/wiki/Black%E2%80%93Litterman_model . Formula not on the page. Implemented in PyPortfolioOpt ("prior return estimate ... with user-supplied views"), Riskfolio-Lib (BL, Bayesian BL, Augmented BL, Entropy Pooling), skfolio (BL, Entropy Pooling, Opinion Pooling) (opened).
- **Kelly / fractional Kelly** [opened]: binary Kelly f = p/l - q/g; reasons for fractional Kelly: "reduce the chance of ruin, reduce volatility, and account for model error"; Kelly 1956 "A New Interpretation of Information Rate"; Thorp applied it to blackjack and markets; Thorp and Rotando 1992 estimate ~117% of S&P 500 per Wikipedia; Samuelson objection. https://en.wikipedia.org/wiki/Kelly_criterion . Library: quantstats `kelly_criterion`; Riskfolio-Lib logarithmic mean-risk "Kelly" (opened).
- **Volatility targeting** [background]: scale exposure by target_vol / forecast_vol. Ref: Moreira and Muir 2017, "Volatility-Managed Portfolios", J. Finance 72(4) [background, unconfirmed].
- **Turnover and cost penalties** [opened]: Riskfolio-Lib constraints include turnover and tracking error (F). PyPortfolioOpt: L2 regularization and discrete allocation (F).
- **Rebalancing bands** [background]: trade only when a weight drifts beyond a threshold. Ref: Vanguard "Best practices for portfolio rebalancing" [unconfirmed link not opened].
- **HK trading costs** [opened, HKEX Securities fee page: https://www.hkex.com.hk/Services/Rules-and-Forms-and-Fees/Fees/Securities-(Hong-Kong)/Trading/Transaction]:
  - Stamp duty 0.1% of transaction value, charged to both buyer and seller, rounded up to the nearest dollar.
  - Trading fee 0.00565% per side (raised from 0.005% on 1 Jan 2023); trading tariff none.
  - SFC transaction levy 0.0027% per side; AFRC transaction levy 0.00015% per side.
  - Investor Compensation Levy 0.002% suspended since 19 Dec 2005.
  - Rate history (search result summaries, secondary): cut from 0.13% to 0.1% per side effective 17 Nov 2023 (KPMG: https://kpmg.com/cn/en/insights/2023/11/tax-alert-21-hk-the-reduced-stamp-duty-rate-on-hk-stock-transfer-will-take-effect-from-17-nov-23.html ). Same search noted HKD 5 fixed fee on instrument of transfer in older sources (conflicting; unconfirmed). Official gov.hk page: fetch returned empty (unconfirmed). IRD notice: https://www.ird.gov.hk/eng/pdf/sog_pn04a.pdf (not opened).
  - Brokerage commission not on HKEX page (broker-specific).
- **Board lots** [opened, partial]: HKEX trading-mechanism page covers odd lot and special lot trades (below / not a multiple of a board lot) and a spread table in the Second Schedule of the Rules; it does not say how lot size is set. Lot size is set per stock by the issuer [background, unconfirmed]. https://www.hkex.com.hk/Services/Trading/Securities/Overview/Trading-Mechanism
- **US costs**: no US stamp duty [background]; SEC Section 31 fee on sales: rate not confirmed (SEC advisories page returned 404). https://www.sec.gov/ (unconfirmed).

## D. Signal research statistics

- **IC / rank IC / ICIR / fundamental law** [background]: IC = correlation (Pearson or Spearman) between forecast and next-period return; ICIR = mean IC / std IC; Grinold: IR ~ IC x sqrt(breadth). Ref: Grinold 1989 "The Fundamental Law of Active Management", J. Portfolio Management 15(3). Library: alphalens-reloaded [background, not checked].
- **Newey-West HAC** [opened]: covariance estimator robust to autocorrelation and heteroskedasticity; Newey and West 1987, Econometrica 55(3) 703-708; common bandwidth T^(1/4); Bartlett weights 1 - l/(L+1). Page does not discuss overlapping returns. https://en.wikipedia.org/wiki/Newey%E2%80%93West_estimator . Library: statsmodels `cov_type='HAC'` (BSD-3, 0.15.0, 2026-08-27) [background on API].
- **Fama-MacBeth** [opened]: time-series betas, then period-by-period cross-sectional regression; premium = average of period estimates; corrects cross-sectional but not time-series correlation; Petersen 2009 suggests double clustering. Fama and MacBeth 1973, J. Political Economy. https://en.wikipedia.org/wiki/Fama%E2%80%93MacBeth_regression . Library: linearmodels `FamaMacBeth` [background, not checked].
- **Event study** [opened]: abnormal return = actual - normal; market model fit on estimation window (typically ~120 days) gives alpha, beta, sigma; CAR not defined on the page; MacKinlay 1997 "Event Studies in Economics and Finance" (J. Economic Literature 35) is the cited survey; short-horizon studies more reliable. https://en.wikipedia.org/wiki/Event_study
- **Bootstrap / block bootstrap** [background]: resample returns (blocks keep autocorrelation). Library: `arch.bootstrap` (arch, above) [background].
- **Multiple testing** [opened for Harvey-Liu-Zhu]: abstract says hundreds of factors across hundreds of papers and argues a new factor needs t-ratio greater than 3.0. https://www.nber.org/papers/w20592 . Bonferroni and Benjamini-Hochberg: statsmodels `multipletests` [background].
- **Deflated Sharpe, PBO** [background; SSRN blocked]: Bailey and Lopez de Prado 2014, "The Deflated Sharpe Ratio", J. Portfolio Management 40(5), SSRN 2460551; Bailey, Borwein, Lopez de Prado, Zhu 2017, "The Probability of Backtest Overfitting", J. Computational Finance 20(4), SSRN 2326253. Library: skfolio has CombinatorialPurgedCV (opened); mlfinlab status unconfirmed.
- **Walk-forward, purged/embargoed CV** [opened for implementations]: skfolio `WalkForward`, `CombinatorialPurgedCV`, multiple randomized CV (https://github.com/skfolio/skfolio). Concept ref: Lopez de Prado 2018, "Advances in Financial Machine Learning" (book) [background].
- **Look-ahead / survivorship bias** [background]: use point-in-time data and delisted names. Not sourced this session.
- **Turnover-adjusted returns**: net return = gross - turnover x cost [background]; HK cost inputs in C.

## E. Models (one line each; all [background] unless stated)

- Ridge/lasso/elastic-net, logistic regression, random forest, gradient boosting, kNN: scikit-learn (BSD-3, 1.9.1, 2026-09-10) https://scikit-learn.org/ ; xgboost (Apache-2.0, 3.4.1); lightgbm (4.7.0). Used for return/direction forecasts and cross-sectional ranking.
- Hidden Markov / regime switching: Hamilton 1989, Econometrica 57(2); hmmlearn (0.3.3, last release 2024-10-31, i.e. over a year old); statsmodels has Markov switching models. Used to label bull/bear or high/low-vol regimes.
- Kalman filter: pykalman (BSD, 0.11.2, 2026-01-31); statsmodels state space. Used for time-varying beta and pairs hedge ratio.
- Cointegration (Engle-Granger 1987, Johansen 1988): statsmodels `coint`, `coint_johansen`. Used for pairs trading.
- ARIMA: statsmodels, pmdarima (2.1.1, 2025-11-17). Used for mean forecasts; weak for daily returns.
- GARCH: arch (above). Used for volatility forecasts.
- Ornstein-Uhlenbeck half-life: ln(2)/kappa from AR(1) fit; statsmodels OLS. Used for mean-reversion speed.
- Bayesian shrinkage: Ledoit-Wolf for covariances (opened, B); Black-Litterman for returns (opened, C).
- Forecast combination: Bates and Granger 1969, Operational Research Quarterly 20(4). The "puzzle" (simple average often beats estimated weights) is associated with Smith and Wallis 2009, Oxford Bulletin of Economics and Statistics [background; Wikipedia page 404, unconfirmed]. skfolio has a Stacking Optimization estimator (opened).
- Text models: FinBERT (Araci 2019, arXiv:1908.10063) [background]; sentence-transformers (Apache-2.0, 6.2.0, 2026-10-21); transformers (Apache 2.0, 5.22.2, 2026-11-06). Used to turn news text into sentiment/embedding features.
- Change-point detection: ruptures (BSD-2, 1.1.10, 2025-09-10) [extra].

## F. Existing tools: what they report

- **QuantStats** [opened: https://github.com/ranaroussi/quantstats ; Apache-2.0]. Reports: `reports.metrics/plots/basic/full/html` (HTML tear sheet). Stats functions listed: sharpe, sortino, max_drawdown, cagr, volatility, win_rate, value_at_risk, conditional_value_at_risk, calmar, kelly_criterion, tail_ratio, ulcer_index, information_ratio. Plots: daily_returns, distribution, drawdown, drawdowns_periods, earnings, histogram, log_returns, monthly_heatmap, montecarlo, returns, rolling_beta, rolling_sharpe, rolling_sortino, rolling_volatility, snapshot, yearly_returns. README says basic vs full split is not documented.
- **pyfolio-reloaded** [opened: https://github.com/stefan-jansen/pyfolio-reloaded]: "tear sheets" combining plots and summary statistics; performance metrics and plots over time, backtest vs out-of-sample. Tear-sheet list (returns, positions, transactions, round trips, Bayesian) not shown on the README (unconfirmed); docs at https://pyfolio.ml4trading.io (not opened).
- **empyrical-reloaded** [opened: https://github.com/stefan-jansen/empyrical-reloaded]: functions max_drawdown, alpha_beta, capture, roll_max_drawdown, roll_up_capture, plus volatility, VaR, Sharpe, Sortino per README; data helpers `get_fama_french`, `get_symbol_returns_from_yahoo`.
- **Riskfolio-Lib** [opened: https://riskfolio-lib.readthedocs.io/en/latest/ ; BSD]: 26 convex risk measures (dispersion, downside incl. CVaR/EVaR, drawdown incl. Ulcer, CDaR); mean-risk and Kelly optimization; risk parity (22 measures); HRP/HERC (37 measures); NCO; Black-Litterman variants and Entropy Pooling; factor models with per-factor risk contribution; constraints (tracking error, turnover, cardinality); efficient frontiers; plots and Jupyter/Excel reports; CVXPY solvers.
- **skfolio** [opened: https://github.com/skfolio/skfolio ; BSD]: naive, convex (MeanRisk, RiskBudgeting, MaxDiversification, DR-CVaR, Benchmark Tracker), clustering (HRP, HERC, Schur, NCO), stacking; risk measures list (variance, semivariance, CVaR, EVaR, drawdown family, Ulcer, etc.); WalkForward, CombinatorialPurgedCV; priors (empirical, factor models, Black-Litterman, synthetic data stress tests, entropy pooling, opinion pooling); `summary()`, `plot_cumulative_returns()`, `plot_distribution()`, Sharpe, Sortino, Calmar attributes.
- **PyPortfolioOpt** [opened: https://github.com/robertmartin8/PyPortfolioOpt ; MIT]: expected returns (historical mean, EWM mean, CAPM); risk models (sample, semicovariance, exponential, MCD, Ledoit-Wolf, OAS); objectives (max Sharpe, min vol, efficient return/risk, max quadratic utility); mean-semivariance, mean-CVaR, HRP, CLA; Black-Litterman; discrete allocation to whole shares; `portfolio_performance` returns expected annual return, annual volatility, Sharpe; covariance/correlation plot, efficient frontier plot.
- **ffn / bt** [opened README only: https://github.com/pmorissette/ffn ; MIT]: ffn described as "performance measurement and evaluation", graphing, data transformations; bt is a backtesting framework on ffn. Specific stats list not on the README (unconfirmed; docs https://pmorissette.github.io/ffn/ not opened).
- **Portfolio Visualizer** [opened: https://www.portfoliovisualizer.com/backtest-portfolio]: Summary (annualized return, benchmark-relative return, std dev, drawdown, growth of $10,000, CAGR, best/worst year, max drawdown, Sharpe, Sortino, active return, tracking error, information ratio, benchmark correlation); Returns (annual, monthly, trailing, rolling); Risk and Return Metrics (arithmetic/geometric mean, downside deviation, beta, alpha, R2, Sharpe, Sortino, Treynor, Calmar, M2, skew, kurtosis, VaR, CVaR, up/down capture, safe and perpetual withdrawal rates, gain/loss ratio); Up vs down market; Benchmark comparison (active return contribution, rolling active return); Drawdowns (worst 10, historical stress periods); Asset-level (per-holding stats, monthly correlations, return decomposition, risk decomposition); Holdings and style (category, weights, yield, expense ratio, P/E, duration, market-cap, sector, credit quality).
- **Ghostfolio** [opened: https://github.com/ghostfolio/ghostfolio ; AGPL-3.0]: transactions, multiple accounts, performance by return on average investment (ROAI) including dividends over Today, WTD, MTD, YTD, 1Y, 5Y, Max; charts; "static analysis to flag potential risks"; import/export; PWA. No Sharpe, beta or VaR listed on the README.
- **Koyfin** [opened: https://www.koyfin.com/features/]: client portfolios (imports from Schwab, Altruist, PDF statements), model portfolios with analytics, reports that track performance and "assess risk"; customizable benchmarks; no attribution or specific risk metrics named on the page.
- **Morningstar Portfolio X-Ray** [unconfirmed: page fetch empty]. https://www.morningstar.com/lp/portfolio-xray . Commonly described contents (asset allocation, style box, sectors, fees, overlap) not verified.
- **Interactive Brokers PortfolioAnalyst** [unconfirmed: https://www.interactivebrokers.com/campus/trading-lessons/portfolioanalyst/ returned 403]. Contents (performance, TWR vs MWR, risk measures, allocation, benchmarks) not verified.
