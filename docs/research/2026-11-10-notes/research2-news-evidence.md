# Research 2: news evidence for a portfolio news-alert tool (fact gathering, no verdicts)

Method note: facts below come from pages opened with WebFetch or from WebSearch results (the search tool returns short summaries, not full pages). Labels: [opened] = I read the primary page or its text; [search] = a search summary of the primary/secondary source, page not opened; [snippet only] = seen only in a search snippet; [unconfirmed] = I could not confirm. Several PDF downloads (SSRN, Scribd, core.ac.uk, bulk curl) were blocked or unreadable, so many magnitudes are missing and are listed as gaps at the end. Date of research: 2026-11-10.

## 1. How fast prices absorb news, by news type

**Scheduled macro releases**
- Most big US macro releases come at 08:30 ET when futures trade but the cash equity market is closed. Andersen, Bollerslev, Diebold, Vega find high-frequency prices jump with the news. [search] https://economics.sas.upenn.edu/sites/default/files/filevault/working-papers/04-028.pdf
- FX: "conditional mean adjustments of exchange rates to news occur quickly, effectively at announcement time"; bad news has more impact than good news (sign effect). [search] https://econpapers.repec.org/RePEc:aea:aecrev:v:93:y:2003:i:1:p:38-62
- The "most large FX changes happen within 10 seconds" claim is attributed to Dominguez (1999), cited in the NBER paper. FX, not equity. [search] https://www.nber.org/system/files/working_papers/w8959/w8959.pdf
- A source stating nonfarm-payroll futures adjust within seconds: [unconfirmed].

**Earnings**
- Martineau ("Rest in Peace Post-Earnings Announcement Drift", Critical Finance Review 11, 613-646): for large stocks drift is non-existent since 2006; microcaps lost it more recently; he says prices reflect the surprise on the announcement day. [search] https://nowpublishers.com/article/Details/CFR-0122
- Counter-evidence: Zhao (2022) attributes the PEAD decline to less persistent earnings news, not arbitrage. Two 2025 papers (Dickerson, Julliard, Mueller) conclude earnings drift remains a major factor; Subrahmanyam (2025) says disagreement reflects research design. Chan and Marsh (2024) find overnight drift after extreme earnings misses. All via one secondary summary. [search, secondary] https://econpapers.repec.org/RePEc:now:jnlcfr:104.00000122
- Minutes-level earnings reaction magnitudes: [unconfirmed] (not found).

**Unscheduled company news, news vs no news (Chan 2003, JFE 70(2):223-260)**
- Monthly returns after headlines versus similar-return stocks with no news: strong drift after bad news; reversal after extreme moves with no public news; effects mainly in small, illiquid stocks. [search] https://econpapers.repec.org/RePEc:eee:jfinec:v:70:y:2003:i:2:p:223-260
- A separate search summary says drift lasts up to 20 days after news; not verified against the paper. [search, secondary] https://academicnewsletter.sufe.edu.cn/info/357702
- Boudoukh, Feldman, Kogan, Richardson: of 1.9 million Dow Jones stories (2000-2009) only about half are identified as relevant events; volatility on identified-news days is over twice other days; news-day vs no-news-day R-squared 16% vs 33%. [search] https://www.nber.org/digest/jun13/which-news-moves-stock-prices
- Boudoukh et al. 2019 RFS: news accounts for 49.6% of overnight idiosyncratic volatility vs 12.4% in trading hours. [search] https://econpapers.repec.org/RePEc:oup:rfinst:v:32:y:2019:i:3:p:992-1033

**Analyst changes**
- Savor 2012 (JFE 106(3):635-659): price events with an analyst report around them are followed by drift; events without are followed by reversal; the drift appears only when price move and recommendation change have the same sign; information-based moves correlate more with later earnings surprises. A secondary source puts the drift within about 3 months. [search] https://econpapers.repec.org/RePEc:eee:jfinec:v:106:y:2012:i:3:p:635-659 and https://repository.upenn.edu/fnce_papers/387
- Savor precise magnitudes (percent per day or month): [unconfirmed]; SSRN and core.ac.uk PDFs returned HTTP 403 or could not be read.

