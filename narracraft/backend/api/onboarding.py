"""Onboarding API routes — franchise search, character discovery, and save."""

import json
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.db.database import get_db
from backend.services.onboarding.wiki_scraper import (
    search_wiki,
    discover_characters as wiki_discover_characters,
    discover_locations as wiki_discover_locations,
    WIKI_SLUGS,
)
from backend.services.onboarding.igdb_client import IGDBClient
from backend.services.onboarding.mal_client import (
    search_anime_jikan,
    search_manga_jikan,
    get_characters_jikan,
    search_anilist,
    get_characters_anilist,
)
from backend.services.onboarding.image_search import search_images
from backend.services.onboarding.bible_generator import (
    generate_bible_from_wiki,
    generate_archetype_id,
)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])
_igdb = IGDBClient()


@router.get("/search")
async def search_franchise(
    q: str,
    category: Optional[str] = Query(None, description="gaming or anime_manga"),
):
    """Search for a franchise across all sources (wiki, IGDB, MAL, AniList)."""
    results = []

    # Search Fandom wikis
    wiki_results = await search_wiki(q)
    for wr in wiki_results[:10]:
        results.append({
            "source": "fandom_wiki",
            "title": wr.title,
            "url": wr.url,
            "summary": wr.summary,
            "wiki_slug": wr.wiki_slug,
        })

    # Search IGDB (gaming)
    if category in (None, "gaming") and _igdb.is_configured:
        try:
            igdb_results = await _igdb.search_games(q)
            for game in igdb_results[:5]:
                results.append({
                    "source": "igdb",
                    "title": game.name,
                    "summary": game.summary[:300],
                    "image_url": game.cover_url,
                    "igdb_id": game.id,
                    "genres": game.genres,
                    "platforms": game.platforms,
                    "rating": game.rating,
                })
        except Exception:
            pass

    # Search anime/manga (Jikan + AniList)
    if category in (None, "anime_manga"):
        try:
            jikan_results = await search_anime_jikan(q, limit=5)
            for anime in jikan_results:
                results.append({
                    "source": "jikan",
                    "title": anime.title,
                    "title_english": anime.title_english,
                    "summary": anime.synopsis,
                    "image_url": anime.image_url,
                    "mal_id": anime.id,
                    "episodes": anime.episodes,
                    "score": anime.score,
                    "genres": anime.genres,
                })
        except Exception:
            pass

        try:
            anilist_results = await search_anilist(q, limit=5)
            for anime in anilist_results:
                results.append({
                    "source": "anilist",
                    "title": anime.title,
                    "title_english": anime.title_english,
                    "summary": anime.synopsis,
                    "image_url": anime.image_url,
                    "anilist_id": anime.id,
                    "episodes": anime.episodes,
                    "score": anime.score,
                    "genres": anime.genres,
                })
        except Exception:
            pass

    return {"query": q, "results": results, "total": len(results)}


@router.get("/characters")
async def discover_characters(
    franchise_id: str,
    wiki_slug: Optional[str] = None,
    mal_id: Optional[int] = None,
    anilist_id: Optional[int] = None,
    igdb_id: Optional[int] = None,
):
    """Discover characters for a franchise from multiple sources."""
    characters = []

    # Wiki characters
    slug = wiki_slug or WIKI_SLUGS.get(franchise_id, "")
    if slug:
        try:
            wiki_chars = await wiki_discover_characters(slug, franchise_id)
            for wc in wiki_chars:
                characters.append({
                    "source": "fandom_wiki",
                    "name": wc.name,
                    "description": wc.description,
                    "image_urls": wc.image_urls,
                    "page_url": wc.page_url,
                    "attributes": wc.attributes,
                })
        except Exception:
            pass

    # MAL characters
    if mal_id:
        try:
            mal_chars = await get_characters_jikan(mal_id)
            for mc in mal_chars:
                characters.append({
                    "source": "jikan",
                    "name": mc.name,
                    "role": mc.role,
                    "image_urls": [mc.image_url] if mc.image_url else [],
                    "description": mc.description,
                })
        except Exception:
            pass

    # AniList characters
    if anilist_id:
        try:
            al_chars = await get_characters_anilist(anilist_id)
            for ac in al_chars:
                characters.append({
                    "source": "anilist",
                    "name": ac.name,
                    "role": ac.role,
                    "image_urls": [ac.image_url] if ac.image_url else [],
                    "description": ac.description,
                })
        except Exception:
            pass

    # IGDB characters
    if igdb_id and _igdb.is_configured:
        try:
            igdb_chars = await _igdb.get_characters(igdb_id)
            for ic in igdb_chars:
                characters.append({
                    "source": "igdb",
                    "name": ic.name,
                    "description": ic.description,
                    "image_urls": [ic.mug_shot_url] if ic.mug_shot_url else [],
                    "games": ic.games,
                })
        except Exception:
            pass

    return {"franchise_id": franchise_id, "characters": characters, "total": len(characters)}


