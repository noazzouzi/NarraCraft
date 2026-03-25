"""Google Image search for reference images during onboarding.

Uses httpx to query Google Custom Search JSON API for images.
Fallback: scrapes DuckDuckGo image search (no API key needed).
"""

import os
import re
from dataclasses import dataclass

import httpx

GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"
DDG_URL = "https://duckduckgo.com/"
DDG_IMAGES_URL = "https://duckduckgo.com/i.js"


@dataclass
class ImageResult:
    url: str
    thumbnail_url: str
    title: str
    source_url: str
    width: int = 0
    height: int = 0


async def search_images_google(query: str, limit: int = 20) -> list[ImageResult]:
    """Search Google Images via Custom Search API (requires API key + CSE ID)."""
    api_key = os.environ.get("GOOGLE_CSE_API_KEY", "")
    cse_id = os.environ.get("GOOGLE_CSE_ID", "")

    if not api_key or not cse_id:
        return []

    results: list[ImageResult] = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(GOOGLE_CSE_URL, params={
                "key": api_key,
                "cx": cse_id,
                "q": query,
                "searchType": "image",
                "num": min(limit, 10),
                "imgSize": "large",
                "safe": "active",
            })
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("items", []):
                image = item.get("image", {})
                results.append(ImageResult(
                    url=item.get("link", ""),
                    thumbnail_url=image.get("thumbnailLink", ""),
                    title=item.get("title", ""),
                    source_url=image.get("contextLink", ""),
                    width=image.get("width", 0),
                    height=image.get("height", 0),
                ))
        except (httpx.HTTPError, ValueError):
            pass

    return results


async def search_images_ddg(query: str, limit: int = 20) -> list[ImageResult]:
    """Search images via DuckDuckGo (no API key needed).

    Uses the DuckDuckGo instant answer / image API endpoint.
    """
    results: list[ImageResult] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
        try:
            # First, get a vqd token
            resp = await client.get(DDG_URL, params={"q": query, "iax": "images", "ia": "images"})
            vqd_match = re.search(r'vqd=["\']([^"\']+)', resp.text)
            if not vqd_match:
                return results
            vqd = vqd_match.group(1)

            # Then fetch images
            resp = await client.get(DDG_IMAGES_URL, params={
                "l": "us-en",
                "o": "json",
                "q": query,
                "vqd": vqd,
                "f": ",,,,,",
                "p": "1",
            })
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("results", [])[:limit]:
                results.append(ImageResult(
                    url=item.get("image", ""),
                    thumbnail_url=item.get("thumbnail", ""),
                    title=item.get("title", ""),
                    source_url=item.get("url", ""),
                    width=item.get("width", 0),
                    height=item.get("height", 0),
                ))
        except (httpx.HTTPError, ValueError, AttributeError):
            pass

    return results


async def search_images(query: str, limit: int = 20) -> list[ImageResult]:
    """Search for images, trying Google CSE first, falling back to DuckDuckGo."""
    results = await search_images_google(query, limit)
    if not results:
        results = await search_images_ddg(query, limit)
    return results
