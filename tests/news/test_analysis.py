"""Tests for the news analysis layer: synthetic store, no network, no model downloads."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from stock_advisor.news import analysis as A
from stock_advisor.news import categories
from stock_advisor.news.model import (
    EventLibrary,
    NewsModel,
    load_event_records,
    save_fitted,
)
from stock_advisor.news.models import Event, ItemScore, NewsItem
from stock_advisor.news.scoring import EMBED_DIM, embedding_to_bytes
from stock_advisor.news.store import NewsStore
from stock_advisor.news_backtest_cli import BacktestResults

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
DIM = 16


def unit(vec) -> np.ndarray:
    vec = np.asarray(vec, dtype=np.float32)
    return vec / np.linalg.norm(vec)


def add_event(store, ident: str, when: datetime, vector, category="war_conflict",
              title=None, source="rss", url=None, summary="", n_items=3, high_impact=True):
    """One event with `n_items` stored headlines that all carry `vector`."""
    title = title or f"{category} headline {ident}"
    for k in range(n_items):
        item = NewsItem(source=source, published_at=when + timedelta(minutes=k),
                        title=title if k == 0 else f"{title} update {k}",
                        url=url or f"https://example.test/{ident}/{k}", summary=summary)
        store.add_items([item])
        store.update_scores(ItemScore(
            item_id=item.id, tone=-0.7, tone_pos=0.1, tone_neg=0.8, tone_neu=0.1,
            category=category, embedding=embedding_to_bytes(unit(vector)),
            event_id=f"ev_{ident}", high_impact=high_impact))
    store.upsert_event(Event(f"ev_{ident}", when, category, title, n_items, min(n_items, 3),
                             high_impact))
    return f"ev_{ident}"


def past_history(store, n=45, seed=0):
    """n past events over two years: war-like ones fall 3% over one day, others are flat."""
    rng = np.random.default_rng(seed)
    war, calm = rng.normal(size=DIM), rng.normal(size=DIM)
    rows = []
    for i in range(n):
        is_war = i % 2 == 0
        when = NOW - timedelta(days=700 - 12 * i)
        vec = (war if is_war else calm) + 0.05 * rng.normal(size=DIM)
        ev = add_event(store, f"p{i}", when, vec, "war_conflict" if is_war else "other",
                       high_impact=is_war)
        for target in ("^GSPC", "^HSI"):
            for horizon, size in (("1d", -0.03), ("1h", -0.01), ("1m", -0.002)):
                value = (size if is_war else 0.0) + rng.normal(0, 0.001)
                rows.append((ev, target, horizon, value, value, pd.Timestamp(when), "1m"))
            for horizon in ("2d", "3d", "5d", "10d", "5m", "15m", "4h"):
                value = (-0.03 if is_war else 0.0) + rng.normal(0, 0.001)
                rows.append((ev, target, horizon, value, value, pd.Timestamp(when), "1m"))
    reactions = pd.DataFrame(rows, columns=["event_id", "target", "horizon", "raw", "adjusted",
                                            "start_ts", "start_source"])
    return war, reactions


@pytest.fixture()
def store(tmp_path):
    with NewsStore(tmp_path / "news.db") as s:
        yield s


def fit_and_save(store, reactions, path, targets=("^GSPC", "^HSI"),
                 horizons=A.HEADLINE_HORIZONS):
    """What news_backtest_cli does: fit on the store's events and save the models to `path`."""
    records = load_event_records(store)
    model = NewsModel(EventLibrary(records), reactions).fit(targets, horizons)
    save_fitted(model.models, path, len(records))
    return path


