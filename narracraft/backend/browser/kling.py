"""Kling AI automation — image-to-video generation (lip sync + motion).

Used by: video_gen.py
Uploads a still image + optional audio → generates animated video clip.
"""

import logging
import time
from pathlib import Path
from typing import Optional

from playwright.async_api import Page

from backend.browser.manager import (
    browser_session,
    human_delay,
    safe_click,
)

logger = logging.getLogger(__name__)

KLING_URL = "https://klingai.com"


async def generate_video(
    image_path: str,
    prompt: str,
    audio_path: Optional[str] = None,
    mode: str = "standard",
    duration: int = 5,
    output_dir: str = "data/output/videos",
    timeout: int = 300000,
) -> Optional[str]:
    """Generate a video clip from a still image using Kling AI.

    Args:
        image_path: Path to the source image.
        prompt: Motion/animation prompt.
        audio_path: Optional audio for lip sync.
        mode: "standard" (10 credits) or "professional" (35 credits).
        duration: Clip duration in seconds (5 or 10).
        output_dir: Directory to save the output video.
        timeout: Max wait time in ms.

    Returns:
        Path to the downloaded video, or None if failed.
    """
    async with browser_session("kling") as page:
        return await _generate_on_page(
            page, image_path, prompt, audio_path, mode, duration, output_dir, timeout
        )


async def _generate_on_page(
    page: Page,
    image_path: str,
    prompt: str,
    audio_path: Optional[str],
    mode: str,
    duration: int,
    output_dir: str,
    timeout: int,
) -> Optional[str]:
    """Internal: run video generation on an already-acquired page."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Navigate to Kling
    if "klingai.com" not in (page.url or ""):
        await page.goto(KLING_URL, wait_until="domcontentloaded")
        await human_delay(3.0, 5.0)

    # Navigate to image-to-video section
    i2v_clicked = await safe_click(
        page,
        'a[href*="image-to-video"], button:has-text("Image to Video"), [data-tab="i2v"]',
        timeout=10000,
    )
    if not i2v_clicked:
        await page.goto(f"{KLING_URL}/image-to-video", wait_until="domcontentloaded")
        await human_delay(2.0, 3.0)

    # Upload the source image
    file_input = await page.query_selector('input[type="file"][accept*="image"]')
    if not file_input:
        file_input = await page.query_selector('input[type="file"]')
    if file_input:
        await file_input.set_input_files(image_path)
        await human_delay(2.0, 3.0)
        logger.info("Uploaded image: %s", image_path)

    # Enter motion prompt
    prompt_selector = 'textarea, input[placeholder*="prompt"], input[placeholder*="describe"]'
    prompt_el = await page.query_selector(prompt_selector)
    if prompt_el:
        await prompt_el.fill(prompt)
        await human_delay(0.5, 1.0)

    # Upload audio for lip sync if provided
    if audio_path and Path(audio_path).exists():
        audio_input = await page.query_selector('input[type="file"][accept*="audio"]')
        if audio_input:
            await audio_input.set_input_files(audio_path)
            await human_delay(1.0, 2.0)
            logger.info("Uploaded audio for lip sync: %s", audio_path)

    # Select mode (standard/professional)
    if mode == "professional":
        await safe_click(page, 'button:has-text("Professional"), [data-mode="professional"]', timeout=3000)
    else:
        await safe_click(page, 'button:has-text("Standard"), [data-mode="standard"]', timeout=3000)
    await human_delay(0.5, 1.0)

    # Set duration
    duration_sel = f'button:has-text("{duration}s"), [data-duration="{duration}"]'
    await safe_click(page, duration_sel, timeout=3000)
    await human_delay(0.5, 1.0)

    # Click generate
    generate_clicked = await safe_click(
        page,
        'button:has-text("Generate"), button:has-text("Create"), button[type="submit"]',
        timeout=5000,
    )
    if not generate_clicked:
        logger.error("Could not find generate button on Kling")
        return None

    await human_delay(3.0, 5.0)

    # Wait for generation to complete and download
    return await _wait_and_download(page, out_path, timeout)


async def _wait_and_download(page: Page, output_dir: Path, timeout: int) -> Optional[str]:
    """Wait for Kling video generation and download the result."""
    import asyncio

    start = asyncio.get_event_loop().time()
    deadline = start + timeout / 1000

    while asyncio.get_event_loop().time() < deadline:
        await human_delay(5.0, 10.0)

        # Check if still generating
        is_loading = await page.evaluate("""() => {
            const text = document.body.innerText.toLowerCase();
            return text.includes('generating') || text.includes('processing')
                || text.includes('in queue') || text.includes('creating');
        }""")

        if is_loading:
            continue

        # Look for download button on the generated video
        download_btn = await page.query_selector(
            'button[aria-label*="download"], a[download], button:has-text("Download")'
        )
        if download_btn:
            try:
                async with page.expect_download(timeout=60000) as download_info:
                    await download_btn.click()
                download = await download_info.value
                ts = int(time.time())
                save_path = str(output_dir / f"kling_{ts}.mp4")
                await download.save_as(save_path)
                logger.info("Downloaded video: %s", save_path)
                return save_path
            except Exception as e:
                logger.warning("Download failed: %s", e)

        # Check for video element with src
        video_src = await page.evaluate("""() => {
            const video = document.querySelector('video[src], video source[src]');
            if (video) return video.src || video.querySelector('source')?.src;
            return null;
        }""")

        if video_src:
            try:
                response = await page.request.get(video_src)
                if response.ok:
                    ts = int(time.time())
                    save_path = str(output_dir / f"kling_{ts}.mp4")
                    Path(save_path).write_bytes(await response.body())
                    logger.info("Downloaded video from src: %s", save_path)
                    return save_path
            except Exception as e:
                logger.warning("Video download from src failed: %s", e)

    logger.warning("Kling video generation timed out after %dms", timeout)
    return None
