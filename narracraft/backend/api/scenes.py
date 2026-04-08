from fastapi import APIRouter, HTTPException

from backend.db.database import get_db
from backend.db.models import SceneUpdate, SceneResponse

router = APIRouter()


@router.put("/{scene_id}", response_model=SceneResponse)
async def update_scene(scene_id: int, body: SceneUpdate):
    db = await get_db()
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [scene_id]
        await db.execute(f"UPDATE scenes SET {set_clause} WHERE id = ?", values)
        await db.commit()

        cursor = await db.execute(
            """SELECT sc.*, c.name as character_name
               FROM scenes sc LEFT JOIN characters c ON sc.character_id = c.id
               WHERE sc.id = ?""",
            (scene_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Scene not found")
        return dict(row)
    finally:
        await db.close()
