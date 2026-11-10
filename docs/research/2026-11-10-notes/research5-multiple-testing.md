# Research 5: guarding against false discoveries when many strategies/signals are tested

Date of gathering: 2026-11-10. Gatherer notes only; no verdicts. Earlier notes read first: research2-maths-toolbox.md (had only one-line, snippet/background entries for HLZ, DSR, PBO, purged CV, and "SSRN blocked") and research2-sota-models.md (book listing only). This file fills in the formulas, procedures, numbers and package details.

Tags: [page] = I opened the page or PDF and read it there (PDFs downloaded and text-extracted locally). [snippet] = seen only in a search result or secondary summary. [unconfirmed] = could not confirm. Where the tag covers a whole bullet, it applies to every fact in it unless a sub-tag is given. "[calc]" = my own arithmetic check, run in this session (script in scratchpad: dsrcheck.py).
PDF text extraction dropped Greek letters and some equations in several papers. Where a formula was reconstructed from the surrounding words and a code snippet, the bullet says so.

Notation used below: SR = Sharpe ratio per period (not annualised unless stated); T = number of return observations; N = number of (independent) trials; M = number of tests or raw trials; g3, g4 = skewness and (raw) kurtosis of returns (g4 = 3 for normal); Z = standard normal CDF; Zinv = its inverse; gamma_E = 0.5772156649 (Euler-Mascheroni).

---------------------------------------------------------------------
## 1. White Reality Check, Hansen SPA, Romano-Wolf StepM, Model Confidence Set; `arch` package

### 1a. Papers
- White (2000), "A Reality Check for Data Snooping", Econometrica 68(5), 1097-1126. Abstract: proposes a straightforward procedure to test the null that the best model found in a specification search has no predictive superiority over a benchmark. [page] https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping . Full-text PDF links found (users.ssc.wisc.edu/~bhansen/718/White2000.pdf) returned an empty file when I downloaded them, so I did not read the paper body. The statistic (maximum of normalised sample-average performance differences across candidates; p-value from a bootstrap distribution of that maximum) comes from a search-result quotation of a later paper. [snippet] 
- Hansen (2005), "A Test for Superior Predictive Ability", J. Business & Economic Statistics 23(4), 365-380. [page] PDF: https://reinhardhansen.github.io/papers/2005Hansen-SPA-JBES.pdf
  - Same framework as White: m alternative forecasts against one benchmark; skill defined by expected loss. Null: the benchmark is not inferior to any alternative. [page]
  - Two changes versus the Reality Check (RC): (1) a studentised statistic, (2) a sample-dependent null distribution. Claimed result: more powerful, less sensitive to poor and irrelevant alternatives; RC can be manipulated by adding poor/irrelevant alternatives. [page]
  - Statistic: T_SPA = max( max_k [ sqrt(n) * dbar_k / omega_k_hat ], 0 ), where dbar_k is the mean loss differential (benchmark loss minus model-k loss) and omega_k_hat^2 estimates var(sqrt(n) dbar_k). [page; the sign convention of dbar_k is my reading of the text]
  - Null centring: mu_c_k = dbar_k * 1{ sqrt(n) dbar_k / omega_k_hat <= -sqrt(2 log log n) }. That is, a model is only "recentred" towards zero when its studentised performance is within the sqrt(2 log log n) threshold of the benchmark. [page]
  - One Monte Carlo example in the paper: studentisation raises power of a 5%-level test from about 15% to about 53%. [page]
  - Empirical application: regression-based forecasts of annual US inflation against a random-walk benchmark. [page]
  - Three p-values (lower, consistent, upper) differ in how they recentre; see `arch` below.
- Romano and Wolf (2005), "Stepwise Multiple Testing as Formalized Data Snooping", Econometrica 73(4), 1237-1282. Stepdown method that asymptotically controls the familywise error rate (FWER), rejects more false nulls than single-step methods (RC), uses the joint dependence through the bootstrap, and favours studentisation. [snippet] https://econpapers.repec.org/RePEc:ecm:emetrp:v:73:y:2005:i:4:p:1237-1282 . The step-by-step algorithm itself: [unconfirmed] (paper not opened; the `arch` StepM docs state it uses the Romano-Wolf method plus SPA-style consistent selection, see below).
- Hansen, Lunde, Nason (2011), "The Model Confidence Set", Econometrica 79(2), 453-497. [page] PDF: https://reinhardhansen.github.io/papers/2011HansenLundeNason-MCS-Econometrica.pdf
  - Idea: a set of models built to contain the best model at a chosen confidence level; no model is assumed true; informative data give a small set, uninformative data a large one. [page]
  - Built from an equivalence test (null: all models in the current set M have equal expected loss) and an elimination rule. Apply the test to the full set; if rejected, eliminate one model by the rule; repeat until the test no longer rejects. The survivors are the MCS. [page]
  - Loss differentials d_ij,t = L_i,t - L_j,t. dbar_ij = mean over t; dbar_i. = average of dbar_ij over j in M. t_ij = dbar_ij / se(dbar_ij); t_i. = dbar_i. / se(dbar_i.). [page]
  - Two statistics: T_max,M = max over i in M of t_i. ; T_R,M = max over i,j in M of |t_ij|. Their null distributions are non-standard and are obtained by bootstrap. [page]
  - Elimination rules: for T_max, remove the model with the largest t_i. ; for T_R, remove the model i that attains the max of |t_ij| (the one with the largest standardised excess loss against some other model). Both pairs satisfy the "coherency" condition in the paper (Proposition 1). [page]
  - A quadratic-form statistic T_Q (chi-squared) is also described but needs closed testing for coherence, and an estimate of a covariance matrix that is hard when the number of models is large relative to T. [page]
  - Assumption 2 is on the loss differentials d_ij,t (strictly stationary, alpha-mixing, finite moments), not on the losses themselves. [page]
  - MCS p-value: for each model, the smallest alpha at which it would still be in the set; a model is in the MCS at level alpha if its MCS p-value >= alpha; for an eliminated model, the MCS p-value is the running maximum of the test p-values over the elimination steps. [snippet] (secondary summary of the paper; the elimination structure is [page] above, the running-max wording is [snippet])
  - A R-package page warns that the t_min statistic violates coherency and should not be used; I did not open that page. [snippet]

### 1b. The `arch` package (Kevin Sheppard)
- PyPI: arch 8.0.0, uploaded 2025-10-21 (per the PyPI JSON for the latest release); license NCSA. [page] https://pypi.org/project/arch/ (data read from https://pypi.org/pypi/arch/json)
- Docs section "Multiple Comparisons": "a set of bootstrap-based multiple comparison procedures" controlling the familywise error rate. [page] https://arch.readthedocs.io/en/latest/multiple-comparison/multiple-comparisons.html and examples https://arch.readthedocs.io/en/stable/multiple-comparison/multiple-comparison_examples.html
- Classes, all imported from `arch.bootstrap`: `SPA`, `StepM`, `MCS`. `RealityCheck` is an alias of `SPA` ("also known as Reality Check"). [page]
- `SPA(benchmark, models, block_size=None, reps=1000, bootstrap='stationary', studentize=True, nested=False, *, seed=None)`. [page] https://arch.readthedocs.io/en/stable/multiple-comparison/generated/arch.bootstrap.SPA.html
  - benchmark: T-element array of benchmark LOSSES. models: T x k array of alternative LOSSES. (Losses, not returns: lower is better.)
  - block_size default sqrt(T), docs say set it from the data. bootstrap: 'stationary'/'sb' (default), 'circular'/'cbb', 'moving block'/'mbb'. studentize=True. nested=False (nested bootstrap needs k extra bootstraps, slow).
  - Methods: compute(), better_models(pvalue, pvalue_type), critical_values(pvalue), reset(), seed(). Property: pvalues (lower, consistent, upper).
  - p-value definitions: upper never recentres any model; consistent recentres only when a model is within a log(log(T)) bound of the benchmark; lower never recentres a model that does worse than the benchmark. The examples page says the consistent p-value should generally be used.
  - Null in the docs example: no model is better than the benchmark, H0: max_i E[L_i] >= E[L_bm].
  - References listed: Hansen (2005); White (2000); related procedure StepM = Romano-Wolf.
