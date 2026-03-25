"""Topics API routes — discovery, listing, queue management."""

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.db.database import get_db
from backend.config.config_loader import get_franchise_registry
from backend.services.topics.wiki_trivia import scrape_trivia
from backend.services.topics.reddit_scraper import (
    scrape_franchise_subreddits,
    filter_lore_posts,
)
from backend.services.topics.youtube_research import research_franchise_youtube
from backend.services.topics.ai_suggestions import generate_suggestions
from backend.services.topics.topic_scorer import score_topic, ScoringInput
from backend.services.topics.topic_dedup import (
    deduplicate_topics,
    RawTopic,
)

router = APIRouter(prefix="/api/topics", tags=["topics"])


class DiscoverRequest(BaseModel):
    franchise_id: str
    sources: list[str] = ["wiki", "reddit", "youtube", "ai"]  # Which sources to query
    similarity_threshold: float = 0.45


@router.post("/discover")
async def discover_topics(req: DiscoverRequest):
    """Run topic discovery pipeline for a franchise.

    1. Scrape wiki trivia sections
    2. Scrape Reddit lore posts
    3. Research YouTube transcripts
    4. Generate AI suggestions
    5. Deduplicate across sources
    6. Score each topic
    7. Save to database
    """
    raw_topics: list[RawTopic] = []
    errors: list[str] = []

    # Get franchise info from DB for context
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT config_json, name FROM franchises WHERE id = ?",
            (req.franchise_id,),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    franchise_name = req.franchise_id.replace("_", " ").title()
    character_names: list[str] = []
    topic_seeds: list[str] = []

    if row:
        franchise_name = row["name"]
        config = json.loads(row["config_json"])
        character_names = [
            c.get("name", "") for c in config.get("character_archetypes", [])
        ]
        topic_seeds = config.get("topic_seeds", [])
    else:
        # Try franchise registry as fallback
        registry = get_franchise_registry()
        for entry in registry.get("franchises", []):
            if entry.get("id") == req.franchise_id:
                franchise_name = entry.get("name", franchise_name)
                for c in entry.get("character_archetypes", []):
                    character_names.append(c.get("name", ""))
                topic_seeds = entry.get("topic_seeds", [])
                break

    # --- Source 1: Wiki trivia ---
    if "wiki" in req.sources:
        try:
            trivia_items = await scrape_trivia(req.franchise_id)
            for item in trivia_items:
                raw_topics.append(RawTopic(
                    title=item.text[:120],
                    description=item.text,
                    source_type="wiki",
                    source_url=item.source_url,
                    source_score=2.0,
                    franchise_id=req.franchise_id,
                    category=_guess_category(item.text),
                ))
        except Exception as e:
            errors.append(f"wiki: {e}")

    # --- Source 2: Reddit lore posts ---
    if "reddit" in req.sources:
        try:
            reddit_posts = await scrape_franchise_subreddits(req.franchise_id)
            lore_posts = filter_lore_posts(reddit_posts)
            for post in lore_posts:
                raw_topics.append(RawTopic(
                    title=post.title,
                    description=post.selftext[:500],
                    source_type="reddit",
                    source_url=post.url,
                    source_score=min(post.score / 100, 5.0),
                    franchise_id=req.franchise_id,
                    category=_guess_category(post.title + " " + post.selftext),
                    extra={
                        "reddit_score": post.score,
                        "reddit_comments": post.num_comments,
                        "subreddit": post.subreddit,
                    },
                ))
        except Exception as e:
            errors.append(f"reddit: {e}")

    # --- Source 3: YouTube transcripts ---
    if "youtube" in req.sources:
        try:
            yt_facts = await research_franchise_youtube(franchise_name)
            for fact in yt_facts:
                raw_topics.append(RawTopic(
                    title=fact.text[:120],
                    description=fact.text,
                    source_type="youtube",
                    source_url=f"https://youtube.com/watch?v={fact.video_id}",
                    source_score=2.5,
                    franchise_id=req.franchise_id,
                    category=_guess_category(fact.text),
                    extra={
                        "video_title": fact.video_title,
                        "video_id": fact.video_id,
                    },
                ))
        except Exception as e:
            errors.append(f"youtube: {e}")

    # --- Source 4: AI suggestions ---
    if "ai" in req.sources:
        try:
            suggestions = generate_suggestions(
                franchise_name=franchise_name,
                character_names=character_names or None,
                existing_seeds=topic_seeds or None,
                count=15,
            )
            for sug in suggestions:
                raw_topics.append(RawTopic(
                    title=sug.title,
                    description=sug.description,
                    source_type="ai",
                    source_url="",
                    source_score=1.0,
                    franchise_id=req.franchise_id,
                    category=sug.category,
                    extra={"requires_fact_check": sug.requires_fact_check},
                ))
        except Exception as e:
            errors.append(f"ai: {e}")

    if not raw_topics:
        return {
            "franchise_id": req.franchise_id,
            "discovered": 0,
            "errors": errors,
            "message": "No topics found from any source",
        }

    # --- Step 5: Deduplicate ---
    deduped = deduplicate_topics(raw_topics, req.similarity_threshold)

    # --- Step 6: Score each topic ---
    scored_topics = []
    for topic in deduped:
        # Build scoring input from aggregated source data
        reddit_score = 0
        reddit_comments = 0
        youtube_views = 0
        has_wiki = False

        for src in topic.sources:
            if src["type"] == "reddit":
                # Find the raw topic's extra data
                for rt in raw_topics:
                    if rt.source_url == src.get("url"):
                        reddit_score = max(reddit_score, rt.extra.get("reddit_score", 0))
                        reddit_comments = max(reddit_comments, rt.extra.get("reddit_comments", 0))
                        break
            elif src["type"] == "wiki":
                has_wiki = True
            elif src["type"] == "youtube":
                youtube_views = max(youtube_views, 1000)  # Default estimate

        scoring_input = ScoringInput(
            title=topic.title,
            sources=topic.sources,
            reddit_score=reddit_score,
            reddit_comments=reddit_comments,
            youtube_views=youtube_views,
            has_wiki_section=has_wiki,
            category=topic.category,
            freshness="evergreen",
        )
        result = score_topic(scoring_input)
        scored_topics.append((topic, result))

    # --- Step 7: Save to database ---
    db = await get_db()
    saved_count = 0
    try:
        for topic, score_result in scored_topics:
            topic_id = f"{req.franchise_id}/topic/{uuid.uuid4().hex[:12]}"
            await db.execute(
                """INSERT OR IGNORE INTO topics
                   (id, franchise_id, title, description, category, score,
                    score_breakdown_json, sources_json, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'discovered', CURRENT_TIMESTAMP)""",
                (
                    topic_id,
                    req.franchise_id,
                    topic.title,
                    topic.description,
                    topic.category,
                    score_result.total_score,
                    json.dumps(score_result.breakdown),
                    json.dumps(topic.sources),
                ),
            )
            saved_count += 1

        await db.commit()
    finally:
        await db.close()

    return {
        "franchise_id": req.franchise_id,
        "raw_count": len(raw_topics),
        "deduped_count": len(deduped),
        "discovered": saved_count,
        "errors": errors if errors else None,
        "top_topics": [
            {
                "title": t.title,
                "score": r.total_score,
                "tier": r.tier,
                "sources": t.source_count,
                "confidence": t.confidence,
                "category": t.category,
            }
            for t, r in sorted(scored_topics, key=lambda x: x[1].total_score, reverse=True)[:10]
        ],
    }


