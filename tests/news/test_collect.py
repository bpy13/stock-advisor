"""Collector tests with fake adapters and a tmp_path store (no network)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from stock_advisor.news import collect
from stock_advisor.news.models import NewsItem, SourceLimitReached
from stock_advisor.news.store import NewsStore

T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _item(source, n, when=None, **kw) -> NewsItem:
    return NewsItem(source=source, published_at=when or T0 + timedelta(days=n),
                    title=f"{source} headline {n}", url=f"https://x/{source}/{n}", **kw)


class FakeSource:
    def __init__(self, name, recent=(), history=(), fail=False, budget_calls=0):
        self.name = name
        self._recent = list(recent)
        self._history = list(history)
        self._fail = fail
        self._budget_calls = budget_calls
        self.budget = None
        self.range_args = []

    def fetch_recent(self):
        if self._fail:
            raise RuntimeError("boom")
        return list(self._recent)

    def fetch_range(self, start, end):
        self.range_args.append((start, end))
        for item in self._history:
            if not start <= item.published_at <= end:
                continue
            if self.budget is not None and not self.budget():  # one "API call" per item
                raise SourceLimitReached("daily budget used up")
            yield item


@pytest.fixture
def store(tmp_path):
    with NewsStore(tmp_path / "news.db") as s:
        yield s


def test_recent_stores_every_source_and_one_failure_does_not_stop_the_rest(store):
    sources = [
        FakeSource("a", recent=[_item("a", 0), _item("a", 1)]),
        FakeSource("bad", fail=True),
        FakeSource("c", recent=[_item("c", 0)]),
    ]
    results = collect.collect_recent(store, sources)
    assert [(r.name, r.fetched, r.new, r.status) for r in results] == [
        ("a", 2, 2, "ok"), ("bad", 0, 0, "failed"), ("c", 1, 1, "ok")]
    assert store.counts_by_source() == {"a": 2, "c": 1}
    again = collect.collect_recent(store, sources)
    assert [r.new for r in again] == [0, 0, 0]  # nothing stored twice


def test_recent_reports_limit_status(store):
    class Limited(FakeSource):
        def fetch_recent(self):
            raise SourceLimitReached("cap")

    [result] = collect.collect_recent(store, [Limited("a")])
    assert result.status == "limit"


def test_backfill_stores_range_and_resumes_after_recent_run(store):
    history = [_item("a", n) for n in range(10)]
    source = FakeSource("a", history=history)
    end = T0 + timedelta(days=20)
    collect.collect_recent(store, [FakeSource("a", recent=[_item("a", 19)])])  # live item
    result = collect.backfill_source(store, source, T0, end)
    assert result.status == "ok" and result.new == 10
    assert source.range_args[0][0] == T0  # the live item did not move the start
    # A second run starts at the cursor (the end of the finished range), not at T0.
    again = FakeSource("a", history=history)
    collect.backfill_source(store, again, T0, end)
    assert again.range_args[0][0] == end


def test_backfill_stops_at_daily_budget_and_resumes_next_run(store):
    history = [_item("guardian", n) for n in range(10)]
    budgets = {"guardian": 4}
    end = T0 + timedelta(days=30)
    first = collect.backfill_source(store, FakeSource("guardian", history=history), T0, end,
                                    budgets=budgets, batch_size=1)
    assert first.status == "limit"
    assert first.new == 4
    assert store.calls_today("guardian") == 4
    # Same day: no budget left, nothing new.
    blocked = collect.backfill_source(store, FakeSource("guardian", history=history), T0, end,
                                      budgets=budgets, batch_size=1)
    assert blocked.status == "limit" and blocked.new == 0
    # Next day (fresh counter): continues from the last stored date, not from the start.
    with store._conn:
        store._conn.execute("DELETE FROM api_calls")
    resumed = FakeSource("guardian", history=history)
    collect.backfill_source(store, resumed, T0, end, budgets=budgets, batch_size=1)
    assert resumed.range_args[0][0] == T0 + timedelta(days=3)
    assert store.count_items("guardian") == 7  # items 0-3, then 3 (stored again) to 6


def test_backfill_rate_limit_http_error_stops_cleanly(store):
    import requests

    class Limited(FakeSource):
        def fetch_range(self, start, end):
            yield _item("a", 0)
            response = requests.Response()
            response.status_code = 429
            raise requests.HTTPError(response=response)

    result = collect.backfill_source(store, Limited("a"), T0, T0 + timedelta(days=5))
    assert result.status == "limit"
    assert store.count_items("a") == 1  # what was fetched before the limit is kept


def test_backfill_source_without_history_fails_cleanly(store):
    class RecentOnly:
        name = "yahoo"

        def fetch_recent(self):
            return []

    assert collect.backfill_source(store, RecentOnly(), T0).status == "failed"


def test_main_recent_prints_count_per_source(tmp_path, capsys):
    sources = [FakeSource("a", recent=[_item("a", 0)]), FakeSource("b", recent=[_item("b", 0)])]
    code = collect.main(["--recent", "--db", str(tmp_path / "n.db")], sources=sources)
    out = capsys.readouterr().out
    assert code == 0
    assert "a " in out and "b " in out and "total" in out and "elapsed" in out


def test_main_backfill_requires_source_and_start(tmp_path):
    with pytest.raises(SystemExit):
        collect.main(["--backfill", "--db", str(tmp_path / "n.db")], sources=[])


def test_main_backfill_runs_one_source(tmp_path, capsys):
    history = [_item("a", n) for n in range(3)]
    sources = [FakeSource("a", history=history), FakeSource("b", fail=True)]
    code = collect.main(["--backfill", "--source", "a", "--start", "2024-01-01",
                         "--end", "2024-02-01", "--db", str(tmp_path / "n.db")], sources=sources)
    assert code == 0
    assert "3" in capsys.readouterr().out


def test_build_sources_covers_the_working_adapters_and_holdings():
    sources = {s.name: s for s in collect.build_sources(["AAPL", "0700.HK", "ZZZZ"])}
    assert set(sources) == {"wikipedia_events", "gdelt", "guardian", "nyt", "yahoo", "edgar", "rss"}
    assert "0700.HK" in sources["yahoo"].symbols
    assert "ZZZZ" in sources["edgar"]._tickers and "0700.HK" not in sources["edgar"]._tickers


# ---- store additions: time_precision, migration, call budget ---------------------------------


def test_time_precision_round_trips_and_defaults_to_exact(store):
    store.add_items([_item("a", 0), _item("w", 0, time_precision="day")])
    assert store.get_item(_item("a", 0).id).time_precision == "exact"
    assert store.get_item(_item("w", 0).id).time_precision == "day"


def test_old_database_is_migrated(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE items (id TEXT PRIMARY KEY, source TEXT NOT NULL, published_at TEXT NOT NULL,"
        " title TEXT NOT NULL, url TEXT NOT NULL DEFAULT '', summary TEXT NOT NULL DEFAULT '',"
        " symbols TEXT NOT NULL DEFAULT '[]', language TEXT NOT NULL DEFAULT 'en', body TEXT)"
    )
    rows = [("1", "wikipedia_events", "2024-01-01T00:00:00.000000+00:00"),
            ("2", "edgar", "2024-01-01T00:00:00.000000+00:00"),
            ("3", "edgar", "2024-01-01T13:45:10.000000+00:00"),
            ("4", "guardian", "2024-01-01T00:00:00.000000+00:00")]
    conn.executemany("INSERT INTO items (id, source, published_at, title) VALUES (?, ?, ?, 't')", rows)
    conn.commit()
    conn.close()
    with NewsStore(path) as migrated:
        precision = {i.id: i.time_precision for i in migrated.query_items()}
        assert precision == {"1": "day", "2": "day", "3": "exact", "4": "exact"}
    with NewsStore(path):  # opening again is harmless
        pass


def test_spend_call_enforces_cap_per_day(store):
    assert [store.spend_call("nyt", 2, day="2026-10-27") for _ in range(3)] == [True, True, False]
    assert store.calls_today("nyt", day="2026-10-27") == 2
    assert store.spend_call("nyt", 2, day="2026-10-28") is True  # new day, fresh counter
    assert store.spend_call("guardian", 2, day="2026-10-27") is True  # separate per source
