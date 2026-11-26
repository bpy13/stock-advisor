# Market-position data: what we can get (Task R2, 2026-11-26)

Brian asked about three kinds of data: order book depth, open interest, crowded positioning.
"Sample fetched" means a real read-only fetch on 2026-11-26 with no sign-up and no new key.
"Unverified" means stated from general knowledge, not checked against the source this run.

| Data | Source | Cost | History | Update | Sample fetched | Terms |
|---|---|---|---|---|---|---|
| Order book depth, HK | Futu OpenAPI `get_order_book` (needs a live subscription per stock) | Free with the account; the number of subscriptions is capped by quota; whether 10-level HK depth needs a paid quote right is unverified | None: live snapshots only, so we must record them ourselves | Real time | **No.** OpenD refused connections at 127.0.0.1:11111 (not running now) | Futu OpenAPI user terms; unverified |
| Order book depth, US | Alpaca free feed has top of book only; full depth is paid | Full depth: paid (not checked) | None | Real time | No | Not checked |
| Open interest, HK stock options | HKEX "Stock Options Daily Market Report" `https://www.hkex.com.hk/eng/stat/dmstat/dayrpt/dqe<yymmdd>.zip` | Free | Daily files; 24 Nov and 25 Nov both answered 200; how far back is unverified | Daily after close | **Yes.** 5.3 MB CSV for 25 Nov; row for Tencent (TCH): volume 96,983, open interest 2,391,744 (calls 1,423,318, puts 968,426), implied volatility 47% | HKEX website terms of use; unverified, read before storing |
| Open interest, HK futures/options per contract | HKEX `.../dmstat/oi/DTOP_O_<yyyymmdd>.zip` (per-contract detail files) | Free | Daily files | Daily | Yes (zip answers 200; contents not opened) | As above |
| Open interest, US stock options | Yahoo Finance via `yfinance` option chain (`openInterest`, `volume` per strike) | Free; the project already uses yfinance | Current chains only: no history, so we must record daily | Delayed during the day | **Yes.** AAPL: expiries from 2026-11-27; strikes with `openInterest` 1, 6, 8 | Yahoo terms: personal use; unverified |
| Open interest, futures (market-wide) | CFTC Commitments of Traders, `publicreporting.cftc.gov` (Socrata JSON) | Free, no key | Weekly reports back to 1986 (legacy) | Weekly, Tuesday data out Friday | **Yes.** Report week 46 of 2026: S&P 500 dividend index open interest 37,828; non-commercial long 12,226 vs short 13,162 | US government data; open use |
| Crowded: HK short positions | SFC weekly short positions | Free | Already stored (`short_selling`, from 1 Oct 2026; full history at next 02:00 backfill) | Weekly | Already stored | Already cleared (Task 6.3) |
| Crowded: US short interest | FINRA bi-monthly short interest file `cdn.finra.org/equity/otcmarket/biweekly/shrt<yyyymmdd>.csv` | Free | Years | Twice a month | File answers 200, not read | FINRA terms forbid scripted access (known-issues); not usable |
| Crowded: insider trades | SEC Form 4 and HK disclosure | Free | Already stored (Task 6.2) | Daily | Already stored | Already cleared |
| Crowded: fund holdings | SEC 13F filings (EDGAR) | Free | Years | Quarterly, 45 days late | Not fetched (EDGAR already used for filings, Task 6.1) | SEC open data; unverified |
| Crowded: speculator positioning | CFTC Commitments of Traders (above) | Free | Weekly since 1986 | Weekly | Yes (above) | Open |

## Recommendation

1. **HKEX stock-option open interest, with put/call ratio.** It is daily, free, covers the big
   Hong Kong names (Tencent, BABA, AIA, Anta), and carries implied volatility. Strategy use:
   a put/call open-interest ratio and a jump in open interest are a crowding and a fear signal
   per stock. Cost to build: one daily download job, 5 MB a day. Hong Kong has no history file
   we found, so the signal starts on the day we begin recording.
2. **CFTC Commitments of Traders for index futures.** It gives the whole-market crowding
   (speculators long or short the S&P 500, Nasdaq) with 30+ years of weekly history, so it can
   be backtested at once. It adds a market-wide risk filter, not a per-stock signal.

