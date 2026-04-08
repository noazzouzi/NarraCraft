from fastapi import APIRouter

from backend.db.database import get_db
from backend.db.models import SettingsUpdate
from backend.llm.manager import init_provider

router = APIRouter()


@router.get("/")
async def get_settings():
    db = await get_db()
    try:
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        return {r["key"]: r["value"] for r in rows}
    finally:
        await db.close()


@router.put("/")
async def update_settings(body: SettingsUpdate):
    db = await get_db()
    try:
        for key, value in body.settings.items():
            await db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
                (key, value, value),
            )
        await db.commit()

        # Re-initialize LLM provider if relevant settings changed
        if "llm_provider" in body.settings or "gemini_api_key" in body.settings:
            cursor = await db.execute("SELECT key, value FROM settings WHERE key IN ('llm_provider', 'gemini_api_key')")
            rows = await cursor.fetchall()
            settings = {r["key"]: r["value"] for r in rows}
            provider_name = settings.get("llm_provider", "gemini_flash")
            api_key = settings.get("gemini_api_key", "")
            if api_key:
                init_provider(provider_name, api_key)

        return {"status": "ok"}
    finally:
        await db.close()
