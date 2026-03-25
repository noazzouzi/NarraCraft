"""Integration tests for the database module."""

import json
import pytest
import pytest_asyncio
from backend.db.database import get_db, init_db, DATABASE_PATH, SCHEMA_SQL, DEFAULT_SETTINGS
import backend.db.database as db_mod


@pytest.fixture(autouse=True)
async def temp_db(tmp_path):
    """Use a temporary database for each test."""
    original = db_mod.DATABASE_PATH
    db_mod.DATABASE_PATH = tmp_path / "test.db"
    await init_db()
    yield
    db_mod.DATABASE_PATH = original


class TestInitDb:
    """Tests for database initialization."""

    @pytest.mark.asyncio
    async def test_tables_created(self):
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in await cursor.fetchall()]
        finally:
            await db.close()

        expected = ["analytics", "assets", "audio_usage", "franchises",
                    "pipeline_runs", "scripts", "settings", "topics", "videos"]
        for t in expected:
            assert t in tables, f"Table '{t}' not found"

    @pytest.mark.asyncio
    async def test_default_settings_inserted(self):
        db = await get_db()
        try:
            cursor = await db.execute("SELECT key, value FROM settings")
            settings = {row[0]: row[1] for row in await cursor.fetchall()}
        finally:
            await db.close()

        for key, value in DEFAULT_SETTINGS.items():
            assert key in settings, f"Default setting '{key}' missing"
            assert settings[key] == value

    @pytest.mark.asyncio
    async def test_init_db_idempotent(self):
        """Running init_db twice should not fail or duplicate data."""
        await init_db()
        db = await get_db()
        try:
            cursor = await db.execute("SELECT COUNT(*) FROM settings")
            count = (await cursor.fetchone())[0]
        finally:
            await db.close()

        assert count == len(DEFAULT_SETTINGS)


class TestFranchiseCrud:
    """Tests for franchise CRUD operations."""

    @pytest.mark.asyncio
    async def test_insert_franchise(self):
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO franchises (id, name, franchise_group, category, config_json) VALUES (?, ?, ?, ?, ?)",
                ("test_re", "Resident Evil", "resident_evil", "gaming", "{}"),
            )
            await db.commit()

            cursor = await db.execute("SELECT * FROM franchises WHERE id = ?", ("test_re",))
            row = await cursor.fetchone()
            assert row is not None
            assert dict(row)["name"] == "Resident Evil"
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_insert_topic_with_fk(self):
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO franchises (id, name, franchise_group, category, config_json) VALUES (?, ?, ?, ?, ?)",
                ("test_re", "Resident Evil", "resident_evil", "gaming", "{}"),
            )
            await db.execute(
                "INSERT INTO topics (id, franchise_id, title, status) VALUES (?, ?, ?, ?)",
                ("t1", "test_re", "Test Topic", "discovered"),
            )
            await db.commit()

            cursor = await db.execute("SELECT * FROM topics WHERE id = ?", ("t1",))
            row = await cursor.fetchone()
            assert row is not None
            assert dict(row)["franchise_id"] == "test_re"
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_fk_constraint_enforced(self):
        """Insert topic without franchise should fail when FK enforced."""
        db = await get_db()
        try:
            with pytest.raises(Exception):
                await db.execute(
                    "INSERT INTO topics (id, franchise_id, title, status) VALUES (?, ?, ?, ?)",
                    ("t1", "nonexistent", "Test", "discovered"),
                )
                await db.commit()
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_update_settings(self):
        db = await get_db()
        try:
            await db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("active_theme", "survival"),
            )
            await db.commit()

            cursor = await db.execute("SELECT value FROM settings WHERE key = ?", ("active_theme",))
            row = await cursor.fetchone()
            assert row[0] == "survival"
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_wal_mode_enabled(self):
        db = await get_db()
        try:
            cursor = await db.execute("PRAGMA journal_mode")
            mode = (await cursor.fetchone())[0]
            assert mode == "wal"
        finally:
            await db.close()
