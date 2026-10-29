"""Tests for the walk-forward backtest CLI, on a synthetic store and synthetic reactions."""

from __future__ import annotations

import json
import sqlite3
import zlib
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from stock_advisor import news_backtest_cli as B
from stock_advisor.news.model import load_fitted
from stock_advisor.news.models import Event, ItemScore, NewsItem
from stock_advisor.news.reactions import HORIZONS
from stock_advisor.news.scoring import embedding_to_bytes
from stock_advisor.news.store import NewsStore

DIM = 16
CATS = ["war_conflict", "monetary_policy", "other"]
EFFECT = {"war_conflict": -0.02, "monetary_policy": 0.015, "other": 0.0}
START = datetime(2016, 1, 1, tzinfo=timezone.utc)


def build_store(path, n: int = 600, years: int = 6, seed: int = 3, start=START) -> dict:
    """A store with n one-headline events; returns {event id: category}."""
    rng = np.random.default_rng(seed)
    centroids = {c: rng.normal(size=DIM) for c in CATS}
    offsets = np.sort(rng.uniform(0, years * 365 * 86400, size=n))
    store = NewsStore(path)
    categories = {}
    items, scores, events = [], [], []
    for i, off in enumerate(offsets):
        cat = CATS[rng.integers(len(CATS))]
        when = start + timedelta(seconds=float(off))
        item = NewsItem("rss", when, f"{cat} headline {i}", url=f"http://x/{seed}/{i}",
                        time_precision="day" if i % 7 == 0 else "exact")
        vec = (centroids[cat] + 0.5 * rng.normal(size=DIM)).astype(np.float32)
        event_id = f"e{seed}_{i:05d}"
        items.append(item)
        scores.append(ItemScore(item.id, tone=float(rng.uniform(-1, 1)),
                                embedding=embedding_to_bytes(vec), category=cat,
                                event_id=event_id))
        events.append(Event(event_id, when, cat, item.title, 1, 1, False))
        categories[event_id] = cat
    store.add_items(items)
    for score in scores:
        store.update_scores(score)
    for event in events:
        store.upsert_event(event)
    store.close()
    return categories


class FakeBuilder:
    """Stands in for build_reaction_table: planted effect on ^GSPC, pure noise on XLK.
    Only "1d" has values; the other horizons are NaN (no prices)."""

    def __init__(self, categories: dict) -> None:
        self.categories = categories
        self.calls = []  # (target, event ids)

    def __call__(self, events, targets, price_loader=None):
        events = list(events)
        self.calls.append((tuple(targets), [e.id for e in events]))
        rows = []
        for target in targets:
            for e in events:
                rng = np.random.default_rng(zlib.crc32(f"{e.id}|{target}".encode()))
                value = rng.normal(0, 0.005)
                if target == "^GSPC":
                    value += EFFECT[self.categories[e.id]]
                for horizon in HORIZONS:
                    v = value if horizon == "1d" else float("nan")
                    rows.append((e.id, target, horizon, v, v, pd.Timestamp(e.started_at),
                                 "1d"))
        return pd.DataFrame(rows, columns=["event_id", "target", "horizon", "raw",
                                           "adjusted", "start_ts", "start_source"])


def no_prices(symbol, interval):
    return None


def run_cli(tmp_path, builder, *extra):
    argv = ["--db", str(tmp_path / "news.db"), "--cache-dir", str(tmp_path / "model"),
            "--targets", "^GSPC", "XLK", "--horizons", "1d", "1h", *extra]
    return B.main(argv, price_loader=no_prices, reaction_builder=builder)


def test_cli_prints_table_saves_results_and_finds_planted_effect(tmp_path, capsys):
    categories = build_store(tmp_path / "news.db")
    builder = FakeBuilder(categories)
    assert run_cli(tmp_path, builder) == 0
    out = capsys.readouterr().out

    assert "Walk-forward results" in out
    for column in ("n", "hit_rate", "mean_signed", "t_stat", "proven"):
        assert column in out
    assert "Category summary at 1d" in out
    assert "war_conflict" in out

    saved = json.loads((tmp_path / "model" / "results.json").read_text(encoding="utf-8"))
    assert saved["version"] == B.RESULTS_VERSION
    assert saved["n_events"] == 600
    by_pair = {(r["target"], r["horizon"]): r for r in saved["results"]}
    assert set(by_pair) == {("^GSPC", "1d"), ("XLK", "1d")}  # 1h has no reactions
    assert {(s["target"], s["horizon"]) for s in saved["skipped"]} == {("^GSPC", "1h"),
                                                                        ("XLK", "1h")}
    gspc = by_pair[("^GSPC", "1d")]
    assert gspc["proven"] and gspc["n"] >= 400 and gspc["hit_rate"] > 0.7
    assert gspc["years"][0] == 2017  # the first year only trains
    assert not by_pair[("XLK", "1d")]["proven"]
    assert set(saved["market_moving"]) == {"war_conflict", "monetary_policy"}
    # Only 1d has values, so no analog has a finished 10d path: no window is usable.
    assert [w["target"] for w in saved["window"]] == ["^GSPC", "XLK"]
    assert all(w["windows"] == 0 and w["n"] == 0 for w in saved["window"])

    results = B.load_results(tmp_path / "model" / "results.json")
    assert results.is_proven("^GSPC", "1d")
    assert results.is_proven("^gspc", "1d")
    assert not results.is_proven("XLK", "1d")
    assert not results.is_proven("^GSPC", "1h")  # skipped -> not proven
    assert not results.is_proven("^HSI", "1d")  # never tested -> not proven


