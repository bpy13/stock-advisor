import pytest

from stock_advisor import watchlist
from stock_advisor.watchlist import load_watchlist

HEADER = "symbol,market,kind,name\n"


def _write(tmp_path, text):
    p = tmp_path / "w.csv"
    p.write_text(text, encoding="utf-8")
    return p


def test_comment_lines_skipped(tmp_path):
    p = _write(tmp_path, "# note\n" + HEADER + "0005.HK,HK,stock,HSBC\n# mid\nSPY,US,index_fund,SPY\n")
    items = load_watchlist(include_holdings=False, path=p)
    assert [i.symbol for i in items] == ["0005.HK", "SPY"]


def test_duplicate_symbol_rejected_with_line_number(tmp_path):
    p = _write(tmp_path, "# c\n" + HEADER + "SPY,US,index_fund,a\nQQQ,US,index_fund,b\nSPY,US,index_fund,c\n")
    with pytest.raises(ValueError, match="line 5.*first on line 3"):
        load_watchlist(include_holdings=False, path=p)


def test_unknown_kind_and_market_rejected(tmp_path):
    with pytest.raises(ValueError, match="line 2.*kind"):
        load_watchlist(False, _write(tmp_path, HEADER + "X,US,widget,x\n"))
    with pytest.raises(ValueError, match="line 2.*market"):
        load_watchlist(False, _write(tmp_path, HEADER + "X,EU,stock,x\n"))


def test_holdings_merged_and_file_kind_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist, "_holding_symbols", lambda: ["0005.HK", "zzz", "9999.HK"])
    p = _write(tmp_path, HEADER + "0005.HK,HK,stock,HSBC\n")
    items = {i.symbol: i for i in load_watchlist(path=p)}
    assert items["0005.HK"].kind == "stock"
    assert items["ZZZ"].kind == "holding" and items["ZZZ"].market == "US"
    assert items["9999.HK"].market == "HK"
    assert len(items) == 3
    assert "ZZZ" not in p.read_text()  # never written back


def test_shipped_file_is_valid():
    items = load_watchlist(include_holdings=False)
    hk = [i for i in items if i.market == "HK" and i.kind == "stock"]
    us = [i for i in items if i.market == "US" and i.kind == "stock"]
    assert 75 <= len(hk) <= 95 and 99 <= len(us) <= 102
