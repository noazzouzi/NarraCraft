"""Source the visuals listed in 03-shots.json.

Archive first: a real photograph beats a generated illustration on a
historical subject, and it costs nothing. Only what the archives cannot
provide goes to image generation.

Every asset carries its licence. A candidate whose licence cannot be read as
free is refused rather than assumed — a monetised channel cannot afford an
optimistic reading.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import requests

from . import config
from .shots import Shot
from .sources import wikimedia
from .sources.base import Candidate

Reporter = Callable[[str], None]


class FetchError(RuntimeError):
    pass


def _extension(candidate: Candidate) -> str:
    return {
        "image/jpeg": ".jpg", "image/png": ".png",
        "image/tiff": ".jpg", "image/webp": ".webp",
    }.get(candidate.mime, ".jpg")


def _record(shot: Shot, candidate: Candidate, filename: str,
            alternatives: list[Candidate], used_query: str = "",
            used_width: int = 0) -> dict[str, Any]:
    return {
        "fichier": f"05-visuals/{filename}",
        "shot": shot.id,
        "beat": shot.beat,
        "source": candidate.provider,
        "titre": candidate.title,
        "auteur": candidate.author,
        "licence": candidate.licence,
        "licence_url": candidate.licence_url,
        "url": candidate.page_url,
        "credit": candidate.credit(),
        "largeur": candidate.width,
        "hauteur": candidate.height,
        "requete": shot.requete,
        # When the search had to be widened, say so: a relaxed query can match
        # something only loosely related, and a human reviewing the assets
        # needs to know which picks deserve a second look.
        "requete_effective": used_query or shot.requete,
        "requete_relachee": bool(used_query) and used_query != shot.requete,
        "largeur_min_utilisee": used_width,
        # Kept so a human can swap a bad pick without searching again.
        "alternatives": [
            {"titre": c.title, "url": c.page_url, "licence": c.licence}
            for c in alternatives[:4]
        ],
    }


def fetch_archives(
    shots: list[Shot],
    visuals_dir: Path,
    report: Reporter | None = None,
    dry_run: bool = False,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Return (assets by shot id, list of shots left unsourced)."""
    say = report or (lambda _: None)
    min_width = 1920   # cascade descendante gérée par search_relaxed
    session = requests.Session()

    assets: dict[str, dict[str, Any]] = {}
    unsourced: list[str] = []

    for shot in shots:
        if shot.type != "archive":
            continue
        try:
            candidates, used_query, used_width = wikimedia.search_relaxed(
                shot.requete, limit=6, min_width=min_width, session=session
            )
        except requests.RequestException as error:
            raise FetchError(
                f"{shot.id} : la recherche d'archive a échoué — {error}\n"
                "Si l'hôte est bloqué par une politique réseau, le sourcing "
                "doit tourner depuis une machine qui y a accès."
            ) from error

        if not candidates:
            say(f"  · {shot.id} : rien de libre pour « {shot.requete} »")
            unsourced.append(shot.id)
            continue

        best = candidates[0]
        filename = f"{shot.id}{_extension(best)}"
        relaxed = " (requête élargie)" if used_query != shot.requete else ""
        say(f"  ✓ {shot.id} : {best.title[:52]} [{best.licence}]{relaxed}")

        if not dry_run:
            visuals_dir.mkdir(parents=True, exist_ok=True)
            try:
                wikimedia.download(best, visuals_dir / filename)
            except requests.RequestException as error:
                # One unavailable file must not cost the whole run: the other
                # shots are independent, and a re-run picks this one back up.
                say(f"  ✗ {shot.id} : téléchargement échoué — {error}")
                (visuals_dir / filename).unlink(missing_ok=True)
                unsourced.append(shot.id)
                continue

        assets[shot.id] = _record(
            shot, best, filename, candidates[1:], used_query, used_width
        )

    return assets, unsourced


def write_assets(assets: dict[str, dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"assets": assets}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def merge_assets(path: Path, new: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Keep what is already sourced; a re-run must not undo a manual fix."""
    existing: dict[str, dict[str, Any]] = {}
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8")).get("assets", {})
    merged = dict(existing)
    merged.update(new)
    return merged