**Geopolitical shocks**
- Caldara and Iacoviello (AER 112(4):1194-1225): news-based GPR index from 10 newspapers; higher GPR foreshadows lower investment and employment and higher disaster probability. The abstract does not mention stock returns; the authors' page says it also foreshadows lower stock prices. [search] https://www.aeaweb.org/doi/10.1257/aer.20191823 and https://matteoiacoviello.com/gpr.htm
- War outbreak: Russia-Ukraine 2022 studies report negative CARs in global indices with heterogeneous effects; reaction began before the official announcement; some European markets stayed negative over longer windows, exposed firms fell more. No single duration figure found. [search] https://www.uni-trier.de/fileadmin/fb4/prof/VWL/EWF/Research_Papers/2023-03.pdf
- Schneider and Troeger (2006) is cited as finding negative impact of Iraq's 1990 invasion of Kuwait and positive impact of Operation Desert Storm; original not opened. [search, secondary] https://orca.cardiff.ac.uk/id/eprint/170384/1/Firms%20Entangled%20in%20Geopolitical%20Conflicts%20-%20RR3%20-%20with%20info.pdf
- Tariffs 2018-19: Amiti, Gomez, Kong, Weinstein: cumulative market drop of 11.5% on eleven tariff-announcement dates; China-exposed firms did worse. Egger and Zhu (2019) use about 19 events, CAR from one day before to up to ten days after. Wengerek (2020) uses a 3-day window on 2,849 announcements, effect driven by China-related ones. [search] https://www.newyorkfed.org/medialibrary/media/research/economists/amiti/Amiti-StockPrices and https://cepr.org/voxeu/columns/stock-market-responses-triggered-us-china-trade-war
- Tariffs April 2025: S&P 500 lost about 12% from Apr 3 to Apr 8, gained 9.5% on Apr 9 after the 90-day pause, fell about 3.5% on Apr 10, regained its Apr 2 level by early May (press). BIS box: recovery through mid-May mostly from backtracking on the tariffs; about 75% of the rise from the Apr 9 trough to end-July attributed to non-tariff positive surprises; S&P 500 passed its pre-stress peak in just under 20 weeks. [search] https://www.bis.org/publ/qtrpdf/r_qt2509w.htm and https://finance.yahoo.com/news/p-500-recovered-losses-215247252.html

**Cyber-security breach disclosures**
- Cavusoglu, Mishra, Raghunathan (2004): about -2.1% market value loss in the two days around the announcement. [search, secondary] https://aisel.aisnet.org/icis2006/94 (cited in Acquisti et al. results)
- Acquisti, Friedman, Telang (ICIS 2006): negative significant effect on announcement day; CAR grows in magnitude the day after, then shrinks and loses significance. [search] https://aisel.aisnet.org/icis2006/94
- Kannan, Rees, Sridhar (2007): no significant abnormal return around breach date. [search] same results page.
- A 2025 study of 3,316 US breaches (2006-2024): -0.26% over a 5-day window, dissipating within a month. [snippet only, source not identified] https://www.emerald.com/ics/article/doi/10.1108/ICS-10-2025-0424/1393614/
- A study of breaches of 30,000+ records: share price stabilizes at event day 6. [snippet only] https://openaccess.nhh.no/nhh-xmlui/handle/11250/2736559?show=full
- Kamiya 2021: [unconfirmed].

