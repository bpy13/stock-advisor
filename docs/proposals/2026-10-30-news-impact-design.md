# Proposal: news → factor shock → stock sensitivity (2026-10-30)

Status: **proposal for Brian's review.** Nothing here is decided until Brian says so; the
decisions already taken are listed in `docs/decisions.md` (2026-10-30 entries).

## The goal (Brian's words, condensed)

Catch significant news (a software vulnerability, the China AI selloff, a Middle East peace
deal), judge how severe it is, and give a quantitative buy/sell suggestion for the portfolio.
Severity must be graded, not just a category label. Different stocks react differently to
the same kind of news, and that sensitivity should drive the suggestion.

## Why the current design falls short

The current model learns "headline text like this → this stock's move" in one step, per
stock. It needs a great deal of clean history, and it never measures severity or a stock's
sensitivity directly. On 2026-10-30 it had valid reactions for one week only (see Task 6.2i).

## The design: two steps

**Step A – news → factor shock.** A factor is a market driver many stocks share. For each
high-impact event, a language model fills in a fixed form:

| Field | Example: "Middle East peace deal signed" |
|---|---|
| factors hit, with direction | oil: down; airlines: up |
| severity, 0–10 | 8 |
| surprise, 0–10 (was it expected?) | 6 |
| scope | global |
| horizon | days to weeks |
| confidence, 0–1 | 0.7 |

The model then learns, per factor, how big the factor's move is for a given severity and
surprise. Example: "severity 8, surprise 6 oil news → Brent −4% to −7% over 2 days". It
learns this from past events and the factor's actual price moves.

**Step B – factor → each stock's sensitivity.** From daily prices only (no news), measure
how much each holding moves per 1% move of each factor. Example: "this holding moves 1.4%
per 1% move of Hang Seng Tech". Yahoo has years of daily data, so this is reliable today.

**Recommendation.** Expected move of each holding = its sensitivities × the expected factor
shocks. Suggest trims or adds sized by the expected move and the confidence. Only factor
links that pass the backtest (with the 250-trading-day rule) may change a recommendation;
the rest are shown as information, as today.

## First factors (Brian, 2026-10-30)

Symbols checked on yfinance on 2026-10-30 (first date of daily history):

| Factor | Symbol | History | Notes |
|---|---|---|---|
| Oil | `CL=F` (WTI crude futures) | 2000 | Longer than Brent `BZ=F` (2007). Monthly contract rolls cause small jumps: filter them. |
| US interest rates | `^TNX` (10-year yield) | 1962 | Use the daily change in yield, not a % return. |
| China/HK tech | `KWEB` (China internet ETF) | 2013 | `^HSTECH` has no data on yfinance; `3033.HK` (2020) as a Hong Kong-hours check. KWEB trades in US hours. |
| US tech | `^NDX` (Nasdaq 100) | 1985 | |
| Cyber security | `HACK` | 2014 | `CIBR` from 2015, `BUG` from 2019. |
| USD/CNY | `CNY=X` | 2001 | Use from mid-2005: the rate was fixed before. |

Prove these first. Add others later (for example "Apple announcement") only once these work.

## Severity scoring: the Claude API (Brian allowed it, 2026-10-30)

- Model: Claude Opus 5.5 (`claude-opus-5-5`), $4 per million input tokens and $20 per
  million output tokens. The fixed instructions are cached (about 90% cheaper on repeats).
  The Message Batches API halves the price for the historical run (results within hours).
- Rough cost per event, assuming ~500 tokens of headlines in, ~1,500 tokens of cached
  instructions, ~600 tokens out: about $0.014 live, about $0.007 in a batch. These are
  estimates; a measured sample of 20 events comes first.
- Live: only high-impact events (a few dozen a day): roughly $0.40 a day, $12 a month.
- History: scoring all 467k events (~$3,300) is not sensible. Score the high-impact ones and
  a sample per category; for example 20,000 events ≈ $140 in a batch.
- A cheaper model (Claude Haiku 5.5, about 40 times cheaper) is possible if a quality check
  shows it scores well enough. That is Brian's call, after the sample.
- No paid run starts without a quoted cost and Brian's go.

## What must be true before step A can learn

1. Task 6.2i: full price history, rebuilt reactions, the 250-trading-day rule.
2. The backfill covers 2003–2025 (today it has reached 2002). Many factors only start
   trading later (Hang Seng Tech index from 2020, cyber ETFs from 2014–2015), so their
   history is short whatever the news covers.
3. Factor reactions are built the same way as stock reactions.

## Phases (to plan in detail after Brian's review)

1. **Sensitivities (step B).** Daily-price betas of each holding to each factor, rolling
   over 2–3 years; shown on the dashboard. Useful on its own: "your portfolio's oil
   exposure".
2. **Severity form.** The prompt, the JSON form, a 20-event sample with measured cost;
   Brian checks the scores by eye.
3. **Factor shock model (step A).** Severity and surprise → factor move, per factor; walk-
   forward backtest with the 250-day rule.
4. **Recommendation.** Holdings' expected moves, trim/add suggestions, Telegram alert text.
5. **Live.** The watcher scores new high-impact events and alerts with the suggestion.

## Open questions for Brian

1. Phase 1 first, since it needs no news data and gives a useful exposure view at once?
2. After the 20-event sample: Opus 5.5 or the cheaper Haiku 5.5 for the bulk run (the
   one-time scoring of ~20,000 past events that builds the training set)?
