"""Tests for the analog and regression model, on synthetic events and reactions only."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from stock_advisor.news import model as M
from stock_advisor.news.model import EventLibrary, EventRecord, NewsModel
from stock_advisor.news.models import Event, ItemScore, NewsItem
from stock_advisor.news.scoring import embedding_to_bytes
from stock_advisor.news.store import NewsStore

DIM = 16
CATS = ["war_conflict", "monetary_policy", "trade_tariffs", "other"]
EFFECT = {"war_conflict": -0.015, "monetary_policy": 0.01, "trade_tariffs": -0.004, "other": 0.0}
START = datetime(2015, 1, 1, tzinfo=timezone.utc)


def make_events(n: int, seed: int, years: int = 8) -> list[EventRecord]:
    """Events spread over `years`; embeddings cluster by category."""
    rng = np.random.default_rng(seed)
    centroids = {c: rng.normal(size=DIM) for c in CATS}
    offsets = np.sort(rng.uniform(0, years * 365 * 86400, size=n))
    events = []
    for i, off in enumerate(offsets):
        cat = CATS[rng.integers(len(CATS))]
        events.append(EventRecord(
            id=f"ev{i:05d}", started_at=START + timedelta(seconds=float(off)),
            embedding=(centroids[cat] + 0.6 * rng.normal(size=DIM)).astype(np.float32),
            category=cat, tone=float(rng.uniform(-1, 1)), n_sources=int(rng.integers(1, 6)),
            high_impact=bool(rng.integers(2)), title=f"{cat} headline {i}",
        ))
    return events


def make_reactions(events, seed: int, planted: bool, targets=("^GSPC",),
                   horizons=("1d",), source: str = "1m") -> pd.DataFrame:
    rng = np.random.default_rng(seed + 1000)
    rows = []
    for target in targets:
        for horizon in horizons:
            for e in events:
                value = rng.normal(0, 0.006)
                if planted:
                    value += EFFECT[e.category] + 0.004 * e.tone
                rows.append((e.id, target, horizon, value, value - 0.001,
                             pd.Timestamp(e.started_at), source))
    return pd.DataFrame(rows, columns=["event_id", "target", "horizon", "raw", "adjusted",
                                       "start_ts", "start_source"])


def new_event(category: str, when: datetime, seed: int = 0, tone: float = -0.5) -> EventRecord:
    """An event outside the library, built from the same centroids as make_events(seed)."""
    rng = np.random.default_rng(seed)
    centroids = {c: rng.normal(size=DIM) for c in CATS}
    return EventRecord("live", when, centroids[category].astype(np.float32), category, tone, 4,
                       True, "live headline")


# ---- the done-when: planted effect found, noise not proven ----------------------------------


def test_planted_effect_is_found_and_proven():
    events = make_events(1200, seed=1)
    model = NewsModel(EventLibrary(events), make_reactions(events, 1, planted=True))
    result = model.walk_forward("^GSPC", "1d")
    assert result.proven
    assert result.n >= 900
    assert result.hit_rate > 0.7
    assert result.t_stat > 5

    model.fit(["^GSPC"], ["1d"])
    coef = model.coefficients("^GSPC", "1d")
    # War is bad news either directly or through the analog mean (they are collinear).
    assert coef["cat_war_conflict"] < 0 or coef["analog_mean"] > 0
    assert coef["tone"] > 0

    live = new_event("war_conflict", datetime(2023, 6, 1, tzinfo=timezone.utc), seed=1)
    pred = model.predict(live, "^GSPC", "1d")
    assert pred.return_kind == "raw"
    assert pred.predicted < -0.01
    assert pred.low < pred.predicted < pred.high
    assert len(pred.analogs) == 20
    assert sum(a.category == "war_conflict" for a in pred.analogs) >= 18
    assert pred.analog_mean == pytest.approx(
        np.average([a.reaction for a in pred.analogs], weights=[a.similarity for a in pred.analogs]))


def test_pure_noise_is_not_proven():
    events = make_events(1200, seed=2)
    model = NewsModel(EventLibrary(events), make_reactions(events, 2, planted=False))
    result = model.walk_forward("^GSPC", "1d")
    assert result.n >= 900
    assert not result.proven
    assert abs(result.t_stat) < 2 or np.isnan(result.t_stat)


# ---- no look-ahead --------------------------------------------------------------------------


def test_analogs_are_strictly_earlier_and_finished():
    events = make_events(400, seed=3)
    model = NewsModel(EventLibrary(events), make_reactions(events, 3, planted=True,
                                                         horizons=("1d", "10d")))
    target = events[300]
    for horizon, lag in (("1d", timedelta(days=5)), ("10d", timedelta(days=17))):
        analogs, _ = model.analogs(target, "^GSPC", horizon)
        assert analogs
        for a in analogs:
            assert a.started_at + lag <= target.started_at


def test_same_time_event_is_not_an_analog():
    t = datetime(2020, 1, 1, tzinfo=timezone.utc)
    vec = np.ones(DIM, dtype=np.float32)
    lib = EventLibrary([EventRecord("a", t, vec), EventRecord("b", t, vec),
                        EventRecord("c", t + timedelta(days=30), vec)])
    idx, _ = lib.candidates()
    assert (idx[lib.position["a"]] == -1).all()
    assert (idx[lib.position["b"]] == -1).all()
    assert set(idx[lib.position["c"]][:2]) == {lib.position["a"], lib.position["b"]}


def test_later_reactions_do_not_change_earlier_features():
    events = make_events(500, seed=4)
    reactions = make_reactions(events, 4, planted=True)
    base = NewsModel(EventLibrary(events), reactions).features("^GSPC", "1d")
    late_ids = {e.id for e in events[250:]}
    changed = reactions.copy()
    changed.loc[changed["event_id"].isin(late_ids), "raw"] += 0.5
    after = NewsModel(EventLibrary(events), changed).features("^GSPC", "1d")
    np.testing.assert_allclose(base.x[:250], after.x[:250])


def test_walk_forward_trains_only_on_finished_reactions(monkeypatch):
    events = make_events(600, seed=5, years=4)
    model = NewsModel(EventLibrary(events), make_reactions(events, 5, planted=True,
                                                         horizons=("10d",)))
    seen = []
    original = model._fit_rows

    def spy(fs, rows):
        seen.append(fs.realized[rows].max() if len(rows) else 0)
        return original(fs, rows)

    monkeypatch.setattr(model, "_fit_rows", spy)
    result = model.walk_forward("^GSPC", "10d")
    for year, latest in zip(result.years, seen):
        assert latest <= M._to_ns(datetime(year, 1, 1, tzinfo=timezone.utc))


# ---- data handling --------------------------------------------------------------------------


def test_intraday_horizons_skip_daily_start_reactions():
    events = make_events(200, seed=6)
    daily_start = make_reactions(events, 6, planted=True, horizons=("1h",), source="1d")
    model = NewsModel(EventLibrary(events), daily_start)
    assert np.isnan(model.features("^GSPC", "1h").y).all()
    analogs, mean = model.analogs(events[-1], "^GSPC", "1h")
    assert analogs == [] and np.isnan(mean)
    # The same rows count for a daily horizon.
    daily = make_reactions(events, 6, planted=True, horizons=("1d",), source="1d")
    assert not np.isnan(NewsModel(EventLibrary(events), daily).features("^GSPC", "1d").y).all()


def test_missing_start_ts_falls_back_to_event_time():
    events = make_events(30, seed=17)
    reactions = make_reactions(events, 17, planted=False)
    reactions["start_ts"] = None
    fs = NewsModel(EventLibrary(events), reactions).features("^GSPC", "1d")
    np.testing.assert_array_equal(fs.realized, fs.times + M._realized_lag("1d"))


def test_stocks_use_adjusted_and_indices_raw():
    assert M.return_kind("^GSPC") == "raw"
    assert M.return_kind("^HSI") == "raw"
    assert M.return_kind("2800.HK") == "raw"
    assert M.return_kind("XLK") == "adjusted"
    assert M.return_kind("0700.HK") == "adjusted"
    events = make_events(50, seed=7)
    reactions = make_reactions(events, 7, planted=False, targets=("XLK",))
    fs = NewsModel(EventLibrary(events), reactions).features("XLK", "1d")
    adjusted = reactions.set_index("event_id")["adjusted"]
    np.testing.assert_allclose(fs.y, adjusted.loc[[e.id for e in events]].to_numpy())


def test_pre_event_volatility_uses_only_earlier_sessions():
    index = pd.date_range("2020-01-01", periods=60, freq="B", tz="America/New_York")
    rng = np.random.default_rng(8)
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 60)))
    frame = pd.DataFrame({"Close": closes}, index=index)
    event_day = index[40]
    t = M._to_ns(event_day + pd.Timedelta(hours=12))
    expected = np.std(np.diff(np.log(closes[19:40])), ddof=1)  # 20 returns ending at day 39
    assert M.pre_event_volatility(frame, np.array([t]))[0] == pytest.approx(expected)
    # A crash on the event day itself does not leak into the feature.
    crashed = frame.copy()
    crashed.iloc[40, 0] *= 0.5
    assert M.pre_event_volatility(crashed, np.array([t]))[0] == pytest.approx(expected)
    assert np.isnan(M.pre_event_volatility(frame, np.array([M._to_ns(index[5])]))[0])
    assert np.isnan(M.pre_event_volatility(None, np.array([t]))[0])


def test_volatility_feature_comes_from_price_loader():
    events = make_events(100, seed=9, years=1)
    index = pd.date_range("2014-06-01", "2016-06-01", freq="B", tz="UTC")
    frame = pd.DataFrame({"Close": 100 * np.exp(np.linspace(0, 1, len(index)) ** 2)}, index=index)
    calls = []

    def loader(symbol, interval):
        calls.append((symbol, interval))
        return frame

    model = NewsModel(EventLibrary(events), make_reactions(events, 9, planted=False), loader)
    vol = model.features("^GSPC", "1d").x[:, M.FEATURE_NAMES.index("vol_20d")]
    assert not np.isnan(vol).any()
    model.features("^GSPC", "5d")  # a second horizon reuses the loaded prices
    assert calls == [("^GSPC", "1d")]


def test_too_few_rows_gives_no_model_but_analogs():
    events = make_events(20, seed=10)
    model = NewsModel(EventLibrary(events), make_reactions(events, 10, planted=True)).fit()
    assert ("^GSPC", "1d") not in model.models
    pred = model.predict(new_event("war_conflict", datetime(2024, 1, 1, tzinfo=timezone.utc),
                                   seed=10), "^GSPC", "1d")
    assert np.isnan(pred.predicted)
    assert len(pred.analogs) == 20 and not np.isnan(pred.analog_mean)


def test_fit_respects_train_end():
    events = make_events(600, seed=11, years=4)
    model = NewsModel(EventLibrary(events), make_reactions(events, 11, planted=True))
    model.fit(["^GSPC"], ["1d"], train_end=datetime(2017, 1, 1, tzinfo=timezone.utc))
    n_cut = model.models[("^GSPC", "1d")].n_train
    model.fit(["^GSPC"], ["1d"])
    assert n_cut < model.models[("^GSPC", "1d")].n_train == 600
    assert model.models[("^GSPC", "1d")].alpha in M.DEFAULT_ALPHAS


def test_score_predictions_rules():
    rng = np.random.default_rng(12)
    actual = rng.normal(0, 1, 200)
    n, hit, signed, t, proven = M.score_predictions(actual + rng.normal(0, 0.5, 200), actual)
    assert n == 200 and hit > 0.7 and signed > 0 and t > 2 and proven
    assert not M.score_predictions(-actual, actual)[4]  # wrong direction is never proven
    assert not M.score_predictions(actual[:20], actual[:20])[4]  # too few
    assert not M.score_predictions(np.ones(200), actual)[4]  # one sign only: no t-stat


# ---- analog search and the library ----------------------------------------------------------


def test_search_matches_brute_force():
    rng = np.random.default_rng(13)
    n = 300
    times = START + pd.to_timedelta(np.sort(rng.integers(0, 100, n)), unit="D")  # many ties
    events = [EventRecord(f"e{i}", times[i].to_pydatetime(), rng.normal(size=8)) for i in range(n)]
    lib = EventLibrary(events, k=5)
    idx, sim = lib.candidates()
    unit = lib.matrix
    for i in range(0, n, 7):
        earlier = np.flatnonzero(lib.times < lib.times[i])
        expected = earlier[np.argsort(-(unit[earlier] @ unit[i]), kind="stable")][:25]
        got = idx[i][idx[i] >= 0]
        assert len(got) == len(expected)
        np.testing.assert_allclose(sim[i][: len(got)], unit[expected] @ unit[i], rtol=1e-5)
        assert set(got) == set(expected) or np.allclose(np.sort(unit[got] @ unit[i]),
                                                        np.sort(unit[expected] @ unit[i]))


def test_search_chunks_give_same_result(monkeypatch):
    events = make_events(300, seed=14)
    full_idx, _ = EventLibrary(events).candidates()
    monkeypatch.setattr(M, "_SEARCH_BUDGET", 500)  # forces many small chunks
    chunk_idx, _ = EventLibrary(events).candidates()
    np.testing.assert_array_equal(full_idx, chunk_idx)


def test_extend_appends_and_reorders():
    events = make_events(300, seed=15)
    full_idx, full_sim = EventLibrary(events).candidates()
    lib = EventLibrary(events[:200])
    lib.candidates()
    lib.extend(events[200:])  # later events: append, older rows kept
    idx, sim = lib.candidates()
    np.testing.assert_array_equal(idx, full_idx)
    shuffled = EventLibrary(events[150:])
    shuffled.extend(events[:150])  # older events: full re-sort
    np.testing.assert_array_equal(shuffled.candidates()[0], full_idx)
    assert [e.id for e in shuffled.events] == [e.id for e in events]


def _no_full_table(self):
    raise AssertionError("full candidate table computed")


def test_fit_without_enough_reactions_skips_the_candidate_table(monkeypatch):
    # The live watcher refits on the whole store (450k events) while no reactions exist yet;
    # the all-pairs search then took hours and GBs for a model it could not fit.
    events = make_events(200, seed=17)
    model = NewsModel(EventLibrary(events), make_reactions(events[:10], 17, planted=True))
    monkeypatch.setattr(EventLibrary, "candidates", _no_full_table)
    assert model.fit(["^GSPC"], ["1d"]).models == {}


def test_library_event_query_does_not_build_the_full_table(monkeypatch):
    events = make_events(200, seed=18)
    expected, expected_sim = EventLibrary(events).candidates()
    lib = EventLibrary(events)
    monkeypatch.setattr(EventLibrary, "candidates", _no_full_table)
    idx, sim, t = lib.candidates_for(events[150])
    np.testing.assert_array_equal(idx, expected[150])
    np.testing.assert_allclose(sim, expected_sim[150], rtol=1e-5)  # one row vs matrix rounding
    assert t == int(lib.times[150])


def test_new_event_query_matches_library_row():
    events = make_events(200, seed=16)
    lib = EventLibrary(events[:-1])
    last = events[-1]
    outside = EventRecord("other-id", last.started_at, last.embedding)
    idx, _, _ = lib.candidates_for(outside)
    inside_idx, _ = EventLibrary(events).candidates()
    np.testing.assert_array_equal(idx, inside_idx[-1])


# ---- store loader ---------------------------------------------------------------------------


def test_load_event_records_from_store(tmp_path):
    store = NewsStore(tmp_path / "news.db")
    t0 = datetime(2021, 3, 1, 9, tzinfo=timezone.utc)
    items = [NewsItem("rss", t0 + timedelta(minutes=i), f"headline {i}", url=f"http://x/{i}")
             for i in range(3)]
    store.add_items(items)
    vecs = [np.eye(4, dtype=np.float32)[i] for i in (0, 1, 1)]
    for item, vec, tone, event_id in zip(items, vecs, (0.2, -0.4, 0.5), ("e1", "e1", "e2")):
        store.update_scores(ItemScore(item.id, tone=tone, embedding=embedding_to_bytes(vec),
                                      event_id=event_id))
    store.upsert_event(Event("e1", t0, "war_conflict", "headline 0", 2, 2, True))
    store.upsert_event(Event("e2", t0 + timedelta(hours=1), "other", "headline 2", 1, 1, False))
    records = M.load_event_records(store)
    store.close()
    assert [r.id for r in records] == ["e1", "e2"]
    np.testing.assert_allclose(records[0].embedding, [1, 1, 0, 0])
    assert records[0].tone == pytest.approx(-0.1)
    assert records[0].n_sources == 2 and records[0].high_impact
    assert records[1].category == "other" and records[1].tone == pytest.approx(0.5)
    later = M.load_event_records(NewsStore(tmp_path / "news.db"),
                                 start=t0 + timedelta(minutes=30))
    assert [r.id for r in later] == ["e2"]