- `StepM(benchmark, models, size=0.05, block_size=None, reps=1000, bootstrap='stationary', studentize=True, nested=False, seed=None)`; compute(); property superior_models (indices or column names of models found better than the benchmark); controls FWER at `size`. Docs say it is the Romano-Wolf (2005) method and uses SPA plus a consistent selection procedure. [page] https://arch.readthedocs.io/en/stable/multiple-comparison/generated/arch.bootstrap.StepM.html
- `MCS(losses, size, block_size=None, method='R', reps=1000, bootstrap='stationary', seed=None)`; losses is T x k (T periods, k models); method 'R' (default) or 'max' = the T_R,M / T_max,M procedures above; compute(); properties included, excluded, pvalues (model p-values for inclusion in the MCS). Docs cite Hansen, Lunde, Nason (2011) only and do not explain the steps. [page] https://arch.readthedocs.io/en/stable/multiple-comparison/generated/arch.bootstrap.MCS.html (the docs examples page uses size=0.10; the class page text mentions a 0.05 default in the description but shows no default in the signature)
- Inputs for all three: a loss matrix of T time points by k strategies (the "trials"), plus a benchmark loss column for SPA/StepM. Number of trials = number of columns. No separate N argument.
- Thresholds from the source: none beyond the user-chosen `size` (0.05 / 0.10 in docs) and the sqrt(2 log log n) recentring threshold in Hansen (2005).
- Note on use: SPA/StepM test "does anything beat the benchmark" given the whole set of columns supplied; the multiplicity is whatever columns you pass in.

---------------------------------------------------------------------
## 2. Sullivan, Timmermann, White (1999) on technical trading rules

- Reference: "Data-Snooping, Technical Trading Rule Performance, and the Bootstrap", Journal of Finance 54(5), 1647-1691. [page] PDF (working-paper-style copy of the JF text): https://bashtage.github.io/kevinsheppard.com/files/teaching/mfe/advanced-econometrics/Sullivan_Timmermann_White.pdf
- What they did: used White's Reality Check bootstrap to evaluate technical rules while adjusting for the search over the whole universe of rules; extended Brock, Lakonishok, LeBaron (1992, "BLL") from 26 rules to a full universe of 7,846 rule parameterisations; applied to 100 years of daily Dow Jones Industrial Average data, 1897-1996. [page]
- Rule families: filter rules, moving averages, support and resistance, channel breakouts, on-balance-volume averages. Performance criteria: mean return and Sharpe ratio. [page]
- Computation note: because of computing limits, a subsample of the 7,846 rules was used for one eigenvalue/correlation comparison. [page]
- Results reported (all [page]):
  - BLL universe of 26 rules: the apparent superiority of the best rule survived the data-snooping adjustment in the full sample and first four sub-periods (every one of the 26 rules beat the benchmark). Best rule over 1897-1996: 50-day variable moving average with a 0.01 band, annualised return 9.4%.
  - Full universe (7,846 rules): best rule by mean return over the 100 years is the five-day simple moving average; data-snooping-adjusted p-values below 0.002 in the four in-sample sub-periods and the best rule's mean return was much higher than the best BLL rule.
  - Out-of-sample, 1987-1996 DJIA: the probability that the best rule did not beat the benchmark was nearly 12%; the authors say there is scant evidence the rules had economic value in that period.
  - S&P 500 futures, 1984-1996 (7,846 rules): the best rule had about 10% annual return and a nominal p-value of 0.04, but the data-snooping-adjusted p-value was 0.90. Under the Sharpe criterion the nominal p-value was below 0.002 and the adjusted p-value 0.99.
  - They state a Bonferroni bound (number of rules times smallest nominal p-value, e.g. 8,000 times) would be misleading for this problem. Calculation checks: the overall probability that a bootstrapped performance measure exceeds the actual was 0.489 across rules and bootstrap samples.
  - Bootstrap: 500 bootstrap samples in the check described; stationary bootstrap style as in White (2000) [snippet for the 500 figure context; text line read mentions "500 bootstrap samples"].
- Inputs the method needs: the daily return series of every rule in the universe (rules x time matrix of returns or of excess returns over a benchmark), the benchmark, the number of bootstrap samples.

---------------------------------------------------------------------
## 3. Harvey, Liu, Zhu (2016); Harvey and Liu "Backtesting" (2015); Bonferroni, Holm, BHY

### 3a. HLZ (2016) "... and the Cross-Section of Expected Returns"
- Reference: NBER WP 20592 (Oct 2014 / 2015 versions); Review of Financial Studies 29(1), 2016 (journal page not opened; volume taken from NBER page text). [page] https://www.nber.org/papers/w20592 ; PDF read: https://www.nber.org/system/files/working_papers/w20592/w20592.pdf
- Count: at least 316 factors tested in the literature through 2012 (collected from top journals and selected working papers; the authors say this undercounts). [page]
- Headline: a newly discovered factor today should clear a t-ratio of about 3.0 (p-value 0.27%), not 2.0. They also say 3.0 is probably too low because unpublished tries are hidden. [page]
- Procedures (p-values p(1) <= ... <= p(M), M tests, FWER level w, FDR level d) [page]:
  - Bonferroni: adjusted p = min(M * p, 1). Reject if p <= w / M. Controls FWER with no dependence assumption.
  - Holm (step-down): find the smallest k with p(k) > w / (M + 1 - k); reject hypotheses 1..k-1. Adjusted p(i) = min( max over j<=i of (M - j + 1) p(j), 1 ). Holm rejects at least everything Bonferroni rejects.
  - BHY (Benjamini, Hochberg, Yekutieli; step-up): find the largest k with p(k) <= (k / M) * d / c(M); reject 1..k. c(M) = sum_{j=1..M} 1/j (the Benjamini-Yekutieli 2001 choice, valid under arbitrary dependence). Adjusted p(M) = p(M); p(i) = min( p(i+1), M * c(M) * p(i) / i ).
- Settings in the paper: FWER w = 5% (Holm/Bonferroni), FDR d = 1% (BHY) for main results; d = 5% also shown. [page]
- Thresholds they report with M = number of published factors, assuming all tried factors were published (M = R) [page]:
  - Bonferroni benchmark t-ratio rises from 1.96 (first test, 1967) to 3.78 by 2012, 4.00 by 2032.
  - Holm 3.64 with 316 factors; 3.29 if the count is cut to 113 "common" factors.
  - BHY (1% FDR) settles near 3.39 after 2010 (p = 0.07%).
- With hidden tests (M > R): they estimate 71% of tried factors are missing; Bonferroni 4.01 and Holm 3.96; BHY from 3.39 to 3.68 at 1%, and from 2.78 to 3.18 at 5%. They state 3.18 as the minimum threshold across their scenarios. [page]
- Their model-based scenarios elsewhere: baseline estimate M = 1,297 tried factors with 39.6% zero-alpha; conservative M = 2,458 with 68.3% zero-alpha (as quoted by Jensen-Kelly-Pedersen). [page, via JKP text] 
- Test dependence: Section 5 of the paper adds a model using correlations among strategy returns (not read in detail).
- Rule from the paper's conclusion: a factor with a first-principles theory could use a lower hurdle than a purely empirical one; 2.0 is no longer appropriate for either. [page]
- Sharpe/t link for use with HLZ thresholds: t = SR_per_period * sqrt(T) (Harvey-Liu 2015, see 3b). [page]