**China/HK policy**
- Zhao (CityU HK): 7-day abnormal change about -8.5% for Alibaba after the Dec 2020 antitrust probe; rivals about -12%. [search] https://www.cb.cityu.edu.hk/CityBusinessMagazine/Issue16/en/regulating-big-tech-in-china-does-it-matter
- Hang Seng Tech was down 31% from its February 2021 high by early July 2021; down 11% in July after the Didi download ban (Bloomberg via press). [search] https://www.bloomberg.com/news/articles/2021-07-07/down-831-billion-china-tech-firm-selloff-may-be-far-from-over
- Sept 24 2024 PBoC package: Hang Seng +13% week to Sep 27, +10.2% week to Oct 4; peak 23,242 on Oct 7; about 4,196 points (23%) gain in six trading days; HSI retraced about 50% by Oct 24 (FX Empire); HSI -3.9% for October. Hang Seng Tech +3.62% on Sep 27 and -1.37% in week to Oct 25. [search; press and broker blogs] https://asiatimes.com/2024/10/chinese-stocks-cool-down-as-investors-check-reality/ and https://www.fxempire.com/forecasts/article/hang-seng-index-falls-despite-china-stimulus-asian-market-weekly-recap-1471582
- A peer-reviewed abnormal-return study for the HK tech selloff or Sept 2024: [unconfirmed] (none found).

## 2. Which news features predict returns after the first minutes

- Tetlock 2007 (JF 62:1139-1168), WSJ "Abreast of the Market" column, Dow Jones returns. [opened, text extracted] https://www.columbia.edu/~pt2238/papers/Tetlock_Media_Sentiment_JF.pdf
  - One standard deviation more pessimism predicts next-day Dow return lower by 8.1 bp, versus unconditional mean 5.4 bp.
  - Reversal in lags 2-5 is 6.8 bp; for Negative words and Weak words the delayed rebound is 9.5 and 10.7 bp, and the paper says reversal is complete for those and over 85% (text fragment: "over 85%").
  - Extreme pessimism or optimism predicts high trading volume. Abstract: evidence "inconsistent" with news as a proxy for fundamentals information.
- Tetlock, Saar-Tsechansky, Macskassy 2008 (JF 63:1437-1467): fraction of negative words in firm-specific stories predicts low earnings; prices briefly underreact; strongest for stories about fundamentals. [search] https://econpapers.repec.org/RePEc:bla:jfinan:v:63:y:2008:i:3:p:1437-1467 (magnitudes and 1-day horizon: [unconfirmed]; PDF not parseable)
- Tetlock 2011 (RFS 24:1481-1512): staleness = text similarity to the firm's previous ten stories; returns react less to stale news, but a stale-news-day return predicts reversal the next week; individual investors trade more aggressively on stale news. [search] https://econpapers.repec.org/RePEc:oup:rfinst:v:24:y:2011:i:5:p:1481-1512
- Tetlock 2010 (RFS 23:3520-3557): news resolves asymmetric information more for small and illiquid stocks; high-volume news-day return positively predicts later return. [search] https://econpapers.repec.org/RePEc:oup:rfinst:v:23:y:2010:i:9:p:3520-3557 and https://projects.nber.org/confer/2009/MMf09/Tetlock.pdf
- Barber and Odean 2008 (RFS 21:785-818): individuals are net buyers of attention-grabbing stocks, proxied by news, abnormal volume, extreme one-day returns; professionals less affected. [search] https://econpapers.repec.org/RePEc:oup:rfinst:v:21:y:2008:i:2:p:785-818
- Chan 2003 and Savor 2012: see section 1 (drift after news, reversal after no-news moves).
- Scott, Stumpp, Xu (FAJ 2003) "News, not trading volume, builds momentum": after controlling for earnings news, the momentum-volume interaction largely disappears. [search] https://rpc.cfainstitute.org/research/financial-analysts-journal/2003/news-not-trading-volume-builds-momentum
- UK news-media study (Durham): tone and volume of news media predict next-period abnormal returns, volume more than tone. [search] https://durham-repository.worktribe.com/OutputFile/1415795
- Overnight news: Lopez-Lira and Tang sample is 82% overnight news (129,953 of 158,998). [opened] https://arxiv.org/html/2304.07619v6. Boudoukh 2019: news explains 49.6% of overnight idiosyncratic variance (section 1).
- Firm-specific vs macro, and source credibility as predictors: [unconfirmed] (no source opened).

## 3. LLM-era results (2023-2026)

