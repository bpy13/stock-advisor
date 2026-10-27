"""Headline tone (FinBERT) and sentence embeddings (MiniLM). Models load lazily, once per process.

Only the title is scored. Both functions accept an optional model object so tests can inject a
fake and never download weights.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import numpy as np

from stock_advisor.news.models import ItemScore

FINBERT_NAME = "ProsusAI/finbert"
EMBED_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384
MAX_TOKENS = 64  # headlines are short; longer inputs are truncated

ToneRow = Tuple[float, float, float, float]  # (p_pos, p_neg, p_neu, tone)


class FinBertModel:
    """Wraps the FinBERT classifier. `predict` returns an (n, 3) array of probabilities in the
    column order positive, negative, neutral (read from the model's own label map)."""

    def __init__(self, name: str = FINBERT_NAME) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(name)
        self._model = AutoModelForSequenceClassification.from_pretrained(name).eval()
        labels = {int(i): str(text).lower() for i, text in self._model.config.id2label.items()}
        self._order = [
            next(i for i, label in labels.items() if label == wanted)
            for wanted in ("positive", "negative", "neutral")
        ]

    def predict(self, texts: Sequence[str]) -> np.ndarray:
        batch = self._tokenizer(
            list(texts),
            padding=True,
            truncation=True,
            max_length=MAX_TOKENS,
            return_tensors="pt",
        )
        with self._torch.no_grad():
            logits = self._model(**batch).logits
        probs = self._torch.softmax(logits, dim=-1).numpy()
        return probs[:, self._order]


_finbert: Optional[FinBertModel] = None
_embedder = None


def get_finbert() -> FinBertModel:
    global _finbert
    if _finbert is None:
        _finbert = FinBertModel()
    return _finbert


def get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(EMBED_NAME, device="cpu")
    return _embedder


def score_tone(texts: Sequence[str], model=None) -> List[ToneRow]:
    """Return (p_pos, p_neg, p_neu, tone) per text, where tone = p_pos - p_neg."""
    if len(texts) == 0:
        return []
    model = model or get_finbert()
    probs = np.asarray(model.predict(list(texts)), dtype=float)
    return [
        (float(p), float(n), float(u), float(p - n)) for p, n, u in probs[:, :3]
    ]


def embed(texts: Sequence[str], model=None) -> np.ndarray:
    """Return an (n, 384) float32 array with unit-length rows."""
    if len(texts) == 0:
        return np.zeros((0, EMBED_DIM), dtype=np.float32)
    model = model or get_embedder()
    vectors = np.asarray(model.encode(list(texts)), dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return (vectors / np.maximum(norms, 1e-12)).astype(np.float32)


def embedding_to_bytes(vector: np.ndarray) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def embedding_from_bytes(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype=np.float32).copy()


def score_pending(
    store,
    batch_size: int = 64,
    limit: Optional[int] = None,
    finbert=None,
    embedder=None,
) -> int:
    """Score tone and embedding for items without a tone. Returns the number scored.

    Category and event fields are left for the later steps (update_scores skips None fields).
    """
    items = store.unscored_items(limit=limit)
    for start in range(0, len(items), batch_size):
        chunk = items[start : start + batch_size]
        titles = [item.title for item in chunk]
        tones = score_tone(titles, model=finbert)
        vectors = embed(titles, model=embedder)
        for item, (pos, neg, neu, tone), vector in zip(chunk, tones, vectors):
            store.update_scores(
                ItemScore(
                    item_id=item.id,
                    tone_pos=pos,
                    tone_neg=neg,
                    tone_neu=neu,
                    tone=tone,
                    embedding=embedding_to_bytes(vector),
                )
            )
    return len(items)
