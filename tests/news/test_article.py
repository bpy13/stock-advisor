"""Article fetch tests. HTTP is faked; no network."""

import numpy as np
import pytest
import requests

from stock_advisor.news import article

PARAGRAPH = (
    "Central banks across Asia moved to steady their currencies on Tuesday after a sharp "
    "sell-off in regional markets, with officials in Seoul and Jakarta stepping in to buy "
    "local currency. Analysts said the intervention could slow but not stop the decline. "
)
ARTICLE_HTML = (
    "<html><head><title>Markets</title></head><body><nav>Home | World</nav><article>"
    "<h1>Asian central banks step in</h1>"
    + "".join(f"<p>{PARAGRAPH} Paragraph {i}.</p>" for i in range(12))
    + "</article><footer>Copyright</footer></body></html>"
)


class FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


class FakeSession:
    """Maps URL -> FakeResponse or exception; records every requested URL."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append(url)
        result = self.responses.get(url, FakeResponse(404, ""))
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture(autouse=True)
def clear_robots_cache():
    article._robots_cache.clear()
    yield
    article._robots_cache.clear()


URL = "https://news.example.org/2026/10/27/asia-markets"
ROBOTS = "https://news.example.org/robots.txt"


def test_paywall_domains():
    assert article.is_paywalled("https://www.nytimes.com/2026/10/20/x.html")
    assert article.is_paywalled("https://ft.com/content/abc")
    assert article.is_paywalled("https://markets.ft.com/data")
    assert not article.is_paywalled("https://draft.com/a")  # suffix match is per label
    assert not article.is_paywalled("https://www.theguardian.com/a")


def test_fetch_body_extracts_text():
    session = FakeSession({ROBOTS: FakeResponse(200, "User-agent: *\nAllow: /\n"),
                           URL: FakeResponse(200, ARTICLE_HTML)})
    body = article.fetch_body(URL, session=session)
    assert body is not None
    assert "Central banks across Asia" in body
    assert "Copyright" not in body
    assert session.calls == [ROBOTS, URL]


def test_fetch_body_caps_length(monkeypatch):
    monkeypatch.setattr(article, "MAX_BODY_CHARS", 500)
    session = FakeSession({URL: FakeResponse(200, ARTICLE_HTML)})  # robots 404 -> allowed
    body = article.fetch_body(URL, session=session)
    assert len(body) == 500


def test_paywalled_domain_is_never_requested():
    session = FakeSession({})
    assert article.fetch_body("https://www.wsj.com/articles/x", session=session) is None
    assert session.calls == []


def test_robots_disallow_skips_article():
    session = FakeSession({ROBOTS: FakeResponse(200, "User-agent: *\nDisallow: /2026/\n"),
                           URL: FakeResponse(200, ARTICLE_HTML)})
    assert article.fetch_body(URL, session=session) is None
    assert session.calls == [ROBOTS]


def test_robots_forbidden_or_unreachable_means_disallowed():
    session = FakeSession({ROBOTS: FakeResponse(403, "")})
    assert article.fetch_body(URL, session=session) is None
    article._robots_cache.clear()
    session = FakeSession({ROBOTS: requests.ConnectionError("down")})
    assert article.fetch_body(URL, session=session) is None


def test_robots_read_once_per_host():
    other = "https://news.example.org/2026/10/27/other"
    session = FakeSession({ROBOTS: FakeResponse(200, ""), URL: FakeResponse(200, ARTICLE_HTML),
                           other: FakeResponse(200, ARTICLE_HTML)})
    article.fetch_body(URL, session=session)
    article.fetch_body(other, session=session)
    assert session.calls.count(ROBOTS) == 1


def test_page_marked_not_free_is_skipped():
    html = ARTICLE_HTML.replace(
        "<head>",
        '<head><script type="application/ld+json">{"isAccessibleForFree": false}</script>',
    )
    session = FakeSession({URL: FakeResponse(200, html)})
    assert article.fetch_body(URL, session=session) is None


@pytest.mark.parametrize(
    "response",
    [requests.Timeout("slow"), FakeResponse(500, "error"), FakeResponse(200, "<p>Too short</p>")],
)
def test_failures_return_none(response):
    session = FakeSession({URL: response})
    assert article.fetch_body(URL, session=session) is None


def test_non_http_url_returns_none():
    assert article.fetch_body("ftp://example.org/a", session=FakeSession({})) is None
    assert article.fetch_body("", session=FakeSession({})) is None


class RecordingFinBert:
    def __init__(self):
        self.texts = []

    def predict(self, texts):
        self.texts.extend(texts)
        # title positive, body pieces negative
        return np.array([[0.9, 0.05, 0.05] if t.startswith("Title") else [0.1, 0.8, 0.1]
                         for t in texts])


def test_rescore_tone_uses_title_and_first_2000_chars():
    body = ("word " * 400) + "TAILMARKER " * 50  # 2,000 chars of words, then the marker
    finbert = RecordingFinBert()
    pos, neg, neu, tone = article.rescore_tone("Title: stocks rally", body, finbert=finbert)
    assert finbert.texts[0] == "Title: stocks rally"
    body_pieces = finbert.texts[1:]
    assert all(len(p) <= article.RESCORE_PIECE_CHARS for p in body_pieces)
    assert sum(len(p) for p in body_pieces) <= article.RESCORE_CHARS
    assert not any("TAILMARKER" in p for p in body_pieces)
    n = len(finbert.texts)
    assert pos == pytest.approx((0.9 + 0.1 * (n - 1)) / n)
    assert tone == pytest.approx(pos - neg)
    assert pos + neg + neu == pytest.approx(1.0)
