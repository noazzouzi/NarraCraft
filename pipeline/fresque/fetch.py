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
import os
from pathlib import Path
from typing import Any, Callable

import requests

from .shots import Shot
from .sources import openverse, wikimedia
from .sources.base import Candidate

Reporter = Callable[[str], None]

#: Wikimedia first: it serves cached renderings at the width we ask for.
#: Openverse second, and only as a fallback — it indexes renditions rather
#: than originals and tops out around 1024px (see its module docstring), so a
#: shot it covers is a shot we would otherwise have had to pay to generate.
CASCADE = ("wikimedia_commons", "openverse")

#: Below this, a source image upscaled into a 1080p frame is visibly soft,
#: and the Ken Burns zoom makes it worse.
WIDTH_TARGET = 1920
WIDTH_FALLBACK = 900


class FetchError(RuntimeError):
    pass


def _extension(candidate: Candidate) -> str:
    return {
        "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
        "image/tiff": ".jpg", "image/webp": ".webp",
    }.get(candidate.mime, ".jpg")


def real_size(path: Path) -> tuple[int, int]:
    """Measure the file we actually got.

    Providers describe the original they hold, not the rendition they serve:
    Rawpixel announces 6999px and returns a 1024px `editor_1024`, Flickr
    announces 1024 and answers 410 for anything larger. Metadata is a
    promise, the file on disk is the fact.
    """
    from PIL import Image

    with Image.open(path) as image:
        return image.size


def _record(shot: Shot, candidate: Candidate, filename: str,
            alternatives: list[Candidate], used_query: str = "",
            used_width: int = 0, real: tuple[int, int] | None = None) -> dict[str, Any]:
    width, height = real or (candidate.width, candidate.height)
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
        # Measured on the downloaded file, not taken from the provider.
        "largeur": width,
        "hauteur": height,
        "largeur_annoncee": candidate.width,
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


def _search_wikimedia(query: str, session) -> tuple[list[Candidate], str, int]:
    return wikimedia.search_relaxed(
        query, limit=6, min_width=WIDTH_TARGET, session=session
    )


def _search_openverse(query: str, session) -> tuple[list[Candidate], str, int]:
    found = openverse.search(
        query, limit=6, min_width=WIDTH_FALLBACK, session=session,
        token=os.environ.get("OPENVERSE_TOKEN"),
    )
    return found, query, WIDTH_FALLBACK


PROVIDERS = {
    "wikimedia_commons": (_search_wikimedia, wikimedia.download),
    "openverse": (_search_openverse, openverse.download),
}


def fetch_archives(
    shots: list[Shot],
    visuals_dir: Path,
    report: Reporter | None = None,
    dry_run: bool = False,
    cascade: tuple[str, ...] = CASCADE,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Return (assets by shot id, list of shots left unsourced)."""
    say = report or (lambda _: None)
    session = requests.Session()

    assets: dict[str, dict[str, Any]] = {}
    unsourced: list[str] = []

    for shot in shots:
        if shot.type != "archive":
            continue

        record = _source_one(shot, visuals_dir, session, cascade, say, dry_run)
        if record is None:
            unsourced.append(shot.id)
        else:
            assets[shot.id] = record

    return assets, unsourced


def _source_one(shot, visuals_dir, session, cascade, say, dry_run):
    """Walk the cascade until one provider yields a usable file."""
    for provider in cascade:
        search, download = PROVIDERS[provider]
        try:
            candidates, used_query, used_width = search(shot.requete, session)
        except (requests.RequestException, ValueError) as error:
            say(f"  ! {shot.id} : {provider} indisponible — {str(error)[:90]}")
            continue

        if not candidates:
            continue

        best = candidates[0]
        filename = f"{shot.id}{_extension(best)}"
        note = " (requête élargie)" if used_query != shot.requete else ""
        origin = "" if provider == "wikimedia_commons" else f" via {provider}"

        if dry_run:
            say(f"  ✓ {shot.id} : {best.title[:48]} [{best.licence}]{note}{origin}")
            return _record(shot, best, filename, candidates[1:], used_query, used_width)

        destination = visuals_dir / filename
        visuals_dir.mkdir(parents=True, exist_ok=True)
        try:
            download(best, destination)
            real = real_size(destination)
        except (requests.RequestException, OSError) as error:
            # One unavailable file must not cost the whole run: the other
            # shots are independent, and a re-run picks this one back up.
            say(f"  ! {shot.id} : téléchargement {provider} échoué — {str(error)[:70]}")
            destination.unlink(missing_ok=True)
            continue

        gap = ""
        if real[0] < best.width:
            gap = f" (annoncé {best.width}px, servi {real[0]}px)"
        say(f"  ✓ {shot.id} : {best.title[:44]} [{best.licence}]{note}{origin}{gap}")
        return _record(shot, best, filename, candidates[1:], used_query,
                       used_width, real=real)

    say(f"  · {shot.id} : rien de libre pour « {shot.requete} »")
    return None


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