- Lopez-Lira and Tang, "Can ChatGPT Forecast Stock Price Movements?" arXiv 2304.07619. Versions: v1 15 Apr 2023 ... v5 11 Sep 2024, v6 28 Oct 2025 (latest seen). [opened] https://arxiv.org/abs/2304.07619
  - Method (v6): GPT-4 (gpt-4-0314, temperature 0) answers YES/NO/UNKNOWN for a headline's short-term stock impact, mapped to +1/-1/0; daily-rebalanced long-short portfolio. Sample Oct 2021 to May 2024; 159,137 firm-headline-date observations, 4,123 companies. [opened] https://arxiv.org/html/2304.07619v6
  - Overnight news, annualized drift Sharpe: GPT-4 2.97 (mean daily drift return 0.34%), GPT-3.5 1.66, DistilBART 1.26, BART-large 1.05, Llama2-70b 0.97, FinBERT -0.33. GPT-4 intraday news Sharpe 2.63. [opened] same.
  - By year, annualized Sharpe: 6.54 (2021Q4), 3.68 (2022), 2.33 (2023), 1.22 (Jan-May 2024). [opened] same.
  - Stronger in small stocks (interaction t=4.75); after dropping stocks below $5 and below the 20th NYSE size percentile, cumulative return before costs "over 300%". No separate large-cap table in the part read. Costs: above 300% at 5 bp, above 100% at 10 bp, unprofitable at 20 bp. [opened] same. (Only first 100,000 of 281,364 characters read.)
  - Earlier versions: v4 reported Sharpe 3.8 for GPT-4 long-short; v5 text gives 3.28. [search] https://arxiv.org/pdf/2304.07619v5.pdf
- Glasserman and Lin (arXiv 2309.17322): look-ahead bias and a "distraction effect" from the model knowing the company. Anonymizing headlines improved in-sample performance, more for large firms; out-of-sample no look-ahead bias but distraction may remain. [opened] https://arxiv.org/abs/2309.17322
- He, Lv, Manela, Wu, "Chronologically Consistent LLMs" (arXiv 2502.21206; Feb 2025, revised Jul 2025): ChronoBERT/ChronoGPT trained only on text before each date; next-day return Sharpe near a much larger Llama model; authors say look-ahead bias is "modest" and varies by model and application. [opened] https://arxiv.org/abs/2502.21206
- Sarkar and Vafa, "Lookahead Bias in Pretrained Language Models" (first version 11 Mar 2024, NBER conference PDF 28 Jun 2024): direct one-sided tests; evidence of look-ahead bias in two applications including firm-risk prediction. [search] https://conference.nber.org/conf_papers/f205530/f205530.pdf (exact title on SSRN: unconfirmed)
- Further look-ahead work 2026: "Evaluating LLMs in Finance Requires Explicit Bias Consideration" https://www.alphaxiv.org/abs/2602.14233.md and "DatedGPT" https://www.alphaxiv.org/abs/2603.11838 (titles only, not read). [snippet only]
- Kirtac and Germano, "Sentiment trading with LLMs" (Finance Research Letters 2024): 965,375 articles 2010-2023; accuracy OPT 74.4%, BERT 72.5%, FinBERT 72.2%, Loughran-McDonald 50.1%; long-short Sharpe OPT 3.05, BERT 2.11, FinBERT 2.07. [search] https://arxiv.org/abs/2412.19245v1
- Chen, Kelly, Xiu, "Expected Returns and Large Language Models": uses contextual embeddings from LLMs (including BERT, Llama) of news to predict returns, compared with word-based models; negation handling noted. Sharpe numbers: [unconfirmed]. [search] https://www.arxiv.org/pdf/2409.11540 was a different paper (Chen, Green, Gulen, Zhou, ChatGPT stock-return forecasts: LLM forecasts over-extrapolate recent returns). [opened] https://arxiv.org/abs/2409.11540
- Chinese news: Zhang et al. 2023 (arXiv 2306.14222): 394,426 Chinese news summaries; Erlangshen-110M beat GPT-3.5 on all reported metrics. [search] https://arxiv.org/pdf/2306.14222
- Tan, Wu, Zhang, "LLMs and Return Prediction in China": seven models; tones from Chinese news predict returns, stronger with information frictions and retail holdings; signals take two days to be incorporated. [search] https://abfer.org/media/abfer-events-2024/cmd/Large-Language-Models-and-Return-Prediction-in-China_Lin-Tan.pdf
- Hong Kong-specific news LLM study: [unconfirmed] (Tan et al. mention prior work on Chinese news for HK; not identified).
- Boudoukh et al. event extraction into 14 categories and 56 subcategories (older, rule-based extraction platform). [search] https://www.nber.org/digest/jun13/which-news-moves-stock-prices

