"""Plain data classes shared by every news source, the store and the scorers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


def ensure_utc(moment: datetime) -> datetime:
    """Return `moment` as a tz-aware UTC datetime (naive values are taken as UTC)."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def make_item_id(
    source: str, url: Optional[str], title: str, published_at: datetime
) -> str:
    """Stable id: sha1 of source+url, or source+title+published_at when there is no url."""
    if url:
        key = f"{source}|{url.strip()}"
    else:
        key = f"{source}|{title.strip()}|{ensure_utc(published_at).isoformat()}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


class SourceLimitReached(Exception):
    """A source stopped because its daily call budget is used up or the server rate-limited
    us (HTTP 429/403). The collector ends that source cleanly and resumes on the next run."""


@dataclass
class NewsItem:
    """One normalized headline from any source."""

    source: str
    published_at: datetime  # tz-aware UTC
    title: str
    url: str = ""
    summary: str = ""
    symbols: List[str] = field(default_factory=list)
    language: str = "en"
    body: Optional[str] = None  # full article text, only fetched for high-impact events
    id: str = ""
    # "exact": published_at is the real publication time. "day": the source only knows the
    # date (published_at is 00:00 UTC); use such items for the 1-day horizon only.
    time_precision: str = "exact"

    def __post_init__(self) -> None:
        self.published_at = ensure_utc(self.published_at)
        if not self.id:
            self.id = make_item_id(self.source, self.url, self.title, self.published_at)


@dataclass
class ItemScore:
    """Scoring results for one item. Fields stay None until the matching step has run."""

    item_id: str
    tone_pos: Optional[float] = None
    tone_neg: Optional[float] = None
    tone_neu: Optional[float] = None
    tone: Optional[float] = None  # tone_pos - tone_neg
    category: Optional[str] = None
    embedding: Optional[bytes] = None  # float32 vector bytes
    event_id: Optional[str] = None
    high_impact: bool = False


@dataclass
class Event:
    """A group of headlines about the same story."""

    id: str
    started_at: datetime  # earliest headline time
    category: Optional[str] = None
    title: str = ""
    n_items: int = 0
    n_sources: int = 0
    high_impact: bool = False

    def __post_init__(self) -> None:
        self.started_at = ensure_utc(self.started_at)
