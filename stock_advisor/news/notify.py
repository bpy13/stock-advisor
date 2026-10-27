"""Telegram alerts for new high-impact news events (plan Task 5.4).

    python -m stock_advisor.news.notify --setup   # find the chat id from the bot's latest message
    python -m stock_advisor.news.notify --test    # send one test message

`news_cli --watch` builds a `TelegramNotifier` and passes it as `on_new_events`.

Alert rule (decision 2026-10-27): the event is high-impact (the watcher only passes those) and
at least one target (a holding, ^HSI or ^GSPC) has a predicted 1-day move of 1.5% or more. Alerts
run 24/7. Only the headline and link are sent, never an item summary (Guardian terms).

Safety rules kept here:
* The bot token comes from settings only. It is part of the Telegram URL, so no exception text
  is ever logged or printed: only the exception type or the HTTP status.
* An event is alerted at most once (`sent_alerts` table in the news store).
* At most `max_per_hour` alerts per rolling hour; the rest are recorded as suppressed and one
  "N more alerts suppressed" message follows.
* Without a token the notifier logs one warning and does nothing.
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Sequence

from stock_advisor.config import NEWS_ACTION_THRESHOLD_PCT
from stock_advisor.news import settings
from stock_advisor.news.analysis import EventAnalysis, TargetOutlook, strong_targets

logger = logging.getLogger(__name__)

API_URL = "https://api.telegram.org/bot{token}/{method}"
MAX_MESSAGE_CHARS = 4096
REQUEST_TIMEOUT = 15
NO_TOKEN_HELP = "Set TELEGRAM_BOT_TOKEN in .env first (create a bot with @BotFather)."

Post = Callable[..., object]  # requests.post-compatible


# ---- message text -------------------------------------------------------------------------------


def _pct(value: float) -> str:
    return "n/a" if value is None or math.isnan(value) else f"{value * 100:+.2f}%"


def _forecast_cell(forecast) -> str:
    if not forecast.available:
        return f"{forecast.horizon} n/a"
    return (f"{forecast.horizon} {_pct(forecast.predicted)} "
            f"({_pct(forecast.low)} to {_pct(forecast.high)})")


def _outlook_lines(outlook: TargetOutlook) -> List[str]:
    cells = " | ".join(_forecast_cell(f) for f in outlook.forecasts.values())
    flag = "" if outlook.action_proven else " (unproven)"
    return [f"{outlook.target}: {cells}",
            f"  action: {outlook.action}{flag}; window: {outlook.window_text}"]


def format_alert(analysis: EventAnalysis, targets: Optional[Sequence[str]] = None) -> str:
    """Plain-text alert (no markup, so nothing needs escaping), at most 4096 characters.

    `targets` default to those with a strong predicted move. The headline and link come first;
    when the message is too long the per-target lines are dropped from the end, then it is cut.
    """
    shown = list(targets) if targets is not None else strong_targets(analysis)
    outlooks = [analysis.outlooks[t] for t in shown if t in analysis.outlooks]
    unproven = any(not f.proven for o in outlooks for f in o.forecasts.values() if f.available)

    head = []
    if unproven:
        head.append("⚠ unproven")  # warning sign
    head.append(f"{analysis.category or 'uncategorized'} - high-impact event")
    head.append(analysis.title)
    if analysis.link:
        head.append(analysis.link)
    if analysis.sources:
        head.append("sources: " + ", ".join(analysis.sources))

    blocks: List[str] = []
    for outlook in outlooks:
        blocks.append("\n".join(_outlook_lines(outlook)))

    text = "\n".join(head)
    for block in blocks:
        candidate = text + "\n\n" + block
        if len(candidate) > MAX_MESSAGE_CHARS:
            text += "\n\n(more targets not shown)"
            break
        text = candidate
    return text[:MAX_MESSAGE_CHARS]


# ---- Telegram API -------------------------------------------------------------------------------


class TelegramClient:
    """Minimal Bot API client. Failures return None/False and never expose the token."""

    def __init__(self, token: str, post: Optional[Post] = None, get: Optional[Post] = None) -> None:
        import requests

        self._token = token
        self._post = post or requests.post
        self._get = get or requests.get

    def _call(self, fn: Post, method: str, **kwargs) -> Optional[dict]:
        try:
            response = fn(API_URL.format(token=self._token, method=method),
                          timeout=REQUEST_TIMEOUT, **kwargs)
            status = response.status_code
            if status != 200:
                logger.warning("Telegram %s returned HTTP %s", method, status)
                return None
            data = response.json()
        except Exception as exc:  # exception text can contain the URL, hence the token
            logger.warning("Telegram %s failed (%s)", method, type(exc).__name__)
            return None
        if not data.get("ok"):
            logger.warning("Telegram %s refused the request", method)
            return None
        return data

    def send_message(self, chat_id: str, text: str) -> bool:
        data = self._call(self._post, "sendMessage", json={
            "chat_id": chat_id, "text": text[:MAX_MESSAGE_CHARS],
            "disable_web_page_preview": True,
        })
        return data is not None

    def latest_chat(self) -> Optional[Dict[str, object]]:
        """The chat of the newest update that has one, as {"id": ..., "type": ...}."""
        data = self._call(self._get, "getUpdates", params={"timeout": 0})
        if data is None:
            return None
        for update in reversed(data.get("result", [])):
            for key in ("message", "edited_message", "channel_post"):
                chat = (update.get(key) or {}).get("chat")
                if chat and "id" in chat:
                    return {"id": chat["id"], "type": chat.get("type", "")}
        return None


# ---- the notifier -------------------------------------------------------------------------------


class TelegramNotifier:
    """Callable for `news_cli.watch(on_new_events=...)`. Returns how many alerts it sent."""

    def __init__(self, store, client: Optional[TelegramClient], chat_id: str,
                 max_per_hour: int = 10, threshold_pct: float = NEWS_ACTION_THRESHOLD_PCT,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self.store = store
        self.client = client
        self.chat_id = chat_id
        self.max_per_hour = max_per_hour
        self.threshold_pct = threshold_pct
        self.clock = clock
        self.enabled = client is not None and bool(chat_id)
        if not self.enabled:
            logger.warning("Telegram alerts are off: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID "
                           "in .env (see python -m stock_advisor.news.notify --setup).")

    def __call__(self, analyses: Sequence[EventAnalysis]) -> int:
        if not self.enabled:
            return 0
        sent, suppressed = 0, 0
        for analysis in analyses:
            targets = strong_targets(analysis, self.threshold_pct)
            if not (analysis.high_impact and targets):
                continue
            if self.store.alert_handled(analysis.event_id):
                continue
            now = self.clock()
            if self.store.alerts_sent_since(now - timedelta(hours=1)) >= self.max_per_hour:
                self.store.record_alert(analysis.event_id, now, kind="suppressed")
                suppressed += 1
                continue
            if self.client.send_message(self.chat_id, format_alert(analysis, targets)):
                self.store.record_alert(analysis.event_id, now)
                sent += 1
            # A failed send is not recorded, so a later batch can try it again.
        if suppressed:
            word = "alert" if suppressed == 1 else "alerts"
            self.client.send_message(
                self.chat_id,
                f"{suppressed} more {word} suppressed (limit {self.max_per_hour} per hour). "
                "Run news_cli to see them.")
        return sent


def build_notifier(store, post: Optional[Post] = None) -> TelegramNotifier:
    """Notifier from the settings (token, chat id, hourly limit). Inert when no token is set."""
    token = settings.telegram_bot_token()
    chat_id = settings.telegram_chat_id()
    client = TelegramClient(token, post=post) if token else None
    return TelegramNotifier(store, client, chat_id, settings.telegram_max_alerts_per_hour())


# ---- command line -------------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None, post: Optional[Post] = None,
         get: Optional[Post] = None, env_file=None, out=print) -> int:
    parser = argparse.ArgumentParser(description="Telegram alert setup and test.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--setup", action="store_true",
                       help="find the chat id from the bot's latest message and save it to .env")
    group.add_argument("--test", action="store_true", help="send one test message")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    token = settings.telegram_bot_token()
    if not token:
        out(NO_TOKEN_HELP)
        return 1
    client = TelegramClient(token, post=post, get=get)

    if args.setup:
        chat = client.latest_chat()
        if chat is None:
            out("No chat found. Send any message to your bot in Telegram, then run --setup again.")
            return 1
        settings.set_env_value("TELEGRAM_CHAT_ID", str(chat["id"]), env_file)
        out(f"Saved TELEGRAM_CHAT_ID (chat type: {chat['type'] or 'unknown'}) to .env. "
            "Now run --test.")
        return 0

    chat_id = settings.telegram_chat_id()
    if not chat_id:
        out("TELEGRAM_CHAT_ID is not set. Run --setup first.")
        return 1
    if client.send_message(chat_id, "Test alert from stock_advisor news monitor. "
                                    "If you can read this, alerts work."):
        out("Test message sent. Check your phone.")
        return 0
    out("Sending failed (see the warning above for the HTTP status).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
