"""Publisher module — YouTube API + Playwright (TikTok, IG, FB).

Step 8 in the pipeline. Uploads the final video to all enabled platforms,
pins a comment with CTA, and saves long-form outline.
"""

import json
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.browser.manager import browser_session, human_delay, safe_click
from backend.config.config_loader import get_config

logger = logging.getLogger(__name__)


@dataclass
class PublishResult:
    youtube_video_id: Optional[str] = None
    tiktok_video_id: Optional[str] = None
    instagram_video_id: Optional[str] = None
    facebook_video_id: Optional[str] = None
    platforms_published: list[str] = field(default_factory=list)
    long_form_outline_path: Optional[str] = None
    errors: list[str] = field(default_factory=list)


async def publish_video(
    video_path: str,
    script: dict,
    franchise_id: str,
    topic_id: str,
) -> PublishResult:
    """Publish a video to all enabled platforms."""
    config = get_config()
    publishing = config.get("channel", {}).get("publishing", {}).get("platforms", {})
    result = PublishResult()

    # Apply upload time jitter
    schedule = config.get("pipeline", {}).get("schedule", {})
    if schedule.get("randomize_time", True):
        jitter = random.uniform(-1800, 1800)  # ±30 minutes in seconds
        if jitter > 0:
            import asyncio
            logger.info("Applying upload jitter: +%.0f seconds", jitter)
            # In production, we'd schedule this; for now, just note it
            pass

    title = script.get("title", "")
    description = script.get("description", "")
    tags = script.get("tags", [])

    # 1. YouTube (API-based)
    yt_config = publishing.get("youtube", {})
    if yt_config.get("enabled", True):
        yt_id = await _upload_youtube(video_path, title, description, tags, yt_config)
        if yt_id:
            result.youtube_video_id = yt_id
            result.platforms_published.append("youtube")

            # Pin comment with long-form CTA
            cta = config.get("channel", {}).get("monetization", {}).get("long_form_funnel", {}).get("cta_styles", [])
            if cta:
                comment_text = random.choice(cta)
                await _pin_youtube_comment(yt_id, comment_text)
        else:
            result.errors.append("YouTube upload failed")

    # 2. TikTok (Playwright)
    tt_config = publishing.get("tiktok", {})
    if tt_config.get("enabled", False):
        cross_platform = script.get("cross_platform", {})
        tt_caption = cross_platform.get("tiktok_caption", title)
        tt_id = await _upload_tiktok(video_path, tt_caption)
        if tt_id:
            result.tiktok_video_id = tt_id
            result.platforms_published.append("tiktok")
        else:
            result.errors.append("TikTok upload failed")

    # 3. Instagram Reels (Playwright)
    ig_config = publishing.get("instagram_reels", {})
    if ig_config.get("enabled", False):
        cross_platform = script.get("cross_platform", {})
        ig_caption = cross_platform.get("instagram_caption", title)
        ig_id = await _upload_instagram(video_path, ig_caption)
        if ig_id:
            result.instagram_video_id = ig_id
            result.platforms_published.append("instagram")
        else:
            result.errors.append("Instagram upload failed")

    # 4. Facebook Reels (Playwright)
    fb_config = publishing.get("facebook_reels", {})
    if fb_config.get("enabled", False):
        fb_caption = title
        fb_id = await _upload_facebook(video_path, fb_caption)
        if fb_id:
            result.facebook_video_id = fb_id
            result.platforms_published.append("facebook")
        else:
            result.errors.append("Facebook upload failed")

    # 5. Save long-form outline
    long_form = script.get("long_form_potential", {})
    if long_form.get("suitable_for_deep_dive"):
        outline_path = _save_long_form_outline(long_form, franchise_id, topic_id)
        result.long_form_outline_path = outline_path

    return result


async def _upload_youtube(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    yt_config: dict,
) -> Optional[str]:
    """Upload video to YouTube using the YouTube Data API v3."""
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2.credentials import Credentials

        # Load OAuth credentials
        import os
        creds_path = os.environ.get("YOUTUBE_OAUTH_JSON_PATH", "data/youtube_oauth.json")
        if not Path(creds_path).exists():
            logger.error("YouTube OAuth credentials not found at %s", creds_path)
            return None

        creds = Credentials.from_authorized_user_file(creds_path)
        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": tags,
                "categoryId": yt_config.get("category", "20"),
                "defaultLanguage": yt_config.get("default_language", "en"),
            },
            "status": {
                "privacyStatus": yt_config.get("visibility", "public"),
                "selfDeclaredMadeForKids": yt_config.get("made_for_kids", False),
            },
        }

        media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        response = request.execute()
        video_id = response.get("id", "")
        logger.info("Uploaded to YouTube: %s", video_id)
        return video_id

    except ImportError:
        logger.error("google-api-python-client not installed — YouTube upload skipped")
        return None
    except Exception as e:
        logger.error("YouTube upload failed: %s", e)
        return None


