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
        # Le sujet est le seul texte que l'utilisateur tape. Il vit dans le
        # projet, pas dans une ligne de commande : l'exploration peut être
        # relancée six mois plus tard sans le retaper.
        project.set_valeurs(sujet=title)
        if template:
            project.set_template(template)
        return project

    @property
    def sujet(self) -> str:
        return str(self._data().get("sujet") or "")

    @property
    def piste(self) -> int | None:
        """La piste retenue dans `pistes.md`, une fois que l'utilisateur a
        choisi. C'est le seul état que produit un clic dans l'interface, et
        il est dans un fichier comme tout le reste."""
        valeur = self._data().get("piste")
        return int(valeur) if isinstance(valeur, (int, str)) and str(valeur).isdigit() else None

    @property
    def pistes(self) -> Path: return self.root / "pistes.md"

    def _data(self) -> dict:
        path = self.root / "projet.yaml"
        if not path.is_file():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    @property
    def template(self) -> str | None:
        """Which template this project was produced with.

        Recorded in the project rather than passed on the command line, so a
        re-run six months later reproduces the same thing — the project stays
        self-describing, like every other piece of its state.
        """
        return self._data().get("template")

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
        return self._data().get("reglages") or {}

    def set_valeurs(self, **champs) -> None:
        """Écrit des champs dans `projet.yaml`, en gardant le reste."""
        path = self.root / "projet.yaml"
        data = self._data()
        data.update(champs)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def set_template(self, name: str) -> None:
        self.set_valeurs(template=name)

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
