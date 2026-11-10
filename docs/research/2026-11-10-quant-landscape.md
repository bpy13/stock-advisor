# Quant landscape: what the field does and what fits this project (2026-11-10)

Research for the replanning. Brian's goal, in his words: "establish portfolio analyzer, watch
news and send Telegram alert accordingly". Ten helper notes with links and quotes sit in
`2026-11-10-notes/`. Nothing here is a decision.

How to read the tags:
- **[page]**: a helper opened the source page and read it.
- **[summary]**: a helper saw it only in a search summary or a secondary source. Treat as unverified.
- **[measured]**: I ran it on this project's data today.
- **[my view]**: my inference from the facts.

## 1. What do the best use? Is it all regression?

**Short answer: mostly yes.** Most of the field predicts a number (the next return) from
features and ranks stocks by it. The winning models differ in shape, not in kind. [my view]

| Who | What they use | Result | Tag |
|---|---|---|---|
| Renaissance (Jim Simons) | Nick Patterson, a senior researcher: the most important tool was simple regression with one input | Medallion fund: about 66% a year before fees, 1988-2018 | [summary] |
| Renaissance | Early years: trend rules such as a 20-day average; later many small signals in one model, short holding periods, heavy cost modelling, a cap on fund size | Right on about 50.75% of trades (wording unconfirmed) | [summary] |
| Academic benchmark (Gu, Kelly, Xiu 2020) | Regression on about 900 inputs, monthly, all US stocks. Trees and neural nets beat linear models | Out-of-sample fit: plain linear regression -3.5%, boosted trees +0.34%, neural net +0.40% | [page] |
| Image model (Jiang, Kelly, Xiu) | A neural net reads price charts and predicts up or down (classification, not regression) | Works best weekly on small stocks; the authors say mostly market makers can trade it | [page] |
| Competitions (Optiver, Jane Street, Numerai) | Boosted trees plus neural nets, blended; time-ordered validation with gaps | No return figures | [summary] |

**Approaches that are not regression** [page for the papers, my grouping]:
- **Rules.** Trend following: buy what rose over the past year (58 futures markets).
- **Pairs and statistical arbitrage.** Two linked stocks drift apart, and the trade bets they
  close. About 11% a year in 1962-2002; weaker since.
- **Regime models.** A hidden Markov model labels the market as calm or stressed. Used for
  risk, not for picking stocks.
- **Optimization.** Given forecasts and risks, compute position sizes.
- **Language models.** Read text and output a label or score.

**Three facts that matter more than the model type:**
1. **The edge per bet is tiny.** A fit of 0.4% means the model explains almost nothing about
   one stock in one month. Funds profit by making thousands of independent bets. The standard
   formula: quality of result = skill per bet x square root of the number of independent bets.
   [page for the papers; the formula is from Grinold and Kahn]
2. **Published signals fade.** Returns fall 26% out of sample and 58% after publication
   (McLean and Pontiff [page]). Of 452 published signals, 65% fail a basic retest (Hou, Xue,
   Zhang [summary]). A new signal should clear a t-stat of 3, not 2 (Harvey, Liu, Zhu [page]).
3. **Trading on it costs money.** The households that traded most earned 11.4% a year against
   17.9% for the market (Barber and Odean [page]).

**What this means here [my view].** This project has about 50 stocks that move together. That
is few independent bets. A return forecast for one holding will stay weak, whatever the model.
The parts of the field that do work at this scale are risk measurement and news triage
(sections 3 and 5).

## 2. Project types by data

**By time scale:**

| Time scale | Typical projects | Evidence | Open to one person? |
|---|---|---|---|
| Tick, under a second | Market making, order-book prediction | Not researched | No: needs servers inside the exchange |
| Minute | First half-hour predicts the last half-hour (S&P 500 fund, about 6% a year); volatility from 5-minute bars; measuring news speed | [summary] | As measurement, yes. As trading, costs eat it |
| Hour to 5 days | Short-term reversal; news scoring by language models; "move with news drifts, move without news reverses" | Section 5 | Partly. HK costs are the barrier |
| Weeks to months | Momentum, nearness to the 52-week high, insider buying, mainland money flows, short selling | Table below | Yes: no speed needed |
| Quarters to years | Value, quality, company accounts | Classic factor papers | Yes for US. No free structured HK accounts found |

**By data type** (US = United States, HK = Hong Kong):

