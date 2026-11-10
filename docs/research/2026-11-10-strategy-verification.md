# Verifying trading strategies: the quantitative methods (2026-11-10)

Brian asked for this on 2026-11-10: "there are quantitative way to verify the strategies. Please
conduct your researches properly". It covers the tests that decide whether a signal is real, the
tests that correct for trying many signals, the published evidence for each strategy family, and
what follows for milestone 3.

How to read the tags:
- **[page]** a helper or Claude opened the paper, its abstract page or the documentation and read
  the fact there.
- **[summary]** seen only in a search result or a second-hand write-up.
- **[calc]** computed in this session from the formula given (scipy 1.18.1 in the project env).
- **[my view]** Claude's inference or proposal. Nothing here is decided until Brian says so.

Raw notes with every link: `2026-11-10-notes/research5-single-strategy-tests.md`,
`research5-multiple-testing.md`, `research5-backtest-design-tools.md`,
`research5-strategy-evidence.md`. Each ends with a "Could not confirm" list.

## 1. The problem in numbers

A backtest answers "did this make money in the past?". Verification answers "how likely is that
result if the signal is worthless?". Three calculations show why the second question is hard on
this project's data (about 200 stocks, 8 to 20 years).

**1a. One strategy: the Sharpe ratio has a wide error bar.** The Sharpe ratio is the average
return divided by its swing, per year. Its standard error for independent returns is
`sqrt((1 + SR²/2) / years)` (Lo 2002, eq. 9) [page]. So [calc]:

| True yearly Sharpe | t-stat after 8 years | after 10 years | after 20 years | Years needed for t = 3 |
|---|---|---|---|---|
| 0.5 | 1.33 | 1.49 | 2.11 | 40 |
| 1.0 | 2.31 | 2.58 | 3.65 | 14 |
| 1.5 | 2.91 | 3.25 | 4.60 | 8 |

A strategy that truly earns a Sharpe of 0.5 cannot be told from luck in 10 years. Serial correlation makes it worse: with +20% monthly autocorrelation
the yearly Sharpe is overstated by the factor 3.46 / 2.88 (Lo 2002) [page].

**1b. Many strategies: the best of N useless ones looks good.** After N independent tries of
strategies with no skill, the best yearly Sharpe is expected to be
`((1 − γ)·Z⁻¹(1 − 1/N) + γ·Z⁻¹(1 − 1/(N·e))) / sqrt(years)`, γ = 0.5772 (Bailey, Borwein, Lopez de
Prado, Zhu 2014, eq. 3.1) [page]. So [calc]:

| Years of data | Best Sharpe from luck, 10 tries | 50 tries | 100 tries | 500 tries |
|---|---|---|---|---|
| 2 | 1.11 | 1.61 | 1.79 | 2.16 |
| 8 | 0.56 | 0.80 | 0.89 | 1.08 |
| 10 | 0.50 | 0.72 | 0.80 | 0.97 |
| 20 | 0.35 | 0.51 | 0.57 | 0.68 |

Fifty tries on ten years of data produce a Sharpe of 0.72 from nothing. The authors' own example:
with 5 years of data, at most 45 independent tries before luck alone gives a Sharpe of 1 [page].
A real case: Sullivan, Timmermann and White (1999) tested 7,846 technical trading rules. On
S&P 500 futures 1984 to 1996 the best rule earned about 10% a year with an ordinary p-value of
0.04. Corrected for the search over all rules, the p-value was 0.90 [page].

**1c. The hit rate needs many cases.** Milestone 4's alert bar is "right at least 60% of the
time in 30 or more past cases". Against a coin flip [calc, exact binomial test]:

| Right / cases | Chance a coin does this well | 95% range for the true rate |
|---|---|---|
| 18 / 30 (60%) | 18% | 41% to 77% |
| 20 / 30 (67%) | 4.9% | 47% to 83% |
| 30 / 50 (60%) | 10% | 45% to 74% |
| 60 / 100 (60%) | 2.8% | 50% to 70% |
| 120 / 200 (60%) | 0.3% | 53% to 67% |

Eighteen right out of 30 is not evidence: a coin does it 18% of the time. A 60% rate needs about
80 independent cases for the usual 5% mark and about 205 for the stricter t > 3 mark [calc].

## 2. Tests for one signal

Each test answers a different question. A signal should pass all that apply.

