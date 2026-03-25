"""IGDB API client for game franchise onboarding.

Uses the IGDB API (via Twitch OAuth) to search for games
and retrieve metadata: cover art, screenshots, characters, etc.
"""

import os
from dataclasses import dataclass, field

import httpx

TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
IGDB_API_URL = "https://api.igdb.com/v4"


@dataclass
class IGDBGame:
    id: int
    name: str
    slug: str
    summary: str = ""
    cover_url: str = ""
    screenshots: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    first_release_date: int | None = None
    rating: float | None = None
    involved_companies: list[str] = field(default_factory=list)


@dataclass
class IGDBCharacter:
    id: int
    name: str
    description: str = ""
    mug_shot_url: str = ""
    games: list[str] = field(default_factory=list)


class IGDBClient:
    """Client for the IGDB API (requires Twitch developer credentials)."""

    def __init__(self):
        self._client_id = os.environ.get("TWITCH_CLIENT_ID", "")
        self._client_secret = os.environ.get("TWITCH_CLIENT_SECRET", "")
        self._access_token: str | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    async def _ensure_token(self) -> str:
        """Get or refresh the Twitch OAuth token."""
        if self._access_token:
            return self._access_token

        if not self.is_configured:
            raise RuntimeError(
                "IGDB not configured: set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET"
            )

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(TWITCH_TOKEN_URL, params={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "client_credentials",
            })
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data["access_token"]
            return self._access_token

    async def _query(self, endpoint: str, body: str) -> list[dict]:
        """Execute an IGDB API query."""
        token = await self._ensure_token()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{IGDB_API_URL}/{endpoint}",
                content=body,
                headers={
                    "Client-ID": self._client_id,
                    "Authorization": f"Bearer {token}",
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def search_games(self, query: str, limit: int = 10) -> list[IGDBGame]:
        """Search for games by name."""
        body = f"""
            search "{query}";
            fields name, slug, summary, cover.image_id,
                   screenshots.image_id, genres.name,
                   platforms.name, first_release_date,
                   total_rating, involved_companies.company.name;
            limit {limit};
        """
        results = await self._query("games", body)
        return [self._parse_game(r) for r in results]

    async def get_game(self, game_id: int) -> IGDBGame | None:
        """Get a specific game by ID."""
        body = f"""
            where id = {game_id};
            fields name, slug, summary, cover.image_id,
                   screenshots.image_id, genres.name,
                   platforms.name, first_release_date,
                   total_rating, involved_companies.company.name;
        """
        results = await self._query("games", body)
        return self._parse_game(results[0]) if results else None

    async def get_characters(self, game_id: int) -> list[IGDBCharacter]:
        """Get characters for a specific game."""
        body = f"""
            where games = [{game_id}];
            fields name, description, mug_shot.image_id, games.name;
            limit 30;
        """
        results = await self._query("characters", body)
        return [self._parse_character(r) for r in results]

    def _parse_game(self, data: dict) -> IGDBGame:
        cover_id = data.get("cover", {}).get("image_id", "") if isinstance(data.get("cover"), dict) else ""
        screenshots = [
            self._image_url(s.get("image_id", ""))
            for s in (data.get("screenshots") or [])
            if isinstance(s, dict) and s.get("image_id")
        ]

        return IGDBGame(
            id=data.get("id", 0),
            name=data.get("name", ""),
            slug=data.get("slug", ""),
            summary=data.get("summary", ""),
            cover_url=self._image_url(cover_id) if cover_id else "",
            screenshots=screenshots,
            genres=[g.get("name", "") for g in (data.get("genres") or []) if isinstance(g, dict)],
            platforms=[p.get("name", "") for p in (data.get("platforms") or []) if isinstance(p, dict)],
            first_release_date=data.get("first_release_date"),
            rating=data.get("total_rating"),
            involved_companies=[
                c.get("company", {}).get("name", "")
                for c in (data.get("involved_companies") or [])
                if isinstance(c, dict) and isinstance(c.get("company"), dict)
            ],
        )

    def _parse_character(self, data: dict) -> IGDBCharacter:
        mug_id = data.get("mug_shot", {}).get("image_id", "") if isinstance(data.get("mug_shot"), dict) else ""
        return IGDBCharacter(
            id=data.get("id", 0),
            name=data.get("name", ""),
            description=data.get("description", ""),
            mug_shot_url=self._image_url(mug_id) if mug_id else "",
            games=[g.get("name", "") for g in (data.get("games") or []) if isinstance(g, dict)],
        )

    @staticmethod
    def _image_url(image_id: str, size: str = "cover_big") -> str:
        """Build an IGDB image URL."""
        if not image_id:
            return ""
        return f"https://images.igdb.com/igdb/image/upload/t_{size}/{image_id}.jpg"