def test_normal_run_saves_the_fitted_models(tmp_path, capsys):
    categories = build_store(tmp_path / "news.db")
    assert run_cli(tmp_path, FakeBuilder(categories)) == 0
    assert "fitted target/horizon pairs" in capsys.readouterr().out
    fitted = load_fitted(tmp_path / "model" / B.FITTED_FILE)
    assert fitted.library_size == 600
    assert set(fitted.models) == {("^GSPC", "1d"), ("XLK", "1d")}  # 1h has no reactions


def test_fit_only_saves_models_and_skips_the_backtest(tmp_path, capsys):
    categories = build_store(tmp_path / "news.db")
    builder = FakeBuilder(categories)
    assert run_cli(tmp_path, builder, "--fit-only") == 0
    out = capsys.readouterr().out
    assert "Fitted 2 target/horizon pairs" in out and "Walk-forward" not in out
    assert not (tmp_path / "model" / B.RESULTS_FILE).exists()
    assert (tmp_path / "model" / B.REACTIONS_FILE).exists()  # reactions are still cached
    assert len(load_fitted(tmp_path / "model" / B.FITTED_FILE).models) == 2

    # An existing results.json is left alone.
    results = tmp_path / "model" / B.RESULTS_FILE
    results.write_text('{"keep": true}', encoding="utf-8")
    assert run_cli(tmp_path, builder, "--fit-only") == 0
    assert results.read_text(encoding="utf-8") == '{"keep": true}'


def test_reaction_cache_is_incremental(tmp_path):
    categories = build_store(tmp_path / "news.db", n=200)
    builder = FakeBuilder(categories)
    store = B.ReadOnlyStore(tmp_path / "news.db")
    events = B.load_event_records(store)
    store.close()
    cache = tmp_path / "model" / B.REACTIONS_FILE
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)  # nothing counts as recent

    first = B.load_or_build_reactions(events[:150], ["^GSPC"], cache, no_prices,
                                      builder=builder, now=now)
    assert len(first) == 150 * len(HORIZONS) and cache.exists()
    assert len(builder.calls[0][1]) == 150

    builder.calls.clear()
    second = B.load_or_build_reactions(events, ["^GSPC"], cache, no_prices,
                                       builder=builder, now=now)
    assert [len(ids) for _, ids in builder.calls] == [50]  # only the new events
    assert len(second) == 200 * len(HORIZONS)

    # A run over a sub-range returns only its events but keeps the rest in the cache.
    builder.calls.clear()
    part = B.load_or_build_reactions(events[:10], ["^GSPC"], cache, no_prices,
                                     builder=builder, now=now)
    assert builder.calls == [] and part["event_id"].nunique() == 10
    assert pd.read_parquet(cache)["event_id"].nunique() == 200

    # Recent events are rebuilt, since their later horizons may have lacked prices.
    builder.calls.clear()
    recent_now = events[-1].started_at + timedelta(days=1)
    B.load_or_build_reactions(events, ["^GSPC"], cache, no_prices, builder=builder,
                              now=recent_now)
    rebuilt = builder.calls[0][1]
    assert 0 < len(rebuilt) < 200
    assert all(events[-1].started_at - timedelta(days=B.REFRESH_DAYS + 1)
               <= next(e.started_at for e in events if e.id == i) for i in rebuilt)


def test_store_is_opened_read_only(tmp_path):
    build_store(tmp_path / "news.db", n=20)
    store = B.ReadOnlyStore(tmp_path / "news.db")
    with pytest.raises(sqlite3.OperationalError):
        store._conn.execute("DELETE FROM events")
    precisions = store.event_precisions()
    store.close()
    assert precisions["e3_00000"] == "day" and precisions["e3_00001"] == "exact"
    # An event with a batch and a day member is "batch"; adding an exact member makes it "exact".
    with sqlite3.connect(str(tmp_path / "news.db")) as conn:
        conn.execute("UPDATE items SET time_precision = 'batch' WHERE id IN "
                     "(SELECT item_id FROM scores WHERE event_id = 'e3_00000')")
    with B.ReadOnlyStore(tmp_path / "news.db") as store:
        assert store.event_precisions()["e3_00000"] == "batch"


