import os
import aiosqlite

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "db", "narracraft.db")


async def get_db() -> aiosqlite.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db


async def init_db():
    db = await get_db()
    try:
        await db.executescript(SCHEMA)
        await db.commit()
    finally:
        await db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS franchises (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT 'gaming',
    visual_aesthetic TEXT,
    iconic_elements TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS characters (
    id              TEXT PRIMARY KEY,
    franchise_id    TEXT NOT NULL REFERENCES franchises(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    appearance      TEXT,
    outfit          TEXT,
    personality     TEXT,
    speech_style    TEXT,
    flow_prompt     TEXT,
    image_path      TEXT,
    flow_url        TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS shorts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    franchise_id        TEXT NOT NULL REFERENCES franchises(id),
    topic               TEXT,
    script_json         TEXT,
    status              TEXT DEFAULT 'draft',
    current_step        INTEGER DEFAULT 1,
    upload_metadata_json TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at        TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scenes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    short_id        INTEGER NOT NULL REFERENCES shorts(id) ON DELETE CASCADE,
    scene_number    INTEGER NOT NULL,
    character_id    TEXT REFERENCES characters(id),
    dialogue        TEXT,
    expression      TEXT,
    environment     TEXT,
    veo3_prompt     TEXT,
    flow_url        TEXT,
    status          TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT
);

INSERT OR IGNORE INTO settings (key, value) VALUES ('llm_provider', 'gemini_flash');
INSERT OR IGNORE INTO settings (key, value) VALUES ('gemini_api_key', '');
INSERT OR IGNORE INTO settings (key, value) VALUES ('theme', 'dark');
"""
