"""Project paths. A project is a directory of files, nothing more."""
from __future__ import annotations

import unicodedata
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import config


def slugify(text: str) -> str:
    """kebab-case, ASCII only — see CLAUDE.md conventions."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
    return re.sub(r"-{2,}", "-", slug)


@dataclass(frozen=True)
class Project:
    slug: str
    root: Path

    @classmethod
    def open(cls, slug: str) -> "Project":
        root = config.repo_root() / "projects" / slug
        if not root.is_dir():
            raise FileNotFoundError(f"Projet introuvable : {root}")
        project = cls(slug=slug, root=root)
        # Every command reads its settings through the project's template,
        # then through the project's own overrides. The project has the last
        # word because it is the only level that knows which video this is.
        config.use_template(project.template)
        config.use_project_overrides(project.reglages)
        return project

    @classmethod
    def create(cls, title: str, template: str | None = None) -> "Project":
        slug = slugify(title)
        root = config.repo_root() / "projects" / slug
        (root / "04-audio" / "beats").mkdir(parents=True, exist_ok=True)
        (root / "05-visuals").mkdir(parents=True, exist_ok=True)
        (root / "07-out").mkdir(parents=True, exist_ok=True)
        project = cls(slug=slug, root=root)
        if template:
            project.set_template(template)
        return project

    @property
    def template(self) -> str | None:
        """Which template this project was produced with.

        Recorded in the project rather than passed on the command line, so a
        re-run six months later reproduces the same thing — the project stays
        self-describing, like every other piece of its state.
        """
        path = self.root / "projet.yaml"
        if not path.is_file():
            return None
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data.get("template")

    @property
    def reglages(self) -> dict:
        """Settings this project overrides, from its `projet.yaml`.

        The layer exists so a two-minute test montage costs one line in the
        project rather than an edit to the template — an edit one then has to
        remember to undo, and does not.

            template: documentaire-historique
            reglages:
              production:
                duree_cible_min: 2
        """
        path = self.root / "projet.yaml"
        if not path.is_file():
            return {}
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data.get("reglages") or {}

    def set_template(self, name: str) -> None:
        path = self.root / "projet.yaml"
        data = {}
        if path.is_file():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        data["template"] = name
        path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    # Numbered files are read in order; a step never reads what follows it.
    @property
    def brief(self) -> Path: return self.root / "00-brief.md"
    @property
    def research(self) -> Path: return self.root / "01-research.md"
    @property
    def script(self) -> Path: return self.root / "02-script.md"
    @property
    def shots(self) -> Path: return self.root / "03-shots.json"
    @property
    def audio_dir(self) -> Path: return self.root / "04-audio"
    @property
    def alignment(self) -> Path: return self.root / "04-audio" / "alignment.json"
    @property
    def visuals_dir(self) -> Path: return self.root / "05-visuals"
    @property
    def assets(self) -> Path: return self.root / "05-visuals" / "assets.json"
    @property
    def timeline(self) -> Path: return self.root / "06-timeline.json"
    @property
    def out_dir(self) -> Path: return self.root / "07-out"