## 4. Event-study practice and free sources

**RavenPack fields** (from academic descriptions, not RavenPack docs; official docs not retrieved) [search]
- Relevance (REL) 0-100; papers use REL of 75 or more (some use 90+). https://wrds-www.wharton.upenn.edu/documents/1395/RavenPack.pdf
- Event Novelty Score (ENS) 0-100 within a 24-hour window; 100 means no earlier coverage; some studies keep ENS=100 only.
- Event Sentiment Score (ESS) 0-100, 50 neutral, derived from financial-expert surveys.
- Bigdata.com (RavenPack successor) weights daily sentiment by (relevance/100)^2 x (novelty/90)^2. https://docs.bigdata.com/blog/market-data/entity-sentiment-signals
- Share of stories kept by RavenPack-style filters: [unconfirmed]. Boudoukh et al. kept about half of 1.9 million Dow Jones stories as relevant events (different system).

**Abnormal return practice**
- Market-model CARs over windows: Egger and Zhu use estimation by market model, event window -1 to +10 days; Wengerek 3-day symmetric window (section 1 sources). Breach studies use 2-day, 3-day, 5-day, up to 10-day windows (section 1).

**GDELT** [search] fields: GKG 2.0 has V2Themes, V2Organizations, V2Tone, GCAM (about 2,238 content-analysis dimensions); GDELT 2.0 updates every 15 minutes; NumMentions, NumArticles, NumSources are Events-table fields. https://blog.gdeltproject.org/introducing-gkg-2-0-the-next-generation-of-the-gdelt-global-knowledge-graph/ ; codebook at data.gdeltproject.org/documentation (not opened).

**SEC EDGAR**
- Fair access: current maximum 10 requests per second; declare a User-Agent with company name and contact email. [opened] https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
- 8-K items (from law-firm and tool pages): 1.05 Material Cybersecurity Incidents (due 4 business days after materiality determination; rule effective 18 Dec 2023); 2.02 Results of Operations and Financial Condition; 5.02 Departure of Directors or Certain Officers; Election of Directors; Appointment of Certain Officers; Compensatory Arrangements. 1.01 is Entry into a Material Definitive Agreement; 5.01 is Changes in Control (one PwC table appears mislabeled). [search] https://www.kovrr.com/glossary-cyber/form-8-k-item-1-05 and https://www.securitieslawyer101.com/2025/understanding-form-8-ks/. Other item numbers (1.02 termination of agreement, 2.01 acquisitions, 2.05 exit costs, 2.06 impairments, 3.01 delisting notice, 4.01 auditor change, 4.02 non-reliance on financials, 8.01 other events): not verified from a source in this session. The full list page (edgar.tools) returned HTTP 403.
- No ticker-relevance score; filings tagged by company CIK.

