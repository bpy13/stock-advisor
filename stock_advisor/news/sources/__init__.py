"""Shared contract and polite-HTTP helper for every news source adapter.

Each adapter module (e.g. `sources/guardian.py`) defines a class with a `name` attribute and
`fetch_recent()`; adapters with history also define `fetch_range(start, end)`. All adapters
fetch through `PoliteSession` so delays, timeouts and retries behave the same everywhere.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, List, Optional, Protocol, runtime_checkable

import requests

from stock_advisor.news.models import NewsItem

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "stock_advisor/0.1 (personal research tool; https://github.com/bpy13/stock_advisor)"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


@runtime_checkable
class NewsSource(Protocol):
    """What the collector expects from an adapter.

    `fetch_range(start, end)` is optional: only adapters with history have it. The collector
    checks `hasattr(source, "fetch_range")`. Both datetimes are tz-aware UTC.
    """

    name: str

    def fetch_recent(self) -> List[NewsItem]: ...

    # Optional:
    # def fetch_range(self, start: datetime, end: datetime) -> Iterator[NewsItem]: ...


class PoliteSession:
    """requests wrapper: descriptive User-Agent, timeout, minimum gap between requests,
    and retry with exponential backoff on 429 and 5xx (honouring Retry-After)."""

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        min_delay: float = 1.0,
        timeout: float = 30.0,
        max_retries: int = 4,
        backoff: float = 2.0,
        session: Optional[requests.Session] = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.min_delay = min_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self._session = session or requests.Session()
        self._session.headers["User-Agent"] = user_agent
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: Optional[float] = None

    def _wait_for_turn(self) -> None:
        if self._last_request_at is not None:
            remaining = self.min_delay - (self._clock() - self._last_request_at)
            if remaining > 0:
                self._sleep(remaining)

    def _retry_wait(self, response: requests.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After", "")
        if retry_after.isdigit():
            return max(float(retry_after), self.backoff**attempt)
        return self.backoff**attempt

    def get(self, url: str, **kwargs) -> requests.Response:
        """GET with politeness. Returns the response; raises requests.HTTPError when a
        non-retryable error occurs or retries run out."""
        kwargs.setdefault("timeout", self.timeout)
        for attempt in range(self.max_retries + 1):
            self._wait_for_turn()
            try:
                response = self._session.get(url, **kwargs)
            except (requests.ConnectionError, requests.Timeout) as exc:
                self._last_request_at = self._clock()
                if attempt == self.max_retries:
                    raise
                logger.warning("GET %s failed (%s); retry %d", url, exc, attempt + 1)
                self._sleep(self.backoff**attempt)
                continue
            self._last_request_at = self._clock()
            if response.status_code in RETRY_STATUSES and attempt < self.max_retries:
                wait = self._retry_wait(response, attempt)
                logger.warning(
                    "GET %s returned %d; retry %d in %.1fs",
                    url, response.status_code, attempt + 1, wait,
                )
                self._sleep(wait)
                continue
            response.raise_for_status()
            return response
        raise RuntimeError("unreachable")  # pragma: no cover