def analyzer_for(store, tmp_path, reactions=None, proven=(), targets=("^GSPC", "^HSI")):
    """An analyzer that reads reactions and a fitted file saved under `tmp_path`.

    No reactions: the fitted file is not written, like a machine that never ran the backtest.
    """
    results = BacktestResults({"results": [
        {"target": t, "horizon": h, "proven": True} for t, h in proven]})
    fitted_path = tmp_path / "fitted.pkl"
    if reactions is None:
        reactions = pd.DataFrame(columns=A.REACTION_COLUMNS)
    else:
        fit_and_save(store, reactions, fitted_path, targets)
    return A.NewsAnalyzer(store, targets, results=results, reactions=reactions,
                          fitted_path=fitted_path, clock=lambda: NOW)


def test_decide_action_thresholds():
    assert A.decide_action(-0.015) == "reduce"
    assert A.decide_action(-0.0149) == "hold"
    assert A.decide_action(0.015) == "add"
    assert A.decide_action(0.0) == "hold"
    assert A.decide_action(float("nan")) == "hold"
    assert A.decide_action(0.02, threshold_pct=3.0) == "hold"


def test_alert_targets_adds_holdings_without_duplicates():
    assert A.alert_targets(["0700.hk", "^gspc", " aapl "]) == ["^HSI", "^GSPC", "0700.HK", "AAPL"]
    assert A.alert_targets() == ["^HSI", "^GSPC"]


def test_no_history_degrades_without_error(store, tmp_path):
    vec = np.ones(DIM)
    add_event(store, "now", NOW - timedelta(hours=1), vec)
    analyzer = analyzer_for(store, tmp_path)
    [analysis] = analyzer.analyze_recent(24)
    assert analysis.similar == []
    for target in ("^GSPC", "^HSI"):
        outlook = analysis.outlooks[target]
        assert not outlook.has_prediction
        assert outlook.action == "hold"
        assert not outlook.action_proven
        assert all(not f.available for f in outlook.forecasts.values())
        assert outlook.window_text  # says why there is no window, never empty
    assert analysis.warnings == []


def test_with_history_predicts_reduce_and_lists_similar(store, tmp_path):
    war, reactions = past_history(store)
    add_event(store, "now", NOW - timedelta(hours=2), war, title="Missiles hit port city")
    analyzer = analyzer_for(store, tmp_path, reactions)
    [analysis] = analyzer.analyze_recent(24)
    outlook = analysis.outlooks["^GSPC"]
    one_day = outlook.forecasts["1d"]
    assert one_day.available and one_day.predicted < -0.015
    assert one_day.low < one_day.predicted < one_day.high
    assert outlook.has_prediction and outlook.action == "reduce"
    assert not one_day.proven and not outlook.action_proven  # nothing proven in results
    assert outlook.window_status != "no_direction"  # a direction exists, so a window is judged
    assert len(analysis.similar) == A.TOP_SIMILAR
    assert all(s.started_at < analysis.started_at for s in analysis.similar)
    assert all(s.reactions["^GSPC"] < -0.02 for s in analysis.similar)  # war analogs fell
    assert A.strong_targets(analysis) == ["^GSPC", "^HSI"]


def test_proven_flag_comes_from_results(store, tmp_path):
    war, reactions = past_history(store)
    add_event(store, "now", NOW - timedelta(hours=2), war)
    analyzer = analyzer_for(store, tmp_path, reactions, proven=[("^GSPC", "1d")])
    [analysis] = analyzer.analyze_recent(24)
    assert analysis.outlooks["^GSPC"].action_proven
    assert analysis.outlooks["^GSPC"].forecasts["1d"].proven
    assert not analysis.outlooks["^GSPC"].forecasts["1h"].proven
    assert not analysis.outlooks["^HSI"].action_proven


def test_guardian_summary_never_reaches_the_analysis(store, tmp_path):
    add_event(store, "g", NOW - timedelta(hours=1), np.ones(DIM), source="guardian",
              summary="SECRET-TRAIL-TEXT", n_items=1, title="Guardian headline")
    [analysis] = analyzer_for(store, tmp_path).analyze_recent(24)
    assert "SECRET-TRAIL-TEXT" not in repr(analysis)
    assert analysis.headlines[0].title == "Guardian headline"
    assert analysis.headlines[0].url.startswith("https://example.test/")
    assert analysis.sources == ["guardian"]


