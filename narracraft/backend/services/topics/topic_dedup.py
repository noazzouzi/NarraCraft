"""Cross-source topic deduplication.

Merges identical or near-identical topics found across different sources
(wiki, Reddit, YouTube, AI). When the same fact appears in 3+ sources,
it gets a high confidence score.
"""

import re
from dataclasses import dataclass, field


@dataclass
class RawTopic:
    title: str
    description: str = ""
    source_type: str = ""  # wiki, reddit, youtube, ai
    source_url: str = ""
    source_score: float = 0  # Source-specific relevance score
    franchise_id: str = ""
    category: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class DeduplicatedTopic:
    title: str  # Best title from sources
    description: str
    sources: list[dict]  # All sources that mention this topic
    source_count: int
    confidence: str  # low (1 source), medium (2), high (3+)
    category: str
    franchise_id: str
    combined_score: float = 0


def deduplicate_topics(
    raw_topics: list[RawTopic],
    similarity_threshold: float = 0.45,
) -> list[DeduplicatedTopic]:
    """Merge similar topics from different sources into deduplicated entries."""
    if not raw_topics:
        return []

    clusters: list[list[RawTopic]] = []

    for topic in raw_topics:
        merged = False
        for cluster in clusters:
            # Check similarity against the cluster representative
            rep = cluster[0]
            sim = _text_similarity(topic.title, rep.title)
            if sim >= similarity_threshold:
                # Also check description similarity for borderline cases
                if sim < 0.6 and topic.description and rep.description:
                    desc_sim = _text_similarity(topic.description, rep.description)
                    if desc_sim < 0.3:
                        continue
                cluster.append(topic)
                merged = True
                break

        if not merged:
            clusters.append([topic])

    # Convert clusters to deduplicated topics
    deduped: list[DeduplicatedTopic] = []
    for cluster in clusters:
        # Pick the best title (longest, most descriptive)
        best_title = max(cluster, key=lambda t: len(t.title)).title

        # Pick the best description
        descriptions = [t.description for t in cluster if t.description]
        best_desc = max(descriptions, key=len) if descriptions else ""

        # Collect all sources
        sources = [{
            "type": t.source_type,
            "url": t.source_url,
            "score": t.source_score,
            "title": t.title,
        } for t in cluster]

        # Count unique source types
        source_types = set(t.source_type for t in cluster)
        source_count = len(source_types)

        # Confidence based on source diversity
        if source_count >= 3:
            confidence = "high"
        elif source_count >= 2:
            confidence = "medium"
        else:
            confidence = "low"

        # Category — use the most common one
        categories = [t.category for t in cluster if t.category]
        category = max(set(categories), key=categories.count) if categories else ""

        franchise_id = cluster[0].franchise_id

        # Combined score — higher for multi-source validation
        combined_score = sum(t.source_score for t in cluster) * (1 + 0.3 * (source_count - 1))

        deduped.append(DeduplicatedTopic(
            title=best_title,
            description=best_desc[:500],
            sources=sources,
            source_count=source_count,
            confidence=confidence,
            category=category,
            franchise_id=franchise_id,
            combined_score=round(combined_score, 2),
        ))

    # Sort by combined score
    deduped.sort(key=lambda t: t.combined_score, reverse=True)
    return deduped


def _text_similarity(a: str, b: str) -> float:
    """Compute word-overlap Jaccard similarity between two texts."""
    words_a = set(_normalize(a).split())
    words_b = set(_normalize(b).split())

    if not words_a or not words_b:
        return 0.0

    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _normalize(text: str) -> str:
    """Normalize text for comparison."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    # Remove common stop words
    stops = {"the", "a", "an", "is", "was", "were", "are", "been", "be",
             "have", "has", "had", "do", "does", "did", "will", "would",
             "could", "should", "may", "might", "shall", "can",
             "this", "that", "these", "those", "it", "its",
             "of", "in", "to", "for", "with", "on", "at", "from", "by",
             "and", "or", "but", "not", "no", "so", "if", "as"}
    words = [w for w in text.split() if w not in stops and len(w) > 1]
    return " ".join(words)