### 3b. Harvey and Liu (2015) "Backtesting" and the haircut Sharpe ratio
- Reference: Journal of Portfolio Management 42(1), Fall 2015, pp. 13-28 (the page I read shows "FALL 2015"; volume number not shown in the extract). [page] PDF: https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF (SSRN 2345489 per citation in Bailey et al.). 
- Procedure ("three steps") [page]:
  1. Convert the Sharpe ratio to a t-ratio: t = SR_hat * sqrt(T) with SR per period (annual SR with monthly data: SR_annual = sqrt(12) * mean/std of monthly returns), and compute the single-test p-value pS = Pr(|r| > t) with r ~ t-distribution, T-1 degrees of freedom.
  2. Compute the multiple-testing adjusted p-value pM. In the independent-tests illustration: pM = 1 - (1 - pS)^N, with N strategies tried and the best one reported. N = 10 and pS = 0.05 gives pM = 0.401.
  3. Convert pM back to a t-ratio, then to a Sharpe ratio: the haircut Sharpe ratio HSR. Haircut hc = (SR - HSR) / SR.
  - With dependence and 3 adjustment methods (Bonferroni, Holm, BHY) they use the HLZ structural model (mixture distribution for true strategy returns, with a correlation parameter rho, parameter estimates for rho = 0, 0.2, 0.4, 0.6, 0.8, interpolated linearly) and simulation: repeat the procedure many times to get a sample of pM, take the median as the final adjusted p-value. Inputs for the program: sampling frequency, number of observations, Sharpe ratio, SR autocorrelation, number of tests, average correlation among strategy returns. [page]
- Worked numbers the paper gives [page]:
  - 20 years of monthly returns (T = 240), annual SR 0.75: single-test p = 0.0008. With N = 200 independent tests, pM = 0.15 and the adjusted annual SR is 0.32, a haircut of about 60%.
  - Three example strategies (E/P, and the best "BAB" with SR 0.78; SRs range 0.43 to 0.78): with 50 trials the haircut is almost 50% for the weakest (E/P) and 7.9% for BAB (Bonferroni). For E/P alone the multiple-testing p-value is 0.029 and the haircut about 27% in the simple 10-test example.
  - General pattern: haircut is almost always more than 50% and sometimes much larger when annual SR < 0.4; at most 25% when SR > 1.0. The authors say the common 50% rule of thumb is too lenient for SR < 0.4 and too harsh for SR > 1.0. Holm gives smaller haircuts than Bonferroni; BHY haircuts are in the same range as the others.
  - Program example: annualised SR 1.0 over 120 months, 100 tests, average correlation 0.4, monthly autocorrelation 0.1: autocorrelation-corrected SR 0.912; BHY-adjusted annual SR 0.438; haircut 52.0%.
  - Profit hurdle example (their Exhibit 4): 240 monthly observations, 10% annual volatility: single test needs 0.365% per month (4.4% a year); BHY with 300 tests needs 0.616% per month (7.4% a year). Program example with 20 years, 10% vol, 300 tests, correlation 0.4, 5% level: BHY hurdle 0.621% a month; average of methods 0.670% a month.
- Code: Matlab functions `Haircut_SR` and `Profit_Hurdle` on the author's page (named in the paper; link http://faculty.fuqua.duke.edu/~charvey/backtesting, not checked as live). [page for the names; link status unconfirmed]
- Python: the package `factor-qc` (below, section 5e) lists a "Harvey-Liu haircut". No other maintained Python port of Haircut_SR found. [page for factor-qc listing; absence is [unconfirmed]]

### 3c. Bonferroni / Holm / BH / BHY as in `statsmodels`: see section 9.

---------------------------------------------------------------------
## 4. Bailey, Borwein, Lopez de Prado, Zhu: MinBTL and PBO

### 4a. "Pseudo-Mathematics and Financial Charlatanism" (Notices of the AMS 61(5), May 2014, 458-471)
- Text read from the authors' copy: https://carmamaths.org/jon/backtest.pdf [page]
- Expected maximum Sharpe ratio after N independent trials with true SR zero, annualised, sample of y years (Eq. 3.1): E[max_N] ~ y^(-1/2) * ( (1 - gamma_E) * Zinv(1 - 1/N) + gamma_E * Zinv(1 - 1/(N*e)) ). [page]
- Minimum Backtest Length (Theorem 3.1): MinBTL (years) < ( (1 - gamma_E) Zinv(1 - 1/N) + gamma_E Zinv(1 - 1/(N e)) )^2 / E[max_N]^2 < 2 ln(N) / E[max_N]^2. [page]
- Inputs: N (number of independent configurations tried) and the target in-sample annualised SR E[max_N] that you want to be unable to produce by luck.
- Numbers the paper gives [page]:
  - With E[max_N] fixed at 1: if only 5 years of data are available, no more than 45 independent configurations should be tried; with 2 years, about 7.
  - The paper says MinBTL is a necessary, not sufficient, condition; the N must be independent and, if trials are dependent, N can be derived by dimension reduction such as PCA. A backtest that does not report N cannot be assessed for overfit risk.
- Model complexity example: 5 on/off parameters gives 2^5 = 32 configurations. [page]
- Python for MinBTL: `deflated_sharpe.min_backtest_length(target_sr, num_trials)` in the small package `deflated-sharpe` (returns observations); `factor-qc` lists a MinTRL gate. [page: PyPI listing]. Whether their formula equals Eq. 3.2 exactly: [unconfirmed].