def test_old_events_and_ordering(store, tmp_path):
    add_event(store, "old", NOW - timedelta(hours=30), np.ones(DIM))
    add_event(store, "quiet", NOW - timedelta(hours=3), np.arange(1, DIM + 1), high_impact=False,
              n_items=1)
    add_event(store, "big", NOW - timedelta(hours=5), np.arange(DIM, 0, -1))
    analyzer = analyzer_for(store, tmp_path)
    assert [a.event_id for a in analyzer.analyze_recent(24)] == ["ev_big", "ev_quiet"]
    assert [a.event_id for a in analyzer.analyze_recent(24, high_impact_only=True)] == ["ev_big"]
    assert [a.event_id for a in analyzer.analyze_recent(24, limit=1)] == ["ev_big"]


def test_prediction_error_becomes_a_warning(store, tmp_path):
    add_event(store, "now", NOW - timedelta(hours=1), np.ones(DIM))
    analyzer = analyzer_for(store, tmp_path)
    analyzer.refresh()

    def boom(*args, **kwargs):
        raise RuntimeError("model broke")

    analyzer.model.predict = boom
    [analysis] = analyzer.analyze_recent(24)
    assert any("prediction failed" in w for w in analysis.warnings)
    assert math.isnan(analysis.outlooks["^GSPC"].predicted_action_move)


def test_refresh_never_fits_and_predicts_from_the_fitted_file(store, tmp_path, monkeypatch):
    # Fitting builds the all-pairs analog table: 30-60 minutes on the live store, and the
    # watcher stops polling meanwhile. refresh must only load.
    war, reactions = past_history(store)
    add_event(store, "now", NOW - timedelta(hours=2), war)
    analyzer = analyzer_for(store, tmp_path, reactions)  # fits and saves here, before the patches

    def boom(*args, **kwargs):
        raise AssertionError("refresh must not fit or build the candidate table")

    monkeypatch.setattr(NewsModel, "fit", boom)
    monkeypatch.setattr(NewsModel, "features", boom)
    monkeypatch.setattr(EventLibrary, "candidates", boom)
    [analysis] = analyzer.analyze_recent(24)
    assert analyzer.model.models
    forecast = analysis.outlooks["^GSPC"].forecasts["1d"]
    assert forecast.available and forecast.predicted < -0.015
    assert not math.isnan(forecast.low) and forecast.n_train > 0
    assert len(analysis.similar) == A.TOP_SIMILAR
    assert analysis.warnings == []


def test_refresh_logs_the_fitted_file_and_warns_when_missing(store, tmp_path, caplog):
    war, reactions = past_history(store)
    add_event(store, "now", NOW - timedelta(hours=2), war)
    with caplog.at_level("INFO"):
        analyzer_for(store, tmp_path, reactions).refresh()
    assert "Fitted models generated" in caplog.text
    assert "Model ready:" in caplog.text and "fitted target/horizon pairs" in caplog.text
    caplog.clear()
    with caplog.at_level("WARNING"):
        analyzer_for(store, tmp_path / "empty").refresh()
    assert "No fitted models" in caplog.text


def test_missing_fitted_file_gives_na_predictions_without_error(store, tmp_path):
    war, reactions = past_history(store)
    add_event(store, "now", NOW - timedelta(hours=2), war)
    analyzer = A.NewsAnalyzer(
        store, ("^GSPC", "^HSI"), results=BacktestResults({}), reactions=reactions,
        fitted_path=tmp_path / "missing.pkl", clock=lambda: NOW)
    [analysis] = analyzer.analyze_recent(24)
    assert analyzer.model.models == {}
    outlook = analysis.outlooks["^GSPC"]
    assert not outlook.has_prediction and outlook.action == "hold"
    assert all(not f.available for f in outlook.forecasts.values())
    assert len(analysis.similar) == A.TOP_SIMILAR  # similar events need no fitted model
    assert analysis.warnings == []


