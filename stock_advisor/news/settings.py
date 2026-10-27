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
