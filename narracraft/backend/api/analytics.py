"""Analytics API routes — dashboard stats, insights, franchise breakdown, feedback loop."""

import json
import logging

from fastapi import APIRouter

from backend.db.database import get_db
from backend.services.analytics.collector import collect_analytics, get_latest_metrics
from backend.services.analytics.feedback import run_feedback_loop, get_feedback_results
from backend.services.analytics.insights import generate_insights, get_cached_insights

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/dashboard")
async def analytics_dashboard():
    """Aggregate analytics stats for the dashboard."""
    db = await get_db()
    try:
        # Total videos
        cursor = await db.execute("SELECT COUNT(*) as count FROM videos")
        total_videos = (await cursor.fetchone())["count"]

        # Total views (latest snapshot per video)
        cursor = await db.execute(
            """SELECT COALESCE(SUM(a.views), 0) as total_views
               FROM analytics a
               INNER JOIN (
                   SELECT video_id, MAX(collected_at) as latest
                   FROM analytics GROUP BY video_id
               ) latest_a ON a.video_id = latest_a.video_id
               AND a.collected_at = latest_a.latest"""
        )
        total_views = (await cursor.fetchone())["total_views"]

        # Videos this week
        cursor = await db.execute(
            """SELECT COUNT(*) as count FROM videos
               WHERE published_at >= datetime('now', '-7 days')"""
        )
        videos_this_week = (await cursor.fetchone())["count"]

        # Queued topics
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM topics WHERE status = 'queued'"
        )
        queued = (await cursor.fetchone())["count"]

        # Total subscribers gained
        cursor = await db.execute(
            "SELECT COALESCE(SUM(subscribers_gained), 0) as subs FROM analytics"
        )
        total_subs = (await cursor.fetchone())["subs"]

        # Weekly views change
        cursor = await db.execute(
            """SELECT
                 (SELECT COALESCE(SUM(a.views), 0) FROM analytics a
                  JOIN videos v ON a.video_id = v.id
                  WHERE v.published_at >= datetime('now', '-7 days')) as this_week,
                 (SELECT COALESCE(SUM(a.views), 0) FROM analytics a
                  JOIN videos v ON a.video_id = v.id
                  WHERE v.published_at BETWEEN datetime('now', '-14 days') AND datetime('now', '-7 days')) as last_week"""
        )
        row = dict(await cursor.fetchone())
        views_change_pct = (
            round(((row["this_week"] - row["last_week"]) / row["last_week"]) * 100, 1)
            if row["last_week"] and row["last_week"] > 0
            else 0
        )

        return {
            "total_videos": total_videos,
            "total_views": total_views,
            "videos_this_week": videos_this_week,
            "queued_topics": queued,
            "total_subscribers_gained": total_subs,
            "views_change_pct": views_change_pct,
        }
    finally:
        await db.close()


@router.get("/insights")
async def analytics_insights():
    """Auto-generated recommendations based on performance data."""
    insights = await get_cached_insights()
    if not insights:
        return {"insights": [], "message": "Not enough data yet — insights generate after first videos are published"}
    return {"insights": insights}


@router.post("/insights/refresh")
async def refresh_insights():
    """Manually trigger insights regeneration."""
    insights = await generate_insights()
    return {"insights": insights, "count": len(insights)}


