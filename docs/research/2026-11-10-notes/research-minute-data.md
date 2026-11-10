# Research: minute-bar data for quant projects (facts only)

Source quality: from web-search summaries; I did not open full papers. Items marked [UNCONFIRMED] were not checked against the primary text.

## 1. Documented uses

### 1a. Intraday momentum
- Gao, Han, Li, Zhou, "Market intraday momentum", J. Financial Economics 129(2), 394-414 (2018). https://econpapers.repec.org/RePEc:eee:jfinec:v:129:y:2018:i:2:p:394-414
  - Data: high-frequency S&P 500 ETF data, 1993-2013 (about 20 years) per JFE abstract. Early working version used 1999-2012. Half-hour bars (derived from higher-frequency data).
  - Claim: first half-hour return (from previous close) predicts last half-hour return. Stronger on volatile, high-volume, recession and macro-news days. Also in 10 other actively traded ETFs.
  - Effect size (varies by working-paper version, [UNCONFIRMED] for the published one): predictive R2 1.6% (2.6% adding the 12th half-hour); out-of-sample R2 1.2-1.4%; timing strategy about 6.3-6.7% per year.
  - Hong Kong: not in the original paper. A replication summary says significant predictability in 12 of 16 markets (global study; whether HK is among them is unknown). Chinese commodity futures also replicate. Source of these claims: search summary, [UNCONFIRMED]. Alpha Architect note says its own backtests did not confirm a related intraday result: https://alphaarchitect.com/2014/08/attention-prop-traders-the-first-half-hour-of-trading-predicts-the-last-half-hour/
- HK index futures: Xin, Lam, Yu (2019), Studies in Economics and Finance, filter trading on high-frequency Hang Seng index futures; profit depends on realized volatility. https://ideas.repec.org/a/eme/sefpps/sef-09-2018-0294.html (paywalled; sample and size not seen).
- HK intraday reversals (not momentum): Fung, Mok, Lam (2000), J. Banking & Finance: "intraday price reversals following large price changes at the opening" of S&P 500 futures and HSI futures; exploitable "after transaction costs, even though these may not be very significant". https://scholars.hkbu.edu.hk/en/publications/intraday-price-reversals-for-index-futures-in-the-us-and-hong-kon/ . Fung, Lam, Lam (2010) J. Empirical Finance: reversals in Asian index futures after extreme US moves. https://scholars.hkbu.edu.hk/en/publications/do-the-prices-of-stock-index-futures-in-asia-overreact-to-us-mark/ (both: sample years not seen).

### 1b. Overnight vs intraday returns
- Lou, Polk, Skouras, "A tug of war: overnight versus intraday expected returns", JFE 134, 192-213 (2019). https://researchonline.lse.ac.uk/id/eprint/119010
  - Granularity: needs only the open and close price per day (daily open/close), not minute bars.
  - Claim (abstract): "profits are either earned entirely overnight (for reversal and a variety of momentum strategies) or entirely intraday". US stocks.
  - Effect size (working-paper summary via Alpha Architect, secondary): momentum overnight 3-factor alpha 0.95%, intraday 0.11% insignificant. https://alphaarchitect.com/2015/02/overnight-momentum-vs-intraday-momentum/
  - HK: not covered by the search results.

### 1c. News reaction speed
- Busse and Green (2002), "Market efficiency in real time", JFE. Via Alpha Architect summary: prices respond within seconds of the first mention on CNBC; positive reports fully priced within about a minute; negative news shows some drift. Data are intraday trades/quotes, finer than 1-minute. https://alphaarchitect.com/2011/10/real-time-market-efficiency/ (secondary).
- Macro announcements in futures: "most of the price adjustment happens in the first minute, volatility stays elevated about fifteen minutes" (study-aid flashcard site, weak source, [UNCONFIRMED]). https://www.brainscape.com/flashcards/477020/packs/1003890
- Analyst recommendations: about 5 minutes (NYSE/AMEX) and about 15 minutes (Nasdaq) per same flashcard source [UNCONFIRMED].
- Polish regulatory announcements (2025): windows of 1, 5, 10, 30, 60, 120 minutes after the announcement. https://managementpapers.polsl.pl/wp-content/uploads/2025/06/223-Zagraba.pdf
- Turkey: reactions slower than developed markets; "developed-market reaction speeds are now measured at the millisecond level". https://academicrepository.khas.edu.tr/xmlui/handle/20.500.12469/3785
- No HK-specific minute-resolution news study was found.

### 1d. Realized volatility (RV, HAR-RV)
- Liu, Patton, Sheppard (2015), "Does anything beat 5-minute RV?", J. Econometrics 187(1), 293-311. https://econpapers.repec.org/RePEc:eee:econom:v:187:y:2015:i:1:p:293-311
  - Data: about 400 estimators, 31 assets, 5 asset classes, 11 years. Finding: "little evidence" that anything beats 5-minute RV in their benchmark comparison. 1-minute bars are therefore not shown to be necessary for RV; 5-minute is the standard.
  - HK: asset list not seen.
