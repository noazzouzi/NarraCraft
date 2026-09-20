"""Source archive footage, and make it affordable through reuse.

A Library of Congress item is a whole film — measured, 1038 MB for
twenty-seven minutes — while a shot needs seven seconds of it. Downloading
one film per shot would cost gigabytes for a fifteen-minute documentary.

So a film is fetched once, stored under a hash of its URL, and several shots
point into it at different in-points. One download, three shots. That single
decision is what makes real footage usable at all here.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import requests

from . import config
from .shots import Shot
from .sources import loc, pexels
from .sources.loc import Clip

Reporter = Callable[[str], None]

RUSHES_DIR = "05-visuals/rushes"


class RushError(RuntimeError):
    pass


@dataclass
class Rush:
    """A downloaded film, and what it cost."""
    clip: Clip
    chemin: str          # relative to the project root
    octets: int


def _cle(clip: Clip) -> str:
    return hashlib.sha256(clip.file_url.encode()).hexdigest()[:16]


def _variantes(requete: str) -> list[str]:
    """Same lesson as Commons: the search combines terms, so a precise query
    is the one most likely to return nothing. Shorten from the tail."""
    termes = requete.split()
    essais = [requete]
    for n in (3, 2):
        court = " ".join(termes[:n])
        if court and court not in essais:
            essais.append(court)
    return essais


def _plafonds() -> tuple[float, int, float]:
    return (
        float(config.get("video", "duree_max_s", default=900)),
        int(float(config.get("video", "taille_max_mo", default=400)) * 1_000_000),
        float(config.get("video", "saut_debut_pct", default=10)) / 100.0,
    )


def chercher(requete: str, session: requests.Session | None = None):
    """Cherche du métrage, fonds par fonds, dans l'ordre du template.

    L'ordre est un réglage parce que c'est une question de genre. Un sujet
    d'histoire ancienne veut d'abord l'archive ; un sujet contemporain veut
    d'abord du métrage net. Le premier fonds qui répond gagne.
    """
    duree_max, _, _ = _plafonds()
    http = session or requests.Session()
    fonds = config.get("visuels", "sources_video",
                       default=["pexels", "loc"]) or []

    dernier = None
    for nom in fonds:
        for essai in _variantes(requete):
            dernier = _chercher_dans(nom, essai, duree_max, http)
            if dernier and dernier.clips:
                return dernier
    return dernier or loc.Resultat(clips=[])


def _chercher_dans(fonds: str, requete: str, duree_max: float,
                   http: requests.Session):
    if fonds == "pexels":
        try:
            return pexels.search(requete, limit=5, max_duree_s=duree_max,
                                 session=http)
        except pexels.PexelsError:
            # Clé absente ou refusée : ce fonds est optionnel, on passe au
            # suivant plutôt que de faire tomber tout le sourcing.
            return None
    if fonds == "loc":
        collections = config.get(
            "visuels", "collections_domaine_public", "loc_video", default=[]
        )
        if not collections:
            # LOC n'expose pas de licence par item : le statut vient de la
            # collection. Sans whitelist, on ne peut rien affirmer, donc on
            # ne prend rien.
            return None
        return loc.search(requete, collections=collections, limit=5,
                          max_duree_s=duree_max, session=http)
    raise RushError(f"Fonds vidéo inconnu : {fonds!r} (pexels, loc).")


def obtenir(
    clip: Clip,
    project_root: Path,
    cache: dict[str, Rush],
    report: Reporter | None = None,
) -> Rush:
    """Download a film once; hand back the cached one on every later shot."""
    say = report or (lambda _: None)
    cle = _cle(clip)
    if cle in cache:
        return cache[cle]

    _, taille_max, _ = _plafonds()
    dossier = project_root / RUSHES_DIR
    dossier.mkdir(parents=True, exist_ok=True)
    destination = dossier / f"{cle}.mp4"

    if destination.is_file():
        rush = Rush(clip, f"{RUSHES_DIR}/{cle}.mp4", destination.stat().st_size)
        cache[cle] = rush
        return rush

    say(f"    ↓ {clip.title[:44]} — {clip.duree_s:.0f}s [{clip.provider}]")
    if clip.provider == "pexels":
        pexels.download(clip, destination, max_octets=taille_max)
    else:
        loc.download(clip, destination, max_octets=taille_max)
    rush = Rush(clip, f"{RUSHES_DIR}/{cle}.mp4", destination.stat().st_size)
    cache[cle] = rush
    return rush


def fetch_videos(
    shots: list[Shot],
    project_root: Path,
    fenetres_s: dict[str, float],
    report: Reporter | None = None,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Source every `video` shot. `fenetres_s` gives each shot's screen time,
    which decides how far into the film we can start."""
    say = report or (lambda _: None)
    http = requests.Session()
    cache: dict[str, Rush] = {}
    usages: dict[str, int] = {}
    assets: dict[str, dict[str, Any]] = {}
    manquants: list[str] = []

    for shot in shots:
        if shot.type != "video":
            continue
        try:
            resultat = chercher(shot.requete, session=http)
            clips = resultat.clips
        except (requests.RequestException, ValueError, RushError) as error:
            say(f"  ! {shot.id} : recherche vidéo impossible — {str(error)[:90]}")
            manquants.append(shot.id)
            continue

        if not clips:
            if resultat.trop_longs:
                duree_max, _, _ = _plafonds()
                say(f"  · {shot.id} : {resultat.trop_longs} film(s) trouvé(s) "
                    f"pour « {shot.requete} », tous au-dessus de "
                    f"{duree_max:.0f}s — reformuler vers un sujet plus court")
            else:
                say(f"  · {shot.id} : aucun métrage pour « {shot.requete} »")
            manquants.append(shot.id)
            continue

        fenetre = fenetres_s.get(shot.id, 8.0)
        choisi = next((c for c in clips if c.duree_s > fenetre + 2), clips[0])

        try:
            rush = obtenir(choisi, project_root, cache, report=say)
        except (requests.RequestException, ValueError, OSError) as error:
            say(f"  ! {shot.id} : {str(error)[:100]}")
            manquants.append(shot.id)
            continue

        rang = usages.get(rush.chemin, 0)
        usages[rush.chemin] = rang + 1
        _, _, saut = _plafonds()
        depart = loc.point_de_depart(choisi.duree_s, fenetre, rang, saut)
        reutilise = " (rush réutilisé)" if rang else ""
        say(f"  ✓ {shot.id} : {choisi.title[:40]} · départ {depart:.0f}s{reutilise}")

        assets[shot.id] = {
            "fichier": rush.chemin,
            "shot": shot.id,
            "beat": shot.beat,
            "media": "video",
            "source": choisi.provider,
            "titre": choisi.title,
            "licence": choisi.licence,
            "url": choisi.page_url,
            "credit": choisi.credit(),
            "largeur": choisi.width,
            "hauteur": choisi.height,
            "duree_source_s": choisi.duree_s,
            "depart_s": round(depart, 2),
            "octets": rush.octets,
            "requete": shot.requete,
            # Archive ou banque contemporaine ? Le code ne sait pas de quelle
            # époque parle un beat, donc il ne tranche pas — il marque, et
            # `review.html` le montre au checkpoint. Sans ça, un plan tourné
            # cette année passerait pour de l'archive sans que personne ne
            # l'ait décidé, ce que le template interdit nommément.
            "nature": choisi.collection,
        }

    if cache:
        total = sum(r.octets for r in cache.values())
        say(f"  {len(cache)} rush(es) · {total / 1e6:.0f} Mo pour "
            f"{len(assets)} plan(s)")
    return assets, manquants
