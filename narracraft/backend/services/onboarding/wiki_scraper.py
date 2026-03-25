"""Fandom wiki HTML scraper for franchise onboarding.

Scrapes character pages, location pages, and trivia sections from
Fandom wikis (e.g., residentevil.fandom.com).
"""

import re
from dataclasses import dataclass, field
from urllib.parse import quote_plus

import httpx

FANDOM_SEARCH_URL = "https://{wiki}.fandom.com/api.php"
FANDOM_SEARCH_PARAMS = {
    "action": "opensearch",
    "format": "json",
    "limit": "20",
}

FANDOM_PARSE_PARAMS = {
    "action": "parse",
    "format": "json",
    "prop": "text|categories|images",
    "disabletoc": "true",
}

# Common Fandom wiki slugs for franchises
WIKI_SLUGS: dict[str, str] = {
    "resident_evil": "residentevil",
    "soulsborne": "darksouls",
    "zelda": "zelda",
    "one_piece": "onepiece",
    "attack_on_titan": "attackontitan",
    "naruto": "naruto",
    "jujutsu_kaisen": "jujutsu-kaisen",
}


@dataclass
class WikiResult:
    title: str
    url: str
    wiki_slug: str
    summary: str = ""
    categories: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    infobox: dict[str, str] = field(default_factory=dict)
    raw_html: str = ""


@dataclass
class WikiCharacter:
    name: str
    description: str
    page_url: str
    image_urls: list[str] = field(default_factory=list)
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass
class WikiLocation:
    name: str
    description: str
    page_url: str
    image_urls: list[str] = field(default_factory=list)


async def search_wiki(query: str, wiki_slug: str | None = None) -> list[WikiResult]:
    """Search a Fandom wiki for pages matching the query.

    If wiki_slug is not provided, searches across known wikis.
    """
    slugs = [wiki_slug] if wiki_slug else list(WIKI_SLUGS.values())
    results: list[WikiResult] = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        for slug in slugs:
            try:
                url = FANDOM_SEARCH_URL.format(wiki=slug)
                params = {**FANDOM_SEARCH_PARAMS, "search": query}
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

                # OpenSearch returns [query, [titles], [descriptions], [urls]]
                if len(data) >= 4:
                    titles = data[1]
                    descriptions = data[2] if len(data) > 2 else [""] * len(titles)
                    urls = data[3] if len(data) > 3 else [""] * len(titles)

                    for title, desc, page_url in zip(titles, descriptions, urls):
                        results.append(WikiResult(
                            title=title,
                            url=page_url,
                            wiki_slug=slug,
                            summary=desc,
                        ))
            except (httpx.HTTPError, ValueError, IndexError):
                continue

    return results


async def get_wiki_page(title: str, wiki_slug: str) -> WikiResult | None:
    """Fetch and parse a specific wiki page."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            url = FANDOM_SEARCH_URL.format(wiki=wiki_slug)
            params = {**FANDOM_PARSE_PARAMS, "page": title}
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            parse = data.get("parse", {})
            html = parse.get("text", {}).get("*", "")
            categories = [c.get("*", "") for c in parse.get("categories", [])]
            images = [img for img in parse.get("images", []) if _is_useful_image(img)]

            # Extract summary from first paragraph
            summary = _extract_first_paragraph(html)

            # Extract infobox data
            infobox = _extract_infobox(html)

            page_url = f"https://{wiki_slug}.fandom.com/wiki/{quote_plus(title)}"

            return WikiResult(
                title=title,
                url=page_url,
                wiki_slug=wiki_slug,
                summary=summary,
                categories=categories,
                images=images,
                infobox=infobox,
                raw_html=html,
            )
        except (httpx.HTTPError, ValueError, KeyError):
            return None


async def discover_characters(wiki_slug: str, franchise_name: str) -> list[WikiCharacter]:
    """Discover character pages from a franchise's Fandom wiki.

    Uses the category system to find character pages.
    """
    characters: list[WikiCharacter] = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            url = FANDOM_SEARCH_URL.format(wiki=wiki_slug)
            params = {
                "action": "query",
                "format": "json",
                "list": "categorymembers",
                "cmtitle": "Category:Characters",
                "cmlimit": "50",
                "cmtype": "page",
            }
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            members = data.get("query", {}).get("categorymembers", [])
            for member in members[:30]:  # Limit to 30 characters
                title = member.get("title", "")
                page = await get_wiki_page(title, wiki_slug)
                if page:
                    characters.append(WikiCharacter(
                        name=title,
                        description=page.summary,
                        page_url=page.url,
                        image_urls=[
                            f"https://{wiki_slug}.fandom.com/wiki/Special:FilePath/{img}"
                            for img in page.images[:5]
                        ],
                        attributes=page.infobox,
                    ))
        except (httpx.HTTPError, ValueError):
            pass

    return characters


async def discover_locations(wiki_slug: str) -> list[WikiLocation]:
    """Discover location/environment pages from a franchise wiki."""
    locations: list[WikiLocation] = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            url = FANDOM_SEARCH_URL.format(wiki=wiki_slug)
            # Try common category names for locations
            for cat_name in ["Category:Locations", "Category:Places", "Category:Areas"]:
                params = {
                    "action": "query",
                    "format": "json",
                    "list": "categorymembers",
                    "cmtitle": cat_name,
                    "cmlimit": "30",
                    "cmtype": "page",
                }
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

                members = data.get("query", {}).get("categorymembers", [])
                for member in members[:20]:
                    title = member.get("title", "")
                    page = await get_wiki_page(title, wiki_slug)
                    if page:
                        locations.append(WikiLocation(
                            name=title,
                            description=page.summary,
                            page_url=page.url,
                            image_urls=[
                                f"https://{wiki_slug}.fandom.com/wiki/Special:FilePath/{img}"
                                for img in page.images[:3]
                            ],
                        ))

                if locations:
                    break  # Found locations in this category
        except (httpx.HTTPError, ValueError):
            pass

    return locations


def _extract_first_paragraph(html: str) -> str:
    """Extract first meaningful paragraph from wiki HTML."""
    # Remove infoboxes and tables first
    clean = re.sub(r"<table[^>]*>.*?</table>", "", html, flags=re.DOTALL)
    clean = re.sub(r"<aside[^>]*>.*?</aside>", "", clean, flags=re.DOTALL)

    # Find first <p> with actual content
    paragraphs = re.findall(r"<p>(.*?)</p>", clean, re.DOTALL)
    for p in paragraphs:
        text = re.sub(r"<[^>]+>", "", p).strip()
        text = re.sub(r"\[.*?\]", "", text)  # Remove citation brackets
        if len(text) > 50:  # Skip short/empty paragraphs
            return text[:500]

    return ""


def _extract_infobox(html: str) -> dict[str, str]:
    """Extract key-value pairs from a Fandom infobox."""
    infobox: dict[str, str] = {}

    # Match data-source attributes in portable infoboxes
    pairs = re.findall(
        r'data-source="([^"]+)"[^>]*>.*?<div[^>]*class="pi-data-value[^"]*"[^>]*>(.*?)</div>',
        html,
        re.DOTALL,
    )
    for key, value in pairs:
        text = re.sub(r"<[^>]+>", "", value).strip()
        if text:
            infobox[key] = text[:200]

    return infobox


def _is_useful_image(filename: str) -> bool:
    """Filter out wiki UI images, keeping only content images."""
    lower = filename.lower()
    skip_patterns = [
        "icon", "logo", "badge", "button", "banner",
        "placeholder", "default", "wiki", "favicon",
        ".svg",
    ]
    return not any(p in lower for p in skip_patterns)
