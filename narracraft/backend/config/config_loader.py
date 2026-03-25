"""Loads config-schema.yaml and franchise-registry.yaml at startup."""

import os
from pathlib import Path
from typing import Any

import yaml


_config: dict[str, Any] | None = None
_franchise_registry: dict[str, Any] | None = None


def _resolve_path(env_var: str, default: str) -> Path:
    return Path(os.environ.get(env_var, default))


def load_config() -> dict[str, Any]:
    """Load the main configuration from config-schema.yaml."""
    global _config
    if _config is not None:
        return _config

    config_path = _resolve_path("CONFIG_PATH", "data/config-schema.yaml")
    if not config_path.exists():
        # Return sensible defaults when config file is not yet copied
        _config = _default_config()
        return _config

    with open(config_path, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f)
    return _config


def load_franchise_registry() -> dict[str, Any]:
    """Load the franchise registry from franchise-registry.yaml."""
    global _franchise_registry
    if _franchise_registry is not None:
        return _franchise_registry

    registry_path = _resolve_path(
        "FRANCHISE_REGISTRY_PATH", "data/franchise-registry.yaml"
    )
    if not registry_path.exists():
        _franchise_registry = {"registry": {}, "franchises": []}
        return _franchise_registry

    with open(registry_path, "r", encoding="utf-8") as f:
        _franchise_registry = yaml.safe_load(f)
    return _franchise_registry


def get_config() -> dict[str, Any]:
    """Return cached config, loading if needed."""
    if _config is None:
        return load_config()
    return _config


def get_franchise_registry() -> dict[str, Any]:
    """Return cached franchise registry, loading if needed."""
    if _franchise_registry is None:
        return load_franchise_registry()
    return _franchise_registry


def reload_config() -> dict[str, Any]:
    """Force-reload config from disk."""
    global _config
    _config = None
    return load_config()


def reload_franchise_registry() -> dict[str, Any]:
    """Force-reload franchise registry from disk."""
    global _franchise_registry
    _franchise_registry = None
    return load_franchise_registry()


def _default_config() -> dict[str, Any]:
    """Minimal default config when YAML file is not present."""
    return {
        "channel": {
            "name": "narracraft",
            "language": "en",
            "voice": {"active_provider": "chatterbox"},
        },
        "pipeline": {
            "schedule": {
                "videos_per_day": 1,
                "videos_per_week": 5,
                "cooldown_hours": 6,
            },
            "retry": {"max_retries_per_module": 3},
        },
        "quality": {
            "script_compliance": {
                "similarity_threshold": 0.70,
                "similarity_lookback": 100,
            }
        },
        "storage": {"base_path": "./data"},
    }
