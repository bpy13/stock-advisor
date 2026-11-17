"""The news linker on hand-written headlines, using the real names file `config/aliases.csv`."""

import pytest

from stock_advisor.news import link as link_mod
from stock_advisor.news.link import Alias, Linker, build_linker, draft_aliases, read_aliases
from stock_advisor.risk import DRIVERS
from stock_advisor.watchlist import load_watchlist


@pytest.fixture(scope="module")
def linker():
    return build_linker(include_holdings=False)


# (headline, expected symbols, expected drivers). Each expected target must be found; no other
# target may appear.
LINKED = [
    ("Tencent shares jump after record game revenue", {"0700.HK"}, set()),
    ("HSBC to cut 3,000 jobs in cost drive", {"0005.HK"}, set()),
    ("Alibaba Health posts first annual profit", {"0241.HK"}, set()),
    ("Alibaba unveils new AI model to rival DeepSeek", {"9988.HK"}, set()),
    ("BYD Electronic wins Apple supplier contract, shares surge", {"0285.HK", "AAPL"}, set()),
    ("BYD sales top Tesla for the third quarter", {"1211.HK", "TSLA"}, set()),
    ("Meituan faces new fee rules from Beijing regulators", {"3690.HK"}, set()),
    ("Xiaomi launches its second electric car", {"1810.HK"}, set()),
    ("JD.com and JD Logistics announce share buyback", {"9618.HK", "2618.HK"}, set()),
    ("AIA Group raises dividend as new business grows", {"1299.HK"}, set()),
    ("Ping An profit falls on investment losses", {"2318.HK"}, set()),
    ("China Mobile adds 5G users in October", {"0941.HK"}, set()),
    ("CNOOC and PetroChina gain as crude oil rallies", {"0883.HK", "0857.HK"}, {"oil"}),
    ("SMIC expands capacity despite US curbs", {"0981.HK"}, set()),
    ("Hang Seng Index closes at a three-month high", {"^HSI"}, set()),
    ("Hang Seng Tech gauge slides as Chinese tech sells off", set(), {"china_hk_tech"}),
    ("Link REIT buys Sydney mall", {"0823.HK"}, set()),
    ("Sun Hung Kai Properties sells flats at a discount", {"0016.HK"}, set()),
    ("Galaxy Entertainment and Sands China lead Macau casino gains", {"0027.HK", "1928.HK"}, set()),
    ("MTR fares to rise 3% next year", {"0066.HK"}, set()),
    ("0700.HK: buyback continues for a tenth day", {"0700.HK"}, set()),
    ("Stock note: 9988 HK and 3690 HK top turnover", {"9988.HK", "3690.HK"}, set()),
    ("HKEX: 00941 announces interim dividend", {"0941.HK"}, set()),
    ("Apple shares fall after iPhone sales miss estimates", {"AAPL"}, set()),
    ("Microsoft and Nvidia lead Nasdaq to record close", {"MSFT", "NVDA"}, {"us_tech"}),
    ("Amazon Web Services outage hits thousands of websites", {"AMZN"}, set()),
    ("Amazon stock rises on Prime Day sales", {"AMZN"}, set()),
    ("Alphabet's Google fined in EU antitrust case", {"GOOG", "GOOGL"}, set()),
    ("Meta shares slump as spending forecast jumps", {"META"}, set()),
    ("JPMorgan and Goldman Sachs beat profit estimates", {"JPM", "GS"}, set()),
    ("Berkshire Hathaway builds cash pile to record", {"BRK-B"}, set()),
    ("Exxon Mobil to buy shale producer in $60 billion deal", {"XOM"}, set()),
    ("Eli Lilly weight-loss drug wins approval", {"LLY"}, set()),
    ("AT&T and Verizon raise wireless prices", {"T", "VZ"}, set()),
    ("$T and $VZ fall premarket", {"T", "VZ"}, set()),
    ("Visa and Mastercard settle swipe-fee lawsuit; shares rise", {"V", "MA"}, set()),
    ("Coca-Cola beats sales forecasts", {"KO"}, set()),
    ("Lowe's cuts outlook as housing slows", {"LOW"}, set()),
    ("NYSE: LOW shares slip in early trade", {"LOW"}, set()),
    ("Oracle stock soars on cloud contracts", {"ORCL"}, set()),
    ("ServiceNow and Salesforce slide on AI fears", {"NOW", "CRM"}, set()),
    ("Palo Alto Networks buys cybersecurity startup", {"PANW"}, {"cyber_security"}),
    ("Ransomware attack hits US hospital chain", set(), {"cyber_security"}),
    ("Federal Reserve holds rates steady, signals two cuts", set(), {"us_rates"}),
    ("Fed's Powell says inflation fight is not over", set(), {"us_rates"}),
    ("Treasury yields climb after strong jobs data", set(), {"us_rates"}),
    ("OPEC+ agrees to extend output cuts", set(), {"oil"}),
    ("Brent crude tops $90 a barrel", set(), {"oil"}),
    ("Yuan weakens past 7.3 per dollar after PBOC fixing", set(), {"usd_cny"}),
    ("Renminbi slips to a 16-year low", set(), {"usd_cny"}),
    ("S&P 500 hits record as tech rallies", {"^GSPC"}, set()),
    ("Nasdaq-100 rebalance adds three stocks", {"^NDX"}, set()),
    ("SPDR S&P 500 ETF sees record outflows", {"SPY"}, set()),
    ("Tracker Fund draws inflows as Hong Kong rallies", {"2800.HK"}, set()),
    ("騰訊控股(00700)第三季盈利勝預期", {"0700.HK"}, set()),
    ("匯豐控股削減成本 股價升百分之二", {"0005.HK"}, set()),
    ("美團與京東外賣戰升級", {"3690.HK", "9618.HK"}, set()),
    ("小米股價創新高", {"1810.HK"}, set()),
    ("港交所公布首季業績", {"0388.HK"}, set()),
    ("聯儲局議息後美債孳息回落", set(), {"us_rates"}),
    ("人民幣兌美元匯率跌至新低", set(), {"usd_cny"}),
    ("恒指收市升300點 恒生科技指數升2%", {"^HSI"}, {"china_hk_tech"}),
    ("中國銀行公布中期業績", {"3988.HK"}, set()),
    ("Tencent closes at HK$500 on 0700 HK board", {"0700.HK"}, set()),
]

