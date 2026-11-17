"""Yahoo adapter tests: parse both yfinance shapes from fixtures; yfinance is mocked."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from yfinance.exceptions import YFDataException

from stock_advisor.news.sources import NewsSource, yahoo
from stock_advisor.news.sources.yahoo import (
    DEFAULT_SYMBOLS,
    YahooNewsSource,
    parse_article,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "news" / "yahoo"
FLAT = json.loads((FIXTURES / "search_xlk_flat.json").read_text(encoding="utf-8"))
NEW = json.loads((FIXTURES / "ticker_news_new_shape.json").read_text(encoding="utf-8"))
# Yahoo's answer to yfinance 1.7.0's Ticker.news request, recorded 2026-11-17: HTTP 404, an
# HTML page that contains "Will be right back".
NCP_404 = (FIXTURES / "ncp_404.html").read_text(encoding="utf-8")


def _patch(monkeypatch, ticker_news, search_news=()):
    """Make yfinance.Ticker(sym).news and yfinance.Search(sym).news return canned data."""
    calls = []

    def ticker(symbol):
        calls.append(("ticker", symbol))
        return MagicMock(news=ticker_news.get(symbol, []) if isinstance(ticker_news, dict) else ticker_news)

    def search(symbol, **kwargs):
        calls.append(("search", symbol))
        return MagicMock(news=list(search_news))

    monkeypatch.setattr(yahoo.yf, "Ticker", ticker)
    monkeypatch.setattr(yahoo.yf, "Search", search)
    return calls


def test_parse_flat_shape():
    item = parse_article(FLAT[0], "XLK")
    assert item.source == "yahoo"
    assert item.title == FLAT[0]["title"]
    assert item.url == FLAT[0]["link"]
    assert item.symbols == ["XLK"]
    assert item.published_at == datetime.fromtimestamp(FLAT[0]["providerPublishTime"], tz=timezone.utc)


def test_parse_new_shape():
    item = parse_article(NEW[0], "XLK")
    assert item.title == "Tech stocks rally as chipmakers lead gains"
    assert item.url == "https://finance.yahoo.com/news/tech-rally-123.html"
    assert item.summary.startswith("Semiconductor")
    assert item.published_at == datetime(2026, 10, 26, 15, 30, tzinfo=timezone.utc)


def test_parse_skips_unusable():
    assert parse_article(NEW[1], "XLK") is None
    assert parse_article({}, "XLK") is None
    assert parse_article("junk", "XLK") is None


def test_default_symbols_and_protocol():
    source = YahooNewsSource()
    assert source.symbols == DEFAULT_SYMBOLS
    assert isinstance(source, NewsSource)
    assert not hasattr(source, "fetch_range")


def test_symbols_normalized_and_deduplicated():
    assert YahooNewsSource([" xlk", "XLK", "2800.hk"]).symbols == ["XLK", "2800.HK"]


def test_same_story_merges_symbols(monkeypatch):
    _patch(monkeypatch, [], search_news=NEW)
    sleeps = []
    source = YahooNewsSource(["XLK", "QQQ"], sleep=sleeps.append)
    items = source.fetch_recent()
    assert len(items) == 1
    assert items[0].symbols == ["XLK", "QQQ"]
    assert sleeps == [1.0]  # one gap between the two calls


def test_recorded_404_makes_yfinance_ticker_news_raise(monkeypatch):
    """The cause of Task 5.2c: yfinance reads Yahoo's 404 page as 'Yahoo is down'."""
    import yfinance as yf

    monkeypatch.setattr(yf.data.YfData, "post",
                        lambda self, url, body=None, **kw: MagicMock(status_code=404, text=NCP_404))
    with pytest.raises(YFDataException):
        yf.Ticker("XLK").news


def test_search_used_while_ticker_news_raises(monkeypatch):
    """Ticker.news raising (the recorded 404) must not hide Search's stories."""
    calls = _patch(monkeypatch, [], search_news=FLAT)

    def ticker(symbol):
        raise YFDataException("*** YAHOO! FINANCE IS CURRENTLY DOWN! ***")

    monkeypatch.setattr(yahoo.yf, "Ticker", ticker)
    items = YahooNewsSource(["XLK"], sleep=lambda s: None).fetch_recent()
    assert len(items) == len(FLAT)
    assert calls == [("search", "XLK")]


def test_one_failing_symbol_does_not_stop_others(monkeypatch):
    def search(symbol, **kwargs):
        if symbol == "BAD":
            raise RuntimeError("boom")
        return MagicMock(news=NEW)

    monkeypatch.setattr(yahoo.yf, "Search", search)
    items = YahooNewsSource(["BAD", "XLK"], sleep=lambda s: None).fetch_recent()
    assert [i.symbols for i in items] == [["XLK"]]