**2a. Does the signal rank stocks correctly? (information coefficient)**
- Each day, correlate the signal across stocks with the return that followed. The rank version
  (Spearman) is the "rank IC". The mean over days divided by its standard deviation is the ICIR
  [page: Qlib and Alphalens source code].
- Test: the mean IC against zero. Alphalens uses a plain t-test, which treats days as
  independent [page]. skfolio's `AlphaForecastEvaluation` uses a standard error that allows for
  serial correlation, plus a bootstrap p-value, and wants at least 20 ICs [page].
- No authoritative pass mark exists. Alphalens, Qlib and Numerai publish none [page]. Blog
  figures (mean IC above 0.03 to 0.05, ICIR above 0.5) have no primary source [summary]. The
  Grinold-Kahn numbers often quoted could not be confirmed.
- Why it suits this project: it uses all 200 stocks every day, so it gains power from breadth
  that a single strategy's Sharpe ratio lacks. Grinold's rule: skill per bet times the square root
  of the number of independent bets [summary].

**2b. Does the top group beat the bottom group? (portfolio sorts, Fama-MacBeth)**
- Sort stocks by the signal each period; test the mean return gap between the top and bottom
  groups [page: Qlib `calc_long_short_return`, Alphalens quantile returns].
- Fama-MacBeth: run one cross-sectional regression per period, then average the slopes; the
  standard error is the slopes' standard deviation over sqrt(periods) [page: linearmodels docs].
  It handles stocks moving together on a day. It does not handle one stock's errors persisting
  through time; then clustered standard errors are right (Petersen 2009) [page].

**2c. Overlapping returns inflate the t-stat.**
- Five-day returns measured every day share four days with their neighbours. Ordinary standard
  errors are then wrong [page: Wei and Wright 2009].
- Newey-West standard errors with lag at least horizon − 1 are the usual fix (statsmodels
  `cov_type='HAC'`) [page; checked that it runs in the project env].
- The fix is imperfect: in simulations with a 12-period overlap, 95% intervals covered the truth
  only 80 to 85% of the time (Wei and Wright 2009) [page].
- Cleaner: use non-overlapping periods, or count independent cases as days / horizon [my view].

**2d. Is the Sharpe ratio above a benchmark? (probabilistic Sharpe ratio)**
- `PSR(SR*) = Z((SR − SR*)·sqrt(T − 1) / sqrt(1 − skew·SR + (kurt − 1)/4·SR²))`, per-period
  Sharpe, T observations (Bailey and Lopez de Prado 2012) [page: formula read in two later papers;
  the 2012 paper itself did not open]. It is the chance that the true Sharpe exceeds SR*. It
  corrects for fat tails and lopsided returns. The usual pass mark is 0.95 [page].
- Minimum track record length turns the formula round: how many observations before the claim
  holds [page; two sources differ by a "+1"].

**2e. Is it more than market exposure? (alpha against factors)**
- Regress the strategy's return on the market's return (and size, value, momentum); the
  intercept is the alpha; test it with Newey-West errors [page: linearmodels `TradedFactorModel`].
- Free factor data: Ken French's library. Its "Asia Pacific ex Japan" set covers Australia, Hong
  Kong, New Zealand and Singapore, daily from July 1990, in US dollars. There is no Hong
  Kong-only file there [page].

**2f. News signals: the event study.**
- Abnormal return = actual return minus the return a market model predicts, fitted on a window
  before the event. Sum over the event window (CAR), average across events, test against zero
  [page: lecture notes after Campbell, Lo, MacKinlay; MacKinlay 1997 itself was a scan].
- Events raise the swing: the Boehmer-Musumeci-Poulsen test standardises each event first
  [page: eventstudytools.com; abstract of the 1991 paper].
- Events on the same day are not independent (one piece of market news hits 50 stocks). The
  Kolari-Pynnönen correction multiplies the t-stat by `sqrt((1 − r) / (1 + (N − 1)·r))`, r = the
  average correlation between stocks' abnormal returns [page: same vendor page]. The other remedy
  is one portfolio return per calendar day [page: lecture notes].
- No maintained Python package implements these tests; they are about 50 lines on statsmodels
  [page for the absence found; my view for the size].