- Corsi HAR-RV (2009): details not confirmed in search; [UNCONFIRMED]. Typically fed by 5-minute RV.

### 1e. Opening range / closing auction
- Gao et al. above (first/last half hour). Fung et al. (2000) HSI opening reversals above.
- City U HK project on closing-auction order flow in HK (description only, no results): https://scholars.cityu.edu.hk/en/projects/order-flows-in-the-closing-auction-evidence-from-the-hong-kong-st/

### 1f. Execution / slippage
- No source found in this pass. Fung et al. say reversal profits after costs "may not be very significant".

## 2. Hong Kong intraday facts
- HKEX hours (consistent across broker pages): pre-opening 9:00-9:30, morning 9:30-12:00, lunch 12:00-13:00, afternoon 13:00-16:00, closing auction session from 16:00, ending at a random time between 16:08 and 16:10. HKEX page: https://www.hkex.com.hk/Services/Trading-hours-and-Severe-Weather-Arrangements/Trading-Hours ; CAS mechanism PDF: https://www.hkex.com.hk/-/media/HKEX-Market/Services/Trading/Securities/Overview/Trading-Mechanism/Trading-Mechanism-of-CAS-in-the-Securities-Market.pdf?la=en
- Continuous trading = 150 + 180 = 330 minutes (my arithmetic).
- Half-day: morning auction 12:00 to random close 12:08-12:10 (per search summary).
- Conflict: one usmart page labels 12:00-13:00 "Extended Morning Session" [UNCONFIRMED, likely error]. Reports that HKEX is exploring longer hours / ending lunch break: proposals only, nothing finalized found. The search was run with no 2026 announcement check; confirm on hkex.com.hk.
- Papers: Cheung, Ho, Pope, Draper (1994), Pacific-Basin Finance J.: HK intraday volatility "double U-shape", attributed to the lunch-break closure. https://scholars.hkbu.edu.hk/en/publications/intraday-stock-return-volatility-the-hong-kong-evidence/ . Cheung and Ahn (1999): U-shaped spread, reverse-U depth, no market makers. https://scholars.hkbu.edu.hk/en/publications/the-intraday-patterns-of-the-spread-and-depth-in-a-market-without/ . These predate the 2008 / 2016 hour changes and the 2008 CAS start [UNCONFIRMED for the exact dates; the 1994 paper mentions a two-hour lunch break]. CAS intro article: https://www.financemagnates.com/institutional-forex/exchanges/hkex-introduces-closing-auction-session-securities-market/

## 3. Storage (my arithmetic, not sourced)
- Bars per year: US 390 x ~252 days = ~98,300. HK 330 x ~247 days = ~81,500 (HK holidays count is approximate).
- Raw: timestamp 8 B + open/high/low/close 4 x 8 B + volume 8 B = 48 B/bar -> US about 4.7 MB/symbol-year, HK about 3.9 MB. With float32 prices + int32 volume + int64 timestamp: ~28 B/bar -> US about 2.8 MB, HK about 2.3 MB.
- Parquet compressed size: no direct source found. Estimate (unmeasured, [UNCONFIRMED]): well below raw; measuring one symbol-year with pyarrow/ZSTD is the way to confirm. Search found MarketParquet showing 741 rows for AAPL on one day (includes extended hours): https://marketparquet.com/faq . A Java OHLC benchmark listing Parquet+ZSTD 46,089 B had no stated row count (https://github.com/dfa1/datastore), and Uber saw ~7% saving from ZSTD vs GZIP (https://www.uber.com/en-US/blog/cost-efficiency-big-data/).
- Example scale (raw, my arithmetic): 500 symbols x 4.7 MB = about 2.4 GB per year uncompressed.

## 4. Yahoo 1-minute data quality
- Window: sources disagree, 7 days per request / 30 days total for 1m; a vendor page (commercial interest) says 1m = last 30 days. https://massive.com/compare/massive-vs-yfinance ; https://marketparquet.com/guides/yfinance-limitations-backtesting . Yahoo publishes no official limits.
- Gaps: no rows for weekends/holidays/halts (expected). "Yahoo Finance may have incomplete or inaccurate historical data for certain stocks, especially for less frequently traded assets" (https://docs.coupler.io/sources/category/finance-and-accounting/yahoo-finance-price/common-issues). yfinance `history(repair=...)` fixes 100x, missing, bad dividend adjustments; default off.
- Gap rate: no source quantifies how often 1m bars are missing. [UNCONFIRMED]. Tool for checking intraday gaps: https://concretumgroup.com/how-to-detect-and-fix-problems-in-intraday-market-data/
- HK-specific Yahoo minute quality: not found.