# ---- processing ---------------------------------------------------------------------------------


class FakeFinBert:
    def predict(self, texts):
        return np.tile([0.1, 0.8, 0.1], (len(texts), 1))


class FakeEmbedder:
    """Same direction for every title, so all headlines fall into one event."""

    def encode(self, texts, **kwargs):
        return np.tile(np.ones(EMBED_DIM, dtype=np.float32), (len(texts), 1))


def test_process_new_scores_categorizes_and_clusters_recent_items_only(store, monkeypatch):
    rng = np.random.default_rng(1)
    centroids = rng.normal(size=(len(categories._centroid_names), EMBED_DIM)).astype(np.float32)
    centroids /= np.linalg.norm(centroids, axis=1, keepdims=True)
    monkeypatch.setattr(categories, "_centroids", centroids)
    recent = [NewsItem("rss", NOW - timedelta(minutes=m), f"Strike news {m}",
                       url=f"https://x/{m}") for m in (5, 10)]
    ancient = NewsItem("rss", NOW - timedelta(days=30), "Old backlog", url="https://x/old")
    store.add_items(recent + [ancient])
    done = A.process_new(store, since=NOW - timedelta(days=3), finbert=FakeFinBert(),
                         embedder=FakeEmbedder())
    assert done.scored == 2 and done.categorized == 2 and done.clustered == 2
    assert store.get_score(ancient.id) is None  # the backfill's backlog is left alone
    ids = {store.get_score(i.id).event_id for i in recent}
    assert len(ids) == 1 and None not in ids
    assert store.get_event(ids.pop()).n_items == 2


def test_process_new_leaves_the_backfills_scored_backlog_alone(store, monkeypatch):
    # The backfill scores old items, then categorizes and clusters them itself. A live run that
    # also took them on loaded the whole backlog every cycle (the watcher grew to 11.9 GB).
    rng = np.random.default_rng(1)
    centroids = rng.normal(size=(len(categories._centroid_names), EMBED_DIM)).astype(np.float32)
    centroids /= np.linalg.norm(centroids, axis=1, keepdims=True)
    monkeypatch.setattr(categories, "_centroids", centroids)
    scored_old = NewsItem("nyt", NOW - timedelta(days=30), "Old scored", url="https://x/s")
    categorized_old = NewsItem("nyt", NOW - timedelta(days=30), "Old categorized",
                               url="https://x/c")
    store.add_items([scored_old, categorized_old])
    vector = embedding_to_bytes(np.ones(EMBED_DIM, dtype=np.float32))
    store.update_scores(ItemScore(item_id=scored_old.id, tone=0.0, embedding=vector))
    store.update_scores(ItemScore(item_id=categorized_old.id, tone=0.0, embedding=vector,
                                  category="war_conflict"))
    done = A.process_new(store, since=NOW - timedelta(days=3), finbert=FakeFinBert(),
                         embedder=FakeEmbedder())
    assert (done.scored, done.categorized, done.clustered) == (0, 0, 0)
    assert store.get_score(scored_old.id).category is None
    assert store.get_score(categorized_old.id).event_id is None


# ---- sources and GDELT guard --------------------------------------------------------------------


def test_gdelt_busy_reads_status_file(tmp_path):
    path = tmp_path / "status.json"
    stamp = lambda minutes: (NOW - timedelta(minutes=minutes)).isoformat()  # noqa: E731

    def write(state, minutes):
        path.write_text(json.dumps({"updated": stamp(minutes),
                                    "sources": {"gdelt": {"run_status": state}}}))

    write("running", 2)
    assert A.gdelt_busy(path, now=NOW)
    write("running", 60)  # stale file: the backfill is gone
    assert not A.gdelt_busy(path, now=NOW)
    write("pending", 2)
    assert not A.gdelt_busy(path, now=NOW)
    assert not A.gdelt_busy(tmp_path / "missing.json", now=NOW)


