"""MyAnimeList / AniList client for anime/manga franchise onboarding.

Uses the Jikan API (unofficial MAL REST API, no auth needed)
and AniList GraphQL API (public, no auth needed) for anime metadata.
"""

from dataclasses import dataclass, field

import httpx

JIKAN_BASE = "https://api.jikan.moe/v4"
ANILIST_URL = "https://graphql.anilist.co"


@dataclass
class AnimeResult:
    id: int
    title: str
    title_english: str = ""
    synopsis: str = ""
    image_url: str = ""
    episodes: int | None = None
    score: float | None = None
    genres: list[str] = field(default_factory=list)
    source: str = ""  # "jikan" or "anilist"


@dataclass
class AnimeCharacter:
    id: int
    name: str
    role: str = ""  # "Main" or "Supporting"
    image_url: str = ""
    description: str = ""
    source: str = ""


async def search_anime_jikan(query: str, limit: int = 10) -> list[AnimeResult]:
    """Search for anime using Jikan (MAL) API."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{JIKAN_BASE}/anime", params={
                "q": query,
                "limit": limit,
                "order_by": "score",
                "sort": "desc",
            })
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data.get("data", []):
                images = item.get("images", {}).get("jpg", {})
                results.append(AnimeResult(
                    id=item.get("mal_id", 0),
                    title=item.get("title", ""),
                    title_english=item.get("title_english", "") or "",
                    synopsis=(item.get("synopsis", "") or "")[:500],
                    image_url=images.get("large_image_url", "") or images.get("image_url", ""),
                    episodes=item.get("episodes"),
                    score=item.get("score"),
                    genres=[g.get("name", "") for g in item.get("genres", [])],
                    source="jikan",
                ))
            return results
        except (httpx.HTTPError, ValueError):
            return []


async def search_manga_jikan(query: str, limit: int = 10) -> list[AnimeResult]:
    """Search for manga using Jikan (MAL) API."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{JIKAN_BASE}/manga", params={
                "q": query,
                "limit": limit,
                "order_by": "score",
                "sort": "desc",
            })
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data.get("data", []):
                images = item.get("images", {}).get("jpg", {})
                results.append(AnimeResult(
                    id=item.get("mal_id", 0),
                    title=item.get("title", ""),
                    title_english=item.get("title_english", "") or "",
                    synopsis=(item.get("synopsis", "") or "")[:500],
                    image_url=images.get("large_image_url", "") or images.get("image_url", ""),
                    episodes=item.get("chapters"),
                    score=item.get("score"),
                    genres=[g.get("name", "") for g in item.get("genres", [])],
                    source="jikan",
                ))
            return results
        except (httpx.HTTPError, ValueError):
            return []


async def get_characters_jikan(anime_id: int) -> list[AnimeCharacter]:
    """Get characters for a MAL anime by ID."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{JIKAN_BASE}/anime/{anime_id}/characters")
            resp.raise_for_status()
            data = resp.json()

            characters = []
            for item in data.get("data", [])[:30]:
                char = item.get("character", {})
                images = char.get("images", {}).get("jpg", {})
                characters.append(AnimeCharacter(
                    id=char.get("mal_id", 0),
                    name=char.get("name", ""),
                    role=item.get("role", ""),
                    image_url=images.get("image_url", ""),
                    source="jikan",
                ))
            return characters
        except (httpx.HTTPError, ValueError):
            return []


async def search_anilist(query: str, media_type: str = "ANIME", limit: int = 10) -> list[AnimeResult]:
    """Search using AniList GraphQL API (no auth needed)."""
    gql_query = """
    query ($search: String, $type: MediaType, $perPage: Int) {
      Page(perPage: $perPage) {
        media(search: $search, type: $type, sort: POPULARITY_DESC) {
          id
          title { romaji english }
          description
          coverImage { large }
          episodes
          chapters
          averageScore
          genres
        }
      }
    }
    """
    variables = {"search": query, "type": media_type, "perPage": limit}

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(ANILIST_URL, json={
                "query": gql_query,
                "variables": variables,
            })
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data.get("data", {}).get("Page", {}).get("media", []):
                title = item.get("title", {})
                # Strip HTML tags from description
                import re
                desc = re.sub(r"<[^>]+>", "", item.get("description", "") or "")

                results.append(AnimeResult(
                    id=item.get("id", 0),
                    title=title.get("romaji", ""),
                    title_english=title.get("english", "") or "",
                    synopsis=desc[:500],
                    image_url=(item.get("coverImage") or {}).get("large", ""),
                    episodes=item.get("episodes") or item.get("chapters"),
                    score=(item.get("averageScore") or 0) / 10,
                    genres=item.get("genres", []),
                    source="anilist",
                ))
            return results
        except (httpx.HTTPError, ValueError):
            return []


async def get_characters_anilist(media_id: int) -> list[AnimeCharacter]:
    """Get characters for an AniList media entry."""
    gql_query = """
    query ($id: Int) {
      Media(id: $id) {
        characters(sort: ROLE, perPage: 25) {
          edges {
            role
            node {
              id
              name { full }
              image { large }
              description
            }
          }
        }
      }
    }
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(ANILIST_URL, json={
                "query": gql_query,
                "variables": {"id": media_id},
            })
            resp.raise_for_status()
            data = resp.json()

            characters = []
            edges = (data.get("data", {}).get("Media", {})
                     .get("characters", {}).get("edges", []))
            for edge in edges:
                node = edge.get("node", {})
                import re
                desc = re.sub(r"<[^>]+>", "", node.get("description", "") or "")
                characters.append(AnimeCharacter(
                    id=node.get("id", 0),
                    name=(node.get("name") or {}).get("full", ""),
                    role=edge.get("role", ""),
                    image_url=(node.get("image") or {}).get("large", ""),
                    description=desc[:500],
                    source="anilist",
                ))
            return characters
        except (httpx.HTTPError, ValueError):
            return []
