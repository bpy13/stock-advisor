"""Tests for the news CLI and watcher: fake sources and models, tmp_path store, no network."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from stock_advisor import news_cli
from stock_advisor.news import analysis as A
from stock_advisor.news import categories
from stock_advisor.news.model import FittedFile, load_fitted
from stock_advisor.news.models import NewsItem
from stock_advisor.news.scoring import EMBED_DIM
from stock_advisor.news.store import NewsStore
from stock_advisor.news_backtest_cli import BacktestResults
from tests.news.test_analysis import (
    DIM,
    FakeEmbedder,
    FakeFinBert,
    add_event,
    fit_and_save,
    past_history,
)

NOW = datetime.now(timezone.utc)  # the CLI uses the real clock; events are placed relative to it
UNPROVEN = "\u26a0 unproven"
EMPTY_FITTED = FittedFile("2026-01-01T00:00:00+00:00", 0, {})  # no models: predictions are n/a


def price_loader(symbol, interval):
    return None


def run_cli(db, argv, reactions, proven=(), **kwargs):
    """Run the CLI on a tmp store. With reactions, fit and load models like the backtest does;
    without, an empty reaction table and an empty fitted file (never the real data files)."""
    lines = []
    results = BacktestResults({"results": [
        {"target": t, "horizon": h, "proven": True} for t, h in proven]})
    if reactions is None:
        reactions, fitted = pd.DataFrame(columns=A.REACTION_COLUMNS), EMPTY_FITTED
    else:
        with NewsStore(db) as store:
            path = fit_and_save(store, reactions, Path(db).with_name("fitted.pkl"))
        fitted = load_fitted(path)
    code = news_cli.main(["--db", str(db), "--targets", "^GSPC", "^HSI", *argv],
                         price_loader=price_loader, results=results, reactions=reactions,
                         fitted=fitted, out=lines.append, **kwargs)
    return code, "\n".join(lines)


def seed_store(path, with_history=True):
    """A store with one fresh war event; optionally 45 past events (see past_history)."""
    with NewsStore(path) as store:
        if with_history:
            vec, reactions = past_history(store)
        else:
            # Full-size vector, orthogonal to the all-ones vector of FakeEmbedder, so fresh
            # headlines start their own event instead of joining this one.
            vec, reactions = np.where(np.arange(EMBED_DIM) % 2, 1.0, -1.0), None
        add_event(store, "now", NOW - timedelta(hours=1), vec, title="Missiles hit port city",
                  source="guardian", summary="HIDDEN-SUMMARY", url="https://guardian.test/a")
    return reactions


def test_report_with_history_shows_everything(tmp_path):
    db = tmp_path / "news.db"
    reactions = seed_store(db)
    code, text = run_cli(db, [], reactions)
    assert code == 0
    assert "war_conflict" in text and "HIGH IMPACT" in text
    assert "Missiles hit port city" in text and "https://guardian.test/a" in text
    assert "HIDDEN-SUMMARY" not in text  # Guardian: headline and link only
    assert "sources: guardian" in text
    assert text.count("    20") >= 5  # five similar past events, each starting with its date
    assert "^GSPC: 1m" in text and "1h" in text and "1d" in text and "80% range" in text
    assert "action: reduce" in text and UNPROVEN in text
    assert "window:" in text
    assert "fitted target/horizon pairs" in text


def test_proven_target_drops_the_warning_on_the_action_line(tmp_path):
    db = tmp_path / "news.db"
    reactions = seed_store(db)
    proven = [(t, h) for t in ("^GSPC", "^HSI") for h in ("1m", "1h", "1d")]
    _, text = run_cli(db, [], reactions, proven=proven)
    assert "action: reduce" in text
    assert UNPROVEN not in text


def test_report_with_no_history_says_so_and_does_not_crash(tmp_path):
    db = tmp_path / "news.db"
    seed_store(db, with_history=False)
    code, text = run_cli(db, [], None)
    assert code == 0
    assert "no fitted model yet" in text
    assert "none yet (not enough history" in text
    assert "1d n/a" in text and "action: hold (no prediction yet)" in text


def test_empty_store_prints_a_hint(tmp_path):
    code, text = run_cli(tmp_path / "news.db", [], None)
    assert code == 0 and "0 found" in text and "--collect" in text


def test_limit_hides_extra_events(tmp_path):
    db = tmp_path / "news.db"
    with NewsStore(db) as store:
        for k in range(3):
            add_event(store, f"e{k}", NOW - timedelta(hours=k + 1),
                      np.roll(np.arange(1, DIM + 1), k))
    _, text = run_cli(db, ["--limit", "1"], None)
    assert "3 found, showing 1" in text and "2 more events not shown" in text


# ---- collect and watch ---------------------------------------------------------------------------


class FakeSource:
    def __init__(self, name, items=()):
        self.name = name
        self.items = list(items)
        self.calls = 0

    def fetch_recent(self):
        self.calls += 1
        return list(self.items)


@pytest.fixture()
def war_centroids(monkeypatch):
    """Make every fake headline (all-ones vector) closest to war_conflict, a macro category."""
    names = categories._centroid_names
    rng = np.random.default_rng(2)
    matrix = rng.normal(size=(len(names), EMBED_DIM)).astype(np.float32)
    matrix[names.index("war_conflict")] = 1.0
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    monkeypatch.setattr(categories, "_centroids", matrix)


def fresh_item(n):
    return NewsItem("fake", datetime.now(timezone.utc) - timedelta(minutes=n),
                    f"Border clash escalates {n}", url=f"https://news.test/{n}")


def test_collect_scores_and_shows_new_event(tmp_path, war_centroids):
    db = tmp_path / "news.db"
    sources = A.WatchSources(fast=[FakeSource("fake", [fresh_item(1), fresh_item(2)])])
    code, text = run_cli(db, ["--collect"], None, sources=sources, finbert=FakeFinBert(),
                         embedder=FakeEmbedder())
    assert code == 0
    assert "Collected 2 new headlines" in text
    assert "Scored 2 items, categorized 2, placed 2 in events." in text
    assert "Border clash escalates" in text and "war_conflict" in text


def test_watch_prints_only_new_high_impact_events_and_calls_the_hook(tmp_path, war_centroids):
    db = tmp_path / "news.db"
    seed_store(db, with_history=False)  # one high-impact event already known
    source = FakeSource("fake")
    sources = A.WatchSources(fast=[source], slow=[FakeSource("slow")])
    sleeps, hooked = [], []

    def sleeper(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 1:  # between cycles 1 and 2 a story breaks
            source.items = [fresh_item(1), fresh_item(2), fresh_item(3)]

    code, text = run_cli(db, ["--watch"], None, sources=sources, finbert=FakeFinBert(),
                         embedder=FakeEmbedder(), sleep=sleeper, max_cycles=3, background_slow=False,
                         on_new_events=lambda analyses: hooked.append(list(analyses)))
    assert code == 0
    assert "1 high-impact events already known" in text
    assert text.count("Border clash escalates") >= 1
    assert text.count("HIGH IMPACT") == 1  # the event known before the watch is not printed
    assert "  Missiles hit port city\n" not in text
    assert len(hooked) == 1 and len(hooked[0]) == 1  # one call, one new event, cycle 3 repeats nothing
    assert hooked[0][0].high_impact
    assert sleeps and all(s >= 1 for s in sleeps)


def test_watch_slow_group_runs_on_its_own_schedule(tmp_path):
    db = tmp_path / "news.db"
    fast, slow = FakeSource("fast"), FakeSource("slow")
    ticks = iter(range(0, 10_000, 60))  # a fake clock that moves 60 s per call
    news_cli.main(["--db", str(db), "--watch", "--targets", "^GSPC"],
                  sources=A.WatchSources([fast], [slow]), price_loader=price_loader,
                  results=BacktestResults({}),
                  reactions=pd.DataFrame(columns=A.REACTION_COLUMNS), fitted=EMPTY_FITTED,
                  finbert=FakeFinBert(),
                  embedder=FakeEmbedder(), out=lambda *_: None, sleep=lambda s: None,
                  clock=lambda: float(next(ticks)), max_cycles=10, slow_interval=300,
                  background_slow=False)
    assert fast.calls == 10
    assert 2 <= slow.calls < 10  # first cycle, then roughly every fifth


def test_watch_survives_a_failing_cycle_and_a_failing_hook(tmp_path, war_centroids, caplog):
    db = tmp_path / "news.db"
    seed_store(db, with_history=False)
    source = FakeSource("fake", [fresh_item(1), fresh_item(2), fresh_item(3)])
    sources = A.WatchSources(fast=[source])
    calls = {"n": 0}

    def hook(analyses):
        calls["n"] += 1
        raise RuntimeError("telegram down")

    with caplog.at_level(logging.WARNING):
        code, text = run_cli(db, ["--watch"], None, sources=sources, finbert=FakeFinBert(),
                             embedder=FakeEmbedder(), sleep=lambda s: None, max_cycles=2, background_slow=False,
                             on_new_events=hook)
    assert code == 0 and calls["n"] == 1
    assert "on_new_events failed" in caplog.text


def test_watch_stops_cleanly_on_ctrl_c(tmp_path):
    db = tmp_path / "news.db"

    def interrupt(seconds):
        raise KeyboardInterrupt

    code, text = run_cli(db, ["--watch"], None,
                         sources=A.WatchSources(fast=[FakeSource("fast")]),
                         finbert=FakeFinBert(), embedder=FakeEmbedder(), sleep=interrupt)
    assert code == 0 and "Stopped." in text


def test_gdelt_is_skipped_while_the_backfill_runs_it(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "gdelt_busy", lambda *a, **k: True)
    gdelt, other = FakeSource("gdelt"), FakeSource("other")
    with NewsStore(tmp_path / "n.db") as store:
        A.collect_group(store, [gdelt, other], skip_gdelt=A.gdelt_busy())
    assert gdelt.calls == 0 and other.calls == 1
