"""ElevenLabs web UI automation — text-to-speech via browser.

Used by: voice_gen.py (when active_provider == "elevenlabs")
Navigates to ElevenLabs, selects/creates a voice, generates speech, downloads audio.
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

ELEVENLABS_URL = "https://elevenlabs.io"
SPEECH_URL = f"{ELEVENLABS_URL}/app/speech-synthesis"


async def generate_speech(
    text: str,
    voice_name: Optional[str] = None,
    output_dir: str = "data/output/audio",
    timeout: int = 120000,
) -> Optional[str]:
    """Generate speech audio using ElevenLabs web UI.

    Args:
        text: The text to convert to speech.
        voice_name: Name of the voice to use (must exist in ElevenLabs account).
        output_dir: Directory to save the audio file.
        timeout: Max wait time in ms.

    Returns:
        Path to the downloaded audio file, or None if failed.
    """
    async with browser_session("elevenlabs") as page:
        return await _generate_on_page(page, text, voice_name, output_dir, timeout)


async def _generate_on_page(
    page: Page,
    text: str,
    voice_name: Optional[str],
    output_dir: str,
    timeout: int,
) -> Optional[str]:
    """Internal: generate speech on an already-acquired page."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Navigate to speech synthesis page
    if "elevenlabs.io" not in (page.url or ""):
        await page.goto(SPEECH_URL, wait_until="domcontentloaded")
        await human_delay(3.0, 5.0)
    elif "/speech-synthesis" not in page.url:
        await page.goto(SPEECH_URL, wait_until="domcontentloaded")
        await human_delay(2.0, 3.0)

    # Select voice if specified
    if voice_name:
        await _select_voice(page, voice_name)

    # Enter text
    text_selector = 'textarea, div[contenteditable="true"][data-placeholder], .text-input'
    await page.wait_for_selector(text_selector, timeout=10000)
    text_el = await page.query_selector(text_selector)
    if text_el:
        tag = await text_el.evaluate("el => el.tagName")
        if tag == "TEXTAREA":
            await text_el.fill(text)
        else:
            await text_el.click()
            await page.keyboard.press("Control+a")
            await page.keyboard.press("Delete")
            await page.keyboard.type(text, delay=5)
        await human_delay(0.5, 1.0)

    # Click generate button
    generate_clicked = await safe_click(
        page,
        'button:has-text("Generate"), button:has-text("Convert"), button[aria-label*="generate"]',
        timeout=5000,
    )
    if not generate_clicked:
        logger.error("Could not find generate button on ElevenLabs")
        return None

    await human_delay(2.0, 3.0)

    # Wait for generation and download
    return await _wait_and_download(page, out_path, timeout)


async def _select_voice(page: Page, voice_name: str) -> None:
    """Select a voice from the voice dropdown."""
    try:
        # Click the voice selector/dropdown
        voice_btn = await safe_click(
            page,
            'button[aria-label*="voice"], .voice-selector, button:has-text("Voice")',
            timeout=5000,
        )
        if not voice_btn:
            return

        await human_delay(0.5, 1.0)

        # Search for the voice
        search = await page.query_selector('input[placeholder*="search"], input[type="search"]')
        if search:
            await search.fill(voice_name)
            await human_delay(0.5, 1.0)

        # Click the matching voice option
        await safe_click(
            page,
            f'[role="option"]:has-text("{voice_name}"), .voice-option:has-text("{voice_name}")',
            timeout=5000,
        )
        await human_delay(0.5, 1.0)
        logger.info("Selected voice: %s", voice_name)
    except Exception as e:
        logger.warning("Failed to select voice %s: %s", voice_name, e)


async def _wait_and_download(page: Page, output_dir: Path, timeout: int) -> Optional[str]:
    """Wait for audio generation and download the result."""
    import asyncio

    start = asyncio.get_event_loop().time()
    deadline = start + timeout / 1000

    while asyncio.get_event_loop().time() < deadline:
        await human_delay(2.0, 4.0)

        # Check if still generating
        is_loading = await page.evaluate("""() => {
            return !!(
                document.querySelector('.loading, .generating, [aria-busy="true"]')
                || document.querySelector('[class*="progress"], [class*="spinner"]')
            );
        }""")

        if is_loading:
            continue

        # Look for download button on generated audio
        download_btn = await page.query_selector(
            'button[aria-label*="download"], a[download], button:has-text("Download")'
        )
        if download_btn:
            try:
                async with page.expect_download(timeout=30000) as download_info:
                    await download_btn.click()
                download = await download_info.value
                ts = int(time.time())
                save_path = str(output_dir / f"elevenlabs_{ts}.mp3")
                await download.save_as(save_path)
                logger.info("Downloaded audio: %s", save_path)
                return save_path
            except Exception as e:
                logger.warning("Download failed: %s", e)

        # Check for audio element with src
        audio_src = await page.evaluate("""() => {
            const audio = document.querySelector('audio[src], audio source[src]');
            if (audio) return audio.src || audio.querySelector('source')?.src;
            return null;
        }""")

        if audio_src:
            try:
                response = await page.request.get(audio_src)
                if response.ok:
                    ts = int(time.time())
                    save_path = str(output_dir / f"elevenlabs_{ts}.mp3")
                    Path(save_path).write_bytes(await response.body())
                    logger.info("Downloaded audio from src: %s", save_path)
                    return save_path
            except Exception as e:
                logger.warning("Audio download from src failed: %s", e)

    logger.warning("ElevenLabs generation timed out after %dms", timeout)
    return None