**2g. Direction and probability.**
- Hit rate against a coin: exact binomial test (`scipy.stats.binomtest`) [page; checked].
- Pesaran-Timmermann (1992) corrects for the base rate: in a rising market "always up" is right
  more than half the time with no skill. In statsmodels as `pesaran_timmermann` [page; checked
  that it exists in the project env].
- "Right 60% of the time when it says 60%": the reliability curve and the Brier score
  (scikit-learn `calibration_curve`) [page].

**2h. Resampling: tests that assume little.**
- Stationary bootstrap (Politis and Romano 1994): resample blocks of random length so that serial
  correlation survives; gives a range for any statistic, including the deepest fall [page: `arch`
  docs; summary for the paper].
- Permutation test (Aronson 2006; Masters 2018): shuffle the link between positions and returns;
  the share of shuffles that beat the real result is the p-value [page: a vendor newsletter;
  the books were not read]. scipy has `permutation_test` [checked].

**2i. Is it worth money? (costs, turnover, decay)**
- Novy-Marx and Velikov (2016): strategies with one-sided monthly turnover under 50% mostly
  survive costs; few above that do. Costs take more than 1% of the monthly one-sided turnover
  from the return. Holding on to stocks that one would no longer newly buy is the best single
  cost saver. Many strategies keep t > 2 after costs; far fewer keep t > 3 [page].
- McLean and Pontiff (2016), 97 published signals: returns are 26% lower in the years after the
  study's sample and 58% lower after publication [page].
- Signal half-life: measure the IC at each holding period; the horizon where it halves sets how
  fast one must trade [page: skfolio `decay_summary`; summary for the half-life formula].

## 3. Tests across many signals

**3a. Raise the bar with the number of tests.** For M tests with p-values sorted ascending
(Harvey, Liu, Zhu 2016) [page]:
- Bonferroni: pass if p ≤ 5% / M. Controls the chance of even one false find.
- Holm: the k-th smallest p must be ≤ 5% / (M + 1 − k). Never weaker than Bonferroni.
- Benjamini-Hochberg-Yekutieli: the largest k with p(k) ≤ (k/M)·level / c(M), c(M) = 1 + 1/2 + … +
  1/M. Controls the share of false finds among the finds, under any dependence.
- All four are in statsmodels `multipletests` (`bonferroni`, `holm`, `fdr_bh`, `fdr_by`)
  [page; checked in the project env].
- Bonferroni t-hurdles [calc]: 1 test 1.96; 10 tests 2.81; 20 tests 3.02; 50 tests 3.29; 100
  tests 3.48; 19,900 tests (every pair among 200 stocks) 4.71.
- Harvey, Liu and Zhu counted 316 published factors and conclude a new one needs t above 3.0;
  with unpublished tries, 3.18 at the least [page]. Chordia, Goyal and Saretto (2020), two
  million generated strategies: hurdles of about 3.8 and 3.4, and about 45% false finds if
  multiple testing is ignored [page: abstract].
- Harvey and Liu (2015) turn this into a "haircut": 20 years monthly, Sharpe 0.75, 200 tries →
  adjusted Sharpe 0.32. Haircuts exceed 50% for Sharpe under 0.4 and stay under 25% for Sharpe
  above 1.0 [page].

**3b. Test the best of the set against a benchmark (data-snooping tests).**
- White's Reality Check (2000): is the best of all tried strategies better than the benchmark,
  given that it was picked as the best? Bootstrap of the maximum [page: abstract; summary for
  the statistic].
- Hansen's SPA test (2005): the same question with a studentised statistic; less distorted by
  poor strategies in the set. In one of his simulations power rises from 15% to 53% [page].
- Romano-Wolf StepM (2005): says which strategies beat the benchmark, not only whether one does
  [summary]. Model Confidence Set (Hansen, Lunde, Nason 2011): the set that contains the best
  model at a chosen confidence [page].
- All in the `arch` package (`arch.bootstrap.SPA`, `StepM`, `MCS`); inputs are losses per period
  per strategy [page]. `arch` is not installed in the project env [checked].