@router.get("/franchise/{franchise_id}")
async def franchise_analytics(franchise_id: str):
    """Per-franchise performance breakdown."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) as videos FROM videos WHERE franchise_id = ?",
            (franchise_id,),
        )
        videos = (await cursor.fetchone())["videos"]

        cursor = await db.execute(
            """SELECT COALESCE(SUM(a.views), 0) as total_views,
                      COALESCE(AVG(a.views), 0) as avg_views,
                      COALESCE(AVG(a.avg_view_duration_pct), 0) as avg_retention,
                      COALESCE(SUM(a.subscribers_gained), 0) as total_subs
               FROM analytics a
               JOIN videos v ON a.video_id = v.id
               WHERE v.franchise_id = ? AND a.snapshot_type = 'after_7d'""",
            (franchise_id,),
        )
        metrics = dict(await cursor.fetchone())

        # Per-video breakdown
        cursor = await db.execute(
            """SELECT v.id, v.title, v.narrator_archetype, v.closer_style,
                      v.published_at, v.youtube_video_id,
                      a.views, a.likes, a.comments, a.avg_view_duration_pct,
                      a.snapshot_type
               FROM videos v
               LEFT JOIN analytics a ON a.video_id = v.id
                 AND a.collected_at = (
                     SELECT MAX(a2.collected_at) FROM analytics a2 WHERE a2.video_id = v.id
                 )
               WHERE v.franchise_id = ?
               ORDER BY v.published_at DESC
               LIMIT 20""",
            (franchise_id,),
        )
        video_rows = [dict(row) for row in await cursor.fetchall()]

        return {
            "franchise_id": franchise_id,
            "total_videos": videos,
            "total_views": metrics["total_views"],
            "avg_views": round(metrics["avg_views"], 1),
            "avg_retention": round(metrics["avg_retention"], 1),
            "total_subscribers_gained": metrics["total_subs"],
            "videos": video_rows,
        }
    finally:
        await db.close()


@router.get("/franchises")
async def all_franchise_analytics():
    """Comparative analytics across all franchises."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT v.franchise_id, f.name, f.category,
                      COUNT(DISTINCT v.id) as video_count,
                      COALESCE(SUM(a.views), 0) as total_views,
                      COALESCE(AVG(a.views), 0) as avg_views,
                      COALESCE(AVG(a.avg_view_duration_pct), 0) as avg_retention,
                      COALESCE(SUM(a.subscribers_gained), 0) as subs_gained
               FROM videos v
               JOIN franchises f ON v.franchise_id = f.id
               LEFT JOIN analytics a ON a.video_id = v.id
                 AND a.snapshot_type = 'after_7d'
               GROUP BY v.franchise_id
               ORDER BY total_views DESC"""
        )
        rows = [dict(row) for row in await cursor.fetchall()]

        # Attach weights from feedback loop
        feedback = await get_feedback_results()
        weights = feedback.get("franchise_weights", {})

        for row in rows:
            w = weights.get(row["franchise_id"], {})
            row["weight"] = w.get("weight", 1.0)
            row["avg_views"] = round(row["avg_views"], 1)
            row["avg_retention"] = round(row["avg_retention"], 1)

        return {"franchises": rows}
    finally:
        await db.close()


@router.get("/videos")
async def video_analytics_list():
    """Per-video analytics — latest metrics for each published video."""
    videos = await get_latest_metrics(limit=50)
    return {"videos": videos, "total": len(videos)}


@router.get("/videos/{video_id}")
async def video_analytics_detail(video_id: int):
    """Detailed analytics for a single video — all snapshots."""
    db = await get_db()
    try:
        # Video info
        cursor = await db.execute(
            """SELECT v.*, f.name as franchise_name
               FROM videos v
               JOIN franchises f ON v.franchise_id = f.id
               WHERE v.id = ?""",
            (video_id,),
        )
        video = await cursor.fetchone()
        if not video:
            return {"error": "Video not found"}

        # All snapshots
        cursor = await db.execute(
            "SELECT * FROM analytics WHERE video_id = ? ORDER BY collected_at",
            (video_id,),
        )
        snapshots = [dict(row) for row in await cursor.fetchall()]

        return {
            "video": dict(video),
            "snapshots": snapshots,
        }
    finally:
        await db.close()


@router.post("/collect")
async def trigger_collection():
    """Manually trigger an analytics collection run."""
    result = await collect_analytics()
    return result


@router.post("/feedback")
async def trigger_feedback_loop():
    """Manually trigger the feedback loop recalculation."""
    result = await run_feedback_loop()
    return {"status": "ok", "results": result}


@router.get("/feedback")
async def get_feedback():
    """Get the latest feedback loop results."""
    results = await get_feedback_results()
    return {"results": results}


@router.get("/scores")
async def derived_scores():
    """Get derived performance scores for all videos with 7d data."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT v.id, v.title, v.franchise_id, v.narrator_archetype,
                      a.views, a.likes, a.comments, a.shares,
                      a.avg_view_duration_pct, a.subscribers_gained
               FROM videos v
               JOIN analytics a ON a.video_id = v.id
               WHERE a.snapshot_type = 'after_7d'
               ORDER BY v.published_at DESC
               LIMIT 50"""
        )
        rows = await cursor.fetchall()

        scored = []
        for row in rows:
            r = dict(row)
            views = r["views"] or 0
            likes = r["likes"] or 0
            comments = r["comments"] or 0
            shares = r["shares"] or 0
            retention = r["avg_view_duration_pct"] or 0
            subs = r["subscribers_gained"] or 0

            # Derived scores per config formulas
            engagement = ((likes + comments * 3) / views) if views > 0 else 0
            growth = (subs / views * 1000) if views > 0 else 0
            virality = views * (shares / max(views, 1)) * min(views / 100, 10)
            retention_score = retention / 100

            scored.append({
                **r,
                "engagement_score": round(engagement, 4),
                "growth_score": round(growth, 4),
                "virality_score": round(virality, 2),
                "retention_score": round(retention_score, 3),
            })

        return {"videos": scored}
    finally:
        await db.close()
