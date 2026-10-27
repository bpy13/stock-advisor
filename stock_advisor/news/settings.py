"""Settings and secrets for the news module, read from the gitignored `.env`."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = _REPO_ROOT / ".env"
NEWS_CACHE_DIR = _REPO_ROOT / "data" / "cache" / "news"
DEFAULT_DB_PATH = NEWS_CACHE_DIR / "news.db"


def load_env(env_file: Optional[Path] = None) -> None:
    """Load `.env` into the process environment. Existing variables are not overwritten."""
    load_dotenv(env_file or ENV_FILE, override=False)


def get_setting(name: str) -> str:
    """Return one setting from the environment (after loading `.env`), or "" if unset."""
    load_env()
    return os.environ.get(name, "").strip()


def sec_contact_email() -> str:
    return get_setting("SEC_CONTACT_EMAIL")


def guardian_api_key() -> str:
    return get_setting("GUARDIAN_API_KEY")


def nyt_api_key() -> str:
    return get_setting("NYT_API_KEY")


def telegram_bot_token() -> str:
    return get_setting("TELEGRAM_BOT_TOKEN")


def telegram_chat_id() -> str:
    return get_setting("TELEGRAM_CHAT_ID")


def telegram_max_alerts_per_hour(default: int = 10) -> int:
    """Hourly alert limit (TELEGRAM_MAX_ALERTS_PER_HOUR); a bad value falls back to the default."""
    try:
        return max(1, int(get_setting("TELEGRAM_MAX_ALERTS_PER_HOUR") or default))
    except ValueError:
        return default


def set_env_value(key: str, value: str, env_file: Optional[Path] = None) -> None:
    """Set one `KEY=value` line in `.env`: replace that key's line or append it.

    Other lines are kept as they are, and nothing is printed."""
    path = env_file or ENV_FILE
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    new_line = f"{key}={value}"
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == key:
            lines[i] = new_line
            break
    else:
        lines.append(new_line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ[key] = value
