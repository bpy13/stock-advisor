"""Event clustering tests. Embeddings are synthetic unit vectors; no model is loaded."""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from stock_advisor.news import events
from stock_advisor.news.events import ClusterItem, cluster_items
from stock_advisor.news.models import ItemScore, NewsItem
from stock_advisor.news.scoring import embedding_to_bytes
from stock_advisor.news.store import NewsStore

T0 = datetime(2026, 10, 27, 8, 0, tzinfo=timezone.utc)
DIM = 384


def story_vector(story: int, variant: int = 0) -> np.ndarray:
    """Unit vector near story `story`'s direction; variants of one story have cosine ~0.9,
    different stories ~0."""
    base = np.random.default_rng(story).normal(size=DIM)
    base /= np.linalg.norm(base)
    noise = np.random.default_rng(10_000 + story * 100 + variant).normal(size=DIM)
    noise /= np.linalg.norm(noise)
    vec = base + 0.3 * noise
    return (vec / np.linalg.norm(vec)).astype(np.float32)


def item(n, story, hours=0.0, source="nyt", precision="exact", tone=0.0, category="war_conflict",
         when=None):
    when = when or T0 + timedelta(hours=hours)
    return ClusterItem(
        item_id=f"item{n:03d}",
        published_at=when,
        embedding=story_vector(story, n),
        source_key=source,
        time_precision=precision,
        title=f"story {story} headline {n}",
        tone=tone,
        category=category,
    )


def groups(assignments):
    out = {}
    for item_id, event_id in assignments.items():
        out.setdefault(event_id, set()).add(item_id)
    return sorted(out.values(), key=lambda g: sorted(g))


def test_synthetic_vectors_are_what_the_tests_assume():
    a, b, c = story_vector(1, 1), story_vector(1, 2), story_vector(2, 1)
    assert float(a @ b) > 0.85
    assert abs(float(a @ c)) < 0.3


def test_same_story_within_window_merges_and_unrelated_do_not():
    items = [
        item(1, story=1, hours=0, source="nyt"),
        item(2, story=1, hours=1, source="guardian"),
        item(3, story=2, hours=1.5, source="guardian"),
        item(4, story=1, hours=3, source="rss:BBC World"),
        item(5, story=3, hours=4, source="yahoo"),
    ]
    result = cluster_items(items)
    assert groups(result) == [{"item001", "item002", "item004"}, {"item003"}, {"item005"}]


def test_same_story_beyond_window_starts_new_event():
    items = [item(1, 1, hours=0), item(2, 1, hours=13)]  # gap 13 h > 12 h window
    assert len(groups(cluster_items(items))) == 2
    assert len(groups(cluster_items(items, window=timedelta(hours=14)))) == 1


def test_threshold_controls_merging():
    items = [item(1, 1, hours=0), item(2, 1, hours=1)]
    assert len(groups(cluster_items(items, threshold=0.99))) == 2


def test_running_story_is_cut_at_max_span():
    # One headline every 10 h for 3 days: each is within the window of the previous one, but
    # an event may not span more than 48 h.
    items = [item(n, 1, hours=10 * n) for n in range(8)]
    result = groups(cluster_items(items))
    assert len(result) == 2
    assert result[0] == {f"item{n:03d}" for n in range(5)}  # hours 0..40


def test_day_precision_item_joins_same_day_only():
    day = datetime(2026, 10, 26, tzinfo=timezone.utc)
    items = [
        item(1, 1, when=day, source="wikipedia_events", precision="day"),
        item(2, 1, when=day + timedelta(hours=20), source="guardian"),  # same day, 20 h later
        item(3, 1, when=day + timedelta(days=2, hours=1), source="nyt"),  # two days later
    ]
    result = groups(cluster_items(items))
    assert result == [{"item001", "item002"}, {"item003"}]


def test_exact_item_before_day_item_on_same_day_merges():
    day = datetime(2026, 10, 26, tzinfo=timezone.utc)
    items = [
        item(1, 1, when=day + timedelta(hours=1), source="guardian"),
        item(2, 1, when=day, source="wikipedia_events", precision="day"),
    ]
    assert len(groups(cluster_items(items))) == 1


