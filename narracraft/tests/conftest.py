"""Shared test fixtures for NarraCraft tests."""

import asyncio
import os
import sys
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set working directory so config loader finds data/
os.chdir(str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def event_loop():
    """Create a shared event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db(tmp_path):
    """Provide a temporary database for tests."""
    import backend.db.database as db_mod

    original_path = db_mod.DATABASE_PATH
    db_mod.DATABASE_PATH = tmp_path / "test.db"

    from backend.db.database import init_db
    await init_db()

    yield db_mod.DATABASE_PATH

    db_mod.DATABASE_PATH = original_path


@pytest.fixture
def reset_config():
    """Reset the config loader cache before and after each test."""
    import backend.config.config_loader as cl
    cl._config = None
    cl._franchise_registry = None
    yield
    cl._config = None
    cl._franchise_registry = None
