"""Fetch the full text of an article, only for high-impact events (decision 2026-10-27).

Rules (decisions 2026-10-27: official access only, skip paywalled articles):
- paywalled domains in PAYWALL_DOMAINS are never requested;
- robots.txt is read once per host and obeyed for our User-Agent;
- a page that marks itself as not free (schema.org `"isAccessibleForFree": false`, used by
  SCMP premium and many others) is dropped;
- the text is extracted with trafilatura and capped at MAX_BODY_CHARS.

Tone is then re-scored on the title plus the first 2,000 characters of the body.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from stock_advisor.news.scoring import ToneRow, score_tone
from stock_advisor.news.sources import DEFAULT_USER_AGENT

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 15
MAX_BODY_CHARS = 20_000  # cap on stored text
MIN_BODY_CHARS = 200  # shorter extracts are usually a paywall or cookie stub
RESCORE_CHARS = 2_000  # body characters used for the tone re-score
# scoring.MAX_TOKENS truncates FinBERT input to 64 tokens (~300 characters), so the body is
# scored in pieces of about this size and the probabilities averaged.
RESCORE_PIECE_CHARS = 280

# Hard paywalls (or metered sites whose terms forbid automated reading). Subdomains match too.
PAYWALL_DOMAINS = (
    "nytimes.com",
    "wsj.com",
    "ft.com",
    "bloomberg.com",
    "economist.com",
    "barrons.com",
    "washingtonpost.com",
    "theathletic.com",
    "marketwatch.com",
    "nikkei.com",
    "asia.nikkei.com",
    "thetimes.co.uk",
    "telegraph.co.uk",
    "businessinsider.com",
    "seekingalpha.com",
    "foreignpolicy.com",
    "newyorker.com",
    "theinformation.com",
)

_NOT_FREE = re.compile(r'"isAccessibleForFree"\s*:\s*"?(false|False)"?')

# host -> parsed robots.txt (None means "could not read; treat as disallowed")
_robots_cache: Dict[str, Optional[RobotFileParser]] = {}


def is_paywalled(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in PAYWALL_DOMAINS)


def _robots_for(url: str, session) -> Optional[RobotFileParser]:
    parts = urlparse(url)
    key = f"{parts.scheme}://{parts.netloc}"
    if key in _robots_cache:
        return _robots_cache[key]
    parser: Optional[RobotFileParser] = RobotFileParser()
    try:
        response = session.get(key + "/robots.txt", timeout=TIMEOUT_SECONDS)
        if response.status_code in (401, 403):
            parser.parse(["User-agent: *", "Disallow: /"])
        elif response.status_code >= 400:
            parser.parse([])  # no robots.txt: everything allowed (standard behaviour)
        else:
            parser.parse(response.text.splitlines())
    except requests.RequestException as exc:
        logger.info("robots.txt unreadable for %s (%s); skipping host", key, exc)
        parser = None
    _robots_cache[key] = parser
    return parser


def allowed_by_robots(url: str, session=None, user_agent: str = DEFAULT_USER_AGENT) -> bool:
    parser = _robots_for(url, session or _default_session())
    return parser is not None and parser.can_fetch(user_agent, url)


def _default_session():
    session = requests.Session()
    session.headers["User-Agent"] = DEFAULT_USER_AGENT
    return session


def extract_text(html: str, url: str = "") -> Optional[str]:
    """Main article text from HTML, or None. Separate so tests can call it directly."""
    import trafilatura

    text = trafilatura.extract(html, url=url or None, include_comments=False,
                               include_tables=False)
    return text.strip() if text else None


def fetch_body(url: str, session=None, timeout: float = TIMEOUT_SECONDS) -> Optional[str]:
    """Return the article text (at most MAX_BODY_CHARS), or None when it may not or could not
    be read: not http(s), paywalled domain, robots.txt disallows, HTTP error, page marked not
    free, or too little text extracted."""
    if urlparse(url).scheme not in ("http", "https"):
        return None
    if is_paywalled(url):
        logger.info("paywalled domain, skipped: %s", url)
        return None
    session = session or _default_session()
    if not allowed_by_robots(url, session):
        logger.info("robots.txt disallows: %s", url)
        return None
    try:
        response = session.get(url, timeout=timeout)
    except requests.RequestException as exc:
        logger.info("article fetch failed for %s: %s", url, exc)
        return None
    if response.status_code != 200:
        logger.info("article fetch HTTP %s for %s", response.status_code, url)
        return None
    html = response.text
    if _NOT_FREE.search(html):
        logger.info("page marked not free (paywall), skipped: %s", url)
        return None
    text = extract_text(html, url)
    if not text or len(text) < MIN_BODY_CHARS:
        return None
    return text[:MAX_BODY_CHARS]


def _pieces(text: str, size: int = RESCORE_PIECE_CHARS) -> List[str]:
    """Split text into pieces of about `size` characters, breaking at spaces."""
    pieces, rest = [], " ".join(text.split())
    while rest:
        if len(rest) <= size:
            pieces.append(rest)
            break
        cut = rest.rfind(" ", 0, size)
        cut = cut if cut > size // 2 else size
        pieces.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    return [p for p in pieces if p]


def rescore_tone(title: str, body: str, finbert=None) -> ToneRow:
    """Tone of the title plus the first RESCORE_CHARS of the body.

    The title and each ~280-character piece of the body are scored separately and their
    probabilities averaged, because FinBERT input is truncated at 64 tokens.
    """
    texts = [title] + _pieces(body[:RESCORE_CHARS])
    rows = score_tone(texts, model=finbert)
    pos = sum(r[0] for r in rows) / len(rows)
    neg = sum(r[1] for r in rows) / len(rows)
    neu = sum(r[2] for r in rows) / len(rows)
    return (pos, neg, neu, pos - neg)