def _guess_category(text: str) -> str:
    """Guess topic category from text content."""
    text_lower = text.lower()
    if any(kw in text_lower for kw in ["easter egg", "hidden", "secret", "reference"]):
        return "easter_egg"
    if any(kw in text_lower for kw in ["cut content", "scrapped", "removed", "unused", "beta"]):
        return "cut_content"
    if any(kw in text_lower for kw in ["design", "developer", "development", "mechanic"]):
        return "dev_design"
    if any(kw in text_lower for kw in ["lore", "story", "mythology", "foreshadow", "symbolism"]):
        return "lore"
    if any(kw in text_lower for kw in ["meme", "funny", "hilarious", "joke", "bug"]):
        return "memes"
    if any(kw in text_lower for kw in ["character", "protagonist", "villain", "hero"]):
        return "characters"
    return "lore"  # default


@router.get("")
async def list_topics(
    status: Optional[str] = Query(None),
    franchise: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """List topics with optional filters."""
    db = await get_db()
    try:
        where = "WHERE 1=1"
        params: list = []

        if status:
            where += " AND status = ?"
            params.append(status)
        if franchise:
            where += " AND franchise_id = ?"
            params.append(franchise)

        # Get total count
        count_cursor = await db.execute(f"SELECT COUNT(*) FROM topics {where}", params)
        total = (await count_cursor.fetchone())[0]

        # Get paginated results
        query = f"SELECT * FROM topics {where} ORDER BY score DESC LIMIT ? OFFSET ?"
        cursor = await db.execute(query, params + [limit, offset])
        rows = await cursor.fetchall()
        return {"topics": [dict(row) for row in rows], "total": total}
    finally:
        await db.close()


@router.get("/{topic_id}")
async def get_topic(topic_id: str):
    """Get a single topic with full details."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM topics WHERE id = ?", (topic_id,))
        row = await cursor.fetchone()
        if not row:
            return {"error": "Topic not found"}
        return dict(row)
    finally:
        await db.close()


@router.put("/{topic_id}/queue")
async def queue_topic(topic_id: str):
    """Move a topic to queued status."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE topics SET status = 'queued', queued_at = CURRENT_TIMESTAMP WHERE id = ?",
            (topic_id,),
        )
        await db.commit()
        return {"status": "queued", "topic_id": topic_id}
    finally:
        await db.close()


@router.put("/{topic_id}/skip")
async def skip_topic(topic_id: str):
    """Skip a topic."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE topics SET status = 'skipped' WHERE id = ?",
            (topic_id,),
        )
        await db.commit()
        return {"status": "skipped", "topic_id": topic_id}
    finally:
        await db.close()


@router.put("/{topic_id}")
async def update_topic(topic_id: str, data: dict):
    """Edit topic fields (narrator, closer_style, etc.)."""
    db = await get_db()
    try:
        allowed_fields = {"narrator_archetype", "closer_style", "title", "description", "category"}
        updates = {k: v for k, v in data.items() if k in allowed_fields}
        if not updates:
            return {"error": "No valid fields to update"}

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [topic_id]
        await db.execute(f"UPDATE topics SET {set_clause} WHERE id = ?", values)
        await db.commit()
        return {"status": "updated", "topic_id": topic_id}
    finally:
        await db.close()
