"""Google Flow (labs.google/flow) automation — AI image generation.

Used by: image_gen.py (character portraits, environments, scene composites)
Uploads reference images + text prompt → downloads generated images.
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

FLOW_URL = "https://labs.google/flow"


async def generate_image(
    prompt: str,
    reference_images: list[str] | None = None,
    output_dir: str = "data/output/images",
    timeout: int = 120000,
) -> list[str]:
    """Generate images using Google Flow.

    Args:
        prompt: Text description for image generation.
        reference_images: Paths to reference images to upload (for character consistency).
        output_dir: Directory to save downloaded images.
        timeout: Max wait time for generation in ms.

    Returns:
        List of paths to downloaded images.
    """
    async with browser_session("google_flow") as page:
        return await _generate_on_page(page, prompt, reference_images, output_dir, timeout)


async def _generate_on_page(
    page: Page,
    prompt: str,
    reference_images: list[str] | None,
    output_dir: str,
    timeout: int,
) -> list[str]:
    """Internal: run generation on an already-acquired page."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Navigate to Flow
    if "labs.google/flow" not in (page.url or ""):
        await page.goto(FLOW_URL, wait_until="domcontentloaded")
        await human_delay(3.0, 5.0)

    # Upload reference images if provided
    if reference_images:
        for img_path in reference_images:
            if Path(img_path).exists():
                await _upload_reference(page, img_path)

    # Enter the prompt
    prompt_selector = 'textarea, input[type="text"], [contenteditable="true"]'
    await page.wait_for_selector(prompt_selector, timeout=15000)
    await page.click(prompt_selector)
    await page.fill(prompt_selector, prompt)
    await human_delay(0.5, 1.0)

    # Click generate button
    generate_clicked = await safe_click(
        page,
        'button:has-text("Generate"), button:has-text("Create"), button[aria-label*="generate"]',
        timeout=5000,
    )
    if not generate_clicked:
        await page.keyboard.press("Enter")

    await human_delay(2.0, 3.0)

    # Wait for generation to complete
    generated_paths = await _wait_and_download(page, out_path, timeout)
    return generated_paths


async def _upload_reference(page: Page, image_path: str) -> None:
    """Upload a reference image to Flow."""
    try:
        # Look for upload/attach button
        upload_btn = await safe_click(
            page,
            'button[aria-label*="upload"], button[aria-label*="attach"], button:has-text("Upload"), input[type="file"]',
            timeout=5000,
        )

        # If there's a file input, use it directly
        file_input = await page.query_selector('input[type="file"]')
        if file_input:
            await file_input.set_input_files(image_path)
            await human_delay(1.0, 2.0)
            logger.info("Uploaded reference image: %s", image_path)
    except Exception as e:
        logger.warning("Failed to upload reference image %s: %s", image_path, e)


async def _wait_and_download(page: Page, output_dir: Path, timeout: int) -> list[str]:
    """Wait for image generation and download results."""
    import asyncio

    start = asyncio.get_event_loop().time()
    deadline = start + timeout / 1000
    downloaded: list[str] = []

    while asyncio.get_event_loop().time() < deadline:
        await human_delay(3.0, 5.0)

        # Check if generation is complete (look for generated images)
        is_loading = await page.evaluate("""() => {
            return !!(
                document.querySelector('.loading, .generating, [aria-busy="true"]')
                || document.querySelector('mat-progress-bar, .progress-bar')
            );
        }""")

        if is_loading:
            continue

        # Look for generated image elements
        image_count = await page.evaluate("""() => {
            const imgs = document.querySelectorAll('.generated-image img, .result-image img, .output img');
            return imgs.length;
        }""")

        if image_count > 0:
            # Download each generated image
            images = await page.query_selector_all(
                ".generated-image img, .result-image img, .output img"
            )
            for i, img in enumerate(images):
                try:
                    src = await img.get_attribute("src")
                    if src:
                        ts = int(time.time())
                        filename = f"flow_{ts}_{i}.png"
                        filepath = output_dir / filename

                        # Download via page context
                        response = await page.request.get(src)
                        if response.ok:
                            filepath.write_bytes(await response.body())
                            downloaded.append(str(filepath))
                            logger.info("Downloaded image: %s", filepath)
                except Exception as e:
                    logger.warning("Failed to download image %d: %s", i, e)

            if downloaded:
                return downloaded

        # Also try right-click save or download button
        download_btn = await page.query_selector(
            'button[aria-label*="download"], button:has-text("Download"), button:has-text("Save")'
        )
        if download_btn:
            async with page.expect_download(timeout=30000) as download_info:
                await download_btn.click()
            download = await download_info.value
            ts = int(time.time())
            save_path = str(output_dir / f"flow_{ts}.png")
            await download.save_as(save_path)
            downloaded.append(save_path)
            return downloaded

    logger.warning("Image generation timed out after %dms", timeout)
    return downloaded
