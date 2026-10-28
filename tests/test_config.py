"""Tests for the news target list."""

from stock_advisor.config import MARKET_INDEX_FOR, NEWS_TARGETS, news_targets, normalize_target


def test_targets_have_label_and_kind():
    for symbol, info in NEWS_TARGETS.items():
        assert info["label"], symbol
        assert info["kind"] in {"index", "sector"}, symbol
    assert "^HSI" in NEWS_TARGETS and "^GSPC" in NEWS_TARGETS


def test_news_targets_appends_normalized_deduplicated_holdings():
    result = news_targets([" aapl ", "AAPL", "xlk", "0700.hk", ""])
    assert result[: len(NEWS_TARGETS)] == list(NEWS_TARGETS)
    assert result[len(NEWS_TARGETS):] == ["AAPL", "0700.HK"]


def test_normalize_target_restores_caret_for_index_keys():
    assert normalize_target("HSI") == "^HSI"
    assert normalize_target(" gspc ") == "^GSPC"
    assert normalize_target("^hsi") == "^HSI"
    assert normalize_target("xlk") == "XLK"
    assert normalize_target("0700.hk") == "0700.HK"


def test_market_index_for():
    assert MARKET_INDEX_FOR("0700.HK") == "^HSI"
    assert MARKET_INDEX_FOR("aapl") == "^GSPC"