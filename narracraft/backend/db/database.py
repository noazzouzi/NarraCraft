"""SQLite database connection and schema initialization."""

import aiosqlite
from pathlib import Path

DATABASE_PATH = Path("backend/data/shorts.db")

SCHEMA_SQL = """
-- Franchises and their entries
CREATE TABLE IF NOT EXISTS franchises (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    franchise_group TEXT NOT NULL,
    category TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Visual assets (characters, environments, props)
CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    franchise_id TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    archetype_id TEXT,
    status TEXT DEFAULT 'pending',
    is_narrator BOOLEAN DEFAULT FALSE,
    model_dir TEXT,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP,
    FOREIGN KEY (franchise_id) REFERENCES franchises(id)
);

-- Topics discovered and queued
CREATE TABLE IF NOT EXISTS topics (
    id TEXT PRIMARY KEY,
    franchise_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,
    freshness TEXT DEFAULT 'evergreen',
    score REAL DEFAULT 0,
    score_breakdown_json TEXT,
    sources_json TEXT,
    characters_needed_json TEXT,
    asset_status TEXT DEFAULT 'unknown',
    suggested_hook TEXT,
    status TEXT DEFAULT 'discovered',
    narrator_archetype TEXT,
    closer_style TEXT,
    queued_at TIMESTAMP,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (franchise_id) REFERENCES franchises(id)
);

-- Generated scripts
CREATE TABLE IF NOT EXISTS scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id TEXT NOT NULL,
    script_json TEXT NOT NULL,
    word_count INTEGER,
    total_duration_seconds REAL,
    similarity_score REAL,
    status TEXT DEFAULT 'generated',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

-- Published videos
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id TEXT NOT NULL,
    script_id INTEGER NOT NULL,
    franchise_id TEXT NOT NULL,
    narrator_archetype TEXT,
    youtube_video_id TEXT,
    tiktok_video_id TEXT,
    instagram_video_id TEXT,
    facebook_video_id TEXT,
    video_path TEXT,
    long_form_outline_path TEXT,
    title TEXT,
    description TEXT,
    tags_json TEXT,
    closer_style TEXT,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (topic_id) REFERENCES topics(id),
    FOREIGN KEY (script_id) REFERENCES scripts(id),
    FOREIGN KEY (franchise_id) REFERENCES franchises(id)
);

-- Analytics snapshots
CREATE TABLE IF NOT EXISTS analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    snapshot_type TEXT NOT NULL,
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    avg_view_duration_pct REAL,
    click_through_rate REAL,
    subscribers_gained INTEGER DEFAULT 0,
    traffic_sources_json TEXT,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id)
);

-- Pipeline run history
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id TEXT,
    status TEXT DEFAULT 'running',
    current_step TEXT,
    steps_log_json TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

-- Audio track usage (for deduplication)
CREATE TABLE IF NOT EXISTS audio_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    track_path TEXT NOT NULL,
    track_type TEXT NOT NULL,
    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_id) REFERENCES videos(id)
);

-- User settings
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

DEFAULT_SETTINGS = {
    "active_theme": "gothic",
    "voice_provider": "chatterbox",
    "youtube_api_configured": "false",
    "tiktok_enabled": "false",
    "instagram_enabled": "false",
    "facebook_enabled": "false",
}


async def get_db() -> aiosqlite.Connection:
    """Get a database connection."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DATABASE_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db() -> None:
    """Initialize database schema and default settings."""
    db = await get_db()
    try:
        await db.executescript(SCHEMA_SQL)

        # Insert default settings if they don't exist
        for key, value in DEFAULT_SETTINGS.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )

        await db.commit()
    finally:
        await db.close()
