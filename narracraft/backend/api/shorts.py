import json

from fastapi import APIRouter, HTTPException

from backend.db.database import get_db
from backend.db.models import (
    ShortCreate,
    ShortUpdate,
    ShortResponse,
    ShortListItem,
    GenerateScriptRequest,
)
from backend.llm.manager import get_provider
from backend.llm.prompts import topic_suggestions, script_generation
from backend.services.prompt_engine import generate_veo3_prompts

router = APIRouter()


@router.get("/", response_model=list[ShortListItem])
async def list_shorts(franchise_id: str | None = None, status: str | None = None):
    db = await get_db()
    try:
        query = """
            SELECT s.*, f.name as franchise_name,
                   (SELECT COUNT(*) FROM scenes WHERE short_id = s.id) as scene_count
            FROM shorts s
            LEFT JOIN franchises f ON s.franchise_id = f.id
            WHERE 1=1
        """
        params = []
        if franchise_id:
            query += " AND s.franchise_id = ?"
            params.append(franchise_id)
        if status:
            query += " AND s.status = ?"
            params.append(status)
        query += " ORDER BY s.created_at DESC"

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.post("/", response_model=ShortResponse)
async def create_short(body: ShortCreate):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM franchises WHERE id = ?", (body.franchise_id,))
        franchise = await cursor.fetchone()
        if not franchise:
            raise HTTPException(status_code=404, detail="Franchise not found")

        cursor = await db.execute(
            "INSERT INTO shorts (franchise_id) VALUES (?) RETURNING *",
            (body.franchise_id,),
        )
        row = await cursor.fetchone()
        await db.commit()

        data = dict(row)
        data["franchise_name"] = franchise["name"]
        data["scenes"] = []
        return data
    finally:
        await db.close()