def test_build_watch_sources_splits_cisa_out_of_the_fast_group(monkeypatch):
    class Dummy:
        def __init__(self, name):
            self.name = name

    monkeypatch.setattr("stock_advisor.news.collect.build_sources",
                        lambda holdings=(): [Dummy(n) for n in
                                             ("wikipedia_events", "gdelt", "guardian", "nyt",
                                              "yahoo", "edgar", "rss")])
    sources = A.build_watch_sources(["AAPL"])
    assert [s.name for s in sources.fast] == ["edgar", "yahoo", "rss"]
    assert [s.name for s in sources.slow] == ["guardian", "nyt", "gdelt", "rss"]
    fast_rss, slow_rss = sources.fast[-1], sources.slow[-1]
    assert not any("CISA" in f.name for f in fast_rss.feeds)
    assert [f.name for f in slow_rss.feeds] == ["CISA Advisories"]


def test_open_store_sets_busy_timeout(tmp_path):
    with A.open_store(tmp_path / "x.db") as s:
        assert s._conn.execute("PRAGMA busy_timeout").fetchone()[0] == A.BUSY_TIMEOUT_MS


def write_reactions(path) -> None:
    """A reaction file shaped like news_backtest_cli's: most rows have no return."""
    start = pd.Timestamp("2026-10-01", tz="UTC")
    rows = []
    for i in range(300):
        for target in ("^GSPC", "^HSI", "XLE"):
            known = i % 50 == 0
            rows.append({
                "event_id": f"e{i}", "target": target, "horizon": "1d",
                "raw": 0.01 * i if known else np.nan,
                "adjusted": (0.005 * i if known else np.nan) if target != "^HSI" else np.nan,
                "start_ts": start + pd.Timedelta(minutes=i), "start_source": "60m",
            })
    pd.DataFrame(rows).to_parquet(path)


def test_read_reactions_keeps_known_rows_of_the_targets_only(tmp_path):
    path = tmp_path / "reactions.parquet"
    write_reactions(path)
    frame = A.read_reactions(path, targets=["^GSPC", "^HSI"])
    assert len(frame) == 12  # 6 known events x 2 targets; empty rows and XLE dropped
    assert set(frame["target"]) == {"^GSPC", "^HSI"}
    assert frame["raw"].notna().all()
    assert isinstance(frame["event_id"].dtype, pd.CategoricalDtype)
    row = frame[(frame["event_id"] == "e50") & (frame["target"] == "^GSPC")].iloc[0]
    assert row["raw"] == pytest.approx(0.5) and row["adjusted"] == pytest.approx(0.25)
    assert row["start_ts"] == pd.Timestamp("2026-10-01 00:50", tz="UTC")
    assert len(A.read_reactions(path)) == 18  # no targets: every target


def test_read_reactions_feeds_the_model_outcomes(tmp_path):
    """Category columns from the streamed read still align with the event library."""
    from stock_advisor.news.model import EventRecord, _outcomes

    path = tmp_path / "reactions.parquet"
    write_reactions(path)
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    records = [EventRecord(id=f"e{i}", started_at=start + timedelta(minutes=i),
                           embedding=unit(np.eye(DIM)[i % DIM] + 0.1)) for i in range(300)]
    out = _outcomes(EventLibrary(records), A.read_reactions(path, ["^GSPC"]), "^GSPC", "1d")
    assert np.count_nonzero(~np.isnan(out.values)) == 6
    assert out.values[50] == pytest.approx(0.5)  # an index: the raw return


def test_read_reactions_missing_or_unreadable_file_gives_empty_table(tmp_path):
    assert A.read_reactions(tmp_path / "none.parquet", ["^GSPC"]).empty
    bad = tmp_path / "bad.parquet"
    bad.write_bytes(b"not parquet")
    assert A.read_reactions(bad, ["^GSPC"]).empty