### 4b. "The Probability of Backtest Overfitting" (Bailey, Borwein, Lopez de Prado, Zhu)
- Journal of Computational Finance 20(4), 2017 (SSRN 2326253). Text read from the authors' copy: https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf [page]. Publication details from earlier notes (research2-maths-toolbox.md) and the SSRN number cited in that file; journal page itself not opened. [snippet]
- Definition: the selection process overfits if the strategy with the best in-sample (IS) performance has an expected out-of-sample (OOS) rank below the median. PBO = probability that the IS-best strategy lands below the median OOS rank. Model-free; works with any performance statistic. [page]
- CSCV procedure (Algorithm 2.3), step by step [page]:
  1. Build a T x N matrix M of P&L (or return) series, one column per trial; rows synchronous across trials; the metric (e.g. Sharpe) must be computable on subsamples.
  2. Split the rows into an even number S of equal, disjoint, time-ordered submatrices M_s, each (T/S) x N.
  3. Form all C(S, S/2) combinations of S/2 submatrices. S = 16 gives 12,870 combinations (the paper's text prints "12, 780"; C(16,8) = 12,870, so I regard 12,780 as a typo; the `fynance` code uses 12,870). S = 12 gives 924; S = 24 gives 2,704,156.
  4. For each combination c: training set J = the S/2 chosen blocks joined in original order (T/2 x N); testing set J-bar = the complement. Compute the metric for each of the N columns on J (vector R_c) and on J-bar (vector R-bar_c); rank them (r_c, r-bar_c).
  5. Find the trial n* with the best IS rank. Take its OOS relative rank omega_c = r-bar_c(n*) / (N + 1), in (0, 1).
  6. logit lambda_c = ln( omega_c / (1 - omega_c) ). High logit = IS and OOS agree.
  7. Collect all logits; PBO = fraction of combinations with lambda_c <= 0, i.e. the share where the IS winner ranks at or below the OOS median.
- Companion statistics in the paper: performance degradation (regression of OOS on IS performance of the selected strategy, slope usually negative), probability of loss (share of splits where the IS-best strategy loses OOS), stochastic dominance of the selection procedure vs picking randomly. [page]
- Threshold: "a customary approach" is to reject models whose estimated PBO exceeds 0.05 (the paper presents this as an application of the Neyman-Pearson convention, not a derived cutoff). Other suggested uses: PBO as a prior; PBO-based portfolio weights (1 - PBO or 1/PBO). [page]
- Choice of S: S must be large enough to give many logits but not so large that blocks break up time structure; for more than 6 years of data S = 24 gives blocks of about a quarter; if quarterly effects matter use S = 12 (924 logits). Sampling error of an estimated proportion is at most 1/(2*sqrt(count)). [page]
- Worked results in the paper: a strategy-optimisation example with PBO 74% (random-walk data) and a real-instrument example with PBO 0.04%. [page]
- Python: `fynance` 2.13.1 (uploaded 2026-07-06, MIT) has `fynance.research.overfit.pbo(returns_panel, n_blocks=16, metric=None)` returning a `PBOResult` (pbo, logits, prob_oos_loss, slope, intercept, is_perf, oos_perf); n_blocks even and at most 16 (cap 12,870 splits); default metric is a Sharpe-like mean/std. [page: source listing at https://fynance.readthedocs.io/en/master/_modules/fynance/research/overfit.html and PyPI JSON]
  - `factor-qc` 0.1.3 (2026-09-04, MIT): DSR, PBO via CSCV (12,870 splits at n_blocks=16), Harvey-Liu haircut, MinTRL; its own README calls it v0.1.3 alpha, "published on PyPI", numpy only, Python >= 3.11, "refuses to judge a backtest that will not declare how many configurations were tried". [page: PyPI JSON description]
  - `sharpebench` 0.28.0 (2026-09-18, MIT OR Apache-2.0): lists deflated Sharpe and `probability_of_backtest_overfitting(perf_matrix, s=16)`; Rust kernel. [snippet from search result; PyPI JSON confirms version/date/summary]
  - A web demo from the authors: http://datagrid.lbl.gov/backtest (named in the DSR paper; liveness unchecked). [page for mention; liveness unconfirmed]

---------------------------------------------------------------------
## 5. Deflated Sharpe Ratio (Bailey and Lopez de Prado 2014) and effective number of trials

### 5a. Formulas (paper read: https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
Reference: Journal of Portfolio Management 40(5), 94-107 (2014); SSRN 2460551. [page]
Greek symbols and equations were lost in extraction. Formulas below are rebuilt from the paper's surrounding words, its Python snippet 1, and Lopez de Prado's 2018 "10 Reasons" paper (which prints the same formulas with symbols partly stripped). The arithmetic check below reproduces the paper's own stated numbers, which supports the reconstruction.
- Probabilistic Sharpe ratio (Bailey and Lopez de Prado 2012): PSR(SR*) = Z( (SR_hat - SR*) * sqrt(T - 1) / sqrt( 1 - g3 * SR_hat + ((g4 - 1)/4) * SR_hat^2 ) ). SR_hat, SR* non-annualised, same frequency as the T observations. [page, reconstructed]
- Expected maximum of N trial Sharpe ratios (False Strategy theorem / Eq. 1): E[max_n SR_n] ~ sqrt(V[{SR_n}]) * ( (1 - gamma_E) * Zinv(1 - 1/N) + gamma_E * Zinv(1 - 1/(N * e)) ), assuming trial SRs are Normal with mean 0 under the null. V[{SR_n}] = variance across the trials' estimated SRs. Confirmed by the paper's code: `maxZ=(1-emc)*ss.norm.ppf(1-1./numTrials)+emc*ss.norm.ppf(1-1./(numTrials*np.e)); return mu+sigma*maxZ`. [page]
- DSR = PSR evaluated at SR* = SR0 where SR0 is that expected maximum: DSR = Z( (SR_hat - SR0) * sqrt(T - 1) / sqrt(1 - g3*SR_hat + ((g4-1)/4)*SR_hat^2) ). The paper describes it as "a PSR where the rejection threshold is adjusted to reflect the multiplicity of trials"; the output is a probability that the true SR exceeds SR0. [page]
- Inputs: SR_hat of the selected strategy; T (number of return observations); g3, g4 of the selected strategy's returns; N (independent trials); V[{SR}] (cross-trial variance of SR at the same frequency). Five things beyond plain SR: non-normality (g3, g4), length T, V[{SR}], N. [page]
- Worked numbers in the paper [page text; parameter values themselves were lost in extraction and are reconstructed in the [calc] bullet]:
  - Strategist backtests many Treasury-auction configurations; many give annualised SR 2, the chosen one 2.5 over 5 years of daily data, T = 1,250 (250 days a year).
  - With the investor's disclosed N, V, skew, kurtosis, the benchmark is non-annualised and the DSR comes out near 0.90, i.e. "only a 90% chance" the true SR is above zero, so the discovery is rejected at 95%.
  - The paper says that with only N = 46 independent trials the DSR would have been 0.9505 (above 95%). And if returns had been Normal, N = 88 would reach the 95% line.
  - [calc] My reconstruction: N = 100, V[{SR}] = 0.5 (annualised, so 0.5/250 per day), SR_hat = 2.5/sqrt(250) = 0.158, T = 1,250, skew -3, kurtosis 10. Result: SR0 = 0.1132, DSR = 0.9004 at N = 100; DSR = 0.9505 at N = 46; with Normal returns DSR = 0.9505 at N = 88 (computed 0.9505) . These match the three numbers the paper states, so the parameter values are probably right, but the paper's own parameter list is [unconfirmed] (glyphs not extracted).
- E[max of N standard-normal SRs] (Z-scale, V = 1) [calc from the formula above]: N = 10: 1.575; 100: 2.531; 200: 2.766; 1,000: 3.255; 10,000: 3.861. For comparison a secondary summary says about 3.3 for 1,000 trials. [snippet] https://www.cxoadvisory.com/big-ideas/estimating-the-level-of-and-correcting-for-snooping-bias/
- The paper encourages computing DSR with both its threshold and the Harvey-Liu threshold (the two are described as complementary). [page]
- "When should we stop testing": a secretary-problem rule: sample about 1/e (37%) of the justifiable configurations at random, then keep going until one beats all earlier ones, and select that one. Described as a rule of thumb. [page]
- The paper says the holdout method cannot prevent backtest overfitting because it treats the test as a single trial; applying holdout about 20 times at 95% makes a false positive expected. [page]

### 5b. Estimating the effective number of independent trials
- Bailey and Lopez de Prado 2014, Appendix A.3 (average-correlation method) [page; equations 7-9 lost in extraction]:
  - M trials run, N <= M independent. Using M overstates E[max SR].
  - Replace every off-diagonal correlation with one constant rho_bar such that the quadratic form w'Cw is unchanged; with equal weights rho_bar = the average of the off-diagonal entries. rho_bar is bounded below by about -1/(M-1) (positive-definiteness).
  - N-hat is obtained by interpolation between the two extremes: rho_bar -> 1 gives N -> 1, and rho_bar -> 0 gives N -> M (Eq. 9). The closed form I recall is N_hat = rho_bar + (1 - rho_bar) * M. [unconfirmed: the equation glyphs were not extractable]
  - Warnings in the paper: correlation is only a linear dependence measure; when M exceeds T the correlation matrix is ill-conditioned and the estimated average correlation may itself be overfit (more correlations than independent pairs of observations); suggested remedy is to reduce the matrix dimension first, or to use an information-theory (entropy) route (named, not developed). [page]
  - MinBTL paper (4a) says dimension reduction such as PCA can give the number of independent trials. [page]
- Lopez de Prado and Lewis (2019), "Detection of False Investment Strategies Using Unsupervised Learning Methods", Quantitative Finance 19(9), 1555-1565. Working paper read: https://smallake.kr/wp-content/uploads/2020/04/SSRN-id3167017.pdf (3rd-party mirror of SSRN 3167017, Nov 2018 version) [page]. The journal abstract page was blocked (403); the journal reference is from a search result. [snippet]
  - Purpose: estimate the number K of effectively uncorrelated trials, and the variance of the Sharpe ratio across them, so both can be fed into the False Strategy theorem / DSR. They control FWER (not FDR) because the investor is shown only the single best strategy. [page]
  - Step 1, ONC (Optimal Number of Clusters) on the trials' correlation matrix rho: distance d_ij = sqrt( (1 - rho_ij) / 2 ); then a distance-of-distances D_ij = sqrt( sum_k (d_ik - d_jk)^2 ); k-means on D with the number of clusters chosen by maximising a silhouette-based quality statistic (mean/std of silhouette scores), many random initialisations; then a recursive second stage re-clusters the clusters whose quality is below average and keeps the re-clustering if it improves average quality. K = number of clusters. Code for both stages is printed in the appendix (sklearn KMeans, silhouette_samples). [page]
  - Step 2, variance of clustered trials: for each cluster form one return series with minimum-variance weights w = C^-1 1 / (1' C^-1 1) (C = covariance of members); compute each cluster-series Sharpe ratio, annualised with a trading-frequency adjustment; estimate V of those cluster SRs; convert back to the selected strategy's frequency. [page]
  - Step 3 (use): put K as N and the cluster-SR variance as V[{SR}] in the expected-max-SR formula, or use K in a Sidak-type FWER correction. [page]
  - Validation: Monte Carlo with random block-correlation matrices of known cluster count; boxplots of (estimated K) / (true K) are close to 1 and the algorithm frequently recovers the right count (exact accuracy numbers not extracted). [page]
  - Limits stated by a secondary summary: true number of backtests behind a published anomaly may be unknown; needs records of a large number of past backtests. [snippet] CXO Advisory page above.
- Lopez de Prado (Fall 2019) "A Data Science Solution to the Multiple-Testing Crisis in Financial Research", Journal of Financial Data Science 1(1). I did not open this paper (SSRN downloads blocked). A search result describes it as the practitioner version of the ONC approach. [snippet] [unconfirmed for contents]
- Lopez de Prado 2018 "The 10 Reasons Most Machine Learning Funds Fail" (working-paper version Jan 27, 2018; JPM 44(6) per the Arnott-Harvey-Markowitz reference list): says that without the number of trials (I) one cannot determine FWER, FDR, PBO or similar; walk-forward backtests have high variance, so selecting the best of many gives false discoveries. [page] https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf . Same paper prints the PSR and DSR formulas above (symbols partly stripped). [page]
- Python for DSR:
  - `deflated-sharpe` 0.1.0 (2026-03-21, Apache-2.0, pure Python, no required dependencies, Python >= 3.10, 1 release, GitHub repo mnemox-ai/deflated-sharpe with about 9 stars and 14 commits): `deflated_sharpe_ratio(observed_sr=, num_trials=, num_obs=, skewness=0.0, kurtosis=3.0)` returning (dsr, p_value); `min_backtest_length(target_sr, num_trials)`; also `benjamini_hochberg` and a regime-decay class. Its README says a positive DSR with p < 0.05 means likely real alpha. It does not take a cross-trial variance argument in the quick-start; whether it estimates V internally: [unconfirmed]. [page: PyPI JSON description and GitHub page]
  - `factor-qc` 0.1.3 and `sharpebench` 0.28.0 (see 4b).
  - `fynance` documentation navigation lists `deflated_sharpe_ratio` and `probabilistic_sharpe_ratio` under `fynance.research`, but I only read the overfit (PBO) source. [page for the nav listing]
  - `mlfinlab` (Hudson & Thames): not on PyPI (404 for the name); the website sells it. Earlier notes (research-quant-projects.md) record the paid product. [page: PyPI 404; earlier notes]
  - `mlfinpy` 0.1.2 (2024-10-09, MIT; github.com/baobach/mlfinpy): described as reproducing Lopez de Prado's data transformation, labeling, sampling and feature-engineering techniques; whether it has DSR/PBO/CPCV: [unconfirmed]. [page: PyPI]
- Reference code in the DSR paper itself: Python snippet 1 (expected max SR, analytic vs simulated) public in the paper. [page]

---------------------------------------------------------------------
## 6. Purged k-fold with embargo; Combinatorial Purged CV (AFML ch. 7 and 12)

Primary text read: Lopez de Prado, "The 10 Reasons Most Machine Learning Funds Fail" (Solutions 8 and 9), which restates AFML material. AFML itself (Wiley 2018) was not opened. [page for the 10 Reasons text] https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf

### 6a. Purging and embargo
- Setting: each label y_i is a function of prices over a closed interval [t_i0, t_i1] (e.g. a triple-barrier label spanning bars t_i0..t_i1). [page]
- Purging: remove from the training set every observation whose label interval overlaps a test label interval. A training label j overlaps a test label i if any of three sufficient conditions holds: (1) t_j0 <= t_i0 <= t_j1; (2) t_j0 <= t_i1 <= t_j1; (3) t_i0 <= t_j0 <= t_j1 <= t_i1. [page]
- Embargo: because features can be serially correlated, also remove training observations that START just after a test set ends. Training labels that end before the test begins need no embargo. Implementation: extend each test label's end to t_i1 + h before purging. Size: h about 0.01 * T (T = number of bars) "often suffices". [page]
- A secondary summary says the same (purging on both sides, embargo after the test set) and that the skfolio doc has the same idea; see below. [snippet] (Wikipedia page for "Purged cross-validation" returned 404 when fetched)
- Why: a plain date split or plain k-fold lets labels that overlap the test window leak into training. The 10 Reasons paper says a single walk-forward path is one possibly unrepresentative split. [page]

### 6b. Combinatorial Purged CV (CPCV)
- Construction [page]: split T observations, in time order, into N groups (the first N-1 of size floor(T/N), the last one takes the rest). Choose k groups as the test set. All C(N, k) combinations give train/test splits (purge and embargo applied around each test group).
- Number of splits = C(N, k). Each group appears in the test set in k/N of the splits, so the tested groups can be reassembled into complete paths: number of backtest paths phi[N, k] = (k / N) * C(N, k) = C(N-1, k-1).
- Example given: N = 6, k = 2 gives C(6,2) = 15 splits and 5 paths, each group in 5 test sets; each path stitches together forecasts for all 6 groups from different splits. [page]
- Claimed use: gives a distribution of Sharpe ratios (one per path) rather than one number; no warm-up loss as in walk-forward. The number of paths grows with N and with k. [page]
- Reported weakness of walk-forward in the same paper: high variance; large portion of decisions based on a small portion of data. [page]
- Implementation 1: `skfolio` 1.12.8 (uploaded 2026-11-08, BSD-3-Clause, Python >= 3.10). `skfolio.model_selection.CombinatorialPurgedCV(n_folds=10, n_test_folds=8, purged_size=0, embargo_size=0)`; methods get_n_splits, get_path_ids, split, summary, plot_train_test_folds; properties n_splits, n_test_paths, recombined_paths, test_set_index, binary_train_test_sets. purged_size = number of observations removed from the train set after a test set and before a test set (as the doc words it); embargo_size = observations removed from the start of the train set after a test set. Docs gave an example n_folds=3, n_test_folds=2 yielding 3 splits and 2 test paths; helper `optimal_folds_number(n_observations, target_n_test_paths, target_train_size)`. Also a `WalkForward` splitter (single path). The reference cited is AFML 2018. [page] https://skfolio.org/generated/skfolio.model_selection.CombinatorialPurgedCV.html , https://skfolio.org/user_guide/model_selection.html , https://pypi.org/pypi/skfolio/json
  - Note: skfolio purges and embargoes by a fixed number of observations, not from per-label end times (t_i1). Whether it accepts label end-times: [unconfirmed] (not stated in the pages read).
- Implementation 2: `timeseriescv` 0.2 (2018-09-07, MIT): "scikit-learn style cross-validation classes for time series data". Contents not read. [snippet from the PyPI summary] 
- Implementation 3: `mlfinpy` and `mlfinlab`: unconfirmed whether they provide PurgedKFold/CPCV (see 5b).

---------------------------------------------------------------------
## 7. Replication evidence

### 7a. McLean and Pontiff (2016) [page]
- "Does Academic Research Destroy Stock Return Predictability?", Journal of Finance 71(1), 5-32. Working paper PDF read: https://counterpointfunds.com/wp-content/uploads/2017/07/PredictabilityMcleanPontiff.pdf
- 97 characteristics that predicted cross-sectional stock returns in peer-reviewed journals; long-short portfolios (extreme quintiles).
- Average predictor return: 26% lower out-of-sample (after the study's sample, before publication) and 58% lower post-publication. In-sample mean return 58.2 bps per month on average. The 26% is called an upper bound on data-mining effects; 58% - 26% = about 32% is attributed to publication-informed trading. They reject both "no decay" and "full disappearance". Decay is larger for predictors with higher in-sample return and t-stat, for price/trading-data-only predictors, and for liquid, low-idiosyncratic-risk stocks.
- Another summary quoted about 35% and "32%" figures; the 32% above is in the paper text I read; the 35% figure I could not trace. [snippet] (disagreement noted)

### 7b. Hou, Xue, Zhang (2020), "Replicating Anomalies"
- Review of Financial Studies 33(5), 2019-2133. [page for bibliographic data: https://ideas.repec.org/a/oup/rfinst/v33y2020i5p2019-2133..html ]
- Published abstract: 452 anomalies; with NYSE breakpoints and value-weighted returns (to cut microcap influence), 65% cannot clear |t| >= 1.96; failure rate rises to 82% under a multiple-test hurdle of 2.78 at 5% significance; even for those that replicate, magnitudes are much smaller. [page: IDEAS abstract]
- Working paper (NBER 23394, May 2017) numbers differ: 447 anomalies; 286 (64%) insignificant at 5%; imposing a t-cutoff of 3 raises insignificant to 380 (85%); 95 of 102 liquidity variables (93%) insignificant; of 161 significant, q-factor model leaves 115 alphas insignificant. [page] https://www.nber.org/papers/w23394 (PDF read: https://www.nber.org/system/files/working_papers/w23394/w23394.pdf). Two versions disagree on counts/thresholds; both recorded.
- Chen and Zimmermann quote HXZ as: 65.4% of anomalies fail |t| >= 1.96 with NYSE breakpoints and value weights; 43.1% if microcaps are allowed (NYSE-Amex-NASDAQ breakpoints, equal weights). [page, via footnote 2 of the Chen-Zimmermann PDF]
- Main mechanism named: microcaps (about 3% of market cap but about 60% of stocks per Fama-French 2008, as cited in the HXZ text). [page]

### 7c. Chordia, Goyal, Saretto (2020), "Anomalies and False Rejections"
- Review of Financial Studies 33(5), 2134-2179. [page: IDEAS/EconPapers listing as seen in search results; abstract page below]
- Abstract (SFI copy): more than two million randomly generated trading strategies built from real data, plus the published ones, are used to estimate how many strategies researchers could have tried; implied multiple-testing t-cutoffs of about 3.84 (time-series regressions) and about 3.38 (cross-sectional regressions); if researchers ignored multiple testing, about 45.3% of findings would be false rejections. [page] https://www.sfi.ch/en/publications/anomalies-and-false-rejections
- Published-abstract rounding: 3.8 and 3.4, 45% [snippet from search summary].
- The method (details of how FDR/FWER corrections are applied to the 2M strategies): [unconfirmed] (full text paywalled/blocked; earlier SSRN title "p-Hacking: Evidence from Two Million Trading Strategies", SFI Research Paper 17-37, as cited by Arnott-Harvey-Markowitz [page]).

### 7d. Jensen, Kelly, Pedersen (2023), counter-view
- "Is There a Replication Crisis in Finance?", Journal of Finance 78(5), 2465-2518 [page: IDEAS record]. Working paper read: https://www.nber.org/papers/w28432 (PDF https://www.nber.org/system/files/working_papers/w28432/w28432.pdf) [page].
- Bayesian hierarchical model of factor alphas (estimates all alphas jointly; they say this controls the false discovery rate without a separate frequentist adjustment: at most 2.5% of discoveries are false under the posterior by their definition; Bayesian FDR is much lower if many factors are highly significant). Data: 153 factors, 93 countries (GlobalFactor code at github.com/bkelly-lab/GlobalFactor). [page]
- Findings: majority of factors replicate; cluster into 13 themes; work out of sample in the new international data; over 80% of US factors stay significant after consistent construction and multiple-testing adjustment; in US data 84.3% of factors have positive returns in the pre-original sample, 82.6% in the post-original sample, 88.5% in the combined out-of-sample, with out-of-sample alpha regressed on in-sample alpha slope 0.43 / 0.25 / 0.30. [page]
- Their argument against the HLZ framing: they test HLZ's scenarios (1,297 or 2,458 tried factors) with simulation and say the conclusion does not change; the authors say they find a high replication rate across the size distribution (mega to nano stocks), against HXZ's microcap argument. [page]
- Names the other critiques: Harvey et al. 2016, Hou et al. 2020, Linnainmaa and Roberts 2018, and Chen-Zimmermann (reproduces nearly 100%). [page]

### 7e. Chen and Zimmermann, "Open Source Cross-Sectional Asset Pricing"
- Critical Finance Review 11(2), 207-264 (May 2022). Working paper (FEDS 2021-037) read: https://www.federalreserve.gov/econres/feds/files/2021-037pap.pdf [page]; journal details from search results [snippet].
- Abstract [page]: data and code that reproduce nearly all cross-sectional return predictors; 319 characteristics; for 161 clearly significant in the original papers, 98% of long-short portfolios have t above 1.96; for 44 mixed-evidence characteristics the average reproduced t is about 2; regression of reproduced on original t slope 0.90, R^2 83%; the other 114 were insignificant originally.
- Code: https://github.com/OpenSourceAP/CrossSection (needs WRDS and Stata per the paper; "anyone with access to WRDS and Stata" can rerun). Signal documentation spreadsheet in that repo. [page]
- Data availability: openassetpricing.com offers test-asset returns and signals; download routes are a Hugging Face dataset (CrossSection), a Python package `openassetpricing` (by Peng Li) and an R package `OpenSourceAP.DownloadR`; the page shows an update dated 2026-10-28 (migration to CRSP v2). It does not state the signal count or license. [page] https://www.openassetpricing.com/ ; PyPI `openassetpricing` 0.1.0, 2026-10-26, GPLv2 [page: PyPI JSON]
  - A Fed page lists the public zip as monthly long-short returns for 205 predictors; I could not confirm the current number. [snippet]
- Coverage: US stocks (CRSP/Compustat-based, WRDS data). Whether any Hong Kong data exists: not mentioned in any page I read. [unconfirmed]
- The JKP global factor data (153 factors, 93 countries) is described as available at bryankellyacademic.org and the GlobalFactor repo; whether HK stocks are included, file size, license: [unconfirmed].

---------------------------------------------------------------------
## 8. Research protocols

### 8a. Arnott, Harvey, Markowitz (2019) "A Backtesting Protocol in the Era of Machine Learning"
- Journal of Financial Data Science 1(1), 64-74 (Winter 2019); DOI 10.3905/jfds.2019.1.064; SSRN 3275654 posted 13 Nov 2018. Read the SSRN working paper through a third-party mirror (version dated October 29, 2018): https://www.smallake.kr/wp-content/uploads/2023/04/SSRN-id3275654.pdf [page]. Published version not checked against it.
- Seven-point protocol (Exhibit 2), with their sub-questions [page]:
  1. Research motivation: (a) solid economic foundation? (b) did the hypothesis exist before the research?
  2. Multiple testing and statistical methods: (a) kept track of all models and variables tried, successful and not, and aware of multiple testing? (b) full accounting of all possible interaction variables? (c) investigated all variables in the research agenda or cut short when a good model was found?
  3. Data and sample choice: (a) do the data and any exclusions make sense; (b) data integrity steps; (c) data transformations (scaling) chosen in advance and robust to minor changes; (d) outlier exclusion rules reasonable; (e) winsorisation rule chosen before the research and only one level tried.
  4. Cross-validation: (a) aware that true out-of-sample is only live trading; (b) steps against "iterated" out-of-sample (modifying a model after seeing OOS results); (c) OOS analysis representative of live trading (trading costs and data revisions included).
  5. Model dynamics: (a) resilient to structural change; (b) overcrowding risk considered; (c) no tweaking of a live model.
  6. Complexity: (a) avoid the curse of dimensionality; (b) simplest practicable specification; (c) interpret the ML model, not a black box.
  7. Research culture: (a) reward quality of science, not winning strategy; (b) understand that most tests will fail; (c) clear expectations when research is delegated.
- Specific statements in the text [page]:
  - Given 20 random strategies, one will likely exceed t = 2 by chance; keep track of the number tried and their correlations (a bigger threshold penalty applies to strategies that are less correlated; 20 strategies with correlation near 1.0 equal one trial).
  - Interaction terms: 20 variables give "20 choose 2" = 190 possible interactions, so adding one or two does not mean 22 tests.
  - The "parallel universe" problem: a researcher who tests one idea after seeing the data is not necessarily making a single test.
  - The training/test sample must be defined before the research starts and must not change; excluding the crisis periods is called out as not allowed.
  - "No true out-of-sample exists": the holdout period has been lived through; deep-history backfilled data and other countries are better but not clean (cross-country correlation).
  - Cites Chordia-Goyal-Saretto's 2.1 million equity models as an example of the dimensionality problem and says Hou, Xue, Zhang show most anomaly excess returns disappear once microcaps are excluded.
  - The authors say the goal is not to eliminate all false positives (reject everything) but to balance false and missed discoveries (refers to Harvey and Liu 2018, "False (and Missed) Discoveries in Financial Economics").
- Quantitative thresholds in this paper: none (no t cutoff or trial-count formula; it points to Harvey 2017 and Lopez de Prado 2018 for those).

### 8b. Lopez de Prado on counting all trials
- In the 10 Reasons paper: "imperative to control for the number of trials" when using walk-forward backtests, because without it FWER, FDR, PBO and similar cannot be determined. [page] (link in section 5b)
- A summary of the same paper says: count the walk-forward trials and use the deflated Sharpe ratio; it also says (secondary source) that 20 walk-forward backtests on the same data are likely to produce one false strategy at 95% naive confidence. [snippet] https://www.cxoadvisory.com/big-ideas/10-steps-to-becoming-a-better-quant
- Fabozzi and Lopez de Prado (2018), "Being Honest in Backtest Reporting: A Template for Disclosing Multiple Tests", Journal of Portfolio Management 45(1): named as a reference in the Arnott-Harvey-Markowitz list only; contents not read. [page for the citation; contents unconfirmed]
- The DSR paper says a backtest that does not report N cannot be assessed (MinBTL paper) and the investor in its example asks for N, V[{SR}], T, skew and kurtosis. [page]

### 8c. Locked final hold-out ("lockbox")
- I found no finance paper that uses the word "lockbox" (the term appears in none of the papers I downloaded: grep over their text gave no hit). [page, negative]
- Related formal source: Dwork, Feldman, Hardt, Pitassi, Reingold, Roth, "Preserving Statistical Validity in Adaptive Data Analysis" (STOC 2015; arXiv 1411.2664; also the Science 2015 "reusable holdout" paper). The arXiv text says reusing a holdout adaptively invalidates standard error guarantees; Kaggle-style repeated scoring on one fixed test set leads to overfitting; they give a method (adding noise, from differential privacy) that allows many adaptive uses of a holdout. [page: arXiv abstract and introduction] https://arxiv.org/pdf/1411.2664 . A wiki-style summary credits the "reusable holdout" to this line of work. [snippet]
- Statements about holdouts from finance papers read: the DSR paper says holdout treats the test as a single trial and so cannot prevent backtest overfitting when applied repeatedly (20 times at 95% makes a false positive expected) [page]; Arnott-Harvey-Markowitz say "iterated out-of-sample is not out-of-sample" (modify the model after OOS failure and it is overfit) and that true OOS exists only in live trading [page].
- Practitioner blog pages describing "true holdout / final test / lockbox computed once" were returned by search but not opened. [snippet]

---------------------------------------------------------------------
## 9. False discovery rate in practice

### 9a. Benjamini-Hochberg (BH) and Benjamini-Yekutieli (BY) steps
- Source page: Wikipedia "False discovery rate" [page] https://en.wikipedia.org/wiki/False_discovery_rate (secondary source; the original papers were not opened). References it lists: Benjamini and Hochberg 1995, J. Royal Statistical Society B 57(1), 289-300; Benjamini and Yekutieli 2001, Annals of Statistics 29(4), 1165-1188; Storey 2002, JRSS-B 64(3), 479-498; Storey and Tibshirani 2003, PNAS 100(16), 9440-9445; Storey 2003, Annals of Statistics 31(6), 2013-2035.
- BH (step-up): sort m p-values ascending P(1) <= ... <= P(m). Find the largest k with P(k) <= (k/m) * alpha. Reject H(1)..H(k). [page]
  - Valid when tests are independent; also holds under various forms of positive dependence but "not universally valid". Under independence FDR <= (m0/m)*alpha (equality when continuous). Putting an estimate of m0 into BH removes the guarantee. [page]
- BY: same, but threshold P(k) <= (k/m) * alpha / c(m), with c(m) = 1 for independent or positively dependent tests and c(m) = sum_{i=1..m} 1/i (about ln(m) + gamma_E + 1/(2m)) for arbitrary dependence. General-case bound: FDR <= (m0/m) * alpha * c(m). [page]
- Worked effect of c(m) [calc]: m = 100 gives c = 5.19, m = 1,000 gives 7.49, m = 10,000 gives 9.79 (so BY thresholds are alpha/5.19 etc. of BH's).
- HLZ use the BY c(M) form under the name BHY (section 3a). [page]
- Holm and Bonferroni (FWER): see 3a.

### 9b. Barras, Scaillet, Wermers (2010), "False Discoveries in Mutual Fund Performance: Measuring Luck in Estimated Alphas"
- Journal of Finance 65(1), 179-216. Published PDF read: https://terpconnect.umd.edu/~wermers/FDR_published.pdf [page]
- Data: 2,076 US actively managed open-end domestic equity funds, 1975-2006 (monthly returns).
- Method [page]: for each fund compute a two-sided p-value for its alpha t-statistic (inputs are only these p-values). Zero-alpha funds' p-values are uniform on [0,1]. Choose lambda (e.g. 0.6) and estimate the share of zero-alpha funds pi0_hat(lambda) = W_hat(lambda) / (M * (1 - lambda)), where W_hat(lambda) = number of funds with p-value above lambda (Storey 2002). lambda chosen by Storey's bootstrap minimising the estimated mean squared error of pi0_hat; they say results are not very sensitive to lambda (0.5 or 0.6 give similar numbers).
  - At significance level gamma: expected share of "lucky" funds in each tail F_hat+ = F_hat- = pi0_hat * gamma / 2 (their Eq. 6). Observed significant share S_hat+ (right tail) and S_hat- (left tail) are measured directly. Estimated skilled proportion at level gamma = S_hat+ - F_hat+; unskilled = S_hat- - F_hat-.
  - They define FDR+ as an extension of the standard FDR for choosing a significance level for building a portfolio of funds (in-sample selection of the level using the previous 5 years of p-values; gamma range 0.01..0.60).
- Results [page]: 75.4% of the funds are zero-alpha (net of expenses); skilled funds were a significant share before 1996 but almost none by 2006; the unskilled share grew. In the paper's example, a portfolio of the funds significant at 5% (t > 1.96) from one hypothetical population gives expected alpha 1.8% a year vs 45 basis points in the other population.
- Transfer note (as stated by the authors): the method needs only p-values of the cross-section, so it applies to any large set of tests whose null p-values are uniform. (The paper itself says it is for funds.) [page for the "only p-values" statement]

### 9c. Storey's q-value
- pi0 estimator: as above, pi0_hat(lambda) = #{p > lambda} / (m (1 - lambda)). The Wikipedia page gives only the rough idea "count p-values above 0.5 and double"; no tuning rule or full algorithm there. [page for both]
- q-value definition and algorithm (q(p_(i)) = min over j >= i of pi0_hat * m * p_(j) / j, i.e. a pi0-scaled BH adjusted p-value): [unconfirmed] (I did not open Storey 2002/2003 or a package page; the formula is stated from memory and should be checked).
- Python implementation of Storey q-values: [unconfirmed]; I did not search for one beyond statsmodels. 

### 9d. statsmodels
- Function: `statsmodels.stats.multitest.multipletests(pvals, alpha=0.05, method='hs', maxiter=1, is_sorted=False, returnsorted=False)`. Returns reject (bool array), pvals_corrected, alphacSidak, alphacBonf. [page] https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html
- Method names: 'bonferroni', 'sidak', 'holm-sidak' (default 'hs'), 'holm', 'simes-hochberg', 'hommel', 'fdr_bh' (Benjamini-Hochberg), 'fdr_by' (Benjamini-Yekutieli), 'fdr_tsbh' and 'fdr_tsbky' (two-stage FDR), 'fdr_gbs', 'lfdr'. Docs label fdr_bh "non-negative" and fdr_by "negative" (meaning: the dependence assumption; the page does not spell it out). Corrections do not depend on alpha except the two-stage ones. [page]
- Release: statsmodels 0.15.0, uploaded 2026-08-27, BSD-3-Clause. [page: PyPI JSON]
- Related: statsmodels also has `statsmodels.stats.multitest.fdrcorrection` (name from memory; not opened). [unconfirmed]

---------------------------------------------------------------------
## Package summary table (data read from PyPI JSON on 2026-11-10 unless noted)
| Package | Version | Upload date | License | What the page says it covers |
|---|---|---|---|---|
| arch | 8.0.0 | 2025-10-21 | NCSA | SPA (alias RealityCheck), StepM, MCS in `arch.bootstrap` |
| skfolio | 1.12.8 | 2026-11-08 | BSD-3 | CombinatorialPurgedCV, WalkForward |
| statsmodels | 0.15.0 | 2026-08-27 | BSD-3 | multipletests (Bonferroni, Holm, BH, BY, two-stage) |
| fynance | 2.13.1 | 2026-07-06 | MIT | `research.overfit.pbo` (CSCV); DSR/PSR names listed |
| deflated-sharpe | 0.1.0 | 2026-03-21 | Apache-2.0 | DSR, min backtest length, BH; one release, tiny repo |
| factor-qc | 0.1.3 | 2026-09-04 | MIT | DSR, PBO (CSCV), Harvey-Liu haircut, MinTRL; self-described alpha |
| sharpebench | 0.28.0 | 2026-09-18 | MIT OR Apache-2.0 | deflated Sharpe, CSCV PBO (Rust kernel) [snippet for function names] |
| mlfinpy | 0.1.2 | 2024-10-09 | MIT | Lopez de Prado-style toolkit; feature list unconfirmed |
| timeseriescv | 0.2 | 2018-09-07 | MIT | sklearn-style time-series CV classes |
| openassetpricing | 0.1.0 | 2026-10-26 | GPLv2 | downloader for Chen-Zimmermann signals |
| mlfinlab | not on PyPI | n/a | n/a | paid (earlier notes) |

---------------------------------------------------------------------
## Could not confirm
1. White (2000) body text (PDF downloads empty); exact bootstrap algorithm and statistic of the Reality Check beyond the abstract and one secondary quotation.
2. Romano-Wolf (2005) stepdown algorithm steps (paper not opened); only `arch` docs and abstract-level summaries.
3. Hansen (2005): I read the intro, the T_SPA statistic and recentring rule, but not the bootstrap implementation section line by line; the sign convention of the loss differential is my reading.
4. MCS: MCS p-value running-maximum wording is from a secondary summary; the R-package warning about t_min is from a summary; no numeric worked example read.
5. DSR paper: equations 7-9 (average-correlation estimate of N) and the numeric-example parameter values were lost in extraction. I rebuilt the example by calculation and it matches the paper's three quoted outcomes (0.9505 at N = 46; about 0.90 at the investor's N; 95% line at N = 88 for Normal returns), but the paper's own parameter list is unconfirmed. The closed form N_hat = rho_bar + (1 - rho_bar) M is from memory.
6. Lopez de Prado (2019) "A Data Science Solution to the Multiple-Testing Crisis" (JFDS): not opened. The Quantitative Finance version (LdP-Lewis) was read only as the SSRN working paper (Nov 2018) through a mirror. The exact accuracy numbers of the ONC experiment were not extracted.
7. AFML (book) chapters 7 and 12 not opened; purging/embargo and CPCV rules come from his 10 Reasons paper. The embargo rule "h about 0.01 T" is from that paper; how AFML code (PurgedKFold) sets it was not checked. Whether skfolio accepts per-label end times: not stated in the pages read.
8. Which Python packages provide purged k-fold/CPCV besides skfolio: `mlfinpy`, `timeseriescv` contents unconfirmed; `mlfinlab` paid and not on PyPI. No maintained Python Harvey-Liu `Haircut_SR` port found except the small `factor-qc` (alpha); Duke Matlab link not tested.
9. Storey q-value formula and any Python q-value implementation; statsmodels `fdrcorrection` name; statsmodels docs do not spell out the BH vs BY dependence labels.
10. Original BH (1995) and BY (2001) papers not opened (Wikipedia used as source for the steps).
11. Chordia-Goyal-Saretto full method (how many tests, which correction, the false-discovery proportions by strategy type) beyond the abstract numbers (3.84/3.38, 45.3%). HXZ published (2020) text not read, only the abstract; two versions differ (447 vs 452 anomalies; 2.78 vs t = 3 hurdles).
12. JKP (2023) published JF text not read; working-paper version read. JKP data coverage of Hong Kong stocks not confirmed; Chen-Zimmermann data is US (CRSP/Compustat via WRDS) per the paper text, current signal count and license on openassetpricing.com not stated on the page I opened.
13. "Lockbox": no finance primary source found using the term; only the Dwork et al. reusable holdout and practitioner blog snippets.
14. McLean-Pontiff: a secondary summary cited a 35% post-publication decay; I could not trace it (the paper says 58% post-publication, 26% out-of-sample, ~32% publication effect).
15. Harvey-Liu 2015 JPM volume/page numbers and Harvey, Liu, Zhu RFS volume/pages were not shown on the pages read (the RFS 2016 29(1) citation is from my background knowledge, not a page).
16. Whether any paper gives a recommended number of trials for about 200 stocks and 8-20 years of daily data: none found (only the MinBTL examples: 5 years, N = 45; 2 years, N = 7 for target IS SR 1).
