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


TEMPLATES_DIR = "templates"

# The active template is process-wide state, set once when a command starts.
# A CLI run handles exactly one project, so threading a config object through
# every function would be ceremony for no gain — but it does mean a library
# caller must call `use_template()` itself.
_active_template: str | None = None


class TemplateError(ValueError):
    pass


def available_templates() -> list[str]:
    directory = repo_root() / TEMPLATES_DIR
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.yaml"))


def use_template(name: str | None) -> None:
    """Select the template whose values overlay the base configuration."""
    global _active_template
    if name and name not in available_templates():
        known = ", ".join(available_templates()) or "aucun"
        raise TemplateError(f"Template inconnu : {name!r} (connus : {known})")
    if name != _active_template:
        _active_template = name
        load.cache_clear()


def active_template() -> str | None:
    return _active_template


def _merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursive for mappings, replacement for everything else.

    A template that redefines `sources_archives` means to replace the order,
    not to append to it — so lists replace rather than merge.
    """
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


@functools.lru_cache(maxsize=1)
def load() -> dict[str, Any]:
    root = repo_root()
    with (root / CONFIG_NAME).open(encoding="utf-8") as fh:
        base = yaml.safe_load(fh)

    if not _active_template:
        return base

    path = root / TEMPLATES_DIR / f"{_active_template}.yaml"
    with path.open(encoding="utf-8") as fh:
        overlay = yaml.safe_load(fh) or {}
    return _merge(base, overlay)


def get(*keys: str, default: Any = None) -> Any:
    """Nested lookup: get("narration", "mots_par_minute")."""
    node: Any = load()
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node
