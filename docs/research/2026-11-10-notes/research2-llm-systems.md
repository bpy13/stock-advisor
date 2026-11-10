# Research 2: LLM systems for portfolio news analysis (facts only)

Read on 2026-11-10 (UTC). Labels: **page** = I opened the live primary page/file; **snippet only** = seen only in a search result summary or via a secondary page; **unconfirmed** = could not confirm. GitHub star counts and push dates are from api.github.com on the same day. No recommendations.

Raw files I downloaded for checking are in `...\scratchpad\raw\` (same folder as this file).

---

## 1. Open-source LLM "analyst" projects

### 1.1 ZhuLinsen/daily_stock_analysis (DSA)
- Stars 69,316; last push 2026-11-09T14:14Z; license MIT. [page] https://api.github.com/repos/ZhuLinsen/daily_stock_analysis
- Goal line: AI analysis of A-share/HK/US/JP/KR/TW watchlists, pushes a "decision dashboard" to WeCom/Feishu/Telegram/Discord/Slack/email. [page] https://github.com/ZhuLinsen/daily_stock_analysis (README)
- HK support: watchlist example `600519,hk00700,AAPL,...`; market-review regions `cn,hk,us,jp,kr`; HK data via AkShare/YFinance/Longbridge (Longbridge token "fills volume ratio, turnover, PE" for HK/US). Market Light alerts only `cn/hk/us`. [page] README; https://github.com/ZhuLinsen/daily_stock_analysis/blob/main/docs/market-support.md
- Market data sources: AkShare, Tushare, Pytdx, Baostock, YFinance, Longbridge. Free sources work with zero config but README says stability "not guaranteed". [page] README
- News search providers (all plug-in, keys optional): Anspire, SerpAPI, Tavily, Bocha, Brave, MiniMax, SearXNG. Default news max age in `SearchService`: `news_max_age_days: int = 3`. [page] README; src/search_service.py (raw.githubusercontent.com/ZhuLinsen/daily_stock_analysis/main/src/search_service.py)
- LLMs: Gemini, OpenAI-compatible (DeepSeek, Qwen), Claude, Ollama, plus sponsor gateways (Modelflare, AIHubMix). Uses LiteLLM routing (`src/agent/litellm_route_resolution.py`) and has `apply_prompt_cache_hints` in src/analyzer.py. [page]
- Architecture: single-prompt analyzer by default (`src/analyzer.py`) and an agent mode `AGENT_ARCH=single|multi`. Multi mode has agent files `intel_agent.py`, `technical_agent.py`, `risk_agent.py`, `decision_agent.py`, `portfolio_agent.py`, with `orchestrator.py`. [page] https://github.com/ZhuLinsen/daily_stock_analysis/blob/main/docs/agent-trajectory-eval.md ; repo tree via API
- Prompt design (src/analyzer.py `SYSTEM_PROMPT_EN`): role "analyst ... producing a professional Decision Dashboard"; forces a JSON dashboard (ideal_buy, secondary_buy, stop_loss, take_profit, position size "X/10", a 6-item checklist with check/warn/cross marks); fixed score bands Strong Buy 80-100, Buy 60-79, Watch 40-59, Reduce 20-39, Sell 0-19. A "no major negative news" checklist item is one of the six. [page] src/analyzer.py lines ~2534-2594
- Guardrail in docs: if core quote/bars/technical data are stale, fallback, missing or partial, the report may not give high confidence; off-hours may not give high-confidence intraday calls. [page] docs/full-guide.md (line ~1078)
- Output: daily "decision dashboard" report (buy/hold/sell style score), market review, web workbench, chat "Agent Q&A". [page] README
- Scheduling: GitHub Actions workflow `.github/workflows/00-daily-analysis.yml`, cron `0 10 * * 1-5` (UTC 10:00 = Beijing 18:00); also Docker, local scheduler, FastAPI. README calls Actions "zero cost, no server". [page]
- Alerts (separate from LLM reports): rule types `price_cross`, `price_change_percent`, `volume_spike` (multiple of 20-day average volume). `sentiment_shift`, `risk_flag`, `custom` are "future placeholders", not executable. [page] https://github.com/ZhuLinsen/daily_stock_analysis/blob/main/docs/alerts.md
- Cost per run: not stated in README or docs I searched ("cost" only appears for Gemini free-tier rate-limit FAQ, ~15 RPM). [page / not found]
- Backtest/accuracy evidence published by the project: a backtest engine exists (`src/core/backtest_engine.py`, long-only, daily bars, `neutral_band_pct = 2.0`, scores `direction_correct`, `stock_return_pct`, stop-loss/take-profit hits) and a web backtest page. I found no published accuracy or return numbers in README. [page for engine; **unconfirmed** that no numbers exist elsewhere]

### 1.2 TauricResearch/TradingAgents
- Stars 121,734; last push 2026-11-04; license Apache-2.0; created 2024-12-28. [page] api.github.com/repos/TauricResearch/TradingAgents
- Architecture: multi-agent (LangGraph). Analyst team (Fundamentals, Sentiment, News, Technical) run in parallel; Bull/Bear researchers debate; Trader; Risk team; Portfolio Manager. Quick-think and deep-think model tiers, each may use a different provider. [page] https://github.com/TauricResearch/TradingAgents (README)
- Data: yfinance default, Alpha Vantage optional, SEC EDGAR fundamentals, FRED, StockTwits/Reddit, Polymarket. HK tickers accepted with exchange suffix, e.g. `0700.HK`. [page] README
- LLMs: OpenAI, Google, Anthropic, xAI, DeepSeek, Qwen, GLM, MiniMax, Ollama, Bedrock, any OpenAI-compatible endpoint. [page] README
- Output: a five-tier rating per ticker and date; reports saved as HTML. Not a scheduler or notifier; CLI/Python library. No Telegram found in README. [page]
- Self-published evaluation: `run_backtest` / `tradingagents backtest` over a ticker x date grid, scoring "realized alpha against the instrument's regional benchmark, grouped by rating"; a memory log settles past decisions. No result numbers in README. README disclaimer: "designed for research purposes". [page] README
- Cost per run: not stated in README. The paper says 11 LLM calls and 20+ tool calls per prediction. [page] arXiv PDF
- Paper arXiv 2412.20138 (Xiao, Sun, Luo, Wang; first posted 2024-12-28): backtest 2024-01-01 to 2024-03-29 (about 3 months) on AAPL, GOOGL, AMZN (the text says "three sampled stocks"; the dataset also lists NVDA, MSFT, META). Baselines Buy and Hold, MACD, KDJ+RSI, ZMR, SMA. Claims "at least a 23.21% cumulative return and a 24.90% annual return" on the three sampled stocks, beating best baseline "by a margin of 6.1%". [page] https://arxiv.org/abs/2412.20138 and PDF
- Same paper on its own Sharpe: highest Sharpe "exceeds our expected empirical range"; authors say it likely reflects "few pullbacks" in the period; they benchmarked 3 months "due to intensive LLM and tool use". Models then: gpt-4o-mini / gpt-4o / o1-preview. [page] PDF
- Independent critique: "The Alpha Illusion" (arXiv 2605.16895, 2026-05-16) names TradingAgents among systems whose reported Sharpe ratios should not be read as deployment evidence; the search summary also says buy-and-hold beat TradingAgents and QuantAgent on 4 of 5 tickers in a separate test (that last claim: snippet only). [page for abstract] https://arxiv.org/abs/2605.16895

### 1.3 virattt/ai-hedge-fund
- Stars 64,604; last push 2026-11-09; license MIT. [page]
- README: "proof of concept", "educational and research purposes only", "not intended for real trading". Needs a Financial Datasets API key (prices, fundamentals, earnings) and one model key (Anthropic, OpenAI, DeepSeek, Google, xAI, Kimi, TypeSafe). Features include backtesting with equity curve against a benchmark. Telegram/schedule: none seen. HK/A-share: not mentioned. Cost, backtest numbers: not stated. [page] https://raw.githubusercontent.com/virattt/ai-hedge-fund/main/README.md (3.5 KB, short; I did not read the agent files)
- Roles (investor-persona agents): **unconfirmed** in this short README; not read from source.

### 1.4 AI4Finance FinRobot and FinGPT
- FinRobot: stars 8,402; push 2026-10-24; Apache-2.0. README: three generations V0 AutoGen (educational), V1 OpenAI Agents SDK (web report generator), V2 PydanticAI (desktop app). V2 has a Lead Agent with sub-agents (Data, Analysis, Modeling, Synthesis, Report); "All financial numbers are produced by pure-Python compute operators, not by the language model". Output: 13-chapter equity research report with 12-month target. [page] https://github.com/AI4Finance-Foundation/FinRobot . No Telegram, no accuracy numbers seen.
- FinGPT: stars 21,546; push 2026-10-25; MIT. Releases: fine-tuned sentiment models and FinGPT-Forecaster (HuggingFace demo); benchmark repo. [page] https://github.com/AI4Finance-Foundation/FinGPT . I did not extract its published F1 numbers: **unconfirmed**.

### 1.5 OpenBB
- API redirected `OpenBB-finance/OpenBB` to a repo whose full_name shows `openbq-org/OpenBB`; stars 75,290; push 2026-11-10; spdx license shown as NOASSERTION, but README says Apache 2.0. (Odd redirect name: reported as returned.) [page]
- README: "Open Data Platform" (data layer); exposes data to Python, Workspace, Excel and MCP servers; AI agents are plugged in through a separate repo. [page] https://raw.githubusercontent.com/OpenBB-finance/OpenBB/develop/README.md
- Agents repo `OpenBB-finance/agents-for-openbb` 412 stars; `experimental-openbb-platform-agent` 1,356 stars (from the org repo list). [page] https://api.github.com/orgs/OpenBB-finance/repos . I did not read their code. "OpenBB AI SDK" as a named product: **unconfirmed** (only `openbb-ai` repo, 76 stars, found).

### 1.6 hsliuping/TradingAgents-CN
- Stars 32,870; push 2026-09-22; mixed licence: Apache-2.0 main, proprietary licences for `app/` and `frontend/` ("commercial use needs a separate licence"). [page] README + GitHub API
- Chinese-localised fork of TradingAgents; A-share / HK / US; data Tushare, AkShare, BaoStock; DeepSeek and other domestic LLMs; MongoDB. Claims "multi-layer news filtering, news quality assessment". [page] README
- News filter design doc: rule-based `NewsRelevanceFilter` scoring 0-100 (company name in title +40, stock code in title +30, include keywords +10, exclude keywords such as ETF/index -30), chosen as "recommended, immediately feasible" over an LLM filter. [page] https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/main/docs/features/NEWS_FILTERING_SOLUTION_DESIGN.md
- Backtest results: none seen. Telegram: none seen.

### 1.7 FinMem, FinAgent, StockAgent (research code)
- FinMem: pipiku915/FinMem-LLM-StockTrading, 972 stars, last push 2024-08-18, MIT. Paper arXiv 2311.13743 (layered memory + character profile agent). Default config is TSLA, 2022-06-30 to 2022-10-11 in the CLI help. [page] repo README
- FinAgent: repo guess DVampire/FinAgent, 77 stars, last push 2024-08-31, MIT. That this is the repo for paper arXiv 2402.18485 ("A Multimodal Foundation Agent for Financial Trading") is **unconfirmed**.
- StockAgent: MingyuJ666/Stockagent, 718 stars, push 2026-06-16, licence not shown in API. Paper arXiv 2407.18957 (trading in simulated markets). [page]
- All three are research prototypes; no notification or scheduling. FINSABER re-tested FinMem and FinAgent (see 2.4).

### 1.8 "LLM stock alert Telegram" projects over 200 stars
- GitHub repository search (queries "stock alert telegram bot", "stock news sentiment telegram", "ai stock analysis telegram bot", "stock news telegram llm alert") returned nothing above 200 stars that fits; top results had 77 stars or fewer (e.g. guccidgi/AI-Stock-Technical-Analysis-n8n-x-FlowiseAI 77; others under 35). [page for search output, but search is not exhaustive: **unconfirmed** that none exist]
- The only large project with Telegram delivery found is DSA (1.1).

### 1.9 Anthropic's own finance examples
- `anthropics/financial-services`: 41,187 stars, push 2026-10-28. README: reference agents/skills/connectors for investment banking, equity research, PE, wealth; installable as Claude Cowork plugin or deployed via Claude Managed Agents API. Listed agents: Pitch, Meeting Prep, Market Researcher, Earnings Reviewer, Model Builder, Valuation Reviewer, GL Reconciler, Month-End Closer, Statement Auditor, KYC Screener. README states these "do not make investment recommendations" and stage output for human sign-off. No news-alerting agent listed. [page] https://github.com/anthropics/financial-services
- `anthropics/claude-for-financial-advisors`: 147 stars, push 2026-11-02, a Cowork plugin for advisors. [page] GitHub API
- `anthropics/claude-cookbooks` has `capabilities/classification` (README, train/test data, evaluation). I did not read it. [page for file list only]

---

## 2. Evidence on whether LLM agents predict or trade well

| Study | Test period | Models | Result vs buy-and-hold | Stated conclusion | Label |
|---|---|---|---|---|---|
| StockBench, arXiv 2510.02209 (Oct 2025) https://arxiv.org/abs/2510.02209 | 2025-03-03 to 2025-06-30, 82 trading days, 20 top-weighted DJIA stocks, daily buy/sell/hold on prices+fundamentals+news (after model cutoffs) | GPT-5, Claude 4, Qwen3, Kimi-K2, GLM-4.5, DeepSeek, GPT-OSS | Table 2: passive equal-weight baseline +0.4% return, -15.2% max drawdown, Sortino 0.0155. Kimi-K2 +1.9% (ranked 1), DeepSeek-V3.1 +1.1%, GPT-5 +0.3%, GPT-OSS-20B -2.8%. | Abstract: "most models struggle to outperform the simple buy-and-hold baseline"; text: agents mostly cut drawdown to about -11% to -14%; static QA skill "do not necessarily translate" to trading. (Abstract and results text read differently on return; I report both.) | page |
| LiveTradeBench, arXiv 2511.03628 https://arxiv.org/abs/2511.03628 | Live 2025-08-18 to 2025-10-24, 50 trading days; US stocks and Polymarket | 21 LLMs | I did not extract per-model returns versus a buy-and-hold line. | "high LMArena scores do not imply superior trading outcomes"; Sharpe correlation across the two markets near zero. | page (abstract, partial text) |
| Agent Market Arena (AMA), arXiv 2510.11695 https://arxiv.org/abs/2510.11695 | Live 2025-08-01 to 2025-09-30; TSLA, BMRN, BTC, ETH | GPT-4o, GPT-4.1, Claude-3.5-haiku, Claude-sonnet-4, Gemini-2.0-flash x 4 agent frameworks | Text: agents "often surpassing simple buy-and-hold"; e.g. DeepFundAgent cumulative return 8.61% TSLA, 9.45% BMRN. Two months, four assets. | "frameworks display markedly distinct behavioral patterns... model backbones contribute less". | page |
| AI-Trader (HKUDS), arXiv 2512.10971 https://arxiv.org/abs/2512.10971 | Live 2025-10-01 to 2025-11-07 (US stocks, A-shares); crypto 2025-11-01 onward | DeepSeek-v3.1, MiniMax-M2, Claude-3.7-sonnet, GPT-5, Qwen3-max, Gemini-2.5 | US: MiniMax-M2 +7.69% excess, DeepSeek-v3.1 +6.52%, Claude-3.7 +1.24% over QQQ. A-shares: no agent beat SSE-50 (+1.65%). Crypto: only DeepSeek beat baseline (-12.18% vs -14.30%). | "general intelligence does not automatically translate to effective trading capability"; "most agents exhibiting poor returns and weak risk management". | page |
| FINSABER, arXiv 2505.07078 (Li et al. 2025) https://arxiv.org/abs/2505.07078 | 2004-2024, 100+ symbols, includes delisted S&P 500 names; also replays prior short windows | FinMem, FinAgent (GPT-4o / 4o-mini); other strategies | Buy and Hold "consistently rank among the top performers"; LLM only clearly ahead on TSLA. | "previously reported LLM advantages deteriorate significantly"; LLMs "overly conservative in bull markets" and "overly aggressive in bear markets". | page |
| InvestorBench, arXiv 2412.18174 https://arxiv.org/abs/2412.18174 | Stocks: warm-up 2020-07-01 to 2020-09-30, test 2020-10-01 to 2021-05-06 (inside many models' training data) | 13 backbones | Reports CR/SR relative to Buy & Hold per model; I did not extract numbers. | Benchmark release; not a post-cutoff test. | page (period); numbers unconfirmed |
| DeepFund, arXiv 2505.11065 https://arxiv.org/abs/2505.11065 | Live, data after each model's cutoff | 9 flagship LLMs | "even... DeepSeek-V3 and Claude-3.7-Sonnet incur net trading losses". | Live fund test shows "significant practical challenges". | page |
| FinBen, arXiv 2402.12659 https://arxiv.org/abs/2402.12659 | Static datasets (36 datasets, 24 tasks), incl. stock-trading task | 15 LLMs | n/a | "excel in IE and textual analysis, struggle with... forecasting". | page |
| Alpha Arena Season 1 (nof1.ai), via forklog https://forklog.com/en/four-out-of-six-ai-models-suffer-losses-in-trading-tournament/ | 2025-10-18 to 2025-11-03, crypto perps, $10,000 each, real money | 6 models | Final: Qwen3 Max $12,231 (+22.3%), DeepSeek $10,489 (+4.9%), Claude Sonnet 4.5 $5,799, Gemini 2.5 Pro $5,445, Grok $4,208, GPT-5 $4,126. A search summary gave GPT-5 about $3,733, so figures differ by source. | Organisers named flaws: prompt bias, short period, little statistical rigour (search summary). nof1.ai primary page not opened (blog URL 404). | secondary page; snippet only for organiser caveats |
| Alpha Arena Season 1.5 (US stocks) | ended 2025-12-03 | "Mystery model" later called Grok 4.20, GPT-5.1 second, Gemini 3 third | Winner about +12% average across four contests; other models mostly losses (per search summaries). | none from organisers seen | snippet only (https://forklog.com/en/ai-model-grok-4-2-triumphs-in-trading-tournament/) |

2026 items:
- "The Alpha Illusion" arXiv 2605.16895 (2026-05-16): "reported alpha from end-to-end LLM trading agents should not be treated as deployment evidence"; says public evidence cannot yet separate predictive skill from temporal contamination, unmodelled frictions and short-window Sharpe noise; proposes an alternative where LLMs act "as auditable information interfaces upstream of independent calibration, risk, and execution modules". [page] https://arxiv.org/abs/2605.16895
- arXiv 2606.08285 (2026-06-06), scoping review of 687 unique records on LLM trading execution realism; final counts "intentionally withheld". [page] https://arxiv.org/abs/2606.08285
- LiveOption arXiv 2609.33470 (2026-09-27): "current agents often fail to achieve competitive returns in most scenarios" (options). [page] https://arxiv.org/abs/2609.33470
- Chicago Booth (Koijen, Levy): live test on nearly 2,000 earnings announcements from late 2025, three unnamed frontier models; best AI explained about 17% of same-day moves versus about 5% for the EPS surprise; authors call it early. [page] https://news.uchicago.edu/story/how-ai-starting-explain-stock-price-moves
- FinMMEval 2026 entry arXiv 2607.12233 beat buy-and-hold on TSLA; authors warn live rankings are unstable in short windows. [snippet only]
- Lopez-Lira and Tang, arXiv 2304.07619 (v6 Oct 2025): "Using post-knowledge-cutoff headlines, GPT-4 captures initial market responses, achieving approximately 90% portfolio-day hit rates for the non-tradable initial reaction"; scores "significantly predict the subsequent drift, especially for small stocks and negative news"; "Strategy returns decline as LLM adoption rises". [page] https://arxiv.org/abs/2304.07619

---

## 3. LLM as a structured news classifier

### 3.1 Designs and measured accuracy
- Fixed-schema event extraction with quote grounding: arXiv 2607.08346 (2026-07-09) tags SEC 8-K filings against a 119-type, three-tier taxonomy; stage 1 constrains output to valid taxonomy entries and anchors each tag to a verbatim quote (fuzzy n-gram check); stage 2 re-grades the quote for a quality score. 292,984 filings (2022-2026), 601,088 tags. On 5,125 stratified tags an **LLM judge** (not humans) finds precision rising from 12% to 96% with the quality score. Event study on unsigned abnormal returns separates event types. [page] https://arxiv.org/abs/2607.08346
- Same family: Massive.com blog on tagging 8-K disclosures with a three-tier taxonomy (8/29/119). [snippet only] https://massive.com/blog/tagging-8-k-disclosures-with-ai-corporate-events-labelled-by-what-actually-happened
- Relevance filtering accuracy against human labels (kappa): the search found none. A LabelFusion-style paper reports zero-shot LLM F1 75.9% for relevance (the summary mixed up which 93.9% figure belongs to which setting). [snippet only] **Human-label materiality accuracy: unconfirmed.**
- Novelty detection by LLM (new vs repeat headline) with measured accuracy: search found none. **unconfirmed.**
- Severity/surprise scoring: Chicago Booth study above uses model explanations of earnings-call reactions; no headline severity benchmark found. [page for the study]

### 3.2 Consistency (same input scored twice)
- arXiv 2503.16974 (Mar 2025): 50 runs per task, GPT-3.5-turbo, GPT-4o-mini, GPT-4o, 3.4 million outputs. "binary classification and sentiment analysis achieving near-perfect reproducibility, while complex tasks show greater variability"; "LLMs significantly outperform expert human annotators in consistency"; "simple aggregation strategies across 3-5 runs dramatically improve consistency". [page] https://arxiv.org/abs/2503.16974
- arXiv 2607.24372 (2026-07-27): LLM output varies across identical requests; temperature 0 "does not eliminate the other sources of randomness"; "exact reproduction is therefore generally not possible when using proprietary" APIs; treat outputs "as draws from a distribution". The search summary says one regression flipped significance across 200 reruns (snippet only). [page for abstract] https://arxiv.org/abs/2607.24372
- arXiv 2311.15180 "Benchmarking Large Language Model Volatility": sentiment discrepancy at feed and ticker level; higher temperature gives more volatile long-short strategies. [snippet only]

### 3.3 Predicting returns from LLM-read news, with post-cutoff tests
- arXiv 2304.07619 (see section 2). [page]
- arXiv 2510.26228 (2025-10-30): ChatGPT reads firm news to condition a momentum strategy; "higher Sharpe and Sortino ratios both in-sample and in a truly out-of-sample period after the model's pre-training cut-off", "robust to transaction costs". S&P 500 universe. [page] https://arxiv.org/abs/2510.26228
- arXiv 2512.23847 "Detecting Lookahead Bias in LLM Forecasts": lookahead propensity "collapses essentially to zero right after the training-data cutoff"; headline-to-return predictive power is amplified on high-propensity pairs and "the interaction loses significance on post-training-cutoff samples". [page] https://arxiv.org/abs/2512.23847
- arXiv 2502.21206 "Chronologically Consistent LLMs": point-in-time models give Sharpe ratios "comparable to a much larger Llama model", "indicating that lookahead bias is modest". [page] https://arxiv.org/abs/2502.21206
- LLM-extracted corporate events with a post-cutoff return test: search found none directly. **unconfirmed.**

### 3.4 "Explain the move" features
- Robinhood Cortex "Digests": plain-English explanations on stock pages; reads news, analyst coverage, chart indicators, Robinhood trading data; UK rollout reported 2025-08-19; trigger rule not stated. [page] https://www.financemagnates.com/forex/brokers/the-uk-investors-get-new-robinhoods-ai-tool-that-explains-why-stocks-jump/
- Finviz Daily Digest / "Why is it moving": "AI-driven explanations for price action", reads social media, forums, SEC filings, news; no trigger threshold or model named. [page] https://finviz.com/blog/the-fastest-way-to-read-stock-market-news
- Google Finance (2025-11-06): Gemini "Deep Search" with cited reports, Kalshi/Polymarket data, earnings tracking; a third-party site says it can "investigate unusual price moves". Official wording not opened. [snippet only] https://www.pymnts.com/google/2025/google-finance-rolls-out-ai-driven-deep-search-prediction-market-data/
- Bloomberg: "AI Portfolio Commentary" in PORT Enterprise explains return drivers; I found no terminal feature named "explain the move". [snippet only] https://www.bloomberg.com/company/press/bloomberg-advances-portfolio-analytics-with-launch-of-ai-portfolio-commentary-in-port-enterprise
- moomoo: Moomoo AI (launched June 2025) with features such as AI Announcement Summary (Australia) and Smart Earnings; a "stock move explanation" feature: **unconfirmed**. Futu NiuNiu AI (牛牛AI): **unconfirmed** (search returned nothing). [snippet only] https://www.moomoo.com/sg/events/ai-features
- Yahoo Finance and Perplexity Finance: no result found. **unconfirmed.**

---

## 4. Claude API cost facts

Source: https://platform.claude.com/docs/en/about-claude/pricing , opened 2026-11-10 ~08:30 UTC [page]. Saved copy: `...\scratchpad\raw\pricing.md`. The page says to see claude.com/pricing for the most current figures (not opened).

Per million tokens (MTok), USD, from the "Model pricing" table (rows as printed):

| Model | Base input | 5m cache write | 1h cache write | Cache hit/refresh | Output |
|---|---|---|---|---|---|
| Claude Fable 5.2 | $8 | $10 | $16 | $0.20 | $40 |
| Claude Mythos 5.2 (limited availability) | $8 | $10 | $16 | $0.20 | $40 |
| Claude Fable 5.1 | $10 | $12.50 | $20 | $0.25 | $50 |
| Claude Fable 5 | $10 | $12.50 | $20 | $1 | $50 |
| Claude Opus 5.5 | $4 | $5 | $8 | $0.20 | $20 |
| Claude Opus 5 / 4.8 / 4.7 / 4.6 / 4.5 | $5 | $6.25 | $10 | $0.50 | $25 |
| Claude Sonnet 5.5 | $2 | $2.50 | $4 | $0.10 | $10 |
| Claude Sonnet 5 | $2 | $2.50 | $4 | $0.20 | $10 |
| Claude Sonnet 4.6 / 4.5 | $3 | $3.75 | $6 | $0.30 | $15 |
| Claude Haiku 5.5, prompts up to 100,000 tokens | $0.10 | $0.125 | $0.20 | $0.01 | $0.50 |
| Claude Haiku 5.5, prompts over 100,000 tokens | $0.50 | $0.625 | $1 | $0.05 | $2.50 |
| Claude Haiku 4.5 | $1 | $1.25 | $2 | $0.10 | $5 |

(Mythos 5.1/5 rows mirror Fable 5.1/5; Opus 4.1 and 4 are listed as retired at $15/$75.)
- Page footnote: Sonnet 5's $2/$10 was introductory pricing, "now the standard price"; the rise to $3/$15 on 2026-09-01 "will not occur". Cache-read multiplier is 0.05x on Opus 5.5 and Sonnet 5.5, 0.025x on Fable/Mythos 5.1-5.2, 0.1x on others.
- Tokenizer note: Claude 4.7 and later "produces approximately 30% more tokens for the same text" than Sonnet 4.6 and earlier.
- Message Batches: "50 percent discount on both input and output tokens". Batch rows: Sonnet 5.5 $1 in / $5 out; Opus 5.5 $2 / $10; Haiku 5.5 (up to 100k prompt) $0.05 / $0.25; Haiku 4.5 $0.50 / $2.50; Fable 5.2 $4 / $20. Batch and caching discounts can be combined (page, line ~539).
- Prompt caching (docs page https://platform.claude.com/docs/en/build-with-claude/prompt-caching, first 100,000 characters read): minimum cacheable prompt 512 tokens for Opus 5.5, Sonnet 5.5, Haiku 5.5, Fable/Mythos; 1,024 for Sonnet 5, Sonnet 4.6/4.5, Opus 4.8; 4,096 for Haiku 4.5 and Opus 4.5/4.6. Default 5-minute lifetime, refreshed free on each hit; optional 1-hour TTL. Writes cost 1.25x (5m) or 2x (1h) of base input. [page]
- Structured outputs (https://platform.claude.com/docs/en/build-with-claude/structured-outputs): JSON outputs via `output_config.format` with `type: "json_schema"`, plus `strict: true` tool use. Supported on Sonnet 5.5, Opus 5.5, Haiku 5.5 and others. An extra system prompt for the format "costs you tokens like any other system prompt"; changing the format invalidates the prompt cache for the thread; first use of a schema adds grammar-compile latency (cached 24 hours). Not supported: recursive schemas, numeric min/max, string length limits, `additionalProperties` other than false. Compatible with batch at the 50% discount. [page, last 6,003 characters unread]
- No separate surcharge for structured outputs was stated on the pricing page text I searched (grep for "structured output" returned nothing). [page]

---

## 5. Design patterns for alert quality

- **Cheap filter first, then LLM (rule-based relevance score):** TradingAgents-CN doc `docs/features/NEWS_FILTERING_SOLUTION_DESIGN.md` — keyword/company/code score 0-100 chosen over an LLM filter. [page] https://github.com/hsliuping/TradingAgents-CN
- **Price/volume triggers as the cheap first stage:** DSA `docs/alerts.md` rules `price_cross`, `price_change_percent` (e.g. "up/down X%"), `volume_spike` (multiple of 20-day average); evaluated by a background worker every `AGENT_EVENT_MONITOR_INTERVAL_MINUTES`. In-process fingerprint stops repeat pushes while a condition stays true; docs say this "is not" a cooldown model and keeps no state across restarts. [page] https://github.com/ZhuLinsen/daily_stock_analysis/blob/main/docs/alerts.md . A trigger that then searches news and asks an LLM why (explain-the-move) is not implemented there: `sentiment_shift`/`risk_flag` are placeholders. [page]
- **Dedup, cooldown, quiet hours, severity floor:** DSA `src/notification_noise.py` (process-local) with env keys `NOTIFICATION_DEDUP_TTL_SECONDS` (same key sent once in TTL), `NOTIFICATION_COOLDOWN_SECONDS`, `NOTIFICATION_QUIET_HOURS` (`HH:MM-HH:MM`, may cross midnight), `NOTIFICATION_TIMEZONE`, `NOTIFICATION_MIN_SEVERITY` (info/warning/error/critical), `NOTIFICATION_DAILY_DIGEST_ENABLED`; all default off; docs say the digest setting is "reserved" and sends nothing yet. [page] https://github.com/ZhuLinsen/daily_stock_analysis/blob/main/docs/notifications.md
- **Confidence gating:** DSA data-quality guardrail blocks high-confidence conclusions when core data is stale or partial (full-guide.md ~line 1078). [page]
- **News freshness window:** DSA `news_max_age_days = 3`. [page]
- **Quote-grounded classification with a second-pass quality score and a calibration check by score band:** arXiv 2607.08346 (3.1). [page]
- **Averaging repeated runs to cut noise:** arXiv 2503.16974, 3-5 runs. [page]
- **LLM as upstream "information interface" feeding independent risk/execution modules:** arXiv 2605.16895 proposal. [page]
- **Portfolio-aware prompts:** TradingAgents lets you pass your holdings so trader/risk/portfolio-manager agents "work against your actual book"; DSA can read Futu holdings each scheduled round and has a `portfolio_agent.py`. [page] TradingAgents README; DSA full-guide.md ~line 834
- **Decision-log settle loop (outcome feedback, not human feedback):** TradingAgents memory log settles past decisions after the holding period using realised alpha. [page] README
- **Human thumbs up/down on alerts feeding thresholds:** no concrete open-source implementation found (GitHub repository searches returned nothing relevant; DSA alerts doc has no feedback field). **unconfirmed**.
- **Explain-the-move from abnormal price move, vendor side:** Finviz/Robinhood describe the output but not the trigger or thresholds (3.4). Concrete repo implementation: **unconfirmed**.
