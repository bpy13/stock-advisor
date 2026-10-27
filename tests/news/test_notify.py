"""Telegram notifier tests. The Telegram API is mocked; nothing touches the network."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest

from stock_advisor.news import notify
from stock_advisor.news.analysis import EventAnalysis, HorizonForecast, TargetOutlook
from stock_advisor.news.store import NewsStore

TOKEN = "123456:SECRET-TOKEN-VALUE"
NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload if payload is not None else {"ok": True, "result": []}

    def json(self):
        return self._payload


class FakeApi:
    """Records calls; `post`/`get` have the shape of requests.post/get."""

    def __init__(self, response=None, error=None):
        self.calls = []
        self.response = response or FakeResponse()
        self.error = error

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return self.response

    @property
    def texts(self):
        return [kw["json"]["text"] for _, kw in self.calls]


def forecast(h, pred, proven=True):
    return HorizonForecast(h, pred, pred - 0.01, pred + 0.01, proven=proven, n_train=50)


def outlook(target, move, proven=True):
    o = TargetOutlook(target)
    o.forecasts = {"1m": forecast("1m", move / 10, proven), "1h": forecast("1h", move / 3, proven),
                   "1d": forecast("1d", move, proven)}
    o.action, o.action_proven, o.has_prediction = "reduce", proven, True
    o.window_text = "sell within 2 h of the event"
    return o


def make_analysis(event_id="e1", move=-0.02, proven=False, high=True, spare=0.001):
    a = EventAnalysis(
        event_id=event_id, started_at=NOW, category="war", title="Missiles hit port <city> & more",
        link="https://www.theguardian.com/world/x", high_impact=high, n_items=3, n_sources=2,
        sources=["guardian", "rss:BBC World"])
    a.outlooks = {"^GSPC": outlook("^GSPC", move, proven), "^HSI": outlook("^HSI", spare, proven)}
    return a


@pytest.fixture
def store(tmp_path):
    with NewsStore(tmp_path / "n.db") as s:
        yield s


def notifier(store, api, max_per_hour=10, clock=lambda: NOW):
    client = notify.TelegramClient(TOKEN, post=api, get=api)
    return notify.TelegramNotifier(store, client, "42", max_per_hour, clock=clock)


# ---- format -------------------------------------------------------------------------------------


def test_message_has_badge_headline_link_sources_and_only_strong_targets():
    text = notify.format_alert(make_analysis())
    assert text.startswith("⚠ unproven")
    assert "Missiles hit port <city> & more" in text  # plain text: nothing to escape
    assert "https://www.theguardian.com/world/x" in text
    assert "sources: guardian, rss:BBC World" in text
    assert "^GSPC: 1m -0.20% (-1.20% to +0.80%) | 1h -0.67%" in text
    assert "1d -2.00% (-3.00% to -1.00%)" in text
    assert "action: reduce (unproven); window: sell within 2 h of the event" in text
    assert "^HSI" not in text  # 0.1% move is below the threshold


def test_proven_forecasts_have_no_badge():
    text = notify.format_alert(make_analysis(proven=True))
    assert "unproven" not in text


def test_message_never_exceeds_the_telegram_limit():
    a = make_analysis()
    a.title = "x" * 5000
    assert len(notify.format_alert(a)) <= notify.MAX_MESSAGE_CHARS
    a2 = make_analysis()
    a2.outlooks = {f"T{i}": outlook(f"T{i}", -0.02) for i in range(80)}
    text = notify.format_alert(a2)
    assert len(text) <= notify.MAX_MESSAGE_CHARS and "more targets not shown" in text


# ---- sending, dedup, rate limit -----------------------------------------------------------------


def test_alert_sent_once_and_recorded(store):
    api = FakeApi()
    n = notifier(store, api)
    assert n([make_analysis()]) == 1
    assert n([make_analysis()]) == 0  # same event again
    assert len(api.calls) == 1
    url, kw = api.calls[0]
    assert url.endswith("/sendMessage") and kw["json"]["chat_id"] == "42"
    assert store.alert_handled("e1")


def test_dedup_survives_a_restart(store):
    api = FakeApi()
    notifier(store, api)([make_analysis()])
    notifier(store, api)([make_analysis()])  # new notifier, same store
    assert len(api.calls) == 1


def test_weak_or_not_high_impact_events_are_skipped(store):
    api = FakeApi()
    n = notifier(store, api)
    n([make_analysis("weak", move=-0.005), make_analysis("low", high=False)])
    assert api.calls == []


def test_rate_limit_suppresses_and_sends_one_summary(store):
    api = FakeApi()
    n = notifier(store, api, max_per_hour=2)
    batch = [make_analysis(f"e{i}") for i in range(5)]
    assert n(batch) == 2
    assert len(api.calls) == 3
    assert "3 more alerts suppressed" in api.texts[-1]
    assert n(batch) == 0  # suppressed events are not retried
    assert len(api.calls) == 3


def test_rate_limit_is_a_rolling_hour(store):
    api = FakeApi()
    times = iter([NOW, NOW + timedelta(minutes=30), NOW + timedelta(minutes=61)])
    n = notifier(store, api, max_per_hour=1, clock=lambda: next(times))
    n([make_analysis("a")])
    n([make_analysis("b")])  # inside the hour: suppressed (summary call uses no clock)
    n([make_analysis("c")])  # 61 min after "a": allowed
    assert [t.split("\n")[0] for t in api.texts if "suppressed" not in t].count("⚠ unproven") == 2


def test_failed_send_is_not_recorded_and_logs_no_token(store, caplog):
    api = FakeApi(error=RuntimeError(f"boom https://api.telegram.org/bot{TOKEN}/sendMessage"))
    n = notifier(store, api)
    with caplog.at_level(logging.DEBUG):
        assert n([make_analysis()]) == 0
    assert not store.alert_handled("e1")
    assert TOKEN not in caplog.text and "SECRET" not in caplog.text
    assert "RuntimeError" in caplog.text


def test_http_error_logs_status_only(store, caplog):
    api = FakeApi(response=FakeResponse(401, {"ok": False}))
    with caplog.at_level(logging.DEBUG):
        notifier(store, api)([make_analysis()])
    assert "HTTP 401" in caplog.text and TOKEN not in caplog.text


def test_without_token_the_notifier_warns_once_and_does_nothing(store, caplog):
    with caplog.at_level(logging.WARNING):
        n = notify.TelegramNotifier(store, None, "")
        assert n([make_analysis()]) == 0
        assert n([make_analysis()]) == 0
    assert caplog.text.count("Telegram alerts are off") == 1
    assert not store.alert_handled("e1")


def test_store_migration_adds_sent_alerts_to_an_old_database(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE items (id TEXT PRIMARY KEY, source TEXT NOT NULL, "
                 "published_at TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL DEFAULT '', "
                 "summary TEXT NOT NULL DEFAULT '', symbols TEXT NOT NULL DEFAULT '[]', "
                 "language TEXT NOT NULL DEFAULT 'en', body TEXT)")
    conn.commit()
    conn.close()
    with NewsStore(path) as s:
        s.record_alert("x", NOW)
        assert s.alert_handled("x") and s.alerts_sent_since(NOW) == 1


def test_news_cli_has_no_alerts_flag():
    from stock_advisor import news_cli

    parser = news_cli.build_arg_parser()
    assert parser.parse_args(["--watch", "--no-alerts"]).no_alerts is True
    assert parser.parse_args(["--watch"]).no_alerts is False


# ---- command line -------------------------------------------------------------------------------


def test_setup_and_test_without_token_exit_1(monkeypatch):
    monkeypatch.setattr(notify.settings, "get_setting", lambda name: "")
    lines = []
    assert notify.main(["--setup"], out=lines.append) == 1
    assert notify.main(["--test"], out=lines.append) == 1
    assert all("TELEGRAM_BOT_TOKEN" in line for line in lines)


def test_setup_saves_chat_id_to_env_file_without_echoing_it(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")  # set_env_value writes os.environ; restore after
    env = tmp_path / ".env"
    env.write_text("KEEP=1\nTELEGRAM_CHAT_ID=\nOTHER=2\n", encoding="utf-8")
    monkeypatch.setattr(notify.settings, "get_setting",
                        lambda name: TOKEN if name == "TELEGRAM_BOT_TOKEN" else "")
    updates = {"ok": True, "result": [
        {"message": {"chat": {"id": 111, "type": "private"}}},
        {"message": {"chat": {"id": 777, "type": "private"}}}]}
    api = FakeApi(response=FakeResponse(200, updates))
    lines = []
    assert notify.main(["--setup"], get=api, env_file=env, out=lines.append) == 0
    assert env.read_text(encoding="utf-8") == "KEEP=1\nTELEGRAM_CHAT_ID=777\nOTHER=2\n"
    assert "777" not in "".join(lines) and TOKEN not in "".join(lines)


def test_setup_with_no_messages_asks_user_to_message_the_bot(monkeypatch, tmp_path):
    monkeypatch.setattr(notify.settings, "get_setting", lambda name: TOKEN)
    lines = []
    code = notify.main(["--setup"], get=FakeApi(), env_file=tmp_path / ".env", out=lines.append)
    assert code == 1 and "Send any message" in lines[0]


def test_test_command_sends_one_message(monkeypatch):
    monkeypatch.setattr(notify.settings, "get_setting",
                        lambda name: TOKEN if name == "TELEGRAM_BOT_TOKEN" else "42")
    api = FakeApi()
    lines = []
    assert notify.main(["--test"], post=api, out=lines.append) == 0
    assert len(api.calls) == 1 and api.calls[0][1]["json"]["chat_id"] == "42"
    assert TOKEN not in "".join(lines)
