"""Load fresque.config.yaml. No production value is ever hardcoded."""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml

CONFIG_NAME = "fresque.config.yaml"


def repo_root(start: Path | None = None) -> Path:
    """Walk up from `start` until the config file is found."""
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / CONFIG_NAME).is_file():
            return candidate
    raise FileNotFoundError(
        f"{CONFIG_NAME} introuvable en remontant depuis {here}"
    )


@functools.lru_cache(maxsize=1)
def load() -> dict[str, Any]:
    path = repo_root() / CONFIG_NAME
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def get(*keys: str, default: Any = None) -> Any:
    """Nested lookup: get("narration", "mots_par_minute")."""
    node: Any = load()
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node