| Data | Finding | Free and allowed source | Tag |
|---|---|---|---|
| Insider trades, US | Trades by insiders who do not trade on a routine earn 0.82% a month; routine trades earn about 0. Buys carry the signal, sales do not | SEC insider data sets, quarterly, 2006-2026; Form 4 is due in 2 business days | [page] |
| Insider trades, HK | Directors profit; outsiders who copy them "earn minimal returns" (1993-1999). Notice is due in 3 business days | HKEX site only, and HKEX bans scripted access | [page] |
| Mainland money into HK (Stock Connect southbound) | A 2025 paper reports flows predict short-term HK returns; up to 25.8% a year on paper, costs not stated | HKEX daily files exist, but HKEX bans scripted access | [page] |
| Short selling | US: total short interest predicts market returns. HK: no study found | SFC weekly CSV per stock, 2012-2026 (no ban found); FINRA daily US files | [page] |
| Earnings surprise drift | Gone for large US stocks since about 2006; disputed | SEC filings | [summary] |
| HK profit warnings | Any drift is small enough that minor costs remove it | HKEX site only | [page] |
| News tone and language-model scores | Section 5 | NYT, Guardian, GDELT, SEC, RSS (already collected) | |
| Web attention (Google searches) | A rise in searches predicts higher prices for two weeks, then a reversal | Google Trends | [summary] |
| Social media mood | The famous Twitter result (87.6% accuracy) failed replication | | [summary] |
| Big-fund holdings (13F) | Filed 45 days after quarter end, so slow | SEC 13F data sets | [page] |
| Options prices | The price of crash protection predicts stock returns for months (US) | US option chains are paid; HKEX publishes ratios | [summary] |
| US close to HK open | US market shocks carry into HK returns | Yahoo | [summary] |
| Calendar | Higher HK returns before Chinese New Year | Yahoo | [summary] |

**A rule that bites [page].** HKEX's terms of use (section 5, updated 19 Aug 2025) forbid
"programmatic, scripted or other mechanical means" on its websites. That covers company
announcements, directors' dealings, shareholding and Stock Connect files. Brian's rule of
2026-10-27 skips sites whose terms forbid automated access. The only official free route for HK
company announcements is the HKEX "News Alert" email: up to 20 companies, sent every 30 minutes.

**Free HK and China feeds that worked on 2026-11-10 [page]:** RTHK finance (English and
Chinese), news.gov.hk, HKMA press releases and open API, the statistics department API, SFC
press releases and circulars, SCMP RSS, CNA. Xinhua's RSS is stale; PBoC blocks crawlers.

## 3. The maths toolbox

"Has" means the project computes it today.

| Group | Technique | Question it answers | Has? |
|---|---|---|---|
| Performance | Time-weighted and money-weighted return | How did the portfolio do, with and without the timing of my deposits? | No |
| | Sharpe ratio (return per unit of risk), Sortino, maximum drawdown | Was the return worth the swings? | No |
| | Alpha and beta against an index | How much is just the market? | No |
| Risk | Volatility (rolling, or weighted to recent days) | How much does it swing now? | Partly (20-day) |
| | Correlation, with shrinkage for small samples (Ledoit-Wolf) | Which holdings move together? | Yes (plain) |
| | Factor exposure: regression of each holding on market, sector, rates, oil, currency | What drives this holding? | No |
| | Risk contribution per holding; concentration | Which positions carry the risk? | Partly (25% cap) |
| | Value at Risk, expected shortfall, stress tests | How bad is a bad day? | No |
| Sizing | Kelly fraction, risk parity, Black-Litterman (blend a forecast with a neutral start) | How big should a position be? | No |
| Testing a signal | Rank IC: do higher scores go with higher later returns? | Does it predict? | No |
| | t-stat with Newey-West correction for overlapping windows | Is it luck? | No (plain t-stat) |
| | Walk-forward test with a gap between training and test | Does it hold on unseen data? | Partly (no gap) |
| | Multiple-testing hurdle (t above 3), deflated Sharpe | Did I just try many things? | No |
| | Event study: abnormal return around an event | What did this news do? | Partly (reactions) |
| Models | Ridge regression, nearest neighbours | | Yes |
| | Boosted trees, hidden Markov regimes, Kalman filter, cointegration | | No |
| | Forecast combination: simple averages often beat fitted weights | | No |
| Text | FinBERT tone, sentence embeddings | | Yes |
| | Language-model classification | | No |

Maintained Python libraries [page]: QuantStats (performance report), Riskfolio-Lib and skfolio
(risk, sizing, walk-forward with gaps), statsmodels (Newey-West), arch (volatility models),
exchange_calendars (HK trading calendar, lunch break, half days).

**What a standard portfolio analyzer shows** (Portfolio Visualizer [page]): Sharpe, Sortino,
beta, alpha, drawdowns, stress periods, monthly correlations, and return and risk per holding.

**Costs [page].** HK stamp duty is 0.1% on each side. With fees, a round trip costs about 0.22%
before the broker's commission and the price spread. The US has no stamp duty.

## 4. Sources

- **"The Man Who Solved the Market" (Zuckerman)** is the main account of Renaissance. No book
  or video called "Jim Simons's playbook" exists; the helper found only a social-media thread.
- **Documented lessons** [summary]: collect and clean data obsessively; use simple statistics
  on many small signals; combine all signals in one model; hold for short periods; model
  trading costs; cap the fund's size.
- **Not documented**: the actual signals. Claims about specific methods (hidden Markov models,
  kernel methods) trace only to staff backgrounds.