def test_event_ids_are_stable_and_named_after_the_founding_item():
    items = [item(1, 1, hours=0), item(2, 1, hours=1), item(3, 2, hours=2)]
    first = cluster_items(items)
    again = cluster_items(list(reversed(items)))
    assert first == again
    assert first["item001"] == events.event_id_for("item001")
    assert first["item003"] == events.event_id_for("item003")


def test_summarize_event_time_title_category_and_sources():
    day = datetime(2026, 10, 26, tzinfo=timezone.utc)
    members = [
        item(1, 1, when=day, source="wikipedia_events", precision="day", category="war_conflict"),
        item(2, 1, when=day + timedelta(hours=5), source="rss:BBC World", category="other"),
        item(3, 1, when=day + timedelta(hours=6), source="rss:RTHK International",
             category="war_conflict"),
    ]
    event = events.summarize_event("ev_x", members)
    assert event.started_at == day + timedelta(hours=5)  # earliest exact-time headline
    assert event.title == "story 1 headline 2"
    assert event.category == "war_conflict"
    assert event.n_items == 3
    assert event.n_sources == 3  # two RSS feeds count separately
    assert events.event_time_precision(members) == "exact"

    day_only = events.summarize_event("ev_y", members[:1])
    assert day_only.started_at == day
    assert events.event_time_precision(members[:1]) == "day"


def test_event_time_precision_ranks_exact_over_batch_over_day():
    day = item(1, 1, source="wikipedia_events", precision="day")
    batch = item(2, 1, source="gdelt", precision="batch")
    exact = item(3, 1, precision="exact")
    assert events.event_time_precision([day, batch, exact]) == "exact"
    assert events.event_time_precision([day, batch]) == "batch"
    assert events.event_time_precision([batch]) == "batch"
    assert events.event_time_precision([day]) == "day"
    assert batch.is_exact  # a batch stamp is still a clock time for the event start


def test_source_key():
    assert events.source_key("rss", "https://bbc.co.uk/x", "[BBC World | world] text") == "rss:BBC World"
    assert events.source_key("rss", "https://www.rthk.hk/a", "") == "rss:www.rthk.hk"
    assert events.source_key("gdelt", "https://www.jpost.com/a", "jpost.com") == "gdelt:jpost.com"
    assert events.source_key("gdelt", "https://www.jpost.com/a", "") == "gdelt:jpost.com"
    assert events.source_key("guardian", "https://theguardian.com/a", "summary") == "guardian"


@pytest.mark.parametrize(
    "category, tone, n_sources, expected",
    [
        ("war_conflict", -0.7, 1, True),  # strong tone
        ("war_conflict", 0.1, 3, True),  # many sources
        ("war_conflict", 0.1, 2, False),
        ("company_results", -0.9, 5, False),  # company news is not macro
        ("other", -0.9, 5, False),
        (None, -0.9, 5, False),
        ("monetary_policy", 0.6, 1, True),  # the boundary counts
    ],
)
def test_high_impact_rule(category, tone, n_sources, expected):
    assert events.is_high_impact(category, tone, n_sources) is expected


def test_market_moving_hook_overrides_rule():
    assert events.is_high_impact("company_results", 0.0, 1, market_moving={"company_results"})


def test_clusterer_closes_idle_events():
    clusterer = events.EventClusterer()
    clusterer.add(item(1, 1, hours=0))
    clusterer.add(item(2, 2, hours=0))
    clusterer.close_idle(T0 + timedelta(hours=13))
    assert clusterer.events == {}
    # a closed slot is reused, so the centroid matrix does not grow
    clusterer.add(item(3, 3, hours=13))
    assert clusterer._matrix.shape[0] == 64


# ---- store integration --------------------------------------------------------------------