**3c. Deflate the Sharpe ratio by the number of tries.**
- Deflated Sharpe Ratio (Bailey and Lopez de Prado 2014) = the probabilistic Sharpe ratio of 2d
  with the benchmark set to the best Sharpe luck would give:
  `SR0 = sqrt(V)·((1 − γ)·Z⁻¹(1 − 1/N) + γ·Z⁻¹(1 − 1/(N·e)))`, V = variance of the Sharpe ratios
  across the tries, N = number of independent tries [page: Claude read the paper's text and code].
- The paper's example: Sharpe 2.5 over 5 years of daily data looks excellent. With the tries
  counted it scores about 0.90 and fails the 0.95 mark; it would pass with 46 tries or fewer
  [page]. Claude reproduced 0.9004, 0.9505 and the N = 88 case [calc].
- N must be independent tries. Fifty variants of one idea are not fifty tries. Lopez de Prado and
  Lewis (2019) cluster the tries by the correlation of their returns and use the number of
  clusters [page]. A simpler formula from the 2014 paper uses the average correlation [page for
  the idea; the closed form was not readable].
- The paper's warning that matters most here: a backtest that does not report the number of
  tries cannot be judged [page].

**3d. Probability of backtest overfitting (PBO).**
- Bailey, Borwein, Lopez de Prado, Zhu (2017). Put the returns of all N variants in a table.
  Cut time into S blocks (16 gives 12,870 ways to pick half). For each way: find the best variant
  on the chosen half; look up its rank on the other half. PBO = the share of ways where the
  in-sample winner lands in the bottom half out of sample [page].
- It needs no assumption about the return distribution. The paper calls rejecting above 0.05
  "customary" [page]. Its examples: 74% on random data, 0.04% on a real instrument [page].

**3e. Splitting time without leaks.**
- A label that looks 5 days ahead overlaps the labels next to it. Purging removes training rows
  whose label window overlaps the test window. An embargo also drops training rows just after the
  test window; about 1% of the sample "often suffices" (Lopez de Prado 2018) [page].
- Walk-forward (train on the past, test on the next stretch, roll on) tests one path only, and
  its early decisions use little data [page: same paper].
- Combinatorial purged cross-validation: cut time into N groups, test on every choice of k
  groups. N = 6, k = 2 gives 15 splits and 5 complete test paths, so a distribution of results
  instead of one number [page; calc]. In skfolio as `CombinatorialPurgedCV`; scikit-learn's
  `TimeSeriesSplit` has a `gap` for simple purging [page; checked]. skfolio is not installed
  [checked].
- One study on simulated markets found the combinatorial method had a lower overfitting
  probability than walk-forward (Arian, Norouzi, Seco 2024) [summary: the paper did not open].

**3f. The hold-out has one use.**
- A period set aside and never looked at is honest once. "If we apply the holdout" many times,
  false finds become expected (Bailey and Lopez de Prado 2014) [page: Claude read it].
- Arnott, Harvey, Markowitz (2019): changing a model after seeing its out-of-sample result makes
  that result in-sample. True out-of-sample exists only in live trading [page].

**3g. A protocol (Arnott, Harvey, Markowitz 2019), seven checks** [page]:
1. A reason for the signal existed before the test.
2. Every model and variable tried is recorded, failures included.
3. Data, exclusions and outlier rules were fixed in advance.
4. No out-of-sample result fed back into the model; costs are in the test.
5. The model survives a change of regime and crowding.
6. The simplest model that works; no black box.
7. The research rewards sound method, not a winning backtest.

## 4. What the published evidence says, family by family

"How verified" names the test design of section 2 or 3 the paper used.

| Family | Original result | How verified | After costs, after publication | Long-only and Hong Kong |
|---|---|---|---|---|
| Pairs (Coca-Cola and Pepsi type) | Top pairs up to 12% a year, US 1962 to 1997 (Gatev, Goetzmann, Rouwenhorst) [page] | Bootstrap against random pairs [page] | Plain rule unprofitable after costs; the best refinements net 0.29% a month, mostly from 2000 to 2002 (Do and Faff 2012) [page: second-hand summary]. Three methods net 0.05% to 0.36% a month, 1962 to 2014 (Rad, Low, Faff 2016) [summary] | Every study is long and short together; no long-only test found. 50 Hang Seng stocks 2013 to 2020: profitable before costs (Ma and Slepaczuk 2022) [page]. Mainland-Hong Kong cross-market pairs 9% a year, fading after 2012 (Zhang and Urquhart 2019) [page] |
| The largest stock | Holding the single largest S&P 500 stock, renewed yearly: 7.71% a year against 11.30% for the whole index, 1971 to 2025 (Bessembinder 2026) [summary: two write-ups agree] | Yearly buckets by size | The 10 largest: 10.72%. Stocks beat the market by 25 points a year before they enter the top 10 and lag it after (Dimensional) [summary] | Long-only by nature. No Hong Kong study found |
| Linked companies lead each other | Customer returns predict supplier returns: 1.55% a month, 1981 to 2004 (Cohen and Frazzini 2008) [summary]. Shared analyst coverage: 1.68% a month, t = 9.67 (Ali and Hirshleifer 2020) [page] | Portfolio alphas; Fama-MacBeth | Customer signal "smaller and not significant" after the original sample (Pinchuk 2023) [page]. No cost-adjusted figures found | Long-short only. After extreme US moves Asian index futures reverse within the day, after costs (Fung, Lam, Lam 2010) [page] |
| Drift after results | Top minus bottom surprise about 4.2% over 60 days, 1974 to 1985 (Bernard and Thomas 1989) [summary] | Event study by surprise group | "no PEAD for large stocks since 2006" (Martineau 2022) [page] | Hong Kong 1988 to 1996: drift found (thesis) [summary] |
| Momentum, reversal | 3 to 12 month winners keep winning (Jegadeesh and Titman 1993) [summary] | Group sorts | Crashes in rebounds: 2009, losers +163% against winners +8% (Daniel and Moskowitz 2016) [summary]. One-month reversal profits fall below likely costs (Avramov, Chordia, Goyal 2006) [summary] | Hong Kong momentum: mixed; not significant after risk adjustment (Cheng and Wu 2010) [summary] |
| Index additions | S&P 500 additions rose 3.4% in the 1980s and 7.6% in the 1990s (Greenwood and Sammon) [page] | Event study by decade | 0.8% in the last decade [page] | Hang Seng: deleted stocks do better over 5 years; added ones do not (Kot, Leung, Tang 2015) [page] |
| Insider buying, short selling | Purchases carry information, sales do not (Lakonishok and Lee 2001) [summary]. Heavily shorted stocks lag by 1.16% over 20 days (Boehmer, Jones, Zhang 2008) [page] | Calendar-time portfolios | No after-publication test found | Purchases are usable long-only; short interest only as a list to avoid [my view] |
| Overnight against daytime | Returns persist within each part and reverse across them (Lou, Polk, Skouras 2019) [page] | Split of 14 strategies | No cost figures found | No Hong Kong figure found |
| Low-risk stocks | Betting against beta: Sharpe 0.78, US 1926 to 2012 (Frazzini and Pedersen 2014) [summary] | Factor portfolios | Costs remove over 55% (Novy-Marx and Velikov 2022) [summary] | No long-only figure found |

Three patterns [my view]:
- **Decay is the rule.** Pairs, index additions, results drift and the customer signal all shrank
  or vanished after publication. McLean and Pontiff's 58% is the average.
- **Costs are measured for few families,** and where measured they remove most of the return.
- **Almost every result is long and short together.** A long-only investor gets the long half at
  best. Hou (2007) reports that slow reaction to bad news drives the industry lead-lag effect
  [summary], which is the short half.

On Brian's two examples:
- **Coca-Cola and Pepsi.** No peer-reviewed study of this pair was found. Course notes disagree
  on whether the two prices are tied together at all [summary]. The standard test is the
  Engle-Granger cointegration test (statsmodels `coint`), then the spread's speed of return.
- **The largest stock.** This row answers a rule Brian did not mean; Claude misread his example.
  His rule is "last year's best stock", covered in 4a below. The row stays as evidence on size.

### 4a. Last year's best stock, renewed each January

Brian's rule (clarified 2026-11-10): find the stock with the highest return last year, hold it
all this year, then switch to this year's best, and so on. The rule spread on social media in
2026. Five tests of the same rule, all on S&P 500 stocks unless noted:

| Source | How the data was handled | Period | The rule's result | The index |
|---|---|---|---|---|
| A post by @gurgavin, as quoted by the Ashoka Investments Club article [page: the quoting article] | Not stated; costs left out | 15 years from 2012 | 65.9% a year; beat the index in 11 of 15 years | 15.1% a year |
| Same post | Same | 30 years | 25.6% a year; beat the index in 19 of 30 years; worst fall 97% | 10.1% a year |
| Same post, selling at a 35% loss | Same | 30 years | 38.2% a year; 20 of 30 years; worst fall 59% | 10.1% a year |
| Trade Intelligent (Substack) [page] | Not stated | End 1997 to 2025 | $10,000 became $172,727, about 10.7% a year [calc]. It was down to $727 at the end of 2011 and took 25 years to recover | $10,000 became $70,660, about 7.2% a year [calc] |
| `thequietearth/backtester` on GitHub (MIT, one unnamed author) [page] | Members of the index as of each year, bankrupt and acquired stocks included, dividends included, 0.1% cost per trade | 1999 to 2025 | 9.5% a year; worst fall 98%; Sharpe 0.41 | SPY 8.4% a year, Sharpe 0.42. All members in equal amounts: 9.9% a year |
| Same repository, run on today's members only | Survivors only | 1999 to 2025 | 19% a year | |
| Malkiel and Michalka, Wealthfront letter, 2025 [page] | Last year's best 5 to 20 US stocks, 16 variants; costs left out | 1964 to 2023 | 9.64% a year on average; yearly swing 43%; beat the market in 46% of years | 10.37% a year; yearly swing 17% |

What the tests of sections 1 to 3 say about it:
- **The start date is a hidden choice.** From 2012 the rule earns 65.9% a year. From 1999 it earns
  9.5%. The 2012 start comes right after the rule's 98% fall.
- **Survivorship doubles the result.** Same rule, same years: 19% a year on today's members, 9.5%
  on the members of each year [page].
- **The Sharpe ratios cannot be told apart.** 0.41 over 27 years has a standard error of 0.20
  (section 1a), so the 95% range is 0.02 to 0.80. SPY's 0.42 sits inside it [calc].
- **The yearly win counts are weak evidence.** 11 of 15 years: a coin does that 5.9% of the time.
  19 of 30: 10%. 20 of 30 with the stop-loss: 4.9%, but the 35% level is itself a chosen setting
  [calc].
- **One bet a year gives 27 to 30 cases.** With a yearly swing of at least 43% (the Wealthfront
  figure for 5 to 20 stocks; one stock swings more), the rule would have to beat the index by 24
  points a year, on average, to reach a t-stat of 3 in 30 years [calc: 3 × 43 / sqrt(30)].
- **Whose numbers.** The best-controlled test is one person's repository, not a reviewed paper.
  Wealthfront sells index funds. The social-media posts give no data source.

[my view] The rule is the most concentrated form of the momentum signal in the table above:
winners over 3 to 12 months tend to keep winning on average, across a wide group, with crashes
after market falls. One stock a year keeps all of the noise and one case per year. The broad
form (rank every watchlist stock by its 12-month return, every day) gives hundreds of cases a
year and can pass or fail the gates of section 8. The one-stock form cannot be verified on any
history that exists.

## 5. How research platforms gate signals

- **WorldQuant BRAIN** (from copies of its documentation; the official pages refused the fetch):
  Sharpe above 1.25, "fitness" above 1.0 where fitness = Sharpe × sqrt(|return| / max(turnover,
  0.125)), turnover between 1% and 70%, no stock above 10% weight, a Sharpe floor on a
  sub-universe, and correlation under 0.7 with one's earlier signals [page: third-party copy].
- **Numerai** scores the rank correlation between prediction and target once per period ("era"),
  not per row, and tells users to treat each era as one data point [page]. It pays more for the
  part of a signal that the pooled model lacks [page].
- **Quantopian's contest** (archived): limits on position size (5%), market exposure (beta under
  0.3), sector exposure, turnover between 5% and 65%, and at least 504 days of backtest [page:
  archived notebook].
