"""The disk snapshot of the event library gives the same analogs as the in-memory library."""

from __future__ import annotations

import numpy as np
import pytest

from stock_advisor.news import analysis as A
from stock_advisor.news import library_snapshot as snap
from stock_advisor.news.model import EventLibrary, NewsModel, load_event_records
from stock_advisor.news.store import NewsStore
from stock_advisor.news_backtest_cli import BacktestResults
from tests.news.test_analysis import NOW, past_history


@pytest.fixture()
def store(tmp_path):
    with NewsStore(tmp_path / "news.db") as s:
        yield s


def test_snapshot_matches_the_in_memory_library(store, tmp_path):
    past_history(store)
    records = load_event_records(store)
    memory = EventLibrary(records)

    snap.build_snapshot(store, tmp_path / "lib")
    mapped = snap.load_snapshot(tmp_path / "lib")

    assert len(mapped) == len(memory)
    assert [e.id for e in mapped.events] == [e.id for e in memory.events]
    assert np.array_equal(mapped.times, memory.times)
    assert mapped.position.get(records[3].id) == 3
    assert mapped.position.get("missing") is None
    probe = records[-1]
    idx_a, sim_a, _ = memory.candidates_for(probe)
    idx_b, sim_b, _ = mapped.candidates_for(probe)
    assert np.array_equal(idx_a, idx_b)
    assert np.allclose(sim_a, sim_b, equal_nan=True)
    first = mapped.events[5]
    assert (first.title, first.category) == (records[5].title, records[5].category)


def test_snapshot_is_read_only_and_missing_means_none(store, tmp_path):
    assert snap.load_snapshot(tmp_path / "nothing") is None
    past_history(store, n=6)
    snap.build_snapshot(store, tmp_path / "lib")
    with pytest.raises(TypeError):
        snap.load_snapshot(tmp_path / "lib").extend(load_event_records(store))


def test_unreadable_snapshot_falls_back_to_none(store, tmp_path):
    past_history(store, n=6)
    folder = snap.build_snapshot(store, tmp_path / "lib")
    (folder / "meta.parquet").write_bytes(b"not a parquet file")
    assert snap.load_snapshot(tmp_path / "lib") is None


def test_rebuild_keeps_only_the_newest_snapshot(store, tmp_path):
    past_history(store, n=6)
    first = snap.build_snapshot(store, tmp_path / "lib")
    # Folder names have one-second resolution; make the second one distinct.
    first.rename(first.with_name("19990101-000000"))
    second = snap.build_snapshot(store, tmp_path / "lib")
    names = sorted(p.name for p in (tmp_path / "lib").iterdir() if p.is_dir())
    assert names == [second.name]


def test_analyzer_uses_the_snapshot_and_never_reads_every_event(store, tmp_path, monkeypatch):
    """The slow path: refresh() must not stream every event out of the store when a snapshot
    exists (it took 3 minutes and 12 GB on the live store)."""
    _, reactions = past_history(store)
    snap.build_snapshot(store, tmp_path / "lib")
    monkeypatch.setattr(snap, "snapshot_root", lambda: tmp_path / "lib")
    A._SNAPSHOT_CACHE.clear()
    A._MODEL_CACHE.clear()

    def boom(*args, **kwargs):
        raise AssertionError("refresh() read all events from the store")

    monkeypatch.setattr("stock_advisor.news.model.load_event_records", boom)
    monkeypatch.setattr(A, "read_reactions", lambda *a, **k: reactions)
    analyzer = A.NewsAnalyzer(store, ["^GSPC"], results=BacktestResults({"results": []}),
                              fitted_path=tmp_path / "none.pkl", clock=lambda: NOW)
    analyzer.refresh()
    assert isinstance(analyzer.model.library, snap.SnapshotLibrary)
    assert analyzer.history_events == len(reactions["event_id"].unique())
    first = analyzer.model.library
    model = analyzer.model
    analyzer.refresh()  # the second open reuses the mapped library and the built model
    assert analyzer.model.library is first
    assert analyzer.model is model


def test_one_event_is_searched_once_for_all_targets_and_horizons(store, monkeypatch):
    """Analysing one event asked for its analog search once per target and horizon (97 searches
    of 1.8M events per event on the dashboard, 10 minutes); it must search once."""
    past_history(store)
    memory = EventLibrary(load_event_records(store))
    calls = []
    real = EventLibrary.search

    def counting(self, *args, **kwargs):
        calls.append(1)
        return real(self, *args, **kwargs)

    monkeypatch.setattr(EventLibrary, "search", counting)
    probe = memory.events[-1]
    first = memory.candidates_for(probe)
    for _ in range(20):
        again = memory.candidates_for(probe)
    assert len(calls) == 1
    assert again[2] == first[2] and np.array_equal(again[0], first[0])
    memory.candidates_for(memory.events[-2])
    assert len(calls) == 2


def test_outcomes_hold_only_known_rows_and_index_like_dense_arrays(store):
    """A dense outcome array per target and horizon (14 MB each at 1.8M events) came to 10 GB on
    the dashboard. The sparse form must answer like the dense one."""
    _, reactions = past_history(store)
    library = EventLibrary(load_event_records(store))
    model = NewsModel(library, reactions)
    out = model.outcomes("^GSPC", "1d")
    dense = np.array(out.values)
    assert len(out.values) == len(library) and dense.shape == (len(library),)
    assert out.values.data.nbytes < dense.nbytes or len(library) < 100
    probe = np.array([[0, 1, 2], [3, len(library) - 1, 0]])
    assert np.array_equal(out.values[probe], dense[probe], equal_nan=True)
    assert out.values[1] == dense[1]
    dense_realized = np.array(out.realized_ns)
    assert np.array_equal(out.realized_ns[probe], dense_realized[probe])
    known = ~np.isnan(dense)
    assert known.sum() == reactions[(reactions.target == "^GSPC")
                                    & (reactions.horizon == "1d")]["event_id"].nunique()
    assert (dense_realized[~known] == np.iinfo(np.int64).max).all()
    assert np.array_equal(np.array(out.start_ns)[known], library.times[known])


def test_prefetch_gives_the_same_candidates_as_one_search_each(store):
    past_history(store)
    records = load_event_records(store)
    one_by_one = EventLibrary(records)
    batched = EventLibrary(records)
    probes = records[-6:]
    batched.prefetch(probes)
    assert len(batched._single) == len(probes)
    for e in probes:
        idx_a, sim_a, t_a = one_by_one.candidates_for(e)
        idx_b, sim_b, t_b = batched.candidates_for(e)
        assert t_a == t_b and np.array_equal(idx_a, idx_b)
        assert np.allclose(sim_a, sim_b, equal_nan=True)
