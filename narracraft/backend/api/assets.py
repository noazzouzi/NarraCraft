"""Assets API routes — list, approve, reject visual assets."""

from typing import Optional

from fastapi import APIRouter, Query

from backend.db.database import get_db

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("")
async def list_assets(
    franchise_id: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """List visual assets with filters."""
    db = await get_db()
    try:
        query = "SELECT * FROM assets WHERE 1=1"
        params: list = []

        if franchise_id:
            query += " AND franchise_id = ?"
            params.append(franchise_id)
        if type:
            query += " AND asset_type = ?"
            params.append(type)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return {"assets": [dict(row) for row in rows], "total": len(rows)}
    finally:
        await db.close()


@router.post("/{asset_id}/approve")
async def approve_asset(asset_id: str):
    """Mark an asset as approved."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE assets SET status = 'approved', approved_at = CURRENT_TIMESTAMP WHERE id = ?",
            (asset_id,),
        )
        await db.commit()
        return {"status": "approved", "asset_id": asset_id}
    finally:
        await db.close()


@router.post("/{asset_id}/reject")
async def reject_asset(asset_id: str):
    """Mark an asset as rejected."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE assets SET status = 'rejected' WHERE id = ?",
            (asset_id,),
        )
        await db.commit()
        return {"status": "rejected", "asset_id": asset_id}
    finally:
        await db.close()