Order book depth is last: it has no history, needs OpenD running all day, and a quota-limited
subscription per stock. Recording it would take months before any backtest. US option open
interest from Yahoo is a cheap later add on the same daily job.

Terms for HKEX and Yahoo are unverified; a build task would read them first.

## Futu order book depth (Task R3, 2026-11-26)

Sources, all read on 2026-11-26 (Futu API Doc v10.12):
[Authorities and Quota](https://openapi.futunn.com/futu-api-doc/en/intro/authority.html),
[Get Real-time Order Book](https://openapi.futunn.com/futu-api-doc/en/quote/get-order-book.html),
[Q&A: quote, Q11 levels per market](https://openapi.futunn.com/futu-api-doc/en/qa/quote.html).
"Reading" marks my interpretation of a table; the docs give no literal "maximum" line.

**Levels per quote right** (Q&A Q11; "/" means none)

| Market | LV1 | LV2 | LV3 | SF |
|---|---|---|---|---|
| HK stocks | / | 10 | / | full order details (up to 1000 orders) |
| US stocks and ETFs | 1 | 60 | 60 Nasdaq + 60 Arca | / |

**What an account gets without paying**
- **HK:** a Global user (decided by the login IP of OpenD) gets LV1 free. LV1 has no order book levels
  (reading of the "/" cell). Ten levels need the paid "HK stocks LV2 advanced market" card. Mainland China
  verified users get LV2 free. The full order details need the paid "HK Stocks Advanced Full Market Quotes" (SF).
- **US:** LV3 is free during a promotion period. Depth of book (60 levels each from Nasdaq TotalView and NYSE
  ArcaBook) was made free "starting from April 16" (no year given). NYSE ArcaBook needs a non-professional
  user evaluation. Futu can end the promotion at any time.
- **Delay:** neither page states a delay in seconds for any level.
- **Price:** the docs pages give no price. The card prices sit on the qtcard.futunn.com pages, not read here.
  So the HK LV2 price is **not checked**.

**Subscription quota** (stocks held in subscription at once; one stock with one data type uses 1)

| Account | Subscriptions | Historical candlestick stocks per 7 days |
|---|---|---|
| Total assets under HK$10,000 | 100 | 100 |
| HK$10,000 or more | 300 | 300 |
| Over HK$500,000, or over 200 filled orders a month, or over HK$2 million traded a month | 1,000 | 1,000 |
| Over HK$5 million, or over 2,000 orders, or over HK$20 million traded | 2,000 | 2,000 |

- Recording the order book of one stock uses 1 subscription. The 300-tier fits the 89 HK watchlist stocks.
- `get_order_book(code, num=10)` needs `subscribe([code], [SubType.ORDER_BOOK])` first. A subscription can be
  cancelled only after 1 minute. The first read waits up to 3 seconds for a push, then returns empty.
- The order book has no history. Recording it means a daily job that holds the subscriptions open.

**This PC, read-only**
- OpenD is installed: `C:\FutuOpenD\Futu_OpenD_10.12.7208_Windows\` (`FutuOpenD.exe`, and a GUI build
  `Futu_OpenD-GUI_10.12.7208_Windows.exe`). Its settings sit in `%APPDATA%\Futu_OpenD`.
- The repo already has Futu code: `stock_advisor/price_sources/futu.py` (daily and hourly bars through
  `OpenQuoteContext` at 127.0.0.1:11111; no credential in the repo), `scripts/record_minutes.py`,
  `tests/test_price_source_futu.py`, `tests/test_record_minutes.py`, and notes in `docs/known-issues.md`.
  No order book code and no `.env` Futu setting exist.
- OpenD was **not running** at 17:58 on 2026-11-26: no Futu process, and a connection to 127.0.0.1:11111
  was refused. I did not start it or log in.
- **Sample:** none. So how many HK levels Brian's account returns is **not measured**. It depends on whether
  he holds the HK LV2 card.

**What it means for option (d) (record the order book from now on)**
- Without the HK LV2 card, HK depth is probably empty or one level, so (d) would have little to record
  for Hong Kong (reading, not measured).
- US depth is free for now, but Futu serves it only through OpenD, and OpenD must stay logged in all day.
- To settle it: Brian starts OpenD and logs in, then a later run fetches 00700 and AAPL with `get_order_book`
  and records the level counts.