def _store_item(store, n, story, hours, source="nyt", url=None, tone=0.0,
                category="war_conflict", summary="", precision="exact"):
    news = NewsItem(
        source=source,
        published_at=T0 + timedelta(hours=hours),
        title=f"story {story} headline {n}",
        url=url if url is not None else f"https://example.com/{n}",
        summary=summary,
        time_precision=precision,
    )
    store.add_items([news])
    store.update_scores(ItemScore(item_id=news.id, tone=tone, category=category,
                                  embedding=embedding_to_bytes(story_vector(story, n))))
    return news.id


def test_cluster_pending_is_incremental(tmp_path):
    with NewsStore(tmp_path / "news.db") as store:
        a1 = _store_item(store, 1, 1, 0, source="nyt")
        a2 = _store_item(store, 2, 1, 1, source="guardian")
        b1 = _store_item(store, 3, 2, 1, source="yahoo", category="company_results")
        assert events.cluster_pending(store) == 3
        event_a = store.get_score(a1).event_id
        assert store.get_score(a2).event_id == event_a
        assert store.get_score(b1).event_id != event_a
        assert store.get_event(event_a).n_sources == 2
        assert not store.get_event(event_a).high_impact
        assert events.cluster_pending(store) == 0  # nothing left

        # Next live batch: a third source joins the open event, which becomes high impact.
        a3 = _store_item(store, 4, 1, 2, source="rss", summary="[BBC World | world] x")
        assert events.cluster_pending(store) == 1
        assert store.get_score(a3).event_id == event_a
        stored = store.get_event(event_a)
        assert (stored.n_items, stored.n_sources, stored.high_impact) == (3, 3, True)
        assert all(store.get_score(i).high_impact for i in (a1, a2, a3))
        assert not store.get_score(b1).high_impact


def test_cluster_pending_late_arrival_joins_existing_event(tmp_path):
    with NewsStore(tmp_path / "news.db") as store:
        later = _store_item(store, 1, 1, 5)
        events.cluster_pending(store)
        earlier = _store_item(store, 2, 1, 1)  # published earlier, collected later (GDELT lag)
        events.cluster_pending(store)
        event_id = store.get_score(later).event_id
        assert store.get_score(earlier).event_id == event_id
        assert store.get_event(event_id).started_at == T0 + timedelta(hours=1)


def test_cluster_pending_waits_for_category_and_chunks(tmp_path):
    with NewsStore(tmp_path / "news.db") as store:
        ids = [_store_item(store, n, 1, n * 0.5) for n in range(5)]
        uncategorized = _store_item(store, 9, 1, 3, category=None)
        assert events.cluster_pending(store, chunk_size=2) == 5
        assert len({store.get_score(i).event_id for i in ids}) == 1
        assert store.get_score(uncategorized).event_id is None


class FakeFinBert:
    def predict(self, texts):
        return np.array([[0.05, 0.9, 0.05] for _ in texts])


def test_fetch_high_impact_bodies(tmp_path):
    with NewsStore(tmp_path / "news.db") as store:
        paywalled = _store_item(store, 1, 1, 0, source="nyt", tone=-0.7,
                                url="https://www.nytimes.com/a")
        free = _store_item(store, 2, 1, 1, source="guardian", tone=-0.7)
        quiet = _store_item(store, 3, 2, 1, source="yahoo", tone=0.0)  # not high impact
        events.cluster_pending(store)

        calls = []

        def fake_fetch(url):
            calls.append(url)
            return None if "nytimes" in url else "Markets fell sharply. " * 50

        assert events.fetch_high_impact_bodies(store, fetch=fake_fetch, finbert=FakeFinBert()) == 1
        assert calls == ["https://www.nytimes.com/a", "https://example.com/2"]
        assert store.get_item(paywalled).body == ""  # tried, nothing allowed
        assert store.get_item(free).body.startswith("Markets fell sharply.")
        assert store.get_item(quiet).body is None
        score = store.get_score(free)
        assert score.tone == pytest.approx(0.05 - 0.9)
        assert score.high_impact and score.event_id == store.get_score(paywalled).event_id

        # The event already has a body, so a second run fetches nothing.
        assert events.fetch_high_impact_bodies(store, fetch=fake_fetch) == 0
        assert len(calls) == 2
