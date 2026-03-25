"""Analytics collector — pulls metrics from YouTube API into DB snapshots.

Collects performance data at 24h, 7d, and 30d after publication.
Uses the same YouTube OAuth credentials as the publisher module.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from backend.config.config_loader import get_config
from backend.db.database import get_db

logger = logging.getLogger(__name__)

# Snapshot windows: (label, hours_after_publish, tolerance_hours)
SNAPSHOT_WINDOWS = [
    ("after_24h", 24, 6),    # Collect 24h snapshot between 18-30h after publish
    ("after_7d", 168, 12),   # Collect 7d snapshot between 156-180h after publish
    ("after_30d", 720, 24),  # Collect 30d snapshot between 696-744h after publish
]


async def collect_analytics() -> dict:
    """Run a full analytics collection pass.

    Finds all published videos that need snapshots and pulls their
    metrics from the YouTube Data API.

    Returns summary of what was collected.
    """
    config = get_config()
    analytics_config = config.get("analytics", {})

    if not analytics_config.get("enabled", True):
        return {"status": "disabled", "collected": 0}

    db = await get_db()
    try:
        # Find videos needing snapshots
        videos_to_check = await _find_videos_needing_snapshots(db)

        if not videos_to_check:
            return {"status": "ok", "collected": 0, "message": "No videos need snapshots right now"}

        # Pull metrics from YouTube API
        collected = 0
        errors = []

        for video in videos_to_check:
            youtube_id = video["youtube_video_id"]
            if not youtube_id:
                continue

            try:
                metrics = await _fetch_youtube_metrics(youtube_id)
                if metrics:
                    await _save_snapshot(
                        db,
                        video_id=video["id"],
                        snapshot_type=video["_snapshot_type"],
                        metrics=metrics,
                    )
                    collected += 1
            except Exception as e:
                logger.error("Failed to collect metrics for video %s: %s", youtube_id, e)
                errors.append(f"{youtube_id}: {str(e)}")

        await db.commit()
        return {
            "status": "ok",
            "collected": collected,
            "checked": len(videos_to_check),
            "errors": errors if errors else None,
        }
    finally:
        await db.close()


async def _find_videos_needing_snapshots(db) -> list[dict]:
    """Find published videos that need a snapshot taken now."""
    now = datetime.now(timezone.utc)
    videos_to_check = []

    for snapshot_type, hours_after, tolerance in SNAPSHOT_WINDOWS:
        # Target window: published_at + hours_after ± tolerance
        window_start = now - timedelta(hours=hours_after + tolerance)
        window_end = now - timedelta(hours=hours_after - tolerance)

        cursor = await db.execute(
            """SELECT v.id, v.youtube_video_id, v.published_at, v.title
               FROM videos v
               WHERE v.youtube_video_id IS NOT NULL
                 AND v.published_at BETWEEN ? AND ?
                 AND NOT EXISTS (
                     SELECT 1 FROM analytics a
                     WHERE a.video_id = v.id AND a.snapshot_type = ?
                 )""",
            (window_start.isoformat(), window_end.isoformat(), snapshot_type),
        )
        rows = await cursor.fetchall()

        for row in rows:
            video = dict(row)
            video["_snapshot_type"] = snapshot_type
            videos_to_check.append(video)

    return videos_to_check


async def _fetch_youtube_metrics(youtube_video_id: str) -> Optional[dict]:
    """Fetch metrics for a single video from the YouTube Data API."""
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials

        creds_path = os.environ.get("YOUTUBE_OAUTH_JSON_PATH", "data/youtube_oauth.json")
        if not Path(creds_path).exists():
            logger.error("YouTube OAuth credentials not found at %s", creds_path)
            return None

        creds = Credentials.from_authorized_user_file(creds_path)
        youtube = build("youtube", "v3", credentials=creds)

        # Get video statistics
        stats_response = youtube.videos().list(
            part="statistics",
            id=youtube_video_id,
        ).execute()

        items = stats_response.get("items", [])
        if not items:
            logger.warning("Video %s not found in YouTube API", youtube_video_id)
            return None

        stats = items[0].get("statistics", {})

        # Get analytics data (requires YouTube Analytics API)
        metrics = {
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "shares": 0,  # Not available via Data API, use Analytics API
        }

        # Try to get advanced metrics from YouTube Analytics API
        advanced = await _fetch_youtube_analytics(creds, youtube_video_id)
        if advanced:
            metrics.update(advanced)

        return metrics

    except ImportError:
        logger.error("google-api-python-client not installed — analytics collection skipped")
        return None
    except Exception as e:
        logger.error("YouTube API error for %s: %s", youtube_video_id, e)
        return None


async def _fetch_youtube_analytics(creds, youtube_video_id: str) -> Optional[dict]:
    """Fetch advanced analytics (retention, CTR) from YouTube Analytics API."""
    try:
        from googleapiclient.discovery import build

        yt_analytics = build("youtubeAnalytics", "v2", credentials=creds)

        # Query for advanced metrics
        response = yt_analytics.reports().query(
            ids="channel==MINE",
            startDate="2020-01-01",
            endDate=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            metrics="averageViewPercentage,subscribersGained,shares",
            filters=f"video=={youtube_video_id}",
            dimensions="video",
        ).execute()

        rows = response.get("rows", [])
        if rows:
            row = rows[0]
            return {
                "avg_view_duration_pct": row[1] if len(row) > 1 else None,
                "subscribers_gained": int(row[2]) if len(row) > 2 else 0,
                "shares": int(row[3]) if len(row) > 3 else 0,
            }

    except Exception as e:
        logger.debug("YouTube Analytics API unavailable for %s: %s", youtube_video_id, e)

    return None


async def _save_snapshot(
    db,
    video_id: int,
    snapshot_type: str,
    metrics: dict,
) -> None:
    """Save an analytics snapshot to the database."""
    await db.execute(
        """INSERT INTO analytics
           (video_id, snapshot_type, views, likes, comments, shares,
            avg_view_duration_pct, click_through_rate, subscribers_gained,
            traffic_sources_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            video_id,
            snapshot_type,
            metrics.get("views", 0),
            metrics.get("likes", 0),
            metrics.get("comments", 0),
            metrics.get("shares", 0),
            metrics.get("avg_view_duration_pct"),
            metrics.get("click_through_rate"),
            metrics.get("subscribers_gained", 0),
            None,  # traffic_sources_json — populated if available
        ),
    )
    logger.info(
        "Saved %s snapshot for video %d: %d views",
        snapshot_type,
        video_id,
        metrics.get("views", 0),
    )


async def get_video_analytics(video_id: int) -> list[dict]:
    """Get all analytics snapshots for a specific video."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM analytics WHERE video_id = ? ORDER BY collected_at""",
            (video_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_latest_metrics(limit: int = 50) -> list[dict]:
    """Get the latest metrics snapshot for each published video."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT v.id as video_id, v.title, v.franchise_id, v.narrator_archetype,
                      v.closer_style, v.published_at, v.youtube_video_id,
                      a.snapshot_type, a.views, a.likes, a.comments, a.shares,
                      a.avg_view_duration_pct, a.click_through_rate,
                      a.subscribers_gained, a.collected_at
               FROM videos v
               LEFT JOIN analytics a ON a.video_id = v.id
                 AND a.collected_at = (
                     SELECT MAX(a2.collected_at) FROM analytics a2 WHERE a2.video_id = v.id
                 )
               ORDER BY v.published_at DESC
               LIMIT ?""",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()
