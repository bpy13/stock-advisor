"""Event categories: nearest seed-phrase centroid by embedding, with keyword overrides.

Each category has a few seed phrases. Their embeddings are averaged into one centroid. A headline
goes to the centroid with the highest cosine similarity. When that similarity is weak, a keyword
match decides; when it is weak and no keyword matches, the headline is "other".
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

import numpy as np

from stock_advisor.news.scoring import embed, embedding_from_bytes

CATEGORIES: List[str] = [
    "trade_tariffs",
    "monetary_policy",
    "fiscal_regulation",
    "war_conflict",
    "geopolitical_tension",
    "terrorism",
    "pandemic_health",
    "cyber_security",
    "natural_disaster",
    "financial_crisis",
    "election_politics",
    "energy_commodities",
    "company_results",
    "company_corporate_action",
    "other",
]
MACRO_CATEGORIES: List[str] = [
    c for c in CATEGORIES if not c.startswith("company_") and c != "other"
]

# Similarity at or above STRONG: trust the centroid. Below MIN with no keyword: "other".
STRONG_SIMILARITY = 0.50
MIN_SIMILARITY = 0.30

# Seed phrases are short generic descriptions. They are kept separate from the test headlines.
SEEDS: Dict[str, List[str]] = {
    "trade_tariffs": [
        "tariffs on imported goods",
        "trade war between two countries",
        "import duties and export controls",
        "trade agreement negotiations",
        "customs levies on foreign products",
        "trade deficit and trade barriers",
    ],
    "monetary_policy": [
        "central bank decision on interest rates",
        "rate hike to curb inflation",
        "quantitative easing and balance sheet",
        "central bank governor speech on monetary policy",
        "inflation data and rate cut expectations",
        "bond yields move on policy meeting",
    ],
    "fiscal_regulation": [
        "government spending bill and budget deficit",
        "new tax law passed by lawmakers",
        "regulator announces tougher rules for industry",
        "antitrust investigation and fines",
        "legislation on financial regulation",
        "government stimulus package",
    ],
    "war_conflict": [
        "military attack and invasion",
        "armed conflict and airstrikes",
        "troops deployed to the border",
        "ceasefire negotiations in the war",
        "missile strike on city",
        "sanctions imposed after military aggression",
    ],
    "geopolitical_tension": [
        "diplomatic dispute between rival powers",
        "sanctions imposed on foreign officials and firms",
        "tensions rise across the Taiwan Strait",
        "ambassador summoned and diplomats expelled",
        "foreign ministry condemns blacklist of its companies",
        "relations between Washington and Beijing deteriorate",
    ],
    "terrorism": [
        "terrorist attack kills civilians",
        "bombing claimed by extremist group",
        "militants carry out deadly assault",
        "hostage situation and security alert",
        "police foil terror plot",
    ],
    "pandemic_health": [
        "disease outbreak spreads across countries",
        "pandemic and new virus variant",
        "health authority warns of infections",
        "vaccine rollout and hospital capacity",
        "epidemic declared by health organization",
    ],
    "cyber_security": [
        "hackers steal data in cyber attack",
        "ransomware locks company systems",
        "data breach exposes customer records",
        "cybersecurity incident and system outage",
        "malware campaign targets infrastructure",
    ],
    "natural_disaster": [
        "earthquake destroys buildings",
        "hurricane and typhoon cause damage",
        "wildfire forces evacuations",
        "severe flooding after heavy rain",
        "tsunami volcano eruption drought",
    ],
    "financial_crisis": [
        "bank failure and bailout",
        "market crash and panic selling",
        "sovereign debt default fears",
        "liquidity crunch and credit freeze",
        "recession fears and financial contagion",
        "stock market plunges on systemic risk",
    ],
    "election_politics": [
        "voters go to the polls in national election",
        "candidate wins the vote for president",
        "government coalition collapses",
        "political party leadership contest",
        "referendum result and political turmoil",
        "prime minister resigns",
    ],
    "energy_commodities": [
        "crude oil price moves",
        "OPEC production decision",
        "natural gas and coal supply",
        "gold silver and copper prices",
        "wheat corn and soybean futures",
        "commodity market rally",
    ],
    "company_results": [
        "company reports quarterly earnings",
        "profit and revenue beat analyst forecasts",
        "company raises annual guidance",
        "earnings per share fall short of expectations",
        "annual results show sales growth",
        "company issues profit warning",
    ],
    "company_corporate_action": [
        "company announces acquisition of rival",
        "merger agreement between two firms",
        "share buyback and dividend announcement",
        "company plans spin-off and stock split",
        "initial public offering priced",
        "chief executive steps down",
        "company announces layoffs and restructuring",
    ],
}

# Keywords checked when the centroid match is weak. Whole-word, case-insensitive.
KEYWORDS: Dict[str, List[str]] = {
    "trade_tariffs": ["tariff", "tariffs", "trade war", "import duties", "import quotas"],
    "monetary_policy": [
        "interest rate",
        "interest rates",
        "rate cut",
        "rate hike",
        "federal reserve",
        "ecb",
        "bank of japan",
        "bank of england",
        "fomc",
    ],
    "fiscal_regulation": ["budget", "tax", "regulator", "antitrust", "stimulus"],
    "war_conflict": ["war", "invasion", "airstrike", "airstrikes", "missile", "troops", "ceasefire"],
    "geopolitical_tension": [
        "sanctions",
        "embassy",
        "cross-strait",
        "taiwan strait",
        "diplomatic row",
        "diplomatic dispute",
        "expels diplomats",
    ],
    "terrorism": ["terror", "terrorist", "terrorism", "suicide bomber", "bombing"],
    "pandemic_health": ["pandemic", "epidemic", "outbreak", "virus", "covid", "who warns"],
    "cyber_security": ["cyberattack", "cyber attack", "hackers", "ransomware", "data breach"],
    "natural_disaster": ["earthquake", "hurricane", "typhoon", "tsunami", "wildfire", "flood", "floods"],
    "financial_crisis": ["bank run", "bailout", "default", "bank collapse", "credit crunch"],
    "election_politics": ["election", "elections", "referendum", "ballot", "voters"],
    "energy_commodities": ["crude", "opec", "oil prices", "natural gas", "gold prices"],
    "company_results": ["quarterly earnings", "quarterly profit", "earnings", "profit warning"],
    "company_corporate_action": ["acquire", "acquisition", "merger", "buyback", "spin off", "spin-off", "ipo"],
}

_KEYWORD_PATTERNS = {
    category: re.compile(r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\b", re.IGNORECASE)
    for category, words in KEYWORDS.items()
}

# Checked before the centroid match, because the embedding gets these wrong (a government bond
# tender result reads like "bond failure"; a generic "Sector Update" has no event in it).
_OVERRIDES = [
    (re.compile(r"^\s*sector update\s*:", re.IGNORECASE), "other"),
    (
        re.compile(
            r"\b(?:(?:bond|bill|bills|note|notes|treasury|treasuries|debt)\b[^.]{0,40}\b(?:tender|auction)"
            r"|(?:tender|auction)\b[^.]{0,40}\b(?:bond|bonds|bills|notes|treasury|treasuries))",
            re.IGNORECASE,
        ),
        "fiscal_regulation",
    ),
]

_centroids: Optional[np.ndarray] = None
_centroid_names = [c for c in CATEGORIES if c != "other"]


def _get_centroids(embedder=None) -> np.ndarray:
    """Unit-length mean embedding of each category's seeds, in `_centroid_names` order.
    Cached after the first call made with the default embedder."""
    global _centroids
    if _centroids is not None and embedder is None:
        return _centroids
    rows = []
    for name in _centroid_names:
        mean = embed(SEEDS[name], model=embedder).mean(axis=0)
        rows.append(mean / max(float(np.linalg.norm(mean)), 1e-12))
    result = np.vstack(rows).astype(np.float32)
    if embedder is None:
        _centroids = result
    return result


def _keyword_category(title: str) -> Optional[str]:
    best, best_hits = None, 0
    for category, pattern in _KEYWORD_PATTERNS.items():
        hits = len(pattern.findall(title))
        if hits > best_hits:
            best, best_hits = category, hits
    return best


def categorize(
    titles: Sequence[str], embeddings: Optional[np.ndarray] = None, embedder=None
) -> List[str]:
    """Return one category per title. Embeds the titles unless `embeddings` (n, 384) is given."""
    if len(titles) == 0:
        return []
    if embeddings is None:
        embeddings = embed(titles, model=embedder)
    sims = np.asarray(embeddings, dtype=np.float32) @ _get_centroids(embedder).T
    result = []
    for title, row in zip(titles, sims):
        override = next((cat for pattern, cat in _OVERRIDES if pattern.search(title)), None)
        if override is not None:
            result.append(override)
            continue
        best = int(np.argmax(row))
        score = float(row[best])
        if score >= STRONG_SIMILARITY:
            result.append(_centroid_names[best])
            continue
        keyword = _keyword_category(title)
        if keyword is not None:
            result.append(keyword)
        elif score >= MIN_SIMILARITY:
            result.append(_centroid_names[best])
        else:
            result.append("other")
    return result


def categorize_pending(store, limit: Optional[int] = None) -> int:
    """Fill the category of scored items that have an embedding but no category.

    Uses the stored embeddings, so no model is loaded. Returns the number categorized.
    """
    rows = store.items_awaiting_category(limit)
    if not rows:
        return 0
    vectors = np.vstack([embedding_from_bytes(emb) for _, emb in rows])
    labels = categorize([item.title for item, _ in rows], embeddings=vectors)
    # set_category, not update_scores: update_scores would reset high_impact to 0.
    for (item, _), label in zip(rows, labels):
        store.set_category(item.id, label)
    return len(rows)
