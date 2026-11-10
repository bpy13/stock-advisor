# Research 2: state of the art in quant investing (facts only)

Labels: [primary] = opened the paper/page text. [secondary] = summary, review, transcript of unknown fidelity. [snippet only] = seen only in a search result. [unconfirmed] = could not verify.
Search results themselves are summaries; where I could not open the page I say so.

---------------------------------------------------------------
## 1. Renaissance Technologies / Medallion

### 1a. Returns, fees, size
- Cornell, "Medallion Fund: The Ultimate Counterexample?" (2 Dec 2019). Institutional Investor's summary [secondary; paper itself not opened]: reported gross returns averaged 66% a year 1988-2018, no negative gross year in 31 years; gross returns are after trading costs; Cornell: "no adequate rational market explanation". https://www.institutionalinvestor.com/article/2bswymr8cih3jeaslxc00/portfolio/famed-medallion-fund-stretches-explanation-to-the-limit-professor-claims
- Same article: Medallion closed to outsiders since 1993, assets near $10bn, net returns above 29% each year 2010-2018 [secondary].
- Blog summary of Cornell: 63.3% gross vs 39.2% after fees, 1988-2018 [snippet only] (search result for Cornell paper, e.g. https://pwlcapital.com/renaissance-technologies-medallion-fund-an-exception-to-the-indexing-rule/ ).
- Wikipedia (secondary): 66% before / 39% after fees average since 1988 (citing a 2019 book); 71.8% before fees 1994-mid-2014 (Bloomberg 2015); 2008 +98.2%; 2020 +76%; closed to outside investors; "petabyte-scale" data warehouse. https://en.wikipedia.org/wiki/Renaissance_Technologies
- Dissent: Guo and Liu (arXiv 2405.10917, 2024) [primary abstract]: reported annualized return above 60%; they estimate 31.8% compounded before fees from fund sizes and profits, and conclude "probably under 35%". https://arxiv.org/abs/2405.10917
- Acquired podcast transcript [secondary]: early management fee 5%, carry raised to 44% in 2002; outside investors removed from Medallion 2003; lower-fee institutional funds (1%/10%) track the S&P more closely than Medallion; Medallion capacity about $10bn (hosts' statement). https://podscripts.co/podcasts/acquired/renaissance-technologies (only first ~100k of 196k chars read)
- Capacity: only figures found are ~$10bn (Institutional Investor, Acquired) and ~$15bn (one secondary summary [snippet only]). Hosts also mention ~$5bn limits from slippage/market impact [secondary, Acquired transcript].

### 1b. "Right 50.75% of the time"
- Attributed to Robert Mercer in Zuckerman's book. Acquired hosts quote: "we're 100% right 50.75% of the time" and note he was likely illustrating, not citing a precise figure [secondary]. https://podscripts.co/podcasts/acquired/renaissance-technologies
- Novel Investor summary version: "We're right 50.75 percent of the time... but we're 100 percent right 50.75 percent of the time. You can make billions that way." [snippet only]. https://novelinvestor.com/notes/the-man-who-solved-the-market-by-gregory-zuckerman/ (could not open this page)
- Goodreads reader notes carry the same line [snippet only; page returned empty]. Original book page not seen. Penguin UK sample PDF (https://cdn.penguin.co.uk/dam-assets/books/9780241309735/9780241309735-sample.pdf) does NOT contain "50.75" (grepped locally). Status: attributed to Mercer by secondary sources; exact wording and page [unconfirmed].

### 1c. Methods named, by source
- Simons, TED interview transcript (Singju Post) [secondary]: early on commodities and currencies "had a tendency to trend"; trend-following "would have been great in the '60s" but not by the '80s; example rule of predicting from the average move over the past 20 days; they tested different trend lengths and he calls this "machine learning" in a sense; they looked for anomalies, persistent ones less likely random, anomalies fade; inputs from weather to annual reports; "terabytes of data a day". https://singjupost.com/a-rare-interview-with-the-mathematician-who-cracked-wall-street-jim-simons-at-ted-full-transcript/
- Zuckerman book as summarized in "How RenTech won" [secondary]: bought decades of price history; hand-collected Fed interest-rate history; early signals: currency momentum, commodity correlations; "retracement" bets that sharp moves partly reverse (~60% of the time, strongest in currencies); required statistical significance before explaining; many signals had no explanation by 1997; kept faint signals; average holding time fell from about 1.5 weeks to about 1.5 days by 1989; positions shrink when strategies underperform or volatility rises; testing academic ideas usually failed. https://ishanjmukherjee.github.io/how-rentec-won
- Acquired transcript [secondary]: Leonard Baum expert on hidden Markov models (~25:45); Brown and Mercer from IBM speech recognition joined 1993; built a single model across currencies, commodities, equities (summary section); Berlekamp's bet-sizing work and a shift to more frequent trading. https://www.acquired.fm/episodes/renaissance-technologies and https://podscripts.co/podcasts/acquired/renaissance-technologies
- Wikipedia: Medallion's roots in Leonard Baum's models (Baum-Welch linked) expanded by James Ax. https://en.wikipedia.org/wiki/Renaissance_Technologies [secondary]. The link between Baum-Welch/HMM and trading signals at Medallion itself: [unconfirmed] by any primary source I opened; search for a Patterson statement on HMM/Baum-Welch found nothing.
- Kernel methods at Renaissance: [unconfirmed]; nothing found.
- Mercer/Brown patents show both listed as inventors on RenTech trading filings [snippet only]: https://trea.com/person/peter-f-brown/information/7364e421-9d8f-447c-adde-66522dd113bb
- Leverage: average about 12.5x attributed to Zuckerman, up to 20x [snippet only, secondary sites]. Trading-cost modelling: no source found.
- Holding periods: Goodreads highlight says "one or two days to one or two weeks" [snippet only]; the 1.5 weeks -> 1.5 days figure above is from the secondary summary.

### 1d. Regression at Renaissance (relevant to the user's question)
- Nick Patterson (ex-Renaissance), on The Talking Machines podcast per a Hacker News post (~30:06 and 38:03): "our most important statistical tool was simple regression with one target and one independent variable"; the hard part is choosing the variables, data, transformations and cleaning. Also a bracketed note (attribution unclear) that 7 PhDs just cleaned data. https://news.ycombinator.com/item?id=19065226 [secondary: HN post quoting the podcast; I did not open the podcast transcript itself]. Same quote on X/Substack (QuantSeeker): https://x.com/quantseeker/status/1879118660108693792 (page returned HTTP 402, snippet only).
- Simons (Numberphile 2015): a Hacker News commenter says he suggests "mostly using ML and other relatively simple techniques" [snippet only, third-hand]. Interview: https://www.numberphile.com/videos/billionaire-mathematician ; non-verbatim transcript: https://hedgefundalpha.com/strategies/jim-simons-numberphile/ (not opened). I did not confirm any model names from the Numberphile video.
- Simons, MIT 2010 talk "Mathematics, Common Sense, and Good Luck": a write-up says models are revised weekly (HedgeWorld) and he decided to focus on building models rather than picking traders [snippet only]. https://news.mit.edu/2011/mitworld-simons . No transcript opened.

### 1e. "Jim Simons's playbook"
- A Threadreader thread titled "Jim Simons' Playbook: the King of Quant" exists (social media thread) https://threadreaderapp.com/thread/1385727922116259842.html [snippet only]. I found no book or video of that exact name. Closest book: Zuckerman, "The Man Who Solved the Market" (Portfolio/Penguin, 2019) https://www.randomhousebooks.com/books/557104 [snippet only; listing].

### 1f. Documented vs speculation (summary of what sources show)
- Documented by Simons himself (TED): trend rules early, anomaly hunting, testing many predictive schemes, huge data intake.
- Documented by a named ex-employee (Patterson, via HN post): simple regression as the most important statistical tool.
- Reported by journalists/book (secondary): short holding periods, many weak signals, leverage, fees, capacity near $10bn, 50.75% line.
- Not confirmed by anything I opened: HMM/Baum-Welch/kernel use in live signals, trading-cost model details, "single model" detail beyond the Acquired hosts' summary.

---------------------------------------------------------------
## 2. Academic ML return prediction

### Gu, Kelly, Xiu (2020, RFS; NBER w25398) [primary text read from the PDF]
- Models: OLS (all 920 predictors), OLS-3 (size, B/M, momentum), PLS, PCR, elastic net, group-lasso GLM, random forest, gradient boosted trees, neural nets with 1-5 layers (13 in total). Monthly stock-level excess returns, US stocks 1957-2016, 94 characteristics plus interactions; 30-year recursive out-of-sample test. Link: https://www.nber.org/papers/w25398 (PDF: https://www.nber.org/system/files/working_papers/w25398/w25398.pdf)
- Table 1 monthly out-of-sample R2, all stocks: OLS -3.46%, OLS-3 0.16%, PLS 0.27%, PCR 0.26%, ENet 0.11%, GLM 0.19%, RF 0.33%, GBRT 0.34%, NN1 0.33%, NN2 0.39%, NN3 0.40%, NN4 0.39%, NN5 0.36%. Top-1000 stocks: NN3 0.70%, RF 0.63%.
- Economic results (paper intro): NN timing of S&P 500, out-of-sample Sharpe 0.77 vs 0.51 buy-and-hold; value-weighted decile long-short Sharpe 1.35 (equal-weighted 2.45), "more than doubling" a leading regression-based strategy.
- Abstract (NBER page): best performers trees and neural nets; gains from nonlinear interactions; dominant signals are momentum, liquidity, volatility variants. In the paper "shallow learning outperforms deeper learning".
- Form of target: continuous excess return (regression), loss is squared error; "regression" includes ridge/lasso/forests/NNs fit to a continuous target.

### Kelly, Malamud, Zhou, "The Virtue of Complexity in Return Prediction" (J. Finance 2024) [primary NBER PDF read]
- Model: ridge/ridgeless regression with more parameters than observations (random-feature neural-net style); target: aggregate market return (Goyal-Welch predictors), monthly; CRSP 1926-2020. https://www.nber.org/papers/w30217 ; J. Finance 79(1): https://econpapers.repec.org/RePEc:bla:jfinan:v:79:y:2024:i:1:p:459-503
- Out-of-sample market-timing Sharpe improvement about 0.47 a year, t-stat near 3.0, while out-of-sample R2 is negative for most models; the authors argue R2 is a poor economic measure. Strategies divest before 14 of 15 NBER recessions. Still regression (continuous target).
- Critics (reported by secondary article): traditionalists say financial data are too small and noisy for complex models [snippet only]: AQR page https://www.aqr.com/Insights/Research/Journal-Article/The-Virtue-of-Complexity-in-Return-Prediction

### Chen, Pelger, Zhu, "Deep Learning in Asset Pricing" (Management Science) [primary arXiv text read]
- Model: neural network estimating a stochastic discount factor (no-arbitrage/GMM criterion), adversarial test assets, macro states from 178 series; CRSP monthly 1967-2016, 46 characteristics. https://arxiv.org/abs/1904.00745
- Out-of-sample annual Sharpe 2.6, vs 1.7 linear version, 1.5 deep-learning forecasting approach, 0.8 Fama-French 5-factor; explains 8% of variation of individual stock returns. Not a plain return regression: a no-arbitrage pricing-kernel estimation.

### Jiang, Kelly, Xiu, "(Re-)Imag(in)ing Price Trends" (J. Finance 2023) [primary text read from the journal PDF]
- Model: CNN on images of price/volume charts (5, 20, 60 days), US stocks 1993-2019, test 2001-2019. Target: binary up/down of the next return, cross-entropy loss (classification, outputs a probability of "up"). https://papers.ssrn.com/abstract=3756587 (page blocked); PDF used: economics.yale.edu copy of the J. Finance article.
- Weekly decile spread out-of-sample gross Sharpe up to 7.2 equal-weight, 1.7 value-weight (benchmarks WSTR/TREND 2.8/2.9 equal-weight); monthly 2.4 and quarterly 1.3 equal-weight; authors say weekly strategy mostly accessible to investors who behave as market makers; profits stay positive after costs at lower rebalancing frequency.

### Kelly and Xiu, "Financial Machine Learning" (Foundations and Trends in Finance, 2023)
- Survey of ML in finance for two audiences; sections include "virtues of complex models", return prediction, risk-return, portfolios. https://www.nber.org/papers/w31502 ; https://nowpublishers.com/article/Details/FIN-064 . I read the abstract and section headings and one passage on ridgeless R2 (PDF text); no new numbers beyond the above.

### Transformer / foundation-model work (snippet only, not opened unless noted)
- StockGPT (arXiv 2404.05101): GPT-style model trained on daily US returns; early version reported equal-weight daily long-short Sharpe 6.5; later version value-weight about 27% a year, Sharpe about 1 [snippet only]. https://arxiv.org/abs/2404.05101
- "Re(Visiting) Time Series Foundation Models in Finance" (arXiv 2511.18578): off-the-shelf pretrained models give out-of-sample R2 -1.37% to -2.80%; best performer CatBoost Sharpe 6.79 at a 252-day window [snippet only]. https://arxiv.org/abs/2511.18578
- NBER w33351, transformer inside the stochastic discount factor, outperforms on out-of-sample risk-adjusted returns [snippet only]. https://www.nber.org/papers/w33351
- Lopez-Lira and Tang, "Can ChatGPT Forecast Stock Price Movements?" (arXiv 2304.07619): LLM labels headlines good/bad/neutral, scores correlate with next-day returns; stronger for small stocks and bad news; latest version says returns decline as LLM adoption rises [snippet only for abstract; PDF text was fetched locally]. https://arxiv.org/abs/2304.07619
- Reinforcement learning as return predictor: no academic RL-for-returns paper checked.

---------------------------------------------------------------
## 3. Practitioner state of the art

### Kaggle and public competitions
(Kaggle write-up bodies could not be fetched; titles/snippets only.)
- Jane Street Market Prediction (2021): 1st place page title "Yirun's Solution (1st place): Training Supervised Autoencoder with MLP" [title only]. https://www.kaggle.com/competitions/jane-street-market-prediction/discussion/224348 . Secondary summary: winning blend was XGBoost plus supervised-autoencoder MLP [snippet only]. Task: choose trade/no-trade (action) scored by a utility metric; a public participant notebook built action = 1 when more than half of five return columns were positive and used PurgedGroupTimeSeriesSplit with XGBoost (not a winner) https://bullettech.github.io/BulletTech/Main_Course/Machine_Learning/2021-09-02-Kaggle-janestreet [secondary].
- Jane Street Real-Time Market Data Forecasting (2024-25): scored by sample-weighted zero-mean R2 on responder_6 (regression) [snippet only from a mirror of the competition page: https://anilkeshwani.github.io/garden/Clippings/Jane-Street-Real-Time-Market-Data-Forecasting--Kaggle , page 404 on re-fetch]. Winner write-up not obtained [unconfirmed]; a 162nd-place write-up used online-learning TabM neural net plus GBDT [snippet only]: https://www.kaggle.com/competitions/jane-street-real-time-market-data-forecasting/writeups/max-abhi-private-lb-162nd-solution . A study note lists a public-LB-6th encoder-decoder GRU solution [snippet only].
- Optiver Realized Volatility Prediction (2021): 1st place thread titled "1st Place Solution - Nearest Neighbors" [title only] https://www.kaggle.com/competitions/optiver-realized-volatility-prediction/discussion/274970 ; a 91st-place write-up says the winner recovered time_id order from price tick size [snippet only]; top-tier solutions combined LightGBM and neural nets with kNN-derived features (silver-medal paper) [snippet only]. Metric RMSPE on realized volatility (regression).
- Optiver Trading at the Close (2023-24): 1st place by "hyd": blend of CatBoost, GRU and Transformer weighted 0.5/0.3/0.2, same 300 features, train on first 400 days, validate on last 81, private LB 5.4030 (MAE metric) [snippet only; writeup page title only when fetched]. https://www.kaggle.com/competitions/optiver-trading-at-the-close/writeups/hyd-1st-place-solution
- Two Sigma news competition (2018): predicts a signed confidence for 10-day market-adjusted return, scored as mean/std of daily score; GPU submissions reportedly not accepted; a 2nd-place code repo exists [snippet only]. 1st place write-up not found [unconfirmed]. https://relatedrepos.com/gh/wonabru/kaggle-two-sigma-winner
- Ubiquant Market Prediction (2022): winning solution and metric not found [unconfirmed].
- Numerai (docs): data rows are a stock at a point in time; `target` aliases target_jupiter_60 (60 business days ahead); scored on correlation (CORR) and meta-model contribution (MMC); docs give a LightGBM regressor as example; submit rank-based predictions per ticker. https://docs.numer.ai/ [primary, fetched main page]

### Firm statements
- WorldQuant: Kakushadze, "101 Formulaic Alphas" abstract: formulas are code; average holding periods about 0.6-6.4 days; average pairwise correlation about 15.9%; returns track volatility, not turnover. https://arxiv.org/abs/1601.00991 [primary abstract]
- Jane Street ML page: neural network models behind strategies; "deep learning is the future of quantitative trading" (firm's words); data mostly noise; its own trades affect the data its models predict; tens of thousands of GPUs. https://www.janestreet.com/machine-learning [primary]
- AQR: Asness said in 2016 AQR was not using machine learning, using simpler predictions; by 2024 said more modern ML is being adopted [snippet only]. https://www.bloombergquint.com/markets/2016/10/27/aqr-s-asness-says-machine-learning-won-t-replace-stock-pickers ; AQR page above on "Virtue of Complexity" (Kelly is AQR's head of machine learning, per the snippet).
- Man AHL: Man's "Diary of a Quant" says true ML has been part of AHL for over a decade, uses reinforcement learning to route trades, warns of data-mining risk; AHL also re-tests momentum systems with ML [snippet only]. https://www.man.com/insights/the-big-picture-ai ; https://www.risk.net/hedge-funds-review/news/2470076/man-ahl-investors-profit-from-artificial-intelligence
- Two Sigma: official page describes a scientific process with data and modelling stages; article on deep learning for sequences in quant finance [snippet only]. https://www.twosigma.com/businesses/investment-management
- D. E. Shaw: systematic side seeks statistically robust market inefficiencies via scientific research and computational methods; also runs discretionary strategies [snippet only]. https://deshaw.com/what-we-do/investment-approach
- Market making vs prediction: Jane Street page above frames ML as prediction for trading; Citadel: nothing found.

---------------------------------------------------------------
## 4. Non-regression approaches (one line each)
- Time-series momentum: go long/short each asset by its own past return; 58 liquid futures (equity index, currency, commodity, bond); diversified portfolio earns abnormal returns with little factor exposure, does best in extreme markets (Moskowitz, Ooi, Pedersen, JFE 2012) https://papers.ssrn.com/abstract=2089463 [snippet only]. Lookback of 1-12 months [unconfirmed in the original; a later Hurst-Ooi-Pedersen paper uses 1/3/12-month mix].
- Pairs trading (distance method): pair stocks by minimum distance between normalized prices, trade divergence; about 11% annualized excess return for top-pairs portfolios, 1962-2002, daily data (Gatev, Goetzmann, Rouwenhorst, RFS 2006) https://econpapers.repec.org/RePEc:oup:rfinst:v:19:y:2006:i:3:p:797-827 [snippet only; abstract not opened].
- Statistical arbitrage with PCA/ETF residuals: Avellaneda and Lee: Sharpe 1.44 PCA 1997-2007 after costs, about 0.9 PCA 2003-2007, 1.1 ETF-based, 1.51 volume-weighted 2003-2007; daily-frequency US equities https://www.math.nyu.edu/faculty/avellane/AvellanedaLeeStatArb20090616.pdf [snippet only; they also use regression of stocks on ETFs to get residuals].
- Hidden Markov regime models: no performance source gathered [unconfirmed]; Baum link in section 1.
- Reinforcement learning for execution: AHL says it uses RL to find the best route to market (section 3 link) [snippet only].
- Optimization-based portfolio construction and market making: no documented-return source gathered [unconfirmed].
- Rule-based trend following is also in Simons's TED description (section 1c).

---------------------------------------------------------------
## 5. Canonical books (one line each; publisher pages mostly not opened)
- Zuckerman, The Man Who Solved the Market (2019): narrative history of Simons and Renaissance; reviews say it does not reveal the full method. https://www.randomhousebooks.com/books/557104 [snippet only]
- Thorp, A Man for All Markets (Random House, 2017): memoir from blackjack card counting to Wall Street. https://www.randomhousebooks.com/books/178551 [snippet only]; Beat the Market (Thorp and Kassouf): co-written; content not confirmed here.
- Grinold and Kahn, Active Portfolio Management: fundamental law IR = IC x sqrt(breadth); full form adds a transfer coefficient (TC x IC x sqrt(breadth)); critics note transaction costs absent. https://corporatefinanceinstitute.com/resources/capital-markets/fundamental-law-of-active-management/ [secondary]; Morgan Stanley note https://www.morganstanley.com/im/publication/insights/articles/dispersion-and-alpha-conversion.pdf (IR 0.10 good, 0.50+ excellent) [snippet only]
- López de Prado, Advances in Financial Machine Learning (Wiley 2018): chapters on triple-barrier labelling, purged cross-validation with embargo, combinatorial purged CV. https://www.lehmanns.de/isbn/978-1-119-48208-6 [catalogue listing, snippet only]
- Narang, Inside the Black Box (Wiley; 3rd ed 2024): non-technical guide to systematic/quant trading. https://parnassusbooks.net/book/9781119931898 [snippet only]
- Pedersen, Efficiently Inefficient (Princeton UP 2015): hedge fund strategies (equity, macro, arbitrage), portfolio choice and risk, with interviews (Asness, Griffin, Harding and others). https://econpapers.repec.org/RePEc:pup:pbooks:10441 [snippet only]
- Chan, Quantitative Trading (Wiley, 2nd ed 2021): idea generation, backtesting, execution, risk, mean reversion vs momentum, adds ML. https://oreilly.com/library/view/quantitative-trading-2nd/9781119800064 [snippet only]. Algorithmic Trading (Chan, Wiley): only confirmed as a Wiley title, content not described.
- Machine Learning for Asset Managers (López de Prado), Ilmanen Expected Returns, Harris Trading and Exchanges: [unconfirmed] no description found this round.

---------------------------------------------------------------
## 6. Realism for an individual
- McLean and Pontiff (J. Finance 2016) [primary abstract read from PDF]: 97 predictors; returns 26% lower out-of-sample and 58% lower post-publication; they attribute 32% (58-26) to publication-informed trading. https://doi.org/10.1111/jofi.12365 (PDF read: https://www.gwern.net/doc/economics/2016-mclean.pdf)
- Harvey, Liu, Zhu (RFS 2016): new factor needs "a much higher hurdle, with a t-ratio greater than 3.0" [primary NBER abstract]. https://www.nber.org/papers/w20592 . CXO summary: 313 published + 63 working-paper = 316 factors [secondary] https://www.cxoadvisory.com/big-ideas/taming-the-factor-zoo/
- Hou, Xue, Zhang, "Replicating Anomalies" (RFS 2020): of 452 anomalies, 65% fail t of 1.96 and 82% fail 2.78 once microcaps are controlled via NYSE breakpoints and value-weighting; 161 survive [snippet only: IDEAS abstract + Alpha Architect]. https://ideas.repec.org/a/oup/rfinst/v33y2020i5p2019-2133..html
- Barber and Odean (J. Finance 2000) [primary abstract read from PDF]: 66,465 households 1991-96; heaviest traders earn 11.4% a year vs market 17.9%; average household 16.4%, turns over 75% a year; gross returns near market, costs drive gap; round trip cost 3% commission plus 1% spread for trades over $1,000. Link: https://econpapers.repec.org/RePEc:bla:jfinan:v:55:y:2000:i:2:p:773-806 (PDF: https://faculty.haas.berkeley.edu/odean/Papers%20current%20versions/Individual_Investor_Performance_Final.pdf)
- Typical IC 0.02-0.05 and resulting Sharpe: no source found for the "typical IC" range itself [unconfirmed]. Arithmetic from the law (formula in section 5): IR = IC x sqrt(breadth); an IC of 0.05 with 100 independent bets a year gives IR about 0.5, 0.02 with 100 gives 0.2, 0.05 with 1,000 gives about 1.6 (my arithmetic, before costs and transfer coefficient).
- Context from section 2: the GKX best-model out-of-sample monthly R2 is about 0.4% (a correlation of roughly 0.06 by my arithmetic: sqrt(0.004)), Jiang-Kelly-Xiu equal-weight weekly Sharpe 7.2 is gross and accessible mainly to market-maker-like traders per the authors.
