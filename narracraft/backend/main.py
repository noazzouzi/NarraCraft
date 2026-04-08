import os
import traceback
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.DEBUG)

from backend.db.database import init_db, get_db
from backend.llm.manager import init_provider
from backend.api.franchises import router as franchises_router
from backend.api.characters import router as characters_router
from backend.api.shorts import router as shorts_router
from backend.api.scenes import router as scenes_router
from backend.api.settings import router as settings_router
from backend.api.llm_status import router as llm_router

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("NarraCraft V3 — Database initialized")

    # Initialize LLM provider from saved settings
    try:
        db = await get_db()
        cursor = await db.execute("SELECT key, value FROM settings WHERE key IN ('llm_provider', 'gemini_api_key')")
        rows = await cursor.fetchall()
        await db.close()
        settings = {r["key"]: r["value"] for r in rows}
        api_key = settings.get("gemini_api_key", "") or os.environ.get("GEMINI_API_KEY", "")
        if api_key:
            provider_name = settings.get("llm_provider", "gemini_flash")
            init_provider(provider_name, api_key)
            print(f"NarraCraft V3 — LLM provider initialized: {provider_name}")
        else:
            print("NarraCraft V3 — No API key configured. Set it in Settings.")
    except Exception as e:
        print(f"NarraCraft V3 — LLM init skipped: {e}")

    yield
    print("NarraCraft V3 — Shutting down")


app = FastAPI(title="NarraCraft V3", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(franchises_router, prefix="/api/franchises", tags=["franchises"])
app.include_router(characters_router, prefix="/api/characters", tags=["characters"])
app.include_router(shorts_router, prefix="/api/shorts", tags=["shorts"])
app.include_router(scenes_router, prefix="/api/scenes", tags=["scenes"])
app.include_router(settings_router, prefix="/api/settings", tags=["settings"])
app.include_router(llm_router, prefix="/api/llm", tags=["llm"])

# Serve uploaded character images
images_dir = os.path.join(os.path.dirname(__file__), "..", "data", "images")
os.makedirs(images_dir, exist_ok=True)
app.mount("/images", StaticFiles(directory=images_dir), name="images")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    print(f"\n{'='*60}\nUNHANDLED ERROR: {request.method} {request.url}\n{tb}\n{'='*60}\n")
    return JSONResponse(status_code=500, content={"detail": str(exc), "traceback": tb})


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "3.0.0"}


@app.post("/api/test-llm")
async def test_llm():
    """Debug endpoint to test LLM directly."""
    try:
        from backend.llm.manager import get_provider
        provider = get_provider()
        status = await provider.check_status()
        result = await provider.generate("Say hello in one word.")
        return {"status": status, "result": result}
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()}
