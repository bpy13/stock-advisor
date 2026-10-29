import pytest


@pytest.fixture(autouse=True)
def _no_real_memory_guard(monkeypatch):
    """Mark the guard as already started so `news_cli.main --watch` starts no real thread.

    tests/test_memory_guard.py resets the flag for its own tests.
    """
    monkeypatch.setattr("stock_advisor.memory_guard._started", True)


@pytest.fixture(autouse=True)
def _no_real_telegram(monkeypatch):
    """Blank the Telegram settings so no test can send a real alert to Brian's phone.

    `settings.load_env` never overwrites variables that already exist, so these empty values
    win over the real token in `.env`. A test that needs a token sets its own fake one.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