# Headlines that must link to nothing.
TRAPS = [
    "Apple harvest falls as frost hits orchards",
    "Meta analysis finds coffee lowers heart risk",
    "Fire breaks out at HSBC Building on Queen's Road",
    "Bank of America Tower lobby reopens after flood",
    "Wells Fargo Center hosts NBA playoff game",
    "Amazon rainforest fires reach record level",
    "Fed up commuters protest new bus timetable",
    "Oracle of Delphi exhibit opens at British Museum",
    "Caterpillar numbers fall in English gardens",
    "Visa rules tightened for foreign students",
    "Low tide strands fishing boats in harbour",
    "Now is the time to plant tulips",
    "Cat cafe opens in Sheung Wan",
    "Prices rose 5% (2020) and 3% (1997) in the survey",
    "Top 5 HK hiking trails for autumn",
    "Olive oil prices soar in Spain",
    "Chevron pattern quilts return to fashion",
    "銀行業界舉辦慈善跑",
    "中銀大廈外牆維修",
    "蘋果收成受霜凍影響",
    "He paid 50 yuan for a bowl of noodles",
]


@pytest.mark.parametrize("title,symbols,drivers", LINKED, ids=[t[:40] for t, _, _ in LINKED])
def test_expected_links_found(linker, title, symbols, drivers):
    result = linker.link(title)
    assert set(result.symbols) == symbols, result.matches
    assert set(result.drivers) == drivers, result.matches


@pytest.mark.parametrize("title", TRAPS, ids=[t[:40] for t in TRAPS])
def test_traps_link_to_nothing(linker, title):
    result = linker.link(title)
    assert not result.linked, result.matches