@router.get("/{short_id}", response_model=ShortResponse)
async def get_short(short_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT s.*, f.name as franchise_name
               FROM shorts s LEFT JOIN franchises f ON s.franchise_id = f.id
               WHERE s.id = ?""",
            (short_id,),
        )
        short = await cursor.fetchone()
        if not short:
            raise HTTPException(status_code=404, detail="Short not found")

        cursor = await db.execute(
            """SELECT sc.*, c.name as character_name
               FROM scenes sc LEFT JOIN characters c ON sc.character_id = c.id
               WHERE sc.short_id = ? ORDER BY sc.scene_number""",
            (short_id,),
        )
        scenes = await cursor.fetchall()

        data = dict(short)
        data["scenes"] = [dict(s) for s in scenes]
        return data
    finally:
        await db.close()


@router.put("/{short_id}", response_model=ShortResponse)
async def update_short(short_id: int, body: ShortUpdate):
    db = await get_db()
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Handle published_at when status changes to published
        if updates.get("status") == "published":
            updates["published_at"] = "CURRENT_TIMESTAMP"

        set_parts = []
        values = []
        for k, v in updates.items():
            if v == "CURRENT_TIMESTAMP":
                set_parts.append(f"{k} = CURRENT_TIMESTAMP")
            else:
                set_parts.append(f"{k} = ?")
                values.append(v)

        values.append(short_id)
        await db.execute(f"UPDATE shorts SET {', '.join(set_parts)} WHERE id = ?", values)
        await db.commit()

        # Return full short with scenes
        return await get_short(short_id)
    finally:
        await db.close()


@router.delete("/{short_id}")
async def delete_short(short_id: int):
    db = await get_db()
    try:
        await db.execute("DELETE FROM shorts WHERE id = ?", (short_id,))
        await db.commit()
        return {"deleted": short_id}
    finally:
        await db.close()


# --- Wizard endpoints ---


@router.post("/{short_id}/generate-topics")
async def generate_topics(short_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT s.*, f.name as franchise_name, f.category, f.iconic_elements FROM shorts s JOIN franchises f ON s.franchise_id = f.id WHERE s.id = ?",
            (short_id,),
        )
        short = await cursor.fetchone()
        if not short:
            raise HTTPException(status_code=404, detail="Short not found")

        cursor = await db.execute(
            "SELECT * FROM characters WHERE franchise_id = ?", (short["franchise_id"],)
        )
        characters = [dict(c) for c in await cursor.fetchall()]

        llm = get_provider()
        system, prompt = topic_suggestions(
            franchise_name=short["franchise_name"],
            category=short["category"],
            characters=characters,
            iconic_elements=short["iconic_elements"] or "",
        )
        result = await llm.generate_json(prompt, system=system)
        return result
    finally:
        await db.close()


@router.post("/{short_id}/generate-script")
async def generate_script(short_id: int, body: GenerateScriptRequest):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT s.*, f.name as franchise_name, f.category, f.visual_aesthetic, f.iconic_elements FROM shorts s JOIN franchises f ON s.franchise_id = f.id WHERE s.id = ?",
            (short_id,),
        )
        short = await cursor.fetchone()
        if not short:
            raise HTTPException(status_code=404, detail="Short not found")

        # Get characters involved
        characters = []
        if body.character_names:
            placeholders = ",".join("?" for _ in body.character_names)
            cursor = await db.execute(
                f"SELECT * FROM characters WHERE franchise_id = ? AND name IN ({placeholders})",
                [short["franchise_id"]] + body.character_names,
            )
            characters = [dict(c) for c in await cursor.fetchall()]

        if not characters:
            cursor = await db.execute(
                "SELECT * FROM characters WHERE franchise_id = ?", (short["franchise_id"],)
            )
            characters = [dict(c) for c in await cursor.fetchall()]

        llm = get_provider()
        system, prompt = script_generation(
            topic_title=body.topic,
            topic_hook=body.hook,
            franchise_name=short["franchise_name"],
            visual_aesthetic=short["visual_aesthetic"] or "",
            iconic_elements=short["iconic_elements"] or "",
            characters=characters,
        )
        script = await llm.generate_json(prompt, system=system)

        # Save script and topic to the short
        upload_metadata = {
            "youtube_title": script.get("title", ""),
            "youtube_description": script.get("youtube_description", ""),
            "youtube_tags": script.get("youtube_tags", []),
            "tiktok_caption": script.get("tiktok_caption", ""),
            "instagram_caption": script.get("instagram_caption", ""),
        }

        await db.execute(
            "UPDATE shorts SET topic = ?, script_json = ?, upload_metadata_json = ?, status = 'scripted', current_step = 2 WHERE id = ?",
            (body.topic, json.dumps(script), json.dumps(upload_metadata), short_id),
        )

        # Create scene records with Veo 3 prompts from LLM
        await db.execute("DELETE FROM scenes WHERE short_id = ?", (short_id,))
        for scene in script.get("scenes", []):
            # Find character_id by name
            char_id = None
            char_name = scene.get("character_name", "")
            for c in characters:
                if c["name"].lower() == char_name.lower():
                    char_id = c["id"]
                    break

            await db.execute(
                """INSERT INTO scenes (short_id, scene_number, character_id, dialogue, expression, environment, veo3_prompt)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    short_id,
                    scene.get("scene_number", 0),
                    char_id,
                    scene.get("dialogue", ""),
                    scene.get("expression", ""),
                    scene.get("environment", ""),
                    scene.get("veo3_prompt", ""),
                ),
            )

        # Veo 3 prompts are now included — go straight to step 3
        await db.execute(
            "UPDATE shorts SET current_step = 3, status = 'in_production' WHERE id = ?",
            (short_id,),
        )

        await db.commit()
        return await get_short(short_id)
    finally:
        await db.close()


@router.post("/{short_id}/generate-prompts")
async def generate_prompts(short_id: int):
    """Fallback: generate Veo 3 prompts via template engine for scenes missing them."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT s.*, f.name as franchise_name, f.visual_aesthetic, f.iconic_elements FROM shorts s JOIN franchises f ON s.franchise_id = f.id WHERE s.id = ?",
            (short_id,),
        )
        short = await cursor.fetchone()
        if not short:
            raise HTTPException(status_code=404, detail="Short not found")

        cursor = await db.execute(
            """SELECT sc.*, c.name as character_name, c.appearance, c.outfit
               FROM scenes sc LEFT JOIN characters c ON sc.character_id = c.id
               WHERE sc.short_id = ? ORDER BY sc.scene_number""",
            (short_id,),
        )
        scenes = [dict(s) for s in await cursor.fetchall()]

        # Only generate for scenes that don't already have a Veo 3 prompt
        for scene in scenes:
            if not scene.get("veo3_prompt"):
                veo3_prompt = generate_veo3_prompts(
                    scene=scene,
                    visual_aesthetic=short["visual_aesthetic"] or "",
                    iconic_elements=short["iconic_elements"] or "",
                )
                await db.execute(
                    "UPDATE scenes SET veo3_prompt = ? WHERE id = ?",
                    (veo3_prompt, scene["id"]),
                )

        await db.commit()
        return await get_short(short_id)
    finally:
        await db.close()