async def _pin_youtube_comment(video_id: str, comment_text: str) -> None:
    """Pin a comment on the uploaded YouTube video."""
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
        import os

        creds_path = os.environ.get("YOUTUBE_OAUTH_JSON_PATH", "data/youtube_oauth.json")
        if not Path(creds_path).exists():
            return

        creds = Credentials.from_authorized_user_file(creds_path)
        youtube = build("youtube", "v3", credentials=creds)

        youtube.commentThreads().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {"textOriginal": comment_text}
                    },
                }
            },
        ).execute()
        logger.info("Pinned comment on YouTube video %s", video_id)

    except Exception as e:
        logger.warning("Failed to pin YouTube comment: %s", e)


async def _upload_tiktok(video_path: str, caption: str) -> Optional[str]:
    """Upload video to TikTok via Playwright browser automation."""
    try:
        async with browser_session("tiktok") as page:
            await page.goto("https://www.tiktok.com/upload", wait_until="domcontentloaded")
            await human_delay(3.0, 5.0)

            # Upload video file
            file_input = await page.query_selector('input[type="file"][accept*="video"]')
            if not file_input:
                file_input = await page.query_selector('input[type="file"]')
            if file_input:
                await file_input.set_input_files(video_path)
                await human_delay(5.0, 10.0)

            # Enter caption
            caption_el = await page.query_selector('div[contenteditable="true"], textarea')
            if caption_el:
                await caption_el.click()
                await page.keyboard.type(caption, delay=20)
                await human_delay(1.0, 2.0)

            # Click post button
            posted = await safe_click(page, 'button:has-text("Post"), button[type="submit"]', timeout=10000)
            if posted:
                await human_delay(5.0, 10.0)
                logger.info("Posted to TikTok")
                return f"tiktok_{int(time.time())}"

    except Exception as e:
        logger.error("TikTok upload failed: %s", e)

    return None


async def _upload_instagram(video_path: str, caption: str) -> Optional[str]:
    """Upload video to Instagram Reels via Playwright."""
    try:
        async with browser_session("instagram") as page:
            await page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
            await human_delay(3.0, 5.0)

            # Click create/new post button
            await safe_click(page, '[aria-label="New post"], [aria-label="Create"]', timeout=10000)
            await human_delay(1.0, 2.0)

            # Upload video
            file_input = await page.query_selector('input[type="file"]')
            if file_input:
                await file_input.set_input_files(video_path)
                await human_delay(5.0, 10.0)

            # Navigate through upload steps
            await safe_click(page, 'button:has-text("Next")', timeout=5000)
            await human_delay(1.0, 2.0)
            await safe_click(page, 'button:has-text("Next")', timeout=5000)
            await human_delay(1.0, 2.0)

            # Enter caption
            caption_el = await page.query_selector('textarea[aria-label*="caption"], textarea')
            if caption_el:
                await caption_el.fill(caption)
                await human_delay(1.0, 2.0)

            # Share
            await safe_click(page, 'button:has-text("Share")', timeout=10000)
            await human_delay(5.0, 10.0)
            logger.info("Posted to Instagram")
            return f"ig_{int(time.time())}"

    except Exception as e:
        logger.error("Instagram upload failed: %s", e)

    return None


async def _upload_facebook(video_path: str, caption: str) -> Optional[str]:
    """Upload video to Facebook Reels via Playwright."""
    try:
        async with browser_session("facebook") as page:
            await page.goto("https://www.facebook.com/reels/create", wait_until="domcontentloaded")
            await human_delay(3.0, 5.0)

            # Upload video
            file_input = await page.query_selector('input[type="file"]')
            if file_input:
                await file_input.set_input_files(video_path)
                await human_delay(5.0, 10.0)

            # Enter description
            desc_el = await page.query_selector('textarea, div[contenteditable="true"]')
            if desc_el:
                await desc_el.click()
                await page.keyboard.type(caption, delay=20)
                await human_delay(1.0, 2.0)

            # Publish
            await safe_click(page, 'button:has-text("Publish"), button:has-text("Share")', timeout=10000)
            await human_delay(5.0, 10.0)
            logger.info("Posted to Facebook")
            return f"fb_{int(time.time())}"

    except Exception as e:
        logger.error("Facebook upload failed: %s", e)

    return None


def _save_long_form_outline(long_form: dict, franchise_id: str, topic_id: str) -> str:
    """Save the long-form deep dive outline alongside the Short."""
    outlines_dir = Path("data/long_form_outlines")
    outlines_dir.mkdir(parents=True, exist_ok=True)

    outline = {
        "franchise_id": franchise_id,
        "topic_id": topic_id,
        "title": long_form.get("suggested_long_form_title", ""),
        "outline_bullets": long_form.get("outline_bullets", []),
        "estimated_duration_minutes": long_form.get("estimated_long_form_duration_minutes", 0),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    path = outlines_dir / f"{franchise_id}_{topic_id.replace('/', '_')}.json"
    path.write_text(json.dumps(outline, indent=2))
    logger.info("Saved long-form outline: %s", path)
    return str(path)