- Common ground [my view]: a minimum risk-adjusted return, a turnover band, a concentration limit,
  and a correlation limit against signals already accepted.

## 6. Tools

| Need | Tool | State |
|---|---|---|
| Newey-West errors, Pesaran-Timmermann, Bonferroni/Holm/BH/BY, cointegration | statsmodels 0.15.0 | installed [checked] |
| Binomial test, bootstrap, permutation test | scipy 1.18.1 | installed [checked] |
| Time split with a gap, calibration curve | scikit-learn 1.9.1 | installed [checked] |
| Stationary bootstrap, SPA, StepM, Model Confidence Set | `arch` 8.0.0 (NCSA licence) | not installed |
| Purged and combinatorial splits, IC with decay | `skfolio` 1.12.8 (BSD) | not installed |
| Fama-MacBeth, factor regressions | `linearmodels` 7.1 (NCSA) | not installed; statsmodels can do it by hand |
| Deflated Sharpe, PBO, event-study tests | small new packages exist (`factor-qc`, `fynance`, `sharpebench`, `purgedcv`), none proven | write ourselves from the formulas above: each is under 50 lines and testable against the papers' own numbers [my view] |
| IC tear sheets | `alphalens-reloaded` 0.5.1 | maintenance mode; its t-test ignores overlap [page] |

