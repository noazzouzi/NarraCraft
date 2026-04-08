import re
import traceback

from fastapi import APIRouter, HTTPException

from backend.db.database import get_db
from backend.db.models import (
    FranchiseCreate,
    FranchiseUpdate,
    FranchiseResponse,
    FranchiseWithCharacters,
    CharacterCreate,
    CharacterResponse,
)
from backend.llm.manager import get_provider
from backend.llm.prompts import franchise_onboarding, character_onboarding

router = APIRouter()


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


@router.get("/", response_model=list[FranchiseResponse])
async def list_franchises():
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM franchises ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.post("/")
async def create_franchise(body: FranchiseCreate):
    try:
        llm = get_provider()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        system, prompt = franchise_onboarding(body.name, body.category)
        result = await llm.generate_json(prompt, system=system)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    franchise_id = slugify(body.name)

    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO franchises (id, name, category, visual_aesthetic, iconic_elements) VALUES (?, ?, ?, ?, ?)",
            (franchise_id, body.name, body.category, result.get("visual_aesthetic", ""), result.get("iconic_elements", "")),
        )

        # Auto-create all characters from the single LLM response
        for char in result.get("characters", []):
            char_id = f"{franchise_id}_{slugify(char.get('name', 'unknown'))}"
            await db.execute(
                """INSERT OR IGNORE INTO characters
                   (id, franchise_id, name, appearance, outfit, personality, speech_style, flow_prompt)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    char_id,
                    franchise_id,
                    char.get("name", ""),
                    char.get("appearance", ""),
                    char.get("outfit", ""),
                    char.get("personality", ""),
                    char.get("speech_style", ""),
                    char.get("flow_prompt", ""),
                ),
            )

        await db.commit()

        # Return full franchise with characters
        cursor = await db.execute("SELECT * FROM franchises WHERE id = ?", (franchise_id,))
        row = await cursor.fetchone()
        cursor = await db.execute(
            "SELECT * FROM characters WHERE franchise_id = ? ORDER BY created_at", (franchise_id,)
        )
        characters = await cursor.fetchall()

        data = dict(row)
        data["characters"] = [dict(c) for c in characters]
        return data
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        await db.close()


@router.get("/{franchise_id}", response_model=FranchiseWithCharacters)
async def get_franchise(franchise_id: str):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM franchises WHERE id = ?", (franchise_id,))
        franchise = await cursor.fetchone()
        if not franchise:
            raise HTTPException(status_code=404, detail="Franchise not found")

        cursor = await db.execute(
            "SELECT * FROM characters WHERE franchise_id = ? ORDER BY created_at", (franchise_id,)
        )
        characters = await cursor.fetchall()

        data = dict(franchise)
        data["characters"] = [dict(c) for c in characters]
        return data
    finally:
        await db.close()


@router.put("/{franchise_id}", response_model=FranchiseResponse)
async def update_franchise(franchise_id: str, body: FranchiseUpdate):
    db = await get_db()
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [franchise_id]
        await db.execute(f"UPDATE franchises SET {set_clause} WHERE id = ?", values)
        await db.commit()

        cursor = await db.execute("SELECT * FROM franchises WHERE id = ?", (franchise_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Franchise not found")
        return dict(row)
    finally:
        await db.close()


@router.delete("/{franchise_id}")
async def delete_franchise(franchise_id: str):
    db = await get_db()
    try:
        await db.execute("DELETE FROM franchises WHERE id = ?", (franchise_id,))
        await db.commit()
        return {"deleted": franchise_id}
    finally:
        await db.close()


@router.post("/{franchise_id}/characters", response_model=CharacterResponse)
async def add_character(franchise_id: str, body: CharacterCreate):
    db = await get_db()
    try:
        # Verify franchise exists
        cursor = await db.execute("SELECT * FROM franchises WHERE id = ?", (franchise_id,))
        franchise = await cursor.fetchone()
        if not franchise:
            raise HTTPException(status_code=404, detail="Franchise not found")

        # Generate character details via LLM — pass franchise context for better prompts
        try:
            llm = get_provider()
            system, prompt = character_onboarding(
                body.name,
                franchise["name"],
                franchise["category"],
                visual_aesthetic=franchise["visual_aesthetic"] or "",
                iconic_elements=franchise["iconic_elements"] or "",
            )
            result = await llm.generate_json(prompt, system=system)
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"LLM error: {e}")

        character_id = f"{franchise_id}_{slugify(body.name)}"

        await db.execute(
            """INSERT INTO characters (id, franchise_id, name, appearance, outfit, personality, speech_style, flow_prompt)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                character_id,
                franchise_id,
                body.name,
                result.get("appearance", ""),
                result.get("outfit", ""),
                result.get("personality", ""),
                result.get("speech_style", ""),
                result.get("flow_prompt", ""),
            ),
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM characters WHERE id = ?", (character_id,))
        row = await cursor.fetchone()
        return dict(row)
    finally:
        await db.close()
