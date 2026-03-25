"""Multi-signal topic scoring algorithm.

Scores topics based on multiple signals:
- Source count (found in multiple sources = more credible)
- Reddit engagement (upvotes, comments)
- YouTube views on similar content
- Wiki presence (has its own wiki section)
- Category bonus (from analytics feedback loop)
- Freshness (evergreen vs trending)
"""

from dataclasses import dataclass, field


@dataclass
class ScoringInput:
    title: str
    sources: list[dict] = field(default_factory=list)
    # Each source: {"type": "wiki"|"reddit"|"youtube"|"ai", "score": float, "details": {...}}
    reddit_score: int = 0
    reddit_comments: int = 0
    youtube_views: int = 0
    has_wiki_section: bool = False
    category: str = ""
    freshness: str = "evergreen"  # evergreen, trending, time_sensitive
    asset_readiness: str = "unknown"  # ready, partial, blocked


@dataclass
class ScoringResult:
    total_score: float
    breakdown: dict[str, float]
    tier: str  # S, A, B, C, D


# Scoring weights
WEIGHTS = {
    "source_diversity": 3.0,    # Found in multiple independent sources
    "reddit_engagement": 2.0,   # High Reddit engagement
    "youtube_validation": 2.5,  # Similar content performs well on YouTube
    "wiki_presence": 1.5,       # Has dedicated wiki content
    "uniqueness": 2.0,          # Not a commonly covered topic
    "freshness": 1.0,           # Bonus for trending topics
    "asset_readiness": 1.0,     # Can we actually make this video?
}

# Category performance bonuses (adjusted by analytics feedback loop)
CATEGORY_BONUSES: dict[str, float] = {
    "characters": 1.2,
    "dev_design": 1.0,
    "lore": 1.1,
    "easter_egg": 1.3,
    "cut_content": 1.1,
    "memes": 0.9,
}


def score_topic(input: ScoringInput) -> ScoringResult:
    """Score a topic based on multiple signals."""
    breakdown: dict[str, float] = {}

    # 1. Source diversity (0-5 points, scaled by weight)
    source_types = set(s.get("type") for s in input.sources)
    source_score = min(len(source_types), 4) / 4 * 5  # Max 5 for 4+ source types
    breakdown["source_diversity"] = round(source_score * WEIGHTS["source_diversity"], 2)

    # 2. Reddit engagement (0-5 points)
    if input.reddit_score > 0:
        # Log scale: 100 upvotes = 2.5, 1000 = 3.75, 10000 = 5
        import math
        reddit_score = min(math.log10(max(input.reddit_score, 1)) / 4 * 5, 5)
        comment_bonus = min(input.reddit_comments / 100, 1.0)
        reddit_score = min(reddit_score + comment_bonus, 5)
    else:
        reddit_score = 0
    breakdown["reddit_engagement"] = round(reddit_score * WEIGHTS["reddit_engagement"], 2)

    # 3. YouTube validation (0-5 points)
    if input.youtube_views > 0:
        import math
        yt_score = min(math.log10(max(input.youtube_views, 1)) / 6 * 5, 5)
    else:
        yt_score = 0
    breakdown["youtube_validation"] = round(yt_score * WEIGHTS["youtube_validation"], 2)

    # 4. Wiki presence (0 or 3 points)
    wiki_score = 3.0 if input.has_wiki_section else 0.0
    breakdown["wiki_presence"] = round(wiki_score * WEIGHTS["wiki_presence"], 2)

    # 5. Uniqueness (baseline 3 — would be adjusted by dedup module)
    uniqueness_score = 3.0
    breakdown["uniqueness"] = round(uniqueness_score * WEIGHTS["uniqueness"], 2)

    # 6. Freshness bonus
    freshness_map = {"trending": 2.0, "time_sensitive": 1.5, "evergreen": 1.0}
    freshness_score = freshness_map.get(input.freshness, 1.0)
    breakdown["freshness"] = round(freshness_score * WEIGHTS["freshness"], 2)

    # 7. Asset readiness
    readiness_map = {"ready": 2.0, "partial": 1.0, "blocked": 0.0, "unknown": 0.5}
    readiness_score = readiness_map.get(input.asset_readiness, 0.5)
    breakdown["asset_readiness"] = round(readiness_score * WEIGHTS["asset_readiness"], 2)

    # Category bonus multiplier
    category_mult = CATEGORY_BONUSES.get(input.category, 1.0)

    # Total
    raw_total = sum(breakdown.values()) * category_mult
    total = round(raw_total, 1)

    # Tier assignment
    if total >= 30:
        tier = "S"
    elif total >= 22:
        tier = "A"
    elif total >= 15:
        tier = "B"
    elif total >= 8:
        tier = "C"
    else:
        tier = "D"

    return ScoringResult(total_score=total, breakdown=breakdown, tier=tier)
