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

# Réglages propres à un projet, lus dans son `projet.yaml`. Ils s'appliquent
# par-dessus le template, qui s'applique lui-même par-dessus la base.
#
# C'est ce qui permet de tester un montage sur deux minutes sans toucher au
# template : la durée cible est un réglage du projet, pas du genre. Sans ce
# niveau, raccourcir une vidéo d'essai reviendrait à modifier le template et
# à le remettre en place après — donc à oublier de le remettre en place.
_project_overrides: dict[str, Any] = {}


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


def use_project_overrides(reglages: dict[str, Any] | None) -> None:
    """Apply a project's own settings on top of its template."""
    global _project_overrides
    reglages = reglages or {}
    if reglages != _project_overrides:
        _project_overrides = reglages
        load.cache_clear()


def project_overrides() -> dict[str, Any]:
    return _project_overrides


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

    if _active_template:
        path = root / TEMPLATES_DIR / f"{_active_template}.yaml"
        with path.open(encoding="utf-8") as fh:
            base = _merge(base, yaml.safe_load(fh) or {})

    # Le projet a le dernier mot : c'est le seul niveau qui connaisse la
    # vidéo qu'on est en train de faire.
    return _merge(base, _project_overrides) if _project_overrides else base


def get(*keys: str, default: Any = None) -> Any:
    """Nested lookup: get("narration", "mots_par_minute")."""
    node: Any = load()
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node
