"""NarraCraft — FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.config_loader import load_config, load_franchise_registry
from backend.db.database import init_db
from backend.api import onboarding, topics, assets, pipeline, analytics, settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Load config files
    config = load_config()
    registry = load_franchise_registry()
    print(f"[NarraCraft] Config loaded: channel={config.get('channel', {}).get('name', 'unknown')}")
    print(f"[NarraCraft] Franchise registry: {len(registry.get('franchises', []))} franchises")

    # Initialize database
    await init_db()
    print("[NarraCraft] Database initialized")

    yield

    print("[NarraCraft] Shutting down")


app = FastAPI(
    title="NarraCraft",
    description="YouTube Shorts Automation System — Gaming & Anime Lore",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(onboarding.router)
app.include_router(topics.router)
app.include_router(assets.router)
app.include_router(pipeline.router)
app.include_router(analytics.router)
app.include_router(settings.router)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "narracraft-backend", "version": "0.1.0"}


@app.get("/api/config")
async def get_config_summary():
    """Return non-sensitive config summary for the frontend."""
    from backend.config.config_loader import get_config, get_franchise_registry

    config = get_config()
    registry = get_franchise_registry()

    franchises = []
    for f in registry.get("franchises", []):
        franchises.append({
            "id": f.get("id"),
            "name": f.get("name"),
            "category": f.get("category"),
            "active": f.get("active", False),
            "character_count": len(f.get("character_archetypes", [])),
            "topic_seed_count": len(f.get("topic_seeds", [])),
        })

    return {
        "channel_name": config.get("channel", {}).get("name", "unknown"),
        "voice_provider": config.get("channel", {}).get("voice", {}).get("active_provider", "chatterbox"),
        "franchises": franchises,
        "pipeline": {
            "videos_per_day": config.get("pipeline", {}).get("schedule", {}).get("videos_per_day", 1),
            "videos_per_week": config.get("pipeline", {}).get("schedule", {}).get("videos_per_week", 5),
        },
    }
