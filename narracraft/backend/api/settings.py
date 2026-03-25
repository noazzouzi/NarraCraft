"""Settings API routes — GET/PUT /settings."""

from fastapi import APIRouter

from backend.db.database import get_db
from backend.db.models import SettingsResponse

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """Return all settings as a key-value dict."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        return SettingsResponse(settings={row["key"]: row["value"] for row in rows})
    finally:
        await db.close()


@router.put("")
async def update_settings(updates: dict[str, str]):
    """Update one or more settings."""
    db = await get_db()
    try:
        for key, value in updates.items():
            await db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        await db.commit()
        # Return updated settings
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        return SettingsResponse(settings={row["key"]: row["value"] for row in rows})
    finally:
        await db.close()
