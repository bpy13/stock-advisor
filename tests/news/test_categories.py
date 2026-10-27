"""Tests for event categories. Logic tests use a fake embedder; the accuracy test uses the real
MiniLM model (already cached locally) on hand-written headlines kept apart from the seed phrases."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from stock_advisor.news import categories
from stock_advisor.news.categories import (
    CATEGORIES,
    MACRO_CATEGORIES,
    categorize,
    categorize_pending,
)
from stock_advisor.news.models import ItemScore, NewsItem
from stock_advisor.news.scoring import embedding_to_bytes
from stock_advisor.news.store import NewsStore

# 32 headlines written before the seeds were tuned. Never copy these into the seed phrases.
HEADLINES = [
    ("US imposes new tariffs on Chinese steel and aluminum imports", "trade_tariffs"),
    ("EU and Washington trade talks stall over import duties on cars", "trade_tariffs"),
    ("Federal Reserve holds interest rates steady, signals cuts later this year", "monetary_policy"),
    ("ECB raises key rate by a quarter point to fight inflation", "monetary_policy"),
    ("Congress passes federal budget as deficit widens", "fiscal_regulation"),
    ("SEC proposes stricter rules for hedge funds and new tax on buybacks", "fiscal_regulation"),
    ("Russian forces launch fresh missile strikes on Ukrainian cities", "war_conflict"),
    ("Israel and Hamas troops clash as ceasefire talks collapse", "war_conflict"),
    ("Suicide bomber kills dozens at crowded market in Pakistan", "terrorism"),
    ("Gunmen claim responsibility for terror attack on hotel", "terrorism"),
    ("WHO warns of new virus outbreak as hospitals fill up", "pandemic_health"),
    ("Health officials report rising cases of measles epidemic", "pandemic_health"),
    ("Hackers breach bank customer database in major ransomware attack", "cyber_security"),
    ("Cyberattack knocks airline booking systems offline", "cyber_security"),
    ("Powerful earthquake strikes coastal region, hundreds feared dead", "natural_disaster"),
    ("Hurricane makes landfall causing widespread flooding and power cuts", "natural_disaster"),
    ("Regional bank collapses as depositors rush to withdraw funds", "financial_crisis"),
    ("Credit markets freeze amid fears of a debt default and recession", "financial_crisis"),
    ("Opposition candidate wins presidential election in surprise result", "election_politics"),
    ("Parliament votes to call snap election after coalition falls apart", "election_politics"),
    ("Oil prices jump after OPEC agrees to cut crude output", "energy_commodities"),
    ("Gold and copper rally as natural gas supplies tighten", "energy_commodities"),
    ("Apple quarterly profit beats estimates on strong iPhone sales", "company_results"),
    ("Retailer posts lower third-quarter earnings and cuts full-year outlook", "company_results"),
    ("Microsoft agrees to acquire gaming studio in 10 billion dollar deal", "company_corporate_action"),
    ("Chipmaker announces share buyback and plans to spin off its unit", "company_corporate_action"),
    ("Pharma giant's board approves merger with rival biotech firm", "company_corporate_action"),
    ("Local bakery wins award for best sourdough in the county", "other"),
    ("Football club signs veteran striker on two-year contract", "other"),
    ("Tesla reports record deliveries and revenue growth in quarterly results", "company_results"),
    ("Floods and landslides leave thousands homeless after monsoon rains", "natural_disaster"),
    ("Government announces new import quotas and retaliatory tariffs on farm goods", "trade_tariffs"),
    # Added before the geopolitical_tension seeds were written.
    ("Beijing summons US ambassador over new arms package for Taiwan", "geopolitical_tension"),
    ("Washington blacklists dozens of Chinese tech firms, Beijing vows countermeasures", "geopolitical_tension"),
    ("Two countries expel diplomats in escalating spy dispute", "geopolitical_tension"),
    # Known mislabels: bond tender results and generic sector updates.
    ("Government 10-year bond tender draws strong demand, yields ease", "fiscal_regulation"),
    ("Sector Update: Consumer Discretionary Stocks Fall Late Afternoon", "other"),
]


class FakeEmbedder:
    """Maps a text to a fixed one-hot-ish vector chosen by a keyword, so logic is predictable."""

    KEYS = ["tariff", "rate", "war", "oil", "zzz"]

    def encode(self, texts):
        out = np.zeros((len(texts), 384), dtype=np.float32)
        for i, text in enumerate(texts):
            hit = next((j for j, k in enumerate(self.KEYS) if k in text.lower()), len(self.KEYS))
            out[i, hit] = 1.0
        return out


def test_category_lists():
    assert len(CATEGORIES) == 15
    assert "geopolitical_tension" in MACRO_CATEGORIES
    assert "other" in CATEGORIES
    assert set(MACRO_CATEGORIES) == {c for c in CATEGORIES if not c.startswith("company_") and c != "other"}
    assert len(HEADLINES) >= 30
    for category in CATEGORIES:
        assert sum(1 for _, c in HEADLINES if c == category) >= 2


def test_every_category_has_seeds():
    for category in CATEGORIES:
        if category != "other":
            assert len(categories.SEEDS[category]) >= 5


def test_empty_input():
    assert categorize([]) == []


def test_keyword_override_beats_weak_centroid():
    # The fake vectors are unrelated to the seeds, so only the keyword rule can decide.
    result = categorize(["Trump announces new tariffs on imports"], embeddings=np.zeros((1, 384), np.float32))
    assert result == ["trade_tariffs"]


def test_overrides_for_bond_tenders_and_sector_updates():
    titles = [
        "Treasury auction of 30-year bonds sees tail",
        "Sector Update: Energy Stocks Slip",
        "Oil auction of drilling rights announced",  # no bond word: not overridden
    ]
    got = categorize(titles, embeddings=np.zeros((3, 384), np.float32))
    assert got[0] == "fiscal_regulation"
    assert got[1] == "other"
    assert got[2] != "fiscal_regulation"


def test_weak_match_falls_back_to_other():
    vectors = np.zeros((1, 384), dtype=np.float32)
    assert categorize(["Local bakery wins award"], embeddings=vectors) == ["other"]


def test_categorize_embeds_when_not_given():
    result = categorize(["something about nothing", "tariff news"], embedder=FakeEmbedder())
    assert len(result) == 2
    assert result[1] == "trade_tariffs"


def test_categorize_pending_fills_only_missing(tmp_path):
    store = NewsStore(tmp_path / "news.db")
    when = datetime(2026, 1, 1, tzinfo=timezone.utc)
    seed = categories.SEEDS["war_conflict"][0]
    vec = np.zeros(384, dtype=np.float32)
    vec[0] = 1.0
    store.add_items(
        [
            NewsItem(id=f"a{i}", source="t", published_at=when, title=t)
            for i, t in enumerate(["Army tariffs plan", "Quiet day", "Unscored one"])
        ]
    )
    for item_id in ("a0", "a1"):
        store.update_scores(ItemScore(item_id=item_id, tone=0.1, embedding=embedding_to_bytes(vec)))
    store.update_scores(ItemScore(item_id="a1", category="monetary_policy"))
    assert seed
    assert categorize_pending(store) == 1  # a0 only: a1 already has a category, a2 has no embedding
    assert store.get_score("a0").category == "trade_tariffs"  # keyword rule fired
    assert store.get_score("a1").category == "monetary_policy"
    assert store.get_score("a2") is None
    assert categorize_pending(store) == 0
    store.close()


def test_seeds_do_not_contain_test_headlines():
    seeds = {s.lower() for group in categories.SEEDS.values() for s in group}
    assert not seeds & {h.lower() for h, _ in HEADLINES}


@pytest.mark.slow
def test_accuracy_on_hand_written_headlines():
    predicted = categorize([h for h, _ in HEADLINES])
    wrong = [(h, want, got) for (h, want), got in zip(HEADLINES, predicted) if want != got]
    accuracy = 1 - len(wrong) / len(HEADLINES)
    assert accuracy >= 0.80, f"accuracy {accuracy:.0%}; wrong: {wrong}"
