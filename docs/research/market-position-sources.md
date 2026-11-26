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
