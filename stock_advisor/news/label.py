"""Label linked news stories with Claude Haiku: relevant, event type, novelty, severity.

One story goes in one request; the answer comes back as structured JSON (a fixed schema), so
the model cannot invent a field or an event type. Every request's tokens and price are stored
on the story's row in the `labels` table, and the month's total there is the spending ceiling:
once it reaches `LABEL_MONTHLY_CEILING_USD` (default US$10), no paid call is made until the
next UTC month.

Prices read on 2026-11-17 from https://platform.claude.com/docs/en/about-claude/pricing:
Claude Haiku 5.5, prompts up to 100,000 tokens: US$0.10 in and US$0.50 out per million tokens
(Batch API half: US$0.05 and US$0.25). A one-story prompt is a few hundred tokens, far under
the 100,000-token tier.

The prompt holds the story's title, summary and the linked symbols with their names, nothing
about the user's holdings.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable, List, Mapping, Optional, Sequence

from stock_advisor.news.models import NewsItem
from stock_advisor.news.settings import get_setting
from stock_advisor.news.store import NewsStore

log = logging.getLogger(__name__)

MODEL = "claude-haiku-5-5"
# Bump when the prompt or schema changes: stories are then labelled again under the new version.
PROMPT_VERSION = "v1"
PRICE_IN_PER_MTOK = 0.10
PRICE_OUT_PER_MTOK = 0.50
DEFAULT_MONTHLY_CEILING_USD = 10.0
# Room for the JSON answer; thinking is off, so the answer is all the model writes.
MAX_TOKENS = 300

EVENT_TYPES = (
    "results", "guidance", "deal", "regulation", "legal", "management",
    "product", "macro", "rating", "capital", "other",
)

LABEL_SCHEMA = {
    "type": "object",
    "properties": {
        "relevant": {"type": "boolean"},
        "event_type": {"type": "string", "enum": list(EVENT_TYPES)},
        "novelty": {"type": "string", "enum": ["new", "repeat"]},
        "severity": {"type": "integer", "enum": [1, 2, 3]},
    },
    "required": ["relevant", "event_type", "novelty", "severity"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You label one financial news story for an investor who follows the listed stocks and "
    "market drivers.\n"
    "relevant: true only if the story could plausibly move the price of at least one listed "
    "stock or driver; false for passing mentions, lists, ads and unrelated stories that merely "
    "share a name.\n"
    "event_type: results (reported earnings or sales), guidance (company outlook), deal "
    "(merger, acquisition, partnership, contract), regulation (rules, policy, sanctions, "
    "tariffs), legal (lawsuits, probes, fines), management (executive or board changes), "
    "product (launches, recalls, approvals), macro (economy, rates, currencies, commodities), "
    "rating (analyst ratings or targets, credit ratings), capital (buybacks, dividends, share "
    "or bond issues), other.\n"
    "novelty: new if the story reports a fact not public before; repeat if it restates, "
    "summarises or comments on known news.\n"
    "severity: 1 minor, 2 notable, 3 major (likely to move the price on the day)."
)


@dataclass
class Label:
    relevant: bool
    event_type: str
    novelty: str
    severity: int


def cost_usd(tokens_in: int, tokens_out: int) -> float:
    return tokens_in * PRICE_IN_PER_MTOK / 1e6 + tokens_out * PRICE_OUT_PER_MTOK / 1e6


def monthly_ceiling_usd() -> float:
    """LABEL_MONTHLY_CEILING_USD from the environment; a bad or missing value gives US$10."""
    try:
        return float(get_setting("LABEL_MONTHLY_CEILING_USD") or DEFAULT_MONTHLY_CEILING_USD)
    except ValueError:
        return DEFAULT_MONTHLY_CEILING_USD


def build_prompt(item: NewsItem, linked: Sequence[str], names: Mapping[str, str]) -> str:
    lines = [f"Title: {item.title}"]
    if item.summary:
        lines.append(f"Summary: {item.summary}")
    lines.append("Linked stocks and drivers:")
    lines += [f"- {s}: {names.get(s, s)}" for s in linked]
    return "\n".join(lines)


def parse_label(text: str) -> Optional[Label]:
    """The label in a JSON answer, or None if anything is missing or outside the schema."""
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict) or set(data) != set(LABEL_SCHEMA["required"]):
        return None
    relevant, event, novelty, severity = (
        data["relevant"], data["event_type"], data["novelty"], data["severity"]
    )
    if not isinstance(relevant, bool) or event not in EVENT_TYPES:
        return None
    if novelty not in ("new", "repeat"):
        return None
    # bool is an int subclass in Python, so rule it out explicitly.
    if isinstance(severity, bool) or not isinstance(severity, int) or severity not in (1, 2, 3):
        return None
    return Label(relevant, event, novelty, severity)


def make_client():
    """A real Anthropic client; it reads ANTHROPIC_API_KEY from the environment (`.env`)."""
    import anthropic

    get_setting("ANTHROPIC_API_KEY")  # loads `.env` into the environment; the value stays there
    return anthropic.Anthropic()


def _ask(client, prompt: str):
    """One request. Returns (answer text or None, tokens in, tokens out)."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        thinking={"type": "disabled"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": LABEL_SCHEMA}},
    )
    usage = response.usage
    tokens = (usage.input_tokens or 0, usage.output_tokens or 0)
    # A refusal or a cut-off answer is treated like a malformed one.
    if response.stop_reason != "end_turn":
        return None, *tokens
    text = next((b.text for b in response.content if b.type == "text"), None)
    return text, *tokens