- **Other standard books**: Thorp, "A Man for All Markets" (bet sizing); Grinold and Kahn,
  "Active Portfolio Management" (skill x breadth); Lopez de Prado, "Advances in Financial
  Machine Learning" (honest backtests); Chan, "Quantitative Trading" (one-person scale);
  Narang, "Inside the Black Box"; Pedersen, "Efficiently Inefficient".

## 5. News: what the evidence says

**Speed.**
- Scheduled economic releases are priced within seconds. [summary]
- News explains about half of overnight stock-specific moves, and 12% of daytime ones
  (Boudoukh and others). Only about half of 1.9 million news stories were relevant events. [summary]

**What still predicts after the first minutes.**
- **Tone**: a pessimistic day lowers the next day's index return by 0.08%, and it reverses
  within a week (Tetlock 2007 [page]). Too small to trade.
- **News versus no news**: a big move with news tends to continue. A big move without news
  tends to reverse. Strongest in small stocks (Chan 2003; Savor 2012 [summary]).
- **Repeated news**: prices move less on stale stories, and the move reverses. [summary]

**Language models (2023-2026).**
- GPT-4 scores of headlines predicted next-day returns. The yearly Sharpe ratio fell from 6.5
  (late 2021) to 3.7, 2.3, then 1.2 (2024). It works in small stocks, and it stops paying at a
  cost of 0.2% a trade (Lopez-Lira and Tang, October 2025 version [page]). An HK round trip
  costs more than that.
- FinBERT, the tone model this project uses, scored a Sharpe of -0.33 in the same test. [page]
- Language models give the same label on repeat runs for simple classification. [page]
- "AI analyst" agents mostly fail to beat buy-and-hold in tests on unseen periods
  (StockBench, FINSABER, DeepFund [page]).

**Big events (rough sizes).**
- US tariff news 2018-19: -11.5% over 11 announcement days. April 2025: -12%, then recovered
  within a month. [summary]
- Cyber breaches: about -2% over two days, then fades. [summary]
- China policy: Alibaba -8.5% in a week after the December 2020 probe. The September 2024
  stimulus: Hang Seng +23% in six sessions, half given back in a month. [summary]

**How others build alerts.**
- The closest open-source project is `daily_stock_analysis` (69,000 stars). It covers HK,
  sends Telegram messages and asks a language model for a scored daily report. It publishes
  no accuracy figures. Its alert rules use price and volume only. [page]
- Commercial tools alert on price thresholds, filing types, analyst changes and earnings.
  None publishes how often its alerts are right. [page]
- No tool found starts from an unusual price move and then looks for the news. [page]

**Claude API prices [page, read 2026-11-10]**, per million tokens in and out: Haiku 5.5
$0.10 and $0.50; Sonnet 5.5 $2 and $10; Opus 5.5 $4 and $20. Batch jobs cost half.

## 6. Data quality: what the checks found

- **One stock drove the price-signal result [measured].** The earlier test showed +15% in 20
  days after a BUY. One thinly traded stock in the test set causes most of it: it has
  hundreds of days with no trades and dozens of daily moves over 40%. The median across the 44
  cached stocks is +0.6%.
- **Yahoo's own tool says "Only US market data appears perfect"** and names HK examples with
  missing volume and missing dividend adjustment. Its repair option is off by default and
  covers daily bars only. [page]
- **Adjusted prices change after every dividend** [page]. This project's cache adds new bars
  to old ones, so old and new bars can sit on different scales. [my view; to check]
- **Timestamps**: SEC filings sent after 17:30 New York time appear the next business day.
  GDELT stamps articles in 15-minute batches. [summary and page]
- **Calendar**: HK has a lunch break, half days, and a closing auction that ends at a random
  time between 16:08 and 16:10. [page]

## 7. What I would change in the plan [my view]

The first replanning draft put a return-prediction model at the centre. The research says
that is the hardest part to make work at this scale. I would reorder the work:

1. **Portfolio analyzer first.** Returns, drawdown, volatility, correlation groups,
   concentration, and each holding's exposure to the market and to the six factors Brian chose
   on 2026-10-30. These numbers are stable and useful without any prediction.
2. **News watch as triage, not prediction.** For each story: is it about a holding or a
   factor the portfolio is exposed to? Is it new? What kind of event? How severe? A language
   model does this classification well and cheaply. The alert says what happened, what the
   portfolio's exposure is, and what similar past events did.
3. **Start alerts from the price too.** When a holding moves far more than its own normal
   and more than its market explains, look for the news. A move with news tends to continue;
   a move without news tends to reverse.
4. **Prediction as a tested research track.** Keep Brian's design: price model, news model
   and combined model, with the best one driving the label. Add slow signals with evidence
   (insider buying, short selling, momentum). Test with the stricter bar (t above 3, costs
   included, medians, capped outliers). Expect a small edge or none, and say so in the report.
5. **Clean prices before any test.** Raw and adjusted prices stored apart, a trading
   calendar, outlier and no-trade filters, and a second source to compare with.

## 8 and 9. Costs, account access and platforms

These two sections compare brokers for Brian's own accounts. They are private and
live in `docs/private/2026-11-10-brokers-costs-platforms.md`, which git ignores.
