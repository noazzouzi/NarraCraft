"""Playwright session manager — single shared browser instance.

ALL browser automation goes through this manager.
- One persistent Chromium instance, reused across modules
- Lock mechanism — only one module at a time
- Persistent profile (stays logged into Google, Kling, ElevenLabs)
- Human-like delays between actions
- Screenshot on error for debugging
"""

import asyncio
import logging
import random
import time
from pathlib import Path
from typing import Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    async_playwright,
    Playwright,
)

from backend.config.config_loader import get_config

logger = logging.getLogger(__name__)

# Module lock — only one browser automation at a time
_lock = asyncio.Lock()


class BrowserManager:
    """Manages a single shared Chromium instance with persistent sessions."""

    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._pages: dict[str, Page] = {}
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized and self._browser is not None

    async def initialize(self) -> None:
        """Start the browser if not already running."""
        if self._initialized:
            return

        import os

        config = get_config()
        browser_config = config.get("browser_automation", {})

        # Prefer env var for Docker portability, fall back to config, then default
        default_dir = browser_config.get("user_data_dir", "./data/browser_data")
        user_data_dir = Path(os.environ.get("BROWSER_PROFILE_DIR", default_dir))
        user_data_dir.mkdir(parents=True, exist_ok=True)

        headless = browser_config.get("headless", False)
        slow_mo = browser_config.get("slow_mo", 500)

        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=headless,
            slow_mo=slow_mo,
            viewport={"width": 1280, "height": 900},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        self._browser = self._context.browser
        self._initialized = True
        logger.info("Browser manager initialized (headless=%s, slow_mo=%d)", headless, slow_mo)

    async def get_page(self, module: str) -> Page:
        """Get or create a page for a specific module.

        Callers must hold the module lock (use `async with session(module):`).
        """
        if not self._initialized:
            await self.initialize()

        if module in self._pages:
            page = self._pages[module]
            if not page.is_closed():
                return page

        page = await self._context.new_page()
        self._pages[module] = page
        return page

    async def close_page(self, module: str) -> None:
        """Close a module's page."""
        page = self._pages.pop(module, None)
        if page and not page.is_closed():
            await page.close()

    async def shutdown(self) -> None:
        """Close all pages and the browser."""
        for module, page in list(self._pages.items()):
            if not page.is_closed():
                await page.close()
        self._pages.clear()

        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()

        self._context = None
        self._browser = None
        self._playwright = None
        self._initialized = False
        logger.info("Browser manager shut down")

    async def screenshot(self, module: str, path: Optional[str] = None) -> str:
        """Take a screenshot of the module's page for debugging."""
        page = self._pages.get(module)
        if not page or page.is_closed():
            return ""

        if not path:
            screenshots_dir = Path("data/screenshots")
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            path = str(screenshots_dir / f"{module}_{ts}.png")

        await page.screenshot(path=path, full_page=True)
        logger.info("Screenshot saved: %s", path)
        return path


# --- Human-like delay utilities ---

async def human_delay(min_s: float = 0.5, max_s: float = 2.0) -> None:
    """Sleep for a randomized human-like duration."""
    await asyncio.sleep(random.uniform(min_s, max_s))


async def human_type(page: Page, selector: str, text: str, delay: float = 50) -> None:
    """Type text with human-like per-character delay."""
    await page.click(selector)
    await human_delay(0.3, 0.6)
    # Add per-character jitter
    for char in text:
        await page.keyboard.type(char, delay=delay + random.uniform(-20, 30))
    await human_delay(0.2, 0.5)


async def safe_click(page: Page, selector: str, timeout: int = 10000) -> bool:
    """Click an element with error handling."""
    try:
        await page.wait_for_selector(selector, timeout=timeout, state="visible")
        await human_delay(0.2, 0.5)
        await page.click(selector)
        return True
    except Exception as e:
        logger.warning("safe_click failed for %s: %s", selector, e)
        return False


async def wait_for_text(page: Page, text: str, timeout: int = 60000) -> bool:
    """Wait for specific text to appear on the page."""
    try:
        await page.wait_for_function(
            f'document.body.innerText.includes("{text}")',
            timeout=timeout,
        )
        return True
    except Exception:
        return False


class BrowserSession:
    """Context manager for locked browser access.

    Usage:
        async with browser_session("gemini") as page:
            await page.goto("https://gemini.google.com")
            ...
    """

    def __init__(self, module: str) -> None:
        self.module = module
        self._page: Optional[Page] = None

    async def __aenter__(self) -> Page:
        await _lock.acquire()
        try:
            self._page = await _manager.get_page(self.module)
            return self._page
        except Exception:
            _lock.release()
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None and self._page and not self._page.is_closed():
            # Screenshot on error
            try:
                await _manager.screenshot(self.module)
            except Exception:
                pass
            logger.error("Browser session error in %s: %s", self.module, exc_val)
        _lock.release()


def browser_session(module: str) -> BrowserSession:
    """Create a locked browser session for a module."""
    return BrowserSession(module)


# Singleton manager instance
_manager = BrowserManager()


def get_manager() -> BrowserManager:
    """Get the singleton browser manager."""
    return _manager
