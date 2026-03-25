"""Feedback loop engine — adjusts system behavior based on analytics data.

Recalculates:
- Topic category bonuses (which categories perform best)
- Franchise weights (prioritize high-performing franchises)
- Hook pattern analysis (which hook styles retain viewers)
- Narrator performance comparison
- Schedule optimization (best upload time windows)

All results are stored in the settings table for use by other modules.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone

from backend.db.database import get_db

logger = logging.getLogger(__name__)


async def run_feedback_loop() -> dict:
    """Run all feedback loop calculations and persist results."""
    db = await get_db()
    try:
        results = {}

        results["topic_scoring"] = await _calculate_topic_category_bonuses(db)
        results["franchise_weights"] = await _calculate_franchise_weights(db)
        results["hook_analysis"] = await _analyze_hook_patterns(db)
        results["narrator_analysis"] = await _analyze_narrator_performance(db)
        results["schedule_analysis"] = await _analyze_schedule(db)

        # Persist all results to settings
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("feedback_loop_results", json.dumps(results)),
        )
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("feedback_loop_last_run", datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()

        logger.info("Feedback loop completed: %s", {k: len(v) if isinstance(v, (list, dict)) else v for k, v in results.items()})
        return results
    finally:
        await db.close()


async def _calculate_topic_category_bonuses(db) -> dict:
    """Calculate score bonuses for topic categories based on video performance.

    If "character_facts" videos average 2x more views than "cut_content",
    the topic scorer should add a bonus to "character_facts" in future discovery.
    """
    cursor = await db.execute(
        """SELECT t.category,
                  COUNT(v.id) as video_count,
                  AVG(a.views) as avg_views,
                  AVG(a.avg_view_duration_pct) as avg_retention,
                  AVG(a.likes + a.comments * 3.0) / NULLIF(AVG(a.views), 0) as avg_engagement
           FROM videos v
           JOIN topics t ON v.topic_id = t.id
           JOIN analytics a ON a.video_id = v.id
             AND a.snapshot_type = 'after_7d'
           WHERE v.published_at >= datetime('now', '-30 days')
           GROUP BY t.category
           HAVING video_count >= 2"""
    )
    rows = await cursor.fetchall()

    if not rows:
        return {}

    categories = [dict(r) for r in rows]

    # Calculate overall average views for normalization
    total_avg_views = sum(c["avg_views"] or 0 for c in categories) / len(categories) if categories else 1

    bonuses = {}
    for cat in categories:
        avg_views = cat["avg_views"] or 0
        # Bonus: ratio vs overall average, capped at ±50%
        if total_avg_views > 0:
            ratio = avg_views / total_avg_views
            bonus = max(-0.5, min(0.5, ratio - 1.0))
        else:
            bonus = 0.0

        bonuses[cat["category"]] = {
            "bonus": round(bonus, 3),
            "avg_views": round(avg_views, 1),
            "video_count": cat["video_count"],
            "avg_retention": round(cat["avg_retention"] or 0, 1),
        }

    # Persist for topic scorer
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("topic_category_bonuses", json.dumps(bonuses)),
    )

    return bonuses


async def _calculate_franchise_weights(db) -> dict:
    """Weight franchise selection probability by performance.

    Higher-performing franchises get more selection probability,
    while still maintaining minimum diversity.
    """
    cursor = await db.execute(
        """SELECT v.franchise_id, f.name,
                  COUNT(v.id) as video_count,
                  AVG(a.views) as avg_views,
                  SUM(a.views) as total_views,
                  AVG(a.avg_view_duration_pct) as avg_retention
           FROM videos v
           JOIN franchises f ON v.franchise_id = f.id
           JOIN analytics a ON a.video_id = v.id
             AND a.snapshot_type = 'after_7d'
           WHERE v.published_at >= datetime('now', '-30 days')
           GROUP BY v.franchise_id"""
    )
    rows = await cursor.fetchall()

    if not rows:
        return {}

    franchises = [dict(r) for r in rows]
    total_avg = sum(f["avg_views"] or 0 for f in franchises) / len(franchises) if franchises else 1

    weights = {}
    for f in franchises:
        avg_views = f["avg_views"] or 0
        # Weight: performance ratio, minimum 0.5 to ensure diversity
        weight = max(0.5, avg_views / total_avg if total_avg > 0 else 1.0)

        weights[f["franchise_id"]] = {
            "name": f["name"],
            "weight": round(weight, 3),
            "avg_views": round(avg_views, 1),
            "total_views": f["total_views"] or 0,
            "video_count": f["video_count"],
            "avg_retention": round(f["avg_retention"] or 0, 1),
        }

    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("franchise_weights", json.dumps(weights)),
    )

    return weights


async def _analyze_hook_patterns(db) -> dict:
    """Track which hook styles perform best for retention.

    Analyzes first-3-second retention by hook type
    (question, bold_claim, shock, story_opening).
    """
    cursor = await db.execute(
        """SELECT
             json_extract(s.script_json, '$.scenes[0].hook_type') as hook_type,
             COUNT(v.id) as video_count,
             AVG(a.views) as avg_views,
             AVG(a.avg_view_duration_pct) as avg_retention,
             AVG(a.click_through_rate) as avg_ctr
           FROM videos v
           JOIN scripts s ON v.script_id = s.id
           JOIN analytics a ON a.video_id = v.id
             AND a.snapshot_type = 'after_7d'
           WHERE v.published_at >= datetime('now', '-30 days')
           GROUP BY hook_type
           HAVING video_count >= 2"""
    )
    rows = await cursor.fetchall()

    hooks = {}
    for row in rows:
        r = dict(row)
        hook = r["hook_type"] or "unknown"
        hooks[hook] = {
            "video_count": r["video_count"],
            "avg_views": round(r["avg_views"] or 0, 1),
            "avg_retention": round(r["avg_retention"] or 0, 1),
            "avg_ctr": round(r["avg_ctr"] or 0, 3),
        }

    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("hook_analysis", json.dumps(hooks)),
    )

    return hooks


async def _analyze_narrator_performance(db) -> dict:
    """Compare retention and engagement across narrators within same franchise.

    Surfaces insights like "Jill-narrated RE videos outperform Wesker by 18%".
    """
    cursor = await db.execute(
        """SELECT v.franchise_id, v.narrator_archetype,
                  COUNT(v.id) as video_count,
                  AVG(a.views) as avg_views,
                  AVG(a.avg_view_duration_pct) as avg_retention,
                  AVG(a.likes + a.comments * 3.0) / NULLIF(AVG(a.views), 0) as engagement_rate
           FROM videos v
           JOIN analytics a ON a.video_id = v.id
             AND a.snapshot_type = 'after_7d'
           WHERE v.published_at >= datetime('now', '-30 days')
             AND v.narrator_archetype IS NOT NULL
           GROUP BY v.franchise_id, v.narrator_archetype
           HAVING video_count >= 2"""
    )
    rows = await cursor.fetchall()

    # Group by franchise
    by_franchise: dict[str, list] = defaultdict(list)
    for row in rows:
        r = dict(row)
        by_franchise[r["franchise_id"]].append({
            "narrator": r["narrator_archetype"],
            "video_count": r["video_count"],
            "avg_views": round(r["avg_views"] or 0, 1),
            "avg_retention": round(r["avg_retention"] or 0, 1),
            "engagement_rate": round(r["engagement_rate"] or 0, 4),
        })

    # Find top narrator per franchise
    comparisons = {}
    for franchise_id, narrators in by_franchise.items():
        sorted_narrators = sorted(narrators, key=lambda n: n["avg_views"], reverse=True)
        comparisons[franchise_id] = {
            "narrators": sorted_narrators,
            "top_narrator": sorted_narrators[0]["narrator"] if sorted_narrators else None,
        }

    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("narrator_analysis", json.dumps(comparisons)),
    )

    return comparisons


async def _analyze_schedule(db) -> dict:
    """Analyze first-24h views by posting time to find optimal upload windows."""
    cursor = await db.execute(
        """SELECT
             strftime('%H', v.published_at) as hour_utc,
             COUNT(v.id) as video_count,
             AVG(a.views) as avg_24h_views
           FROM videos v
           JOIN analytics a ON a.video_id = v.id
             AND a.snapshot_type = 'after_24h'
           WHERE v.published_at >= datetime('now', '-30 days')
           GROUP BY hour_utc
           HAVING video_count >= 2
           ORDER BY avg_24h_views DESC"""
    )
    rows = await cursor.fetchall()

    time_slots = {}
    for row in rows:
        r = dict(row)
        hour = r["hour_utc"] or "00"
        time_slots[f"{hour}:00"] = {
            "video_count": r["video_count"],
            "avg_24h_views": round(r["avg_24h_views"] or 0, 1),
        }

    # Identify best time slots
    best_times = sorted(time_slots.items(), key=lambda x: x[1]["avg_24h_views"], reverse=True)

    result = {
        "time_slots": time_slots,
        "recommended_times": [t[0] for t in best_times[:3]],
    }

    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("schedule_analysis", json.dumps(result)),
    )

    return result


async def get_feedback_results() -> dict:
    """Retrieve the latest feedback loop results."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = 'feedback_loop_results'"
        )
        row = await cursor.fetchone()
        if row:
            return json.loads(row["value"])
        return {}
    finally:
        await db.close()
