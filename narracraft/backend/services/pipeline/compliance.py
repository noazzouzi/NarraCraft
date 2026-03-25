"""Compliance module — script similarity check + content filter.

Step 3 in the pipeline. Ensures:
1. Script is sufficiently original vs recent scripts (cosine/Jaccard similarity)
2. Content is advertiser-friendly (no blocked topics)
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from backend.browser.gemini import send_prompt
from backend.config.config_loader import get_config
from backend.db.database import get_db

logger = logging.getLogger(__name__)


@dataclass
class ComplianceResult:
    passed: bool
    similarity_score: float
    content_filter_passed: bool
    content_filter_flags: list[str]
    errors: list[str]


async def check_compliance(
    script_text: str,
    script_json: dict,
    franchise_id: str,
) -> ComplianceResult:
    """Run full compliance checks on a script."""
    errors: list[str] = []

    # 1. Similarity check against recent scripts
    similarity = await _check_similarity(script_text, franchise_id)

    config = get_config()
    threshold = config.get("quality", {}).get("script_compliance", {}).get("similarity_threshold", 0.70)

    if similarity > threshold:
        errors.append(f"Script too similar to a recent script (score: {similarity:.2f}, threshold: {threshold})")

    # 2. Content filter
    filter_passed, flags = await _check_content_filter(script_text)
    if not filter_passed:
        errors.append(f"Content filter flagged: {', '.join(flags)}")

    return ComplianceResult(
        passed=len(errors) == 0,
        similarity_score=similarity,
        content_filter_passed=filter_passed,
        content_filter_flags=flags,
        errors=errors,
    )


async def _check_similarity(script_text: str, franchise_id: str) -> float:
    """Check similarity of the new script against the last N scripts."""
    config = get_config()
    lookback = config.get("quality", {}).get("script_compliance", {}).get("similarity_lookback", 100)

    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT script_json FROM scripts
               WHERE topic_id IN (SELECT id FROM topics WHERE franchise_id = ?)
               ORDER BY created_at DESC LIMIT ?""",
            (franchise_id, lookback),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()

    if not rows:
        return 0.0

    new_words = _extract_words(script_text)
    max_similarity = 0.0

    for row in rows:
        try:
            old_script = json.loads(row["script_json"])
            old_dialogue = " ".join(
                scene.get("dialogue", "")
                for scene in old_script.get("scenes", [])
            )
            old_words = _extract_words(old_dialogue)
            sim = _jaccard_similarity(new_words, old_words)
            max_similarity = max(max_similarity, sim)
        except (json.JSONDecodeError, KeyError):
            continue

    return max_similarity


def _extract_words(text: str) -> set[str]:
    """Extract normalized words from text."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    # Remove stop words
    stops = {
        "the", "a", "an", "is", "was", "were", "are", "been", "be",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can",
        "this", "that", "these", "those", "it", "its",
        "of", "in", "to", "for", "with", "on", "at", "from", "by",
        "and", "or", "but", "not", "no", "so", "if", "as", "i", "me", "my",
    }
    return {w for w in text.split() if w not in stops and len(w) > 1}


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    """Compute Jaccard similarity between two word sets."""
    if not a or not b:
        return 0.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union)


async def _check_content_filter(script_text: str) -> tuple[bool, list[str]]:
    """Check if script content is advertiser-friendly.

    Uses Gemini as a content classifier.
    """
    config = get_config()
    filter_config = config.get("quality", {}).get("script_compliance", {}).get("content_filter", {})

    if not filter_config.get("enabled", True):
        return True, []

    block_topics = filter_config.get("block_on", [
        "graphic_violence", "hate_speech", "sexual_content",
        "dangerous_acts", "misinformation", "child_safety",
    ])
    warn_topics = filter_config.get("warn_on", [
        "mild_controversy", "health_claims", "political_reference",
    ])

    prompt = f"""Analyze this script for a YouTube Short and classify it for advertiser safety.

Script:
\"\"\"
{script_text}
\"\"\"

Check for these BLOCKED categories: {', '.join(block_topics)}
Check for these WARNING categories: {', '.join(warn_topics)}

Respond with ONLY a JSON object:
{{
  "safe": true/false,
  "blocked_flags": ["list of blocked categories found, empty if none"],
  "warning_flags": ["list of warning categories found, empty if none"],
  "reason": "brief explanation"
}}"""

    try:
        from backend.browser.gemini import parse_json_response
        raw = await send_prompt(prompt, timeout=30000)
        result = parse_json_response(raw)

        if result:
            blocked = result.get("blocked_flags", [])
            warnings = result.get("warning_flags", [])
            is_safe = result.get("safe", True) and len(blocked) == 0
            return is_safe, blocked + warnings
    except Exception as e:
        logger.warning("Content filter check failed: %s — defaulting to pass", e)

    # Default to pass if filter fails (don't block on filter errors)
    return True, []
