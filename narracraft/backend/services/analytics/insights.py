"""Insights generator — auto-generated actionable recommendations.

Reads feedback loop data + raw analytics to produce human-readable
recommendations shown in the dashboard. Refreshed weekly.

Example insights:
- "Increase RE content from 2/week to 3/week (23% above avg views)"
- "Use question hooks more — 12% better retention than bold claims"
- "Shift upload time to 18:00 UTC — 23% better first-24h performance"
- "Wesker in thumbnails increases CTR by 18% — test as narrator"
"""

import json
import logging
from datetime import datetime, timezone

from backend.db.database import get_db

logger = logging.getLogger(__name__)


async def generate_insights() -> list[dict]:
    """Generate all insights from feedback loop data and raw analytics."""
    db = await get_db()
    try:
        insights = []

        insights.extend(await _franchise_insights(db))
        insights.extend(await _hook_insights(db))
        insights.extend(await _narrator_insights(db))
        insights.extend(await _schedule_insights(db))
        insights.extend(await _trend_insights(db))
        insights.extend(await _growth_insights(db))

        # Persist insights
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("generated_insights", json.dumps(insights)),
        )
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("insights_last_generated", datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()

        logger.info("Generated %d insights", len(insights))
        return insights
    finally:
        await db.close()


async def _franchise_insights(db) -> list[dict]:
    """Insights about franchise performance — which to increase/decrease."""
    insights = []

    cursor = await db.execute(
        "SELECT value FROM settings WHERE key = 'franchise_weights'"
    )
    row = await cursor.fetchone()
    if not row:
        return insights

    weights = json.loads(row["value"])
    if not weights:
        return insights

    avg_views_all = sum(f["avg_views"] for f in weights.values()) / len(weights) if weights else 0

    for fid, data in weights.items():
        pct_above = ((data["avg_views"] - avg_views_all) / avg_views_all * 100) if avg_views_all > 0 else 0

        if pct_above > 20:
            insights.append({
                "tag": "FRANCHISE",
                "type": "opportunity",
                "priority": "high",
                "text": f"Increase {data['name']} content — {pct_above:+.0f}% above avg views ({data['avg_views']:.0f} avg)",
                "franchise_id": fid,
                "metric": round(pct_above, 1),
            })
        elif pct_above < -30:
            insights.append({
                "tag": "FRANCHISE",
                "type": "warning",
                "priority": "medium",
                "text": f"{data['name']} underperforming at {pct_above:+.0f}% below avg — consider reducing frequency",
                "franchise_id": fid,
                "metric": round(pct_above, 1),
            })

    return insights


async def _hook_insights(db) -> list[dict]:
    """Insights about which hook styles perform best."""
    insights = []

    cursor = await db.execute(
        "SELECT value FROM settings WHERE key = 'hook_analysis'"
    )
    row = await cursor.fetchone()
    if not row:
        return insights

    hooks = json.loads(row["value"])
    if len(hooks) < 2:
        return insights

    # Find best and worst hooks by retention
    by_retention = sorted(hooks.items(), key=lambda x: x[1].get("avg_retention", 0), reverse=True)
    best_hook, best_data = by_retention[0]
    worst_hook, worst_data = by_retention[-1]

    best_ret = best_data.get("avg_retention", 0)
    worst_ret = worst_data.get("avg_retention", 0)

    if best_ret > 0 and worst_ret > 0:
        diff_pct = ((best_ret - worst_ret) / worst_ret) * 100
        if diff_pct > 5:
            insights.append({
                "tag": "HOOKS",
                "type": "opportunity",
                "priority": "high",
                "text": f"{best_hook.replace('_', ' ').title()} hooks retain {diff_pct:.0f}% better than {worst_hook.replace('_', ' ')}",
                "metric": round(diff_pct, 1),
            })

    return insights


async def _narrator_insights(db) -> list[dict]:
    """Insights about narrator performance within franchises."""
    insights = []

    cursor = await db.execute(
        "SELECT value FROM settings WHERE key = 'narrator_analysis'"
    )
    row = await cursor.fetchone()
    if not row:
        return insights

    comparisons = json.loads(row["value"])

    for franchise_id, data in comparisons.items():
        narrators = data.get("narrators", [])
        if len(narrators) < 2:
            continue

        best = narrators[0]
        second = narrators[1]

        if best["avg_views"] > 0 and second["avg_views"] > 0:
            diff_pct = ((best["avg_views"] - second["avg_views"]) / second["avg_views"]) * 100
            if diff_pct > 10:
                insights.append({
                    "tag": "VOICE",
                    "type": "insight",
                    "priority": "medium",
                    "text": f"{best['narrator']} outperforms {second['narrator']} by {diff_pct:.0f}% in views ({franchise_id})",
                    "franchise_id": franchise_id,
                    "metric": round(diff_pct, 1),
                })

    return insights


async def _schedule_insights(db) -> list[dict]:
    """Insights about optimal posting times."""
    insights = []

    cursor = await db.execute(
        "SELECT value FROM settings WHERE key = 'schedule_analysis'"
    )
    row = await cursor.fetchone()
    if not row:
        return insights

    schedule = json.loads(row["value"])
    recommended = schedule.get("recommended_times", [])
    time_slots = schedule.get("time_slots", {})

    if not recommended or not time_slots:
        return insights

    best_time = recommended[0]
    best_views = time_slots.get(best_time, {}).get("avg_24h_views", 0)

    # Compare to worst time
    worst_time = min(time_slots.items(), key=lambda x: x[1].get("avg_24h_views", 0))
    worst_views = worst_time[1].get("avg_24h_views", 0)

    if best_views > 0 and worst_views > 0:
        diff_pct = ((best_views - worst_views) / worst_views) * 100
        if diff_pct > 10:
            insights.append({
                "tag": "TIME",
                "type": "opportunity",
                "priority": "medium",
                "text": f"Posts at {best_time} UTC get {diff_pct:.0f}% better first-day views — consider shifting schedule",
                "metric": round(diff_pct, 1),
            })

    return insights


async def _trend_insights(db) -> list[dict]:
    """Identify trending franchises (week-over-week growth)."""
    insights = []

    cursor = await db.execute(
        """WITH recent AS (
               SELECT v.franchise_id, f.name, AVG(a.views) as avg_views
               FROM videos v
               JOIN franchises f ON v.franchise_id = f.id
               JOIN analytics a ON a.video_id = v.id AND a.snapshot_type = 'after_7d'
               WHERE v.published_at >= datetime('now', '-14 days')
               GROUP BY v.franchise_id
           ), prior AS (
               SELECT v.franchise_id, AVG(a.views) as avg_views
               FROM videos v
               JOIN analytics a ON a.video_id = v.id AND a.snapshot_type = 'after_7d'
               WHERE v.published_at BETWEEN datetime('now', '-28 days') AND datetime('now', '-14 days')
               GROUP BY v.franchise_id
           )
           SELECT recent.franchise_id, recent.name,
                  recent.avg_views as recent_avg,
                  prior.avg_views as prior_avg
           FROM recent
           JOIN prior ON recent.franchise_id = prior.franchise_id
           WHERE prior.avg_views > 0"""
    )
    rows = await cursor.fetchall()

    for row in rows:
        r = dict(row)
        growth = ((r["recent_avg"] - r["prior_avg"]) / r["prior_avg"]) * 100
        if growth > 15:
            insights.append({
                "tag": "TREND",
                "type": "trending",
                "priority": "high",
                "text": f"{r['name']} trending +{growth:.0f}% — consider increasing to 2-3 per week",
                "franchise_id": r["franchise_id"],
                "metric": round(growth, 1),
            })
        elif growth < -20:
            insights.append({
                "tag": "TREND",
                "type": "declining",
                "priority": "low",
                "text": f"{r['name']} declining {growth:.0f}% — rotate in fresher topics",
                "franchise_id": r["franchise_id"],
                "metric": round(growth, 1),
            })

    return insights


async def _growth_insights(db) -> list[dict]:
    """Overall channel growth insights."""
    insights = []

    # Compare this week vs last week total views
    cursor = await db.execute(
        """SELECT
             (SELECT COALESCE(SUM(a.views), 0) FROM analytics a
              JOIN videos v ON a.video_id = v.id
              WHERE a.snapshot_type = 'after_7d'
                AND v.published_at >= datetime('now', '-7 days')) as this_week,
             (SELECT COALESCE(SUM(a.views), 0) FROM analytics a
              JOIN videos v ON a.video_id = v.id
              WHERE a.snapshot_type = 'after_7d'
                AND v.published_at BETWEEN datetime('now', '-14 days') AND datetime('now', '-7 days')) as last_week"""
    )
    row = await cursor.fetchone()
    r = dict(row)

    if r["last_week"] and r["last_week"] > 0:
        growth = ((r["this_week"] - r["last_week"]) / r["last_week"]) * 100
        if abs(growth) > 10:
            direction = "up" if growth > 0 else "down"
            insights.append({
                "tag": "GROWTH",
                "type": "trending" if growth > 0 else "declining",
                "priority": "high",
                "text": f"Weekly views {direction} {abs(growth):.0f}% ({r['this_week']:,} vs {r['last_week']:,})",
                "metric": round(growth, 1),
            })

    return insights


async def get_cached_insights() -> list[dict]:
    """Retrieve the latest cached insights."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = 'generated_insights'"
        )
        row = await cursor.fetchone()
        if row:
            return json.loads(row["value"])
        return []
    finally:
        await db.close()