Backtest engines (vectorbt, backtesting.py, zipline-reloaded, LEAN): none models Hong Kong stamp
duty or board lots [page: none found in their docs]. The project's own fee tables (milestone 1)
already do. [my view] Keep the test inside the project, on the price store.

## 7. Data gaps that bias any test here

- **Survivorship.** The watchlist is today's index members. Stocks that fell out are missing, so
  every backtest on it flatters the past. Free point-in-time lists: S&P 500 from 1996
  (`fja05680/sp500` on GitHub, MIT) [page]; none found for the Hang Seng Index or the S&P 100.
  Free prices for delisted US stocks: none found [summary].
- **Hong Kong factors.** Only the four-country Asia Pacific set, in US dollars [page].
- **Results dates.** US: free from SEC EDGAR filings [page]. Hong Kong: on HKEX sites, whose
  terms forbid scripted access.
- [my view] State the survivorship bias on every report, and prefer tests that compare stocks
  with each other on the same day (section 2a), which the bias distorts less than a total return.

## 8. What this means for milestone 3 [my view]

Milestone 3 as approved says "three models, one test". The research says the test is the larger
part of the work. A proposal, for Brian's decision:

**The ledger.** Every test of every signal variant gets a line in a tracked file before it runs:
what, why, horizon, universe, date. The count of independent tries (section 3c) comes from it.
Without it none of the corrections can be computed.

