# Price data sources: facts (checked 2026-11-10)

Method: WebFetch of the providers' own pages plus web search. WebFetch summarises pages with a small model, so quotes are the summariser's text unless marked as direct. Anything not seen on a live provider page is marked "unconfirmed". No verdicts.

## Table

| Source | HK stocks | US / indices / futures | Intraday granularity | Intraday depth | Daily depth | Free tier | Cheapest paid with multi-year intraday | Adjusted | Personal use | Python |
|---|---|---|---|---|---|---|---|---|---|---|
| Alpaca | No (HK not mentioned) | US stocks/ETFs yes; indices, futures not listed | 1Min..59Min, 1H..23H, 1D (bars API) | Not stated on page; pricing page says "7+ years" | 7+ years | $0, IEX feed only, 200 calls/min | $99/mo Algo Trader Plus (all US exchanges, unlimited calls) | `adjustment` param: raw (default), split, dividend, spin-off, all | Not confirmed | alpaca-py (unconfirmed on page) |
| Massive (ex-Polygon) | No (US only) | US stocks, options, indices, futures (CME/CBOT/NYMEX/COMEX), forex, crypto; billed per asset class | 1m and up (aggregates) | History by plan: Basic 2y, Starter 5y, Developer 10y, Advanced 20+y | same plan limits | $0 Basic: EOD, 2y, 5 calls/min | $29 (5y, 15-min delayed), $79 (10y), $199 (20+y, real time) | Split-adjusted by default; `adjusted=false` for raw | Individual plans "personal, non-professional use"; Business $2,499/mo | Official Python SDK |
| Tiingo | HK not mentioned (global list 110,471 securities; 49,645 US and Chinese stocks) | US stocks; other not confirmed | IEX feed intraday (e.g. resampleFreq=5min) | Not stated | 30+ years | Starter $0: 50 req/hour, 1,000/day, 500 symbols/month, 1 GB | Power $30/mo (10,000 req/hour) - intraday depth unconfirmed | Not stated on page | "Internal Use Only", no sharing | `tiingo` package (unconfirmed on page) |
| EODHD | Intraday page does not mention HK; HK listed on EODHD ticker pages (`.HK` suffix, generic text) - HK intraday unconfirmed | US yes; indices/commodities in plans (unconfirmed detail) | 1m, 5m, 1h | US 1m from 2004; 5m and 1h from Oct 2020. Other exchanges: 5m/1h from Oct 2020; 1m "not guaranteed". Per request: 1m 120 days, 5m 600 days, 1h 7,200 days | 30+ years on paid | $0: 1 year EOD, 20 calls/day, no intraday | $29.99/mo "EOD + Intraday All-World Extended" ($24.99/mo annual) | Intraday NOT adjusted (raw OHLCV); EOD has adjusted_close | Separate personal pricing; terms not read | `eodhd` package / REST (unconfirmed) |
| Twelve Data | Yes: XHKG listed; plan shown as Pro/Venture ($229/mo on page) | US on Basic; indices/futures unconfirmed | 1min..4h, 8h, 1day.. | Not stated | Not stated | Basic $0: 8 credits/min, 800/day | Pro $229/mo (page also shows $99 in structured data; page flags mismatch) | `adjust`: all, splits, dividends, none; default splits | Add-ons priced personal vs commercial; terms unconfirmed | Official SDK (package name unconfirmed) |
| Alpha Vantage | Not stated for intraday; daily endpoint shows non-US suffixes | US yes; indices unconfirmed | 1,5,15,30,60min | 25+ years (`month` param since 2000-01) | 20+ years (unconfirmed) | 25 requests/day | $49.99/mo (75 req/min) for premium; intraday needs premium | `adjusted=true` default | Terms not read | Third-party libs; REST |
| Finnhub | International stocks yes (per Massive comparison; candles for HK unconfirmed) | US yes | Candle resolutions (unconfirmed) | Unconfirmed | Daily 10/25/40+ years by plan (Massive comparison, third party) | 60 calls/min; stock candles reported as paid-only (third-party, GitHub issue) | US $49.99 to $199.99/mo per Massive comparison (third party, unconfirmed) | Unconfirmed | "Every self-serve plan is personal use only" (Massive's comparison page) | `finnhub-python` (unconfirmed) |
| Databento | "Hong Kong Stock Exchange" listed in venue directory; schema/history unconfirmed | CME/CBOT/NYMEX/COMEX, ICE, US equities, OPRA | ohlcv-1s/1m/1h/1d schemas; page says OHLCV-1h on all plans | 16+ years for US datasets; HK unconfirmed | 16+ years | $125 free credit (6 months) | Usage-based $/GB (no subscription); Standard $199/mo | Raw (unconfirmed) | Not read | `databento` package |
| Interactive Brokers API | Yes (SEHK) with subscription | US, HK, indices, futures with subscriptions | Bars from 1 sec up; | Limits: bars of 30 s or less older than 6 months unavailable (third-party summary); 1h bar request duration limits | Long | Needs funded account; delayed data free where available | HKEX Top of Book L1 HKD 130/mo (third-party-indexed IBKR page; waiver for non-mainland accounts with HK trading permission: unconfirmed) | Via `whatToShow` (unconfirmed) | Account holder use | `ib_async`/`ibapi` |
| Futu OpenAPI / moomoo | Yes (HK, US, A-shares) | HK, US, A-share; indices incl. | 1m,3m,5m,15m,30m,60m, day.. | Minute-level (60 min and below): last 8 years. Daily: 20 years | 20 years | Free with Futu account + OpenD; quota by assets | Free for account holders; LV1 free for global users, LV2 purchased | `autype` QFQ default (also none/HFQ) | Account-holder API | `futu-api` |
| Tushare | HK daily needs permission; `hk_mins` unconfirmed | Mainly China | Unconfirmed | Unconfirmed | HK daily: unadjusted, 5,000 rows/request | Points/permission system | Unconfirmed (a Juejin tutorial says minute data needs "1000 yuan donation": third party) | HK daily unadjusted | Unconfirmed | `tushare` |
| AKShare | Yes, scraped from Eastmoney / Sina | HK only for this question | 1,5,15,30,60 min (`stock_hk_hist_min_em`) | Only the latest 5 trading days of 1-minute (not adjusted) | `stock_hk_hist` from 1970 default range; `stock_hk_daily` (Sina) | Free, open source | n/a | qfq/hfq options (1-min always unadjusted) | Scraper; terms of upstream sites | `akshare` |
| Stooq | Stooq lists HK packages on its db page; page text sparse | US, HK, indices, FX | Daily, hourly, 5-min (db page text) | Not stated | Not stated | Free downloads; "daily hits limit" reported (third party) | n/a | Unconfirmed | Terms page returned no text; unconfirmed | `pandas-datareader` / CSV |
| FirstRate Data | No individual HK stocks found; EWH ETF yes; "110 major international indices" | US stocks (16,333 incl. 7,000+ delisted), ETFs, futures (130 contracts), US + international indices, FX | 1m, 5m, 30m, 1h, 1d | Stocks/ETFs from 2000; futures 2008; intl indices 2007 | From 2000 | Free samples (unconfirmed) | One-off purchase; update $59.95/mo ($79 with fundamentals) after first free month; bundle price not on page | Stocks adjusted for splits and dividends; futures continuous roll-adjusted | "private use of the Subscriber only"; perpetual | Files (CSV) |
| Kibot | No HK found | US stocks, ETFs, futures, forex, indexes; 82,000 instruments | tick, 1-minute, daily (page lists no 5m/1h) | 1-minute from 1998; tick NBBO from 2009 | From 1962 | Unconfirmed | One-off: from $19; ES 1-min full $110; SPY/QQQ 1-min $125 | Unadjusted, split-adjusted, fully adjusted offered | Unconfirmed | Historical Data API / Kibot Agent |
| Longport (extra) | Yes | HK, US, A-shares | Minute+ candlesticks | HK minute from 2022-09-28; US minute from 2023-12-04 | HK daily from 2004-06-01; US from 2010-06-01 | Account tiers | Account holders | NoAdjust documented; others unconfirmed | Account holders | `longport` |
| TickDB (extra) | Yes | HK focus | 1m..1M | Plan history 1y Starter, 3y Pro, 5y All HK-Shares, 10y Enterprise | Unconfirmed | 7-day trial; no historical ranges | Starter $99/mo list ($79 annual): 1 year; Enterprise $899/mo list: 10 years | Unconfirmed | Unconfirmed | REST / WebSocket |
| AllTick (extra) | Yes | HK, US, forex, crypto | Unconfirmed | Free tier 1 year (search snippet); full HK market plan listed 399 USDT/month | Unconfirmed | Free tier | Search snippet only | Unconfirmed | Unconfirmed | REST |
| Barchart (extra) | HKEX OTC ticker page says intraday "approximately 10 years" (search snippet; not 0700.HK) | - | 1-minute | ~10 years (snippet) | - | - | - | - | - | - |

## Per-source notes

### Alpaca Market Data
- https://alpaca.markets/data (checked 2026-11-10): Free $0, Algo Trader Plus $99/mo. Free: IEX only, 200 calls/min, "15-minute delay via the API". Both: "7+ years" history. HK not mentioned.
- https://docs.alpaca.markets/reference/stockbars : `adjustment` default `raw`, options split/dividend/spin-off/all; `feed` default `sip`, also iex/otc/boats; timeframes 1Min-59Min, 1H-23H, 1D.
- https://docs.alpaca.markets/docs/historical-stock-data-1 : IEX covers "roughly 2.5% of market volume" and "is the only feed that can be used without a subscription".
- Intraday-specific history limit: unconfirmed.

### Massive (formerly Polygon.io)
- https://polygon.io/pricing redirects (301) to https://massive.com/pricing, so Polygon is renamed Massive.
- https://massive.com/stocks plan table: Basic $0 EOD 2y 5 calls/min; Starter $29 15-min delayed 5y; Developer $79 10y; Advanced $199 real-time 20+y; Business $2,499. "Individual plans are for personal, non-professional use." Official SDKs: Python, JS/TS, Go, Kotlin.
- https://massive.com/pricing fetched: Stocks Advanced $199/mo "20+ years of history". Page did not list Indices or Futures plan prices (the compare page says indices and futures (CME, CBOT, NYMEX, COMEX) exist, billed per asset class).
- https://massive.com/docs/rest/stocks/aggregates/custom-bars : "Set this to false to get results that are NOT adjusted for splits"; history table Basic 2y / Starter 5y / Developer 10y / Advanced all.
- https://massive.com/knowledge-base : SPX, DJI, RUT, VIX need a paid Indices tier.
- Non-US stocks: not listed (https://massive.com/compare/massive-vs-finnhub).

### Tiingo
- https://www.tiingo.com/about/pricing : Starter $0 (50 req/hour, 1,000/day, 500 symbols/month, 1 GB); Power $30/mo or $300/yr (10,000 req/hour, 100,000/day, 110,471 symbols, 40 GB). Price history "30+ years". License "Internal Use Only".
- https://www.tiingo.com/documentation/iex : endpoint `/iex/<ticker>/prices`, `resampleFreq=5min` example, `startDate=2019-01-02` in example only. IEX intraday depth: unconfirmed. HK: not mentioned.

### EODHD
- https://eodhd.com/pricing : Free (1 year, 20 calls/day, no intraday); Historian $19.99; Active trader $29.99 (EOD + Intraday All-World Extended); All-in-one $99.99. Paid: 100,000 calls/day, 1,000 req/min; intraday request costs 5 calls.
- https://eodhd.com/financial-apis/intraday-historical-data-api : 1m from 2004 for US, 5m/1h from Oct 2020; other exchanges 1m "not guaranteed and varies"; intraday "not adjusted". HK/HKEX not mentioned on this page.
- A search for HK intraday on EODHD returned only generic `.HK` ticker pages. HK intraday support: unconfirmed.

### Twelve Data
- https://twelvedata.com/pricing : Basic $0 (8 credits/min, 800/day); Grow $79; Pro $229; Ultra $999. The page's own comparison table and structured data show different numbers ($29/$99/$329), so exact prices unconfirmed.
- https://twelvedata.com/exchanges : "Hong Kong Stock Exchange (XHKG)" shown with plan "Pro Venture" (summariser reading). US requires Basic.
- https://twelvedata.com/docs/market-data/time-series : intervals 1min to 1month; outputsize 1-5000; `adjust` all/splits/dividends/none, default splits. Intraday history depth: not stated.

### Alpha Vantage
- https://www.alphavantage.co/premium/ : 75 req/min $49.99/mo; 150 $99.99; 300 $149.99; 600 $199.99; 1200 $249.99. Free: "25 API requests per day" (https://www.alphavantage.co/support/).
- https://www.alphavantage.co/documentation/ : TIME_SERIES_INTRADAY intervals 1/5/15/30/60min; `month` parameter reaches back to January 2000; `adjusted` default true. HK intraday: unconfirmed (examples are US).

### Finnhub
- Own pages (finnhub.io/pricing, docs) returned no usable text. All below is third party and unconfirmed: free 60 calls/min; stock candles paid-only (GitHub issue https://github.com/finnhubio/Finnhub-API/issues/546); Massive's comparison https://massive.com/compare/massive-vs-finnhub says international stocks covered, "LSE is 15-min delayed, most others end-of-day", plans $49.99/$129.99 per month quarterly, $199.99 annual, "Every Finnhub self-serve plan is personal use only".

### Databento
- https://databento.com/pricing : usage-based; Standard $199/mo (L1 1 year, L0 16+ years); Plus $1,750/mo; Unlimited $4,500/mo ("16+ years of history across all schemas"). $125 free credit, expires 6 months. "OHLCV-1h bars are included as L0 data on every plan, with 16+ years of history." Pricing page lists CME/CBOT/NYMEX/COMEX, CFE, Eurex, ICE, OPRA, Databento US Equities; no HKEX.
- https://databento.com/venues lists "Hong Kong Stock Exchange" under Asia-Pacific. Dataset schemas, start date, price for HK: unconfirmed.

### Interactive Brokers
- TWS API historical limits (https://www.interactivebrokers.com/docs/tws-api/doc/market-data-historical/historical-data-limitations/introduction returned 403 to the fetcher; below via web-search snippets): limits for bars of 1 minute and larger "have been lifted"; same request within 15 s is a pacing violation for 30 s bars and under; bars 30 s or less older than 6 months unavailable; no historical data for expired options. Max lookback for hourly bars for HK: unconfirmed.
- HKEX market data: snippet of https://www.interactivebrokers.com/en/pricing/research-news-marketdata.php : "Hong Kong Securities Exchange (Stocks, Warrants & Bonds) Top of Book (L1) | HKD 130.00 | HKD 130.00"; Level 2 HKD 225. Footnote: Level 1 fee waived "for clients who have accounts registered outside of Mainland China, and have activated Hong Kong Securities/Derivatives trading permissions" (could not tie the waiver to the HKD 130 line). The page itself returned 403 to the fetcher, so current price unconfirmed.

### Futu OpenAPI / moomoo
- https://openapi.futunn.com/futu-api-doc/en/quote/request-history-kline.html (fetched live): "Minute-level candlesticks (60 minutes and below)" last 8 years; daily 20 years; "A maximum of 60 requests per 30 seconds"; `max_count` default 1000; `autype` default QFQ; quota per account assets and trading, released after 7 days.
- https://openapi.futunn.com/futu-api-doc/en/intro/authority.html : historical candlestick quota by account tier: under HKD 10,000 assets 100; HKD 10,000+ 300; assets over HKD 500,000 or 200 monthly orders or HKD 2m monthly volume 1,000; higher tier 2,000. Repeat requests for the same stock are not counted again. Quotes: global users LV1 free, LV2 HK needs purchased package; mainland-verified LV2 free (by OpenD login IP).
- Quota counts distinct stocks, so a list of ~100 symbols fits the lowest tier (inference from the text).

### Tushare / AKShare
- Tushare https://tushare.pro/document/2?doc_id=192 (hk_daily): unadjusted daily, "up to 5,000 rows" per request, needs separate permission "港股历史日线". `hk_mins` doc not found: unconfirmed.
- AKShare https://akshare.akfamily.xyz/data/stock/stock_quote.html : `stock_hk_hist_min_em` returns the last 5 trading days of minute data; 1-minute is unadjusted; periods 1/5/15/30/60; source Eastmoney, "港股数据有延时". `stock_hk_hist` daily/weekly/monthly with qfq/hfq. `stock_hk_daily` (Sina) may not cover full listing history.

### Stooq
- https://stooq.com/db/h/ fetch text mentioned HK and US packages, 5-minute, hourly and daily; no detail. Terms page (https://stooq.com/terms.html) returned no text: personal-use terms unconfirmed. Third-party mention of "Exceeded the daily hits limit" (Wealth-Lab wiki). 0700.HK availability: unconfirmed (page returned empty).

### FirstRate Data
- https://firstratedata.com/ : stocks 16,333 tickers, 1m/5m/30m/1h/1d from 2000; futures 130 contracts from 2008; "110 major international indices" 1-minute from 2007; HK not named. Stocks and volumes adjusted for splits and dividends. Page headline figures conflict (15 vs 25 years).
- https://firstratedata.com/b/22/stock-complete : "9333 most liquid US stocks"; "Updates are $59.95 per month thereafter ($79 if fundamentals are included)". One-off bundle price not on the fetched text.
- License (http://firstratedata.com/about/license): "the Data is for the private use of the Subscriber only"; perpetual; derived charts/reports/models may be distributed.
- EWH (iShares MSCI Hong Kong ETF) is listed (https://firstratedata.com/i/etf/EWH); individual HK stocks not found.

### Kibot
- https://kibot.com/ : 1-minute from 1998, tick+NBBO from 2009, daily from 1962; unadjusted, split-adjusted and fully adjusted; US stocks, ETFs, futures, forex, indexes; "ES 1-minute full history at $110, SPY and QQQ 1-minute at $125"; custom orders from $19. HK: not mentioned.

### Other sources with HK intraday
- Longport https://open.longportapp.com/docs/quote/pull/history-candlestick : "Hong Kong stocks: 2022-09-28 to present" for minute candlesticks; HK daily from 2004-06-01; 60 requests/30 s; monthly quota by account tier.
- TickDB https://tickdb.ai/en/markets/hk-stocks : plans and history as in table (list prices). Quoted: "Historical access depends on entitlements and availability."
- AllTick https://alltick.io/stock-api (search snippets only, not opened): free 1 year; 399 USDT/month full HK plan. Unconfirmed.
- LSEG SEHK pricing dataset, tick history from 1996, enterprise (search snippet, no price).
- HKEX Data Marketplace (https://www.hkex.com.hk/Services/Market-Data-Services/Historical-Data-Services/HKEX-Data-Marketplace) sells exchange historical data; contents and prices not opened: unconfirmed.
- Barchart: HKXCF page snippet says 1-minute "approximately 10 years" (not checked for 0700.HK).

## Gaps (unconfirmed)
Alpaca intraday cap; Tiingo IEX start date; EODHD HK intraday depth; Twelve Data depth and current price; Finnhub own page; Databento HK schema and price; IBKR HK hourly lookback and current HKD fee; Tushare hk_mins; Stooq terms and HK intraday; FirstRate bundle price; Kibot HK.