**Free news APIs**
- Alpha Vantage: free key commonly reported as 25 requests/day (older sources 500/day or 5 per minute); NEWS_SENTIMENT returns news with sentiment, optional tickers filter. ticker_relevance_score, time_from, limit=1000, history depth: [unconfirmed] (documentation page too long to read; first 100k chars lacked the section). [search] https://www.alphavantage.co/documentation/ and https://www.macroption.com/alpha-vantage-api-limits/
- Finnhub: free plan 60 calls/minute, US coverage, personal use; company-news 1-year history on free plan reported by one summary, not confirmed officially. [search] https://finnhub.io/pricing
- Marketaux: free $0, 100 requests/day, 3 articles per request; entity-level sentiment; history and advanced filters need paid plans (third parties). [search] https://marketaux.com/pricing
- Tiingo: news API free plan under "Internal Use Only": 50 hourly, 1,000 daily requests, news history N/A; Power adds 3 months of history. Conflicting QuantConnect forum posts say Tiingo news is paid there. [search] https://api.tiingo.com/products/news-api
- NewsAPI.org: Developer plan free, development only, 24-hour article delay, reportedly 100 requests/day and one-month search window, non-commercial. [search] https://newsapi.org/pricing
- Benzinga: a free "Basic" news API on AWS Marketplace with headline, teaser and link; call limits not stated; docs mention 429 throttling. [search] https://aws.amazon.com/marketplace/pp/prodview-xwgvhwowjmw3g and https://docs.benzinga.com/introduction
- StockTwits: [unconfirmed] (search returned nothing).
- Reddit Data API: commonly reported 100 queries/minute per OAuth client, 10 without OAuth, free tier non-commercial; one source says new access needs manual approval (2-4 weeks); not checked on Reddit's own pages. [search, third-party blogs] https://www.techloy.com/reddit-api-pricing-in-2026-complete-guide-for-developers-and-businesses/

**Hong Kong and China sources**
- HKEX Terms of Use, section on copyright and permitted use [opened]: bars "text or data mining or web scraping"; lists "robot", "bot", "spider", "scraper"; bars "programmatic, scripted or other mechanical means to access this Website"; also bars automated analysis to "develop, train, fine-tune or validate AI systems or models". https://www.hkex.com.hk/Global/Exchange/Terms-of-Use?sc_lang=en. Whether HKEXnews has an official API or RSS: [unconfirmed]. A Hyperlink Policy page at https://www2.hkexnews.hk/Global/Exchange/Hyperlink-Policy?sc_lang=en reportedly repeats the scraping ban [search].
- RTHK English RSS: Local https://rthk.hk/rthk/news/rss/e_expressnews_elocal.xml ; Finance https://rthk.hk/rthk/news/rss/e_expressnews_efinance.xml (RSS page: https://news.rthk.hk/rthk/en/rss.htm). Terms and ticker tagging: [unconfirmed]; no ticker tags expected from headline RSS.
- AAStocks: no official RSS URL found; only a FeedSpot-generated feed listing. [search] https://rss.feedspot.com/hong_kong_stock_rss_feeds/. ETNet, HKEJ, Xinhua, Caixin feeds: [unconfirmed] (not searched successfully).
- China policy sites: State Council reportedly has no own RSS (aggregator claim); PBoC, CSRC, MOFCOM, CAC feeds: [unconfirmed]. National Bureau of Statistics RSS exists: http://www.stats.gov.cn/english/PressRelease/rss.xml [snippet only]. https://feeder.co/discover/dd6dd9956f/gov-cn

## 5. Alert design evidence

