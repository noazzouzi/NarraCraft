"""Gemini web UI automation — send prompts, receive responses.

Used by: script_gen.py (script generation), compliance.py (content filter)
"""

import json
import logging
import re
from typing import Optional

from playwright.async_api import Page

from backend.browser.manager import (
    browser_session,
    human_delay,
    human_type,
    safe_click,
    wait_for_text,
)

logger = logging.getLogger(__name__)

GEMINI_URL = "https://gemini.google.com/app"


async def send_prompt(prompt: str, timeout: int = 120000) -> str:
    """Send a prompt to Gemini and return the text response.

    Uses the shared browser session (must be logged into Google).
    """
    async with browser_session("gemini") as page:
        return await _send_prompt_on_page(page, prompt, timeout)


async def _send_prompt_on_page(page: Page, prompt: str, timeout: int) -> str:
    """Internal: send prompt on an already-acquired page."""
    # Navigate to Gemini if not already there
    if "gemini.google.com" not in (page.url or ""):
        await page.goto(GEMINI_URL, wait_until="domcontentloaded")
        await human_delay(2.0, 4.0)

    # Start a new chat to avoid context from previous conversations
    new_chat = await safe_click(page, '[aria-label="New chat"]', timeout=5000)
    if new_chat:
        await human_delay(1.0, 2.0)

    # Find the input area and type the prompt
    input_selector = 'div[contenteditable="true"], textarea[aria-label*="prompt"], .ql-editor'
    await page.wait_for_selector(input_selector, timeout=15000)
    await human_delay(0.5, 1.0)

    # Clear any existing text
    await page.click(input_selector)
    await page.keyboard.press("Control+a")
    await page.keyboard.press("Delete")
    await human_delay(0.3, 0.5)

    # Paste the prompt (faster than typing for long prompts)
    await page.evaluate(
        """(text) => {
            const el = document.querySelector('div[contenteditable="true"], textarea[aria-label*="prompt"], .ql-editor');
            if (el) {
                if (el.tagName === 'TEXTAREA') el.value = text;
                else el.innerText = text;
                el.dispatchEvent(new Event('input', {bubbles: true}));
            }
        }""",
        prompt,
    )
    await human_delay(0.5, 1.0)

    # Click send button
    send_clicked = await safe_click(
        page,
        'button[aria-label="Send message"], button[data-test-id="send-button"], button.send-button',
        timeout=5000,
    )
    if not send_clicked:
        # Try pressing Enter as fallback
        await page.keyboard.press("Enter")

    await human_delay(1.0, 2.0)

    # Wait for response to complete
    response = await _wait_for_response(page, timeout)
    return response


async def _wait_for_response(page: Page, timeout: int) -> str:
    """Wait for Gemini to finish generating and extract the response text."""
    import asyncio

    start = asyncio.get_event_loop().time()
    deadline = start + timeout / 1000

    last_text = ""
    stable_count = 0

    while asyncio.get_event_loop().time() < deadline:
        await human_delay(1.5, 2.5)

        # Extract the latest response text
        text = await page.evaluate("""() => {
            const messages = document.querySelectorAll(
                '.response-container, .model-response-text, [data-message-author-role="model"], .markdown'
            );
            if (messages.length === 0) return '';
            const last = messages[messages.length - 1];
            return last.innerText || last.textContent || '';
        }""")

        if not text:
            continue

        # Check if response is still generating (look for loading indicators)
        is_loading = await page.evaluate("""() => {
            return !!(
                document.querySelector('.loading, .generating, [aria-busy="true"], .thinking')
                || document.querySelector('mat-progress-bar, .progress-indicator')
            );
        }""")

        if text == last_text and not is_loading:
            stable_count += 1
            if stable_count >= 3:
                # Response has stabilized
                return text.strip()
        else:
            stable_count = 0
            last_text = text

    logger.warning("Gemini response timed out after %dms", timeout)
    return last_text.strip()


async def send_prompt_json(prompt: str, timeout: int = 120000) -> Optional[dict]:
    """Send a prompt and parse the response as JSON.

    Handles common issues like markdown code blocks around JSON.
    """
    raw = await send_prompt(prompt, timeout)
    return parse_json_response(raw)


def parse_json_response(text: str) -> Optional[dict]:
    """Extract and parse JSON from a Gemini response.

    Handles: raw JSON, ```json blocks, extra text before/after.
    """
    if not text:
        return None

    # Try direct JSON parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Extract from markdown code block
    code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1))
        except json.JSONDecodeError:
            pass

    # Find first { ... } block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    logger.error("Failed to parse JSON from Gemini response: %s...", text[:200])
    return None
