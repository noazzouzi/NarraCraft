import os
import shutil

from fastapi import APIRouter, HTTPException, UploadFile, File

from backend.db.database import get_db
from backend.db.models import CharacterUpdate, CharacterResponse

router = APIRouter()

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "images", "characters")


@router.put("/{character_id}", response_model=CharacterResponse)
async def update_character(character_id: str, body: CharacterUpdate):
    db = await get_db()
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [character_id]
        await db.execute(f"UPDATE characters SET {set_clause} WHERE id = ?", values)
        await db.commit()

        cursor = await db.execute("SELECT * FROM characters WHERE id = ?", (character_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Character not found")
        return dict(row)
    finally:
        await db.close()


@router.delete("/{character_id}")
async def delete_character(character_id: str):
    db = await get_db()
    try:
        # Delete image file if exists
        cursor = await db.execute("SELECT image_path FROM characters WHERE id = ?", (character_id,))
        row = await cursor.fetchone()
        if row and row["image_path"]:
            full_path = os.path.join(IMAGES_DIR, os.path.basename(row["image_path"]))
            if os.path.exists(full_path):
                os.remove(full_path)

        await db.execute("DELETE FROM characters WHERE id = ?", (character_id,))
        await db.commit()
        return {"deleted": character_id}
    finally:
        await db.close()


@router.post("/{character_id}/image", response_model=CharacterResponse)
async def upload_character_image(character_id: str, file: UploadFile = File(...)):
    os.makedirs(IMAGES_DIR, exist_ok=True)

    # Save file with character_id as filename
    ext = os.path.splitext(file.filename or "image.png")[1] or ".png"
    filename = f"{character_id}{ext}"
    filepath = os.path.join(IMAGES_DIR, filename)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Store relative path for serving via /images/characters/
    image_path = f"characters/{filename}"

    db = await get_db()
    try:
        await db.execute("UPDATE characters SET image_path = ? WHERE id = ?", (image_path, character_id))
        await db.commit()

        cursor = await db.execute("SELECT * FROM characters WHERE id = ?", (character_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Character not found")
        return dict(row)
    finally:
        await db.close()