@dataclass
class LabelRun:
    labelled: int = 0
    errors: int = 0
    skipped: int = 0
    cost_usd: float = 0.0
    stopped_at_ceiling: bool = False


def label_items(
    store: NewsStore,
    items: Iterable[NewsItem],
    names: Mapping[str, str],
    client=None,
    ceiling_usd: Optional[float] = None,
    linked: Optional[Callable[[NewsItem], List[str]]] = None,
    now: Optional[Callable[[], datetime]] = None,
) -> LabelRun:
    """Label each item that has no label under PROMPT_VERSION yet; stop at the monthly ceiling.

    `names` maps a symbol or driver to its name for the prompt. `linked(item)` gives the item's
    linked symbols and drivers (default: `item.symbols`). A malformed answer is asked again
    once; a second malformed answer is stored with status 'error', never guessed. An item with
    any row under this version (label or error) is not sent again.
    """
    client = client if client is not None else make_client()
    ceiling = monthly_ceiling_usd() if ceiling_usd is None else ceiling_usd
    linked = linked or (lambda item: list(item.symbols))
    now = now or (lambda: datetime.now(timezone.utc))
    run = LabelRun()

    for item in items:
        if store.has_label(item.id, PROMPT_VERSION):
            run.skipped += 1
            continue
        prompt = build_prompt(item, linked(item), names)
        tokens_in = tokens_out = 0
        label: Optional[Label] = None
        for _attempt in range(2):
            month = now().strftime("%Y-%m")
            spent = store.label_cost_in_month(month)
            if spent >= ceiling:
                run.stopped_at_ceiling = True
                break
            text, used_in, used_out = _ask(client, prompt)
            tokens_in += used_in
            tokens_out += used_out
            label = parse_label(text) if text is not None else None
            if label is not None:
                break
        if run.stopped_at_ceiling and tokens_in == 0:
            # Stopped before any call for this item: nothing was spent, nothing is stored.
            break
        cost = cost_usd(tokens_in, tokens_out)
        store.add_label(
            item.id, PROMPT_VERSION, MODEL, label.__dict__ if label else None,
            tokens_in, tokens_out, cost, now(),
        )
        run.cost_usd += cost
        if label is None:
            run.errors += 1
            log.warning("label error for %s after a retry: answer did not fit the schema", item.id)
        else:
            run.labelled += 1
        if run.stopped_at_ceiling:
            break

    if run.stopped_at_ceiling:
        log.warning(
            "labelling stopped: this month's Claude cost reached the US$%.2f ceiling "
            "(LABEL_MONTHLY_CEILING_USD); no paid call until next month", ceiling,
        )
    return run
