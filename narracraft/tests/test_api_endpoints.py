"""Integration tests for API endpoints using FastAPI TestClient."""

import json
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

import backend.db.database as db_mod
from backend.db.database import init_db, get_db


@pytest.fixture(autouse=True)
async def temp_db(tmp_path):
    """Use a temporary database for each test."""
    original = db_mod.DATABASE_PATH
    db_mod.DATABASE_PATH = tmp_path / "test_api.db"
    await init_db()
    yield
    db_mod.DATABASE_PATH = original


@pytest.fixture
async def client():
    """Create an async test client for the FastAPI app."""
    from backend.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"


class TestConfigEndpoint:
    """Tests for the config summary endpoint."""

    @pytest.mark.asyncio
    async def test_config_returns_franchises(self, client):
        resp = await client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "franchises" in data
        assert "channel_name" in data
        assert "voice_provider" in data


class TestSettingsEndpoints:
    """Tests for settings GET/PUT."""

    @pytest.mark.asyncio
    async def test_get_settings(self, client):
        resp = await client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "settings" in data
        assert "active_theme" in data["settings"]

    @pytest.mark.asyncio
    async def test_update_settings(self, client):
        resp = await client.put(
            "/api/settings",
            json={"active_theme": "survival"},
        )
        assert resp.status_code == 200

        # Verify it was saved
        resp = await client.get("/api/settings")
        data = resp.json()
        assert data["settings"]["active_theme"] == "survival"


class TestTopicsEndpoints:
    """Tests for topic management endpoints."""

    async def _insert_franchise(self):
        db = await get_db()
        try:
            await db.execute(
                "INSERT OR IGNORE INTO franchises (id, name, franchise_group, category, config_json) VALUES (?, ?, ?, ?, ?)",
                ("test_re", "Resident Evil", "resident_evil", "gaming", "{}"),
            )
            await db.commit()
        finally:
            await db.close()

    async def _insert_topic(self, topic_id="t1", status="discovered"):
        await self._insert_franchise()
        db = await get_db()
        try:
            await db.execute(
                "INSERT OR IGNORE INTO topics (id, franchise_id, title, description, category, score, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (topic_id, "test_re", "Test Topic", "Description", "lore", 15.0, status),
            )
            await db.commit()
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_list_topics_empty(self, client):
        resp = await client.get("/api/topics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["topics"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_topics_with_data(self, client):
        await self._insert_topic()
        resp = await client.get("/api/topics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["topics"][0]["title"] == "Test Topic"

    @pytest.mark.asyncio
    async def test_list_topics_filter_by_status(self, client):
        await self._insert_topic("t1", "discovered")
        await self._insert_topic("t2", "queued")
        resp = await client.get("/api/topics?status=queued")
        data = resp.json()
        assert data["total"] == 1
        assert data["topics"][0]["id"] == "t2"

    @pytest.mark.asyncio
    async def test_list_topics_filter_by_franchise(self, client):
        await self._insert_topic()
        resp = await client.get("/api/topics?franchise=test_re")
        data = resp.json()
        assert data["total"] == 1

        resp = await client.get("/api/topics?franchise=nonexistent")
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_get_single_topic(self, client):
        await self._insert_topic()
        resp = await client.get("/api/topics/t1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Topic"

    @pytest.mark.asyncio
    async def test_get_nonexistent_topic(self, client):
        resp = await client.get("/api/topics/nonexistent")
        data = resp.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_queue_topic(self, client):
        await self._insert_topic("t1", "discovered")
        resp = await client.put("/api/topics/t1/queue")
        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"

        # Verify in DB
        resp = await client.get("/api/topics/t1")
        assert resp.json()["status"] == "queued"

    @pytest.mark.asyncio
    async def test_skip_topic(self, client):
        await self._insert_topic("t1", "discovered")
        resp = await client.put("/api/topics/t1/skip")
        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_update_topic(self, client):
        await self._insert_topic()
        resp = await client.put("/api/topics/t1", json={"title": "Updated Title"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    @pytest.mark.asyncio
    async def test_update_topic_invalid_fields(self, client):
        await self._insert_topic()
        resp = await client.put("/api/topics/t1", json={"invalid_field": "value"})
        data = resp.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_pagination(self, client):
        await self._insert_franchise()
        db = await get_db()
        try:
            for i in range(10):
                await db.execute(
                    "INSERT INTO topics (id, franchise_id, title, score, status) VALUES (?, ?, ?, ?, ?)",
                    (f"t{i}", "test_re", f"Topic {i}", float(i), "discovered"),
                )
            await db.commit()
        finally:
            await db.close()

        resp = await client.get("/api/topics?limit=3&offset=0")
        data = resp.json()
        assert len(data["topics"]) == 3
        assert data["total"] == 10


class TestAssetsEndpoints:
    """Tests for asset management endpoints."""

    async def _insert_asset(self):
        db = await get_db()
        try:
            await db.execute(
                "INSERT OR IGNORE INTO franchises (id, name, franchise_group, category, config_json) VALUES (?, ?, ?, ?, ?)",
                ("test_re", "Resident Evil", "resident_evil", "gaming", "{}"),
            )
            await db.execute(
                "INSERT OR IGNORE INTO assets (id, franchise_id, asset_type, status, metadata_json) VALUES (?, ?, ?, ?, ?)",
                ("test_re/chars/jill", "test_re", "character", "pending", "{}"),
            )
            await db.commit()
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_list_assets_empty(self, client):
        resp = await client.get("/api/assets")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_approve_asset(self, client):
        await self._insert_asset()
        resp = await client.post("/api/assets/test_re/chars/jill/approve")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_reject_asset(self, client):
        await self._insert_asset()
        resp = await client.post("/api/assets/test_re/chars/jill/reject")
        assert resp.status_code == 200


class TestPipelineEndpoints:
    """Tests for pipeline status endpoint."""

    @pytest.mark.asyncio
    async def test_pipeline_status(self, client):
        resp = await client.get("/api/pipeline/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "is_running" in data

    @pytest.mark.asyncio
    async def test_quarantine_list(self, client):
        resp = await client.get("/api/pipeline/quarantine")
        assert resp.status_code == 200


class TestAnalyticsEndpoints:
    """Tests for analytics endpoints."""

    @pytest.mark.asyncio
    async def test_dashboard(self, client):
        resp = await client.get("/api/analytics/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_videos" in data

    @pytest.mark.asyncio
    async def test_insights(self, client):
        resp = await client.get("/api/analytics/insights")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_franchise_analytics_list(self, client):
        resp = await client.get("/api/analytics/franchises")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_video_analytics_list(self, client):
        resp = await client.get("/api/analytics/videos")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_derived_scores(self, client):
        resp = await client.get("/api/analytics/scores")
        assert resp.status_code == 200
