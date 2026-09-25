"""Pexels — du métrage contemporain, libre et utilisable.

`rushes.py` sait depuis longtemps télécharger un film une fois et y pointer
plusieurs plans. Ce qui lui manquait, c'était une source exploitable : le
seul fonds branché était la Library of Congress, et ce qu'il a rendu sur un
sujet judiciaire français — un bagne américain des années 1900, un film
d'exécution de 1901 — était inutilisable. Tous les plans `video` ont fini
par être supprimés du premier documentaire.

CE QUE PEXELS EST, ET CE QU'IL N'EST PAS
========================================
C'est de la **banque d'images contemporaine**, pas de l'archive. La
distinction n'est pas une nuance de vocabulaire, c'est la règle numéro un
du template documentaire :

> Interdits : la reconstitution déguisée en archive.

Un plan de palais de justice filmé cette année est parfaitement légitime
quand le récit parle d'aujourd'hui, ou quand l'intention est « le lieu, tel
qu'il est » — c'est exactement ce que Frontier étiquette « Sarajevo ·
today ». Le même plan posé sous une narration qui raconte 2007 est un
mensonge visuel.

Le code ne peut pas trancher ça : il ne sait pas de quelle époque parle un
beat. Il fait donc la seule chose honnête — il **marque** chaque plan venu
d'ici comme contemporain, dans `assets.json`, et `review.html` le montre au
checkpoint. La décision reste humaine, mais elle n'est plus implicite.

LA LICENCE
==========
La licence Pexels autorise l'usage commercial et la modification, sans
attribution obligatoire. Elle remplit donc les deux critères que
`base.is_free_licence` vérifie, mais elle n'est pas une licence Creative
Commons et n'en porte aucun des mots-clés : elle est donc déclarée
explicitement plutôt que devinée.

On crédite quand même l'auteur dans `assets.json`. L'attribution n'est pas
due, mais elle ne coûte rien et un fichier de licences qui dit d'où vient
chaque image vaut mieux qu'un fichier à trous.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests

from .base import (Candidate, Throttle, expects_json, is_retryable,
                   retry_delay)
from .loc import Clip, Resultat

BASE = "https://api.pexels.com"

#: Pexels annonce 200 requêtes par heure. Une toutes les 0,4 s laisse une
#: marge confortable et ne ralentit pas un sourcing réel.
MIN_INTERVAL_S = 0.4
_throttle = Throttle(MIN_INTERVAL_S)

#: Au-delà, on télécharge une minute de film pour en garder sept secondes.
MAX_DUREE_S = 90
MAX_OCTETS = 120_000_000

#: Déclarée en toutes lettres : la licence Pexels autorise l'usage
#: commercial et la modification, mais n'est pas une licence CC et ne
#: passerait aucun test par mot-clé.
LICENCE = "Pexels License"
LICENCE_URL = "https://www.pexels.com/license/"

#: Ce qu'on refuse de se laisser prendre pour de l'archive.
NATURE = "stock contemporain"


class PexelsError(RuntimeError):
    pass


def api_key() -> str:
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        raise PexelsError(
            "PEXELS_API_KEY absente.\n"
            "  · la clé est gratuite : https://www.pexels.com/api/\n"
            "  · la mettre dans .env"
        )
    return key


@dataclass(frozen=True)
class Fichier:
    url: str
    width: int
    height: int
    octets: int


def _get(http: requests.Session, chemin: str, params: dict[str, Any],
         timeout: float) -> requests.Response:
    for tentative in range(3):
        _throttle.wait()
        response = http.get(
            f"{BASE}{chemin}", params=params, timeout=timeout,
            headers={"Authorization": api_key(),
                     "User-Agent": "fresque/1.0 (documentaire, local)"},
        )
        if is_retryable(response.status_code) and tentative < 2:
            import time
            time.sleep(retry_delay(response, tentative, MIN_INTERVAL_S))
            continue
        if response.status_code == 401:
            raise PexelsError("PEXELS_API_KEY refusée (HTTP 401).")
        response.raise_for_status()
        expects_json(response)
        return response
    raise PexelsError(f"Pexels : {chemin} inaccessible après trois essais.")


def _meilleur_fichier(video: dict[str, Any], largeur_min: int) -> Fichier | None:
    """Le plus petit fichier qui atteint encore la largeur voulue.

    Prendre systématiquement la version 4K ferait payer en disque et en
    temps de rendu une définition que le montage réduit aussitôt.
    """
    candidats = [
        Fichier(url=f.get("link", ""), width=int(f.get("width") or 0),
                height=int(f.get("height") or 0), octets=int(f.get("size") or 0))
        for f in video.get("video_files", [])
        if (f.get("file_type") or "").endswith("mp4")
    ]
    assez = [f for f in candidats if f.width >= largeur_min and f.url]
    if not assez:
        return None
    return min(assez, key=lambda f: (f.width, f.octets))


def _titre(video: dict[str, Any], defaut: str) -> str:
    """Un titre lisible.

    Pexels ne renvoie pas de titre : le champ `alt` est nul sur toutes les
    vidéos essayées. Mais l'URL de la page porte un slug descriptif —
    `.../video/aerial-view-of-central-paris-skyline-38835028/` — et c'est
    la seule chose qui distingue deux plans dans `review.html`. Renvoyer la
    requête à la place donnerait dix lignes identiques.
    """
    url = (video.get("url") or "").rstrip("/")
    slug = url.rsplit("/", 1)[-1] if url else ""
    # `"".split("-")` rend `[""]`, qui est une liste non vide : sans le test
    # sur `m`, une vidéo sans URL recevait un titre vide plutôt que le défaut.
    mots = [m for m in slug.split("-") if m and not m.isdigit()]
    return " ".join(mots).capitalize() if mots else defaut


def search(query: str, limit: int = 5, largeur_min: int = 1920,
           max_duree_s: float = MAX_DUREE_S,
           session: requests.Session | None = None,
           timeout: float = 45.0) -> Resultat:
    """Cherche du métrage paysage, et dit ce qu'il a écarté.

    Le `Resultat` est celui de `loc` : `rushes.py` ne doit pas savoir de
    quel fonds vient un plan, seulement qu'il en a un.

    PAS DE FILTRE DE PERTINENCE, ET C'EST MESURÉ
    --------------------------------------------
    Le filtre de Wikimedia exige que tous les mots de la requête se
    retrouvent dans le titre. Appliqué ici, il jetterait les bons résultats
    avec les mauvais — relevé sur « prison wall razor wire » :

        0/4  Empty jail                                  <- excellent
        0/4  An inmate putting his hands on a metal gate  <- excellent
        0/4  Close up shot of barbed fence                <- excellent
        0/4  A stormy weather                             <- hors sujet

    La différence tient à la nature du titre. Sur Wikimedia c'est une notice
    de catalogue, qui nomme le sujet ; ici c'est la description d'une scène
    écrite par un contributeur, et elle ne reprend pas les mots de la
    recherche. Le signal est donc trop faible pour trancher, et une règle qui
    se trompe dans les deux sens vaut moins que pas de règle.

    On garde donc le classement de Pexels, qui est sémantique — c'est lui qui
    sort « Empty jail » sur « prison wall ». L'écart entre l'intention et ce
    qui a été trouvé reste visible là où il doit l'être : dans `review.html`,
    au checkpoint, devant un humain.
    """
    http = session or requests.Session()
    response = _get(http, "/videos/search", {
        "query": query, "per_page": min(max(limit * 3, 10), 80),
        "orientation": "landscape",
    }, timeout)

    charge = response.json()
    clips: list[Clip] = []
    vus = 0
    trop_longs = 0

    for video in charge.get("videos", []) or []:
        vus += 1
        duree = float(video.get("duration") or 0)
        if duree <= 0 or duree > max_duree_s:
            trop_longs += 1
            continue
        fichier = _meilleur_fichier(video, largeur_min)
        if fichier is None:
            continue

        clips.append(Clip(
            provider="pexels",
            title=_titre(video, query),
            page_url=video.get("url", ""),
            file_url=fichier.url,
            licence=LICENCE,
            duree_s=duree,
            width=fichier.width,
            height=fichier.height,
            collection=NATURE,
            date=str(video.get("id", "")),
            author=(video.get("user") or {}).get("name", ""),
        ))
        if len(clips) >= limit:
            break

    return Resultat(clips=clips, vus=vus, trop_longs=trop_longs)


def taille(clip: Clip, session: requests.Session | None = None) -> int:
    """Le poids du fichier, demandé avant de le télécharger."""
    http = session or requests.Session()
    try:
        tete = http.head(clip.file_url, timeout=30, allow_redirects=True)
        return int(tete.headers.get("Content-Length") or 0)
    except requests.RequestException:
        return 0


def download(clip: Clip, destination, timeout: float = 300.0,
             max_octets: int = MAX_OCTETS,
             session: requests.Session | None = None) -> None:
    """Télécharge le métrage, en refusant ce qui est trop gros avant d'y
    passer du temps."""
    poids = taille(clip, session)
    if poids and poids > max_octets:
        raise PexelsError(
            f"{poids / 1e6:.0f} Mo pour {clip.duree_s:.0f} s — au-dessus du "
            f"plafond de {max_octets / 1e6:.0f} Mo."
        )
    http = session or requests.Session()
    from pathlib import Path

    chemin = Path(destination)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with http.get(clip.file_url, stream=True, timeout=timeout) as flux:
        flux.raise_for_status()
        ecrits = 0
        with chemin.open("wb") as sortie:
            for morceau in flux.iter_content(chunk_size=1 << 20):
                ecrits += len(morceau)
                if ecrits > max_octets:
                    sortie.close()
                    chemin.unlink(missing_ok=True)
                    raise PexelsError(
                        f"téléchargement interrompu au-delà de "
                        f"{max_octets / 1e6:.0f} Mo — le serveur n'avait pas "
                        "annoncé la taille."
                    )
                sortie.write(morceau)


# --- Images fixes ------------------------------------------------------------
#
# Pexels n'était branché que sur la vidéo. Son fonds d'images est pourtant
# le plus utile là où les archives libres s'épuisent : le contemporain.
# Mesuré sur un film réel, trois plans sont restés sans visuel faute de
# photographie moderne dans Wikimedia — un comptoir de restaurant, une
# salle vide, un client qui paie. Ce fonds les couvre.
#
# Ce n'est pas de l'archive et ça ne doit jamais en tenir lieu : `NATURE`
# le dit, et le plan visuel le sait (« une banque d'images contemporaine
# sert le présent, jamais le passé »).

def search_photos(query: str, limit: int = 5, min_width: int = 1920,
                  session: requests.Session | None = None,
                  timeout: float = 45.0) -> list[Candidate]:
    """Cherche des photographies paysage assez grandes pour du 1080p.

    Pas de filtre de pertinence sur le titre, pour la raison mesurée plus
    haut sur la vidéo : les descriptions de Pexels sont écrites par des
    contributeurs et ne reprennent pas les mots de la recherche. Le
    classement de Pexels est sémantique, il vaut mieux que le nôtre.
    """
    http = session or requests.Session()
    response = _get(http, "/v1/search", {
        "query": query, "per_page": min(max(limit * 3, 15), 80),
        "orientation": "landscape",
    }, timeout)

    trouves: list[Candidate] = []
    for photo in response.json().get("photos", []) or []:
        sources = photo.get("src") or {}
        # `original` est la pleine résolution ; les autres sont des
        # rendus. On prend l'original et on mesure le fichier obtenu
        # plus tard, comme pour tous les fonds.
        url = sources.get("original") or sources.get("large2x")
        largeur = int(photo.get("width") or 0)
        if not url or largeur < min_width:
            continue
        trouves.append(Candidate(
            provider="pexels",
            title=(photo.get("alt") or "").strip() or query,
            page_url=photo.get("url", ""),
            file_url=url,
            licence=LICENCE,
            licence_url=LICENCE_URL,
            author=(photo.get("photographer") or "").strip(),
            width=largeur,
            height=int(photo.get("height") or 0),
            mime="image/jpeg",
            extra={"nature": NATURE},
        ))
        if len(trouves) >= limit:
            break
    return trouves


def download_photo(candidate: Candidate, destination,
                   session: requests.Session | None = None,
                   timeout: float = 60.0) -> None:
    from pathlib import Path

    http = session or requests.Session()
    chemin = Path(destination)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with http.get(candidate.file_url, stream=True, timeout=timeout) as flux:
        flux.raise_for_status()
        with chemin.open("wb") as sortie:
            for morceau in flux.iter_content(chunk_size=1 << 20):
                sortie.write(morceau)