**Five gates for a signal**, in order; a fail stops the signal.
1. **Reason and plan.** A written reason and one planned test, entered in the ledger first.
2. **Ranking power.** Mean daily rank IC on non-overlapping horizons, t-stat with Newey-West
   errors. Pass mark t ≥ 3.0 (Harvey, Liu, Zhu). Across a round of signals, also the
   Benjamini-Yekutieli procedure at 5%. News signals use the event study with the
   Kolari-Pynnönen correction instead.
3. **Money after costs, long-only.** The top group against the whole watchlist, bought at the
   first tradable price, minus the fee table's cost. Purged splits. Pass mark: deflated Sharpe
   ratio ≥ 0.95 with the ledger's count of tries.
4. **Robustness.** Probability of backtest overfitting across the signal's variants ≤ 0.05;
   positive in both halves of the history and in each market; still positive at double the cost.
5. **Hold-out, opened once.** The last two years, never used before. The effect keeps its sign
   and at least half its size (published signals lose 26% on average out of sample).

After the gates: a live record. Forecasts are stored daily for three months before any Telegram
alert uses the signal, because only live results are truly out of sample.

**What to expect.** With 10 years of data, a signal needs a yearly Sharpe near 1 or better to
pass. Most candidates will fail, and "no signal proven yet" is a possible honest result of the
first rounds. The dashboard would then show forecasts marked unproven and send no alerts.

**The alert bar.** "60% right in 30 cases" (milestone 4) does not pass a coin-flip test (section
1c). A bar that does: the low end of the 95% range for the hit rate must be above 50%, counted on
non-overlapping cases. That is 20 of 30, or 60 of 100.

## 9. Could not confirm

The four note files list every gap. The ones that touch the proposal above:
- Bailey and Lopez de Prado's 2012 paper (the probabilistic Sharpe ratio) did not open; the
  formula comes from two later papers that restate it.
- White (2000), Romano and Wolf (2005), MacKinlay (1997), Boehmer et al. (1991) and Kolari and
  Pynnönen (2010) were read as abstracts; their formulas come from documentation and a vendor
  page.
- The closed form for the number of independent tries from the average correlation.
- Any authoritative pass mark for the information coefficient.
- Bessembinder's 2026 paper itself, and Dimensional's and Research Affiliates' pages: read
  second-hand only.
- The official WorldQuant BRAIN thresholds.
- Whether any free source has past Hang Seng Index membership.