@router.get("/locations")
async def discover_locations(
    franchise_id: str,
    wiki_slug: Optional[str] = None,
):
    """Discover locations for a franchise from wiki."""
    slug = wiki_slug or WIKI_SLUGS.get(franchise_id, "")
    if not slug:
        return {"franchise_id": franchise_id, "locations": [], "total": 0}

    try:
        wiki_locs = await wiki_discover_locations(slug)
        locations = [{
            "name": loc.name,
            "description": loc.description,
            "image_urls": loc.image_urls,
            "page_url": loc.page_url,
        } for loc in wiki_locs]
    except Exception:
        locations = []

    return {"franchise_id": franchise_id, "locations": locations, "total": len(locations)}


@router.get("/images")
async def search_reference_images(q: str, limit: int = Query(20, le=50)):
    """Search for reference images to use during asset generation."""
    results = await search_images(q, limit)
    return {
        "query": q,
        "images": [{
            "url": r.url,
            "thumbnail_url": r.thumbnail_url,
            "title": r.title,
            "source_url": r.source_url,
            "width": r.width,
            "height": r.height,
        } for r in results],
    }


class GenerateBibleRequest(BaseModel):
    character_name: str
    wiki_summary: str = ""
    infobox: dict[str, str] = {}


@router.post("/generate-bible")
async def generate_bible(req: GenerateBibleRequest):
    """Generate a character bible from wiki data."""
    bible = generate_bible_from_wiki(
        character_name=req.character_name,
        wiki_summary=req.wiki_summary,
        infobox=req.infobox,
    )
    return {
        "archetype_id": bible.archetype_id,
        "visual_description": bible.visual_description,
        "character_bible": bible.character_bible,
        "source_character_name": bible.source_character_name,
    }


class SaveFranchiseRequest(BaseModel):
    id: str
    name: str
    franchise_group: str
    category: str
    characters: list[dict] = []
    environments: list[dict] = []
    props: list[dict] = []
    visual_style: dict = {}
    audio_profile: dict = {}
    topic_seeds: list[str] = []
    content_notes: dict = {}


@router.post("/save")
async def save_franchise(req: SaveFranchiseRequest):
    """Save a franchise entry to the database with all its configuration."""
    db = await get_db()
    try:
        config = {
            "character_archetypes": req.characters,
            "environments": req.environments,
            "props": req.props,
            "visual_style": req.visual_style,
            "audio_profile": req.audio_profile,
            "topic_seeds": req.topic_seeds,
            "content_notes": req.content_notes,
        }

        await db.execute(
            """INSERT OR REPLACE INTO franchises (id, name, franchise_group, category, config_json)
               VALUES (?, ?, ?, ?, ?)""",
            (req.id, req.name, req.franchise_group, req.category, json.dumps(config)),
        )

        # Create asset entries for each character archetype
        for char in req.characters:
            archetype_id = char.get("archetype_id", "")
            if not archetype_id:
                continue
            asset_id = f"{req.id}/characters/{archetype_id}"
            await db.execute(
                """INSERT OR IGNORE INTO assets (id, franchise_id, asset_type, archetype_id, is_narrator, metadata_json)
                   VALUES (?, ?, 'character', ?, ?, ?)""",
                (
                    asset_id,
                    req.id,
                    archetype_id,
                    char.get("is_narrator", False),
                    json.dumps(char),
                ),
            )

        # Create asset entries for environments
        for env in req.environments:
            env_id = env.get("env_id", "")
            if not env_id:
                continue
            asset_id = f"{req.id}/environments/{env_id}"
            await db.execute(
                """INSERT OR IGNORE INTO assets (id, franchise_id, asset_type, metadata_json)
                   VALUES (?, ?, 'environment', ?)""",
                (asset_id, req.id, json.dumps(env)),
            )

        # Create asset entries for props
        for prop in req.props:
            prop_id = prop.get("prop_id", "")
            if not prop_id:
                continue
            asset_id = f"{req.id}/props/{prop_id}"
            await db.execute(
                """INSERT OR IGNORE INTO assets (id, franchise_id, asset_type, metadata_json)
                   VALUES (?, ?, 'prop', ?)""",
                (asset_id, req.id, json.dumps(prop)),
            )

        await db.commit()
        return {"status": "saved", "franchise_id": req.id}
    finally:
        await db.close()
