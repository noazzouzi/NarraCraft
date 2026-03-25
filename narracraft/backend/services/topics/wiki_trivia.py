"""Scrape Trivia/Easter Eggs sections from Fandom wikis."""

import re
from dataclasses import dataclass, field

import httpx

from backend.services.onboarding.wiki_scraper import FANDOM_SEARCH_URL, WIKI_SLUGS


@dataclass
class TriviaItem:
    text: str
    source_page: str
    source_url: str
    section: str = "Trivia"


async def scrape_trivia(
    franchise_id: str,
    wiki_slug: str | None = None,
    max_pages: int = 20,
) -> list[TriviaItem]:
    """Scrape trivia and easter egg sections from franchise wiki pages."""
    slug = wiki_slug or WIKI_SLUGS.get(franchise_id, "")
    if not slug:
        return []

    items: list[TriviaItem] = []

    # Get pages that likely have trivia
    pages = await _get_trivia_pages(slug, max_pages)

    async with httpx.AsyncClient(timeout=15.0) as client:
        for page_title in pages:
            try:
                url = FANDOM_SEARCH_URL.format(wiki=slug)
                resp = await client.get(url, params={
                    "action": "parse",
                    "page": page_title,
                    "prop": "sections|text",
                    "format": "json",
                })
                resp.raise_for_status()
                data = resp.json()

                parse = data.get("parse", {})
                sections = parse.get("sections", [])
                html = parse.get("text", {}).get("*", "")

                # Find trivia-like sections
                trivia_indices = []
                for sec in sections:
                    name = sec.get("line", "").lower()
                    if any(kw in name for kw in ["trivia", "easter egg", "behind the scene", "fun fact", "notes"]):
                        trivia_indices.append(sec.get("index", ""))

                # Extract content from trivia sections
                page_url = f"https://{slug}.fandom.com/wiki/{page_title.replace(' ', '_')}"

                if trivia_indices:
                    # Fetch specific sections
                    for sec_idx in trivia_indices:
                        sec_resp = await client.get(url, params={
                            "action": "parse",
                            "page": page_title,
                            "prop": "text",
                            "section": sec_idx,
                            "format": "json",
                        })
                        sec_data = sec_resp.json()
                        sec_html = sec_data.get("parse", {}).get("text", {}).get("*", "")
                        section_items = _extract_list_items(sec_html)

                        for text in section_items:
                            if len(text) > 30:  # Skip very short items
                                items.append(TriviaItem(
                                    text=text,
                                    source_page=page_title,
                                    source_url=page_url,
                                    section="Trivia",
                                ))

            except (httpx.HTTPError, ValueError, KeyError):
                continue

    return items


async def _get_trivia_pages(wiki_slug: str, limit: int) -> list[str]:
    """Get wiki pages that are likely to have trivia sections."""
    pages = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            url = FANDOM_SEARCH_URL.format(wiki=wiki_slug)

            # Get popular/main pages
            resp = await client.get(url, params={
                "action": "query",
                "format": "json",
                "list": "allpages",
                "aplimit": str(limit),
                "apfilterredir": "nonredirects",
            })
            resp.raise_for_status()
            data = resp.json()

            for page in data.get("query", {}).get("allpages", []):
                pages.append(page.get("title", ""))

            # Also try main article
            resp = await client.get(url, params={
                "action": "query",
                "format": "json",
                "titles": "Main_Page",
                "prop": "links",
                "pllimit": "50",
            })
            resp.raise_for_status()
            data = resp.json()

            for page_data in data.get("query", {}).get("pages", {}).values():
                for link in page_data.get("links", []):
                    title = link.get("title", "")
                    if title and not title.startswith(("Category:", "Template:", "User:")):
                        pages.append(title)

        except (httpx.HTTPError, ValueError):
            pass

    return list(set(pages))[:limit]


def _extract_list_items(html: str) -> list[str]:
    """Extract bullet-point items from wiki HTML."""
    items = []
    # Match <li> elements
    li_matches = re.findall(r"<li>(.*?)</li>", html, re.DOTALL)
    for li in li_matches:
        text = re.sub(r"<[^>]+>", "", li).strip()
        text = re.sub(r"\[.*?\]", "", text)  # Remove citations
        text = re.sub(r"\s+", " ", text)
        if text:
            items.append(text)
    return items
