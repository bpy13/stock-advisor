"""Scoring tests use fake models; nothing is downloaded."""

from datetime import datetime, timezone

import numpy as np
import pytest

from stock_advisor.news import scoring
from stock_advisor.news.models import NewsItem
from stock_advisor.news.store import NewsStore


class FakeFinBert:
    """Positive for titles containing 'up', negative for 'crash', else neutral."""

    def __init__(self):
        self.calls = []

    def predict(self, texts):
        self.calls.append(list(texts))
        rows = []
        for t in texts:
            if "crash" in t:
                rows.append([0.05, 0.85, 0.10])
            elif "up" in t:
                rows.append([0.70, 0.10, 0.20])
            else:
                rows.append([0.10, 0.10, 0.80])
        return np.array(rows)


class FakeEmbedder:
    def encode(self, texts):
        rng_rows = [
            np.random.default_rng(abs(hash(t)) % (2**32)).normal(size=384) * 3
            for t in texts
        ]
        return np.array(rng_rows)


def test_score_tone_values():
    out = scoring.score_tone(["stocks crash", "shares up", "meeting held"], model=FakeFinBert())
    assert out[0][3] == pytest.approx(0.05 - 0.85)
    assert out[1][3] == pytest.approx(0.60)
    assert out[2][:3] == pytest.approx((0.10, 0.10, 0.80))
    assert all(len(row) == 4 for row in out)


def test_empty_inputs():
    assert scoring.score_tone([], model=FakeFinBert()) == []
    assert scoring.embed([], model=FakeEmbedder()).shape == (0, 384)


def test_embed_is_float32_unit_norm():
    vectors = scoring.embed(["a", "b"], model=FakeEmbedder())
    assert vectors.dtype == np.float32
    assert vectors.shape == (2, 384)
    assert np.linalg.norm(vectors, axis=1) == pytest.approx(1.0, abs=1e-5)


def test_embedding_bytes_round_trip():
    vector = scoring.embed(["a"], model=FakeEmbedder())[0]
    data = scoring.embedding_to_bytes(vector)
    assert len(data) == 384 * 4
    back = scoring.embedding_from_bytes(data)
    assert back.dtype == np.float32
    assert np.array_equal(back, vector)


def _item(n, title):
    return NewsItem(
        source="test",
        published_at=datetime(2026, 1, 1, n, tzinfo=timezone.utc),
        title=title,
        url=f"http://x/{n}",
    )


def test_score_pending_batches_and_skips_scored(tmp_path):
    with NewsStore(tmp_path / "news.db") as store:
        store.add_items([_item(i, f"stocks crash {i}") for i in range(5)])
        finbert = FakeFinBert()
        count = scoring.score_pending(
            store, batch_size=2, finbert=finbert, embedder=FakeEmbedder()
        )
        assert count == 5
        assert [len(c) for c in finbert.calls] == [2, 2, 1]
        assert store.unscored_items() == []
        item = store.query_items()[0] if hasattr(store, "query_items") else None
        assert item is not None
        score = store.get_score(item.id)
        assert score.tone == pytest.approx(-0.80)
        assert score.category is None and score.event_id is None
        assert len(score.embedding) == 384 * 4
        # nothing left, so a second run scores nothing
        assert scoring.score_pending(store, finbert=finbert, embedder=FakeEmbedder()) == 0


def test_score_pending_limit(tmp_path):
    with NewsStore(tmp_path / "news.db") as store:
        store.add_items([_item(i, f"shares up {i}") for i in range(4)])
        assert scoring.score_pending(
            store, limit=3, finbert=FakeFinBert(), embedder=FakeEmbedder()
        ) == 3
        assert len(store.unscored_items()) == 1