- Eventus/Datos Insights surveillance survey: about 70% of 20 banks and broker-dealers had false-positive rates above 25%; Eventus warns that over-tuning creates blind spots. [search, trade-surveillance context, not retail] https://www.eventus.com/cat-article/product-corner-the-danger-of-reducing-false-positives/ and https://thefullfx.com/survey-sees-compliance-alert-fatigue/
- SOC security context: average 3,832 alerts a day with 62% ignored (vendor-cited). [search] https://www.techtarget.com/searchsecurity/tip/Why-security-alert-fatigue-matters-and-how-to-address-it
- TradingView: news alerts fire when a story matches a custom News Flow filter; price and indicator alerts separate. [search] https://www.tradingview.com/blog/en/real-time-news-alerts-54444
- Koyfin: alerts for price targets, technical signals, valuation levels; delivery desktop, mobile push, email. [search] https://www.koyfin.com/features/alerts/ and https://www.koyfin.com/help/release-notes/v3-66-desktop-alerts
- Benzinga Pro: squawk audio (6am-6pm ET), newsfeed alerts with 25+ category alerts, filters by source/category/watchlist; advanced filtering on higher plans. [search] https://help.benzinga.com/en/articles/2106004-what-is-squawk-and-how-do-i-use-it
- LevelFields: claims 24 (or 25) event types (CEO change, layoffs, activist, buyback, FDA); shows 5-year win rate and average 1-, 10-, 30-day returns per event type. Vendor claims, unverified. [search] https://www.levelfields.ai/faq
- Seeking Alpha, moomoo/Futu, Bloomberg alert trigger lists: [unconfirmed].
- Boudoukh et al.: identified-news-day volatility over twice no-news days (section 1), the basis for separating news days from no-news days.
- Tetlock (NBER, 2010): for small and illiquid stocks, volume-induced momentum occurs only on news days and volume-induced reversal on other days. [search] https://projects.nber.org/confer/2009/MMf09/Tetlock.pdf
- z-score abnormal return detection and market/sector decomposition as alert triggers; studies showing news plus abnormal volume beats news alone: [unconfirmed] (no direct study found).

## 6. Portfolio owner evidence

- Barber and Odean 2000 (JF 55:773-806): 60,000+ households, 1991-1996; average gross 17.7% vs market 17.1%, net 15.3%; most active 20% earned 10.0% net. [search] https://econpapers.repec.org/RePEc:bla:jfinan:v:55:y:2000:i:2:p:773-806 and https://faculty.haas.berkeley.edu/odean/papers/returns/Returns.html
- Odean disposition effect: investors about 1.5 times more likely to sell a given winner than a loser (as described on that page). [search] https://faculty.haas.berkeley.edu/odean/papers/returns/Returns.html (the 1998 paper itself not opened)
- Barber and Odean 2008 (attention-driven buying): section 2.
- Tetlock 2011: individual investors trade more on stale news. section 2.
- Moreira and Muir 2017 (JF): volatility-managed portfolios; market alpha 4.9%, appraisal ratio 0.33, Sharpe up about 25%; scaled by inverse of prior-month realized variance. [search] https://law-journals-books.vlex.com/vid/volatilitymanaged-portfolios-855591267
- Cederburg, O'Doherty, Wang, Yan (JFE 138:95-117, 2020): 103 strategies; in-sample alphas positive, but not implementable in real time; out-of-sample versions generally earn lower certainty-equivalent returns and Sharpe than unmanaged; exceptions momentum, profitability, BAB. [search] https://econpapers.repec.org/RePEc:eee:jfinec:v:138:y:2020:i:1:p:95-117
- DeMiguel, Martin-Utrera, Uppal (JF 2024): multifactor conditional portfolio net-of-cost out-of-sample Sharpe 13% higher than unconditional; single-factor gains weaker. [search] https://lbsresearch.london.edu/id/eprint/3716/1/The%20Journal%20of%20Finance%20-%202024%20-%20DeMIGUEL%20-%20A%20Multifactor%20Perspective%20on%20Volatility%E2%80%90Managed%20Portfolios.pdf
- Studies on trimming or reducing exposure after news (other than volatility management): [unconfirmed].

## Gaps summary (not confirmed)
Savor 2012 magnitudes; Tetlock 2008 and 2011 magnitudes; Chen-Kelly-Xiu Sharpe numbers; Lopez-Lira large-cap results (not separately reported in the part read; 181k characters unread); RavenPack official docs and share of stories kept; Alpha Vantage NEWS_SENTIMENT details; StockTwits; HKEXnews API/RSS; ETNet/HKEJ/Xinhua/Caixin/PBoC/CSRC/MOFCOM/CAC feeds; moomoo, Seeking Alpha, Bloomberg alert triggers; studies of news plus abnormal volume; 8-K item list beyond 1.05, 2.02, 5.02.