def test_fixture_size():
    assert len(LINKED) + len(TRAPS) >= 60 and len(TRAPS) >= 20


def test_result_holds_matched_text(linker):
    result = linker.link("Tencent rallies", summary="騰訊 shares rose", body="Analysts at HSBC upgraded it.")
    assert ("0700.HK", "Tencent") in result.matches
    assert ("0700.HK", "騰訊") in result.matches
    assert ("0005.HK", "HSBC") in result.matches
    assert result.symbols == ["0005.HK", "0700.HK"] and result.drivers == []


def test_weak_alias_confirmed_by_strong_alias_of_same_symbol(linker):
    assert linker.link("Apple unveils new iPhone").symbols == ["AAPL"]


def test_short_ticker_needs_dollar_or_exchange(linker):
    assert linker.link("Meet C at the cafe").symbols == []
    assert linker.link("$C rallies").symbols == ["C"]
    assert linker.link("Citigroup (NYSE: C) beats estimates").symbols == ["C"]


def test_exchange_prefix_is_not_a_mention_of_the_exchange(linker):
    result = linker.link("NASDAQ: AAPL and HKEX: 00700 both rise")
    assert result.symbols == ["0700.HK", "AAPL"] and result.drivers == []


def test_names_file_is_valid_and_covers_the_watchlist():
    aliases = read_aliases()
    items = load_watchlist(include_holdings=False)
    symbols = {i.symbol for i in items}
    for a in aliases:
        assert a.target in symbols or a.target in DRIVERS, a
    covered = {a.target for a in aliases}
    for i in items:
        if i.kind in ("stock", "index_fund", "index"):
            assert i.symbol in covered, i.symbol
    assert set(DRIVERS) <= covered


def test_draft_aliases_for_hk_and_us():
    hk = {(a.alias, a.kind) for a in draft_aliases("0700.HK", "Tencent Holdings Limited")}
    assert {("Tencent Holdings Limited", "name"), ("Tencent", "short"), ("0700.HK", "ticker"),
            ("700.HK", "ticker"), ("700 HK", "ticker"), ("00700", "ticker")} <= hk
    assert ("5 HK", "ticker") not in {(a.alias, a.kind) for a in draft_aliases("0005.HK", "HSBC")}
    us = {(a.alias, a.kind) for a in draft_aliases("BRK-B", "Berkshire Hathaway")}
    assert {("BRK-B", "ticker"), ("BRK.B", "ticker"), ("$BRK.B", "ticker")} <= us
    assert draft_aliases("^HSI", "Hang Seng Index") == [Alias("^HSI", "Hang Seng Index", "name")]


def test_hans_rows_match_like_traditional_rows():
    # A placeholder stands in for a Simplified name: the kind only marks the row.
    linker = Linker([Alias("0700.HK", "騰訊", "zh"), Alias("0700.HK", "騰迅", "hans")])
    assert linker.link("騰迅股價").symbols == ["0700.HK"]


def test_bad_kind_rejected(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("symbol,alias,kind\nAAPL,Apple,nickname\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown kind"):
        read_aliases(p)


def test_holdings_join_at_run_time(tmp_path, monkeypatch):
    names = tmp_path / "aliases.csv"
    names.write_text("symbol,alias,kind\nAAPL,Apple Inc.,name\n", encoding="utf-8")
    wl = tmp_path / "w.csv"
    wl.write_text("symbol,market,kind,name\nAAPL,US,stock,Apple Inc.\n", encoding="utf-8")
    monkeypatch.setattr("stock_advisor.watchlist._holding_symbols", lambda: ["1234.HK"])
    linker = build_linker(names, include_holdings=True, watchlist_path=wl)
    assert linker.link("Unknown Co (1234.HK) jumps").symbols == ["1234.HK"]


def test_module_link_uses_default_linker(monkeypatch):
    monkeypatch.setattr(link_mod, "_default_linker", lambda: Linker([Alias("AAPL", "Apple Inc.", "name")]))
    assert link_mod.link("Apple Inc. results").symbols == ["AAPL"]