def test_missing_store_and_missing_results(tmp_path):
    with pytest.raises(FileNotFoundError):
        B.ReadOnlyStore(tmp_path / "nope.db")
    results = B.load_results(tmp_path / "nope.json")
    assert not results.is_proven("^GSPC", "1d")
    assert results.market_moving() == []


def test_start_end_limit_events(tmp_path, capsys):
    categories = build_store(tmp_path / "news.db", n=300)
    assert run_cli(tmp_path, FakeBuilder(categories), "--start", "2018-01-01",
                   "--end", "2020-01-01") == 0
    saved = json.loads((tmp_path / "model" / "results.json").read_text(encoding="utf-8"))
    assert saved["first_event"] >= "2018-01-01" and saved["last_event"] < "2020-01-01"
    assert 0 < saved["n_events"] < 300


def test_category_summary_flags_moving_categories(tmp_path):
    categories = build_store(tmp_path / "news.db", n=400)
    store = B.ReadOnlyStore(tmp_path / "news.db")
    events = B.load_event_records(store)
    store.close()
    reactions = FakeBuilder(categories)(
        [B._ReactionEvent(e.id, e.started_at) for e in events], ["^GSPC", "XLK"])
    summary = B.category_summary(events, reactions, ["^GSPC", "XLK"], ["1d"])
    flags = {(r.target, r.category): r.moves for r in summary.itertuples()}
    assert flags[("^GSPC", "war_conflict")] and flags[("^GSPC", "monetary_policy")]
    gspc_war = summary[(summary.target == "^GSPC") & (summary.category == "war_conflict")]
    assert gspc_war["mean_return"].iloc[0] < -0.015
    assert not any(v for (t, _), v in flags.items() if t == "XLK")


def test_results_json_has_no_nan(tmp_path):
    categories = build_store(tmp_path / "news.db", n=40, years=1)  # one year: nothing to test on
    assert run_cli(tmp_path, FakeBuilder(categories)) == 0
    text = (tmp_path / "model" / "results.json").read_text(encoding="utf-8")
    assert "NaN" not in text
    saved = json.loads(text)
    assert [r["n"] for r in saved["results"]] == [0, 0]
    assert all(r["hit_rate"] is None and r["t_stat"] is None for r in saved["results"])
    assert len(saved["skipped"]) == 2


class PathBuilder(FakeBuilder):
    """Full reaction paths for ^GSPC: the category effect peaks at day 2, then reverses to
    minus half the effect by day 10 (so exiting at the window beats holding)."""

    SHAPE = {"1m": 0.05, "5m": 0.1, "15m": 0.15, "1h": 0.2, "4h": 0.3, "1d": 0.8, "2d": 1.0,
             "3d": 0.8, "5d": 0.4, "10d": -0.5}

    def __call__(self, events, targets, price_loader=None):
        rows = []
        for target in targets:
            for e in events:
                rng = np.random.default_rng(zlib.crc32(f"{e.id}|{target}".encode()))
                effect = EFFECT[self.categories[e.id]]
                for horizon in HORIZONS:
                    v = effect * self.SHAPE[horizon] + rng.normal(0, 0.002)
                    rows.append((e.id, target, horizon, v, v, pd.Timestamp(e.started_at), "1m"))
        return pd.DataFrame(rows, columns=["event_id", "target", "horizon", "raw",
                                           "adjusted", "start_ts", "start_source"])


def test_window_section_beats_holding_when_moves_reverse(tmp_path, capsys):
    categories = build_store(tmp_path / "news.db", n=400)
    argv = ["--db", str(tmp_path / "news.db"), "--cache-dir", str(tmp_path / "model"),
            "--targets", "^GSPC", "--horizons", "1d"]
    assert B.main(argv, price_loader=no_prices, reaction_builder=PathBuilder(categories)) == 0
    out = capsys.readouterr().out
    assert "Profitable window" in out and "follow_window" in out and "hold_10d" in out
    saved = json.loads((tmp_path / "model" / "results.json").read_text(encoding="utf-8"))
    (row,) = saved["window"]
    assert row["target"] == "^GSPC" and row["n"] > 100 and row["windows"] >= row["n"]
    assert row["mean_window"] > 0.005 and row["mean_hold"] < 0
    assert row["mean_diff"] > 0 and row["t_stat"] > 2 and row["beat_rate"] > 0.5