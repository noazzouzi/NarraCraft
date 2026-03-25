"""Unit tests for config loader."""

import os
import pytest
import yaml
from pathlib import Path

from backend.config.config_loader import (
    load_config,
    load_franchise_registry,
    get_config,
    get_franchise_registry,
    reload_config,
    reload_franchise_registry,
    _default_config,
)


class TestDefaultConfig:
    """Tests for the default configuration."""

    def test_has_channel_section(self):
        cfg = _default_config()
        assert "channel" in cfg
        assert "name" in cfg["channel"]

    def test_has_pipeline_section(self):
        cfg = _default_config()
        assert "pipeline" in cfg
        assert "schedule" in cfg["pipeline"]
        assert cfg["pipeline"]["schedule"]["videos_per_day"] == 1

    def test_has_quality_section(self):
        cfg = _default_config()
        assert "quality" in cfg
        assert cfg["quality"]["script_compliance"]["similarity_threshold"] == 0.70

    def test_has_storage_section(self):
        cfg = _default_config()
        assert "storage" in cfg


class TestLoadConfig:
    """Tests for config loading from YAML."""

    def test_load_returns_dict(self, reset_config):
        cfg = load_config()
        assert isinstance(cfg, dict)

    def test_load_config_cached(self, reset_config):
        """Second call returns same object (cached)."""
        cfg1 = load_config()
        cfg2 = load_config()
        assert cfg1 is cfg2

    def test_get_config_loads_if_needed(self, reset_config):
        cfg = get_config()
        assert isinstance(cfg, dict)

    def test_reload_config_fresh(self, reset_config):
        cfg1 = load_config()
        cfg2 = reload_config()
        # After reload, may be same content but the cache was cleared
        assert isinstance(cfg2, dict)

    def test_missing_config_returns_defaults(self, reset_config, tmp_path, monkeypatch):
        """When config file doesn't exist, returns defaults."""
        monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "nonexistent.yaml"))
        cfg = reload_config()
        assert "channel" in cfg
        assert cfg["pipeline"]["schedule"]["videos_per_day"] == 1


class TestLoadFranchiseRegistry:
    """Tests for franchise registry loading."""

    def test_load_returns_dict(self, reset_config):
        reg = load_franchise_registry()
        assert isinstance(reg, dict)

    def test_has_franchises_key(self, reset_config):
        reg = load_franchise_registry()
        assert "franchises" in reg

    def test_cached(self, reset_config):
        reg1 = load_franchise_registry()
        reg2 = load_franchise_registry()
        assert reg1 is reg2

    def test_reload_fresh(self, reset_config):
        reg1 = load_franchise_registry()
        reg2 = reload_franchise_registry()
        assert isinstance(reg2, dict)

    def test_get_franchise_registry_loads(self, reset_config):
        reg = get_franchise_registry()
        assert isinstance(reg, dict)

    def test_missing_registry_returns_empty(self, reset_config, tmp_path, monkeypatch):
        monkeypatch.setenv("FRANCHISE_REGISTRY_PATH", str(tmp_path / "nonexistent.yaml"))
        reg = reload_franchise_registry()
        assert reg == {"registry": {}, "franchises": []}

    def test_resident_evil_in_registry(self, reset_config):
        """The real registry should have Resident Evil."""
        reg = load_franchise_registry()
        franchise_ids = [f.get("id") for f in reg.get("franchises", [])]
        assert "resident_evil" in franchise_ids

    def test_franchise_has_required_fields(self, reset_config):
        reg = load_franchise_registry()
        for f in reg.get("franchises", []):
            assert "id" in f, f"Franchise missing 'id': {f}"
            assert "name" in f, f"Franchise missing 'name': {f}"
            assert "category" in f, f"Franchise missing 'category': {f}"
