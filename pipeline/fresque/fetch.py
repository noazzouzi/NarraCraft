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

from . import config
from .shots import SOURCEES, Shot
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


#: Deep enough that one query can serve several shots once the files already
#: taken are removed. A documentary comes back to the same courthouse, and at
#: fifteen shots a minute it comes back often.
PROFONDEUR = 14


def _search_wikimedia(query: str, session) -> tuple[list[Candidate], str, int]:
    return wikimedia.search_relaxed(
        query, limit=PROFONDEUR, min_width=WIDTH_TARGET, session=session
    )


def _search_openverse(query: str, session) -> tuple[list[Candidate], str, int]:
    found = openverse.search(
        query, limit=PROFONDEUR, min_width=WIDTH_FALLBACK, session=session,
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
    deja: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Return (assets by shot id, list of shots left unsourced).

    `deja` holds what a previous run already sourced. Those shots are skipped
    whole: at roughly a second per request and several attempts per shot, a
    re-run to fix a handful of queries would otherwise re-fetch everything.
    """
    say = report or (lambda _: None)
    session = requests.Session()
    deja = deja or {}

    assets: dict[str, dict[str, Any]] = {}
    unsourced: list[str] = []
    repris = 0

    ecart = int(config.get("visuels", "reutilisation", "ecart_min_plans", default=25))
    # What has already been seen on screen, and where. A file may come back —
    # a documentary returns to the same courthouse, and the free archives on a
    # given subject are finite — but never close to itself. See `_eligibles`.
    histoire: dict[str, dict[str, Any]] = {}
    for identifiant, record in deja.items():
        url = record.get("url")
        if url:
            histoire[url] = {"position": -10**6, "beat": record.get("beat"),
                             "record": record}

    # Searches are deduplicated within a run: shots sharing a query hit the
    # API once. At a hundred and fifty archive shots this is the difference
    # between a three-minute run and a ten-minute one.
    cache: dict[tuple[str, str], tuple[list[Candidate], str, int]] = {}

    position = 0
    for shot in shots:
        if shot.type not in SOURCEES:
            # A motion panel or a generated still still occupies the screen,
            # so it counts towards the distance between two reuses.
            position += 1
            continue

        acquis = deja.get(shot.id)
        if acquis and (visuals_dir.parent / acquis.get("fichier", "")).is_file() \
                and acquis.get("requete") == shot.requete:
            repris += 1
            if acquis.get("url"):
                histoire[acquis["url"]] = {
                    "position": position, "beat": shot.beat, "record": acquis,
                }
            position += 1
            continue

        record = _source_one(shot, visuals_dir, session, cascade, say, dry_run,
                             histoire, cache, position, ecart)
        if record is None:
            unsourced.append(shot.id)
        else:
            assets[shot.id] = record
            if record.get("url"):
                histoire[record["url"]] = {
                    "position": position, "beat": shot.beat, "record": record,
                }
        position += 1

    if repris:
        say(f"  {repris} plan(s) déjà sourcés, conservés")
    return assets, unsourced


def _eligibles(candidates, histoire, position, ecart, beat):
    """Split candidates into never-seen, reusable, and too-close.

    A file already on screen is not disqualified for ever — on a subject
    whose free archives number in the dozens, that would leave a third of the
    montage blank. It is disqualified for a while: not in the same beat, and
    not within `ecart` shots of its last appearance. Far enough apart, and
    with a different camera move, the same photograph reads as a return
    rather than as a repeat.
    """
    neufs, reutilisables = [], []
    for candidate in candidates:
        vu = histoire.get(candidate.page_url)
        if vu is None:
            neufs.append(candidate)
        elif vu["beat"] != beat and position - vu["position"] >= ecart:
            reutilisables.append((position - vu["position"], candidate))
    # Never-seen first; failing that, whatever has been off screen longest.
    reutilisables.sort(key=lambda pair: -pair[0])
    return neufs, [candidate for _, candidate in reutilisables]


def _source_one(shot, visuals_dir, session, cascade, say, dry_run,
                histoire=None, cache=None, position=0, ecart=25):
    """Walk the cascade until one provider yields a usable file."""
    histoire = histoire if histoire is not None else {}
    cache = cache if cache is not None else {}

    for provider in cascade:
        search, download = PROVIDERS[provider]
        cle = (provider, shot.requete)
        try:
            if cle not in cache:
                cache[cle] = search(shot.requete, session)
            candidates, used_query, used_width = cache[cle]
        except (requests.RequestException, ValueError) as error:
            say(f"  ! {shot.id} : {provider} indisponible — {str(error)[:90]}")
            continue

        neufs, reutilisables = _eligibles(
            candidates, histoire, position, ecart, shot.beat
        )
        if not neufs and reutilisables:
            # Nothing new under this query. Bring back the file that has been
            # off screen longest, pointing at the copy already on disk — a
            # second download of the same bytes would be pure waste, and the
            # camera move on this shot differs anyway.
            repris = reutilisables[0]
            ancien = histoire[repris.page_url]["record"]
            record = dict(ancien)
            record.update({
                "shot": shot.id, "beat": shot.beat, "requete": shot.requete,
                "requete_effective": used_query or shot.requete,
                "reutilise_de": ancien.get("shot"),
            })
            say(f"  ↺ {shot.id} : {repris.title[:44]} — revu depuis "
                f"{ancien.get('shot')}")
            return record

        candidates = neufs
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
