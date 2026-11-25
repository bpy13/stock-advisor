"""Brian's research-inbox shares tagged `stock`, read from a local file.

This source fetches nothing from any site, so the "official feeds only" rule (which governs
what this tool downloads) does not apply: the file is written by Brian's own tool from posts
he chose to send himself. Only Claude's summary, the topics, the link and Brian's note are
kept here; never the video, the caption or the page. Stored under its own source name so any
report can count it or leave it out.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from stock_advisor.news.models import NewsItem, make_item_id

logger = logging.getLogger(__name__)

SOURCE = "research_inbox"
PROJECT_TAG = "stock"
USABLE_STATUS = {"done", "caption_only"}
# <stock_advisor folder>/../research-inbox/data/shared/items.jsonl
DEFAULT_PATH = Path(__file__).resolve().parents[3].parent / "research-inbox" / "data" / "shared" / "items.jsonl"


def items_path() -> Path:
    return Path(os.environ.get("RESEARCH_INBOX_ITEMS") or DEFAULT_PATH)


def _to_item(line: dict) -> Optional[NewsItem]:
    if PROJECT_TAG not in (line.get("projects") or []) or line.get("status") not in USABLE_STATUS:
        return None
    title = str(line.get("title") or "").strip()
    published_at = datetime.fromisoformat(line["received_at"])
    summary_lines = [str(s) for s in (line.get("summary") or [])]
    topics = [str(t) for t in (line.get("topics") or [])]
    if topics:
        summary_lines.append("Topics: " + ", ".join(topics))
    return NewsItem(
        source=SOURCE,
        published_at=published_at,
        title=title,
        url=str(line.get("url") or ""),
        summary="\n".join(summary_lines),
        body=(str(line["note"]).strip() or None) if line.get("note") else None,
        id=make_item_id(SOURCE, f"research-inbox:item/{line['id']}", title, published_at),
        language="en",
        time_precision="exact",
    )


class ResearchInboxSource:
    name = SOURCE

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else items_path()
        self._missing_logged = False

    def fetch_recent(self) -> List[NewsItem]:
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            if not self._missing_logged:
                logger.warning("research_inbox: %s not found; no shared items", self.path.name)
                self._missing_logged = True
            return []
        items: List[NewsItem] = []
        for number, raw in enumerate(text.splitlines(), start=1):
            if not raw.strip():
                continue
            try:
                item = _to_item(json.loads(raw))
            except (ValueError, KeyError, TypeError, AttributeError):
                logger.warning("research_inbox: skipped unreadable line %d", number)
                continue
            if item is not None:
                items.append(item)
        return items
