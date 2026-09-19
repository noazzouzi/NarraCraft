"""Source a background bed from the free archives, and keep its licence.

The synthesised bed stays in `sons.py` and remains the default: it costs
nothing, needs no network and carries no licence. This module exists for
when a real recording is wanted instead — a human ear beats a sine stack,
and a template is allowed to say so.

What makes a downloaded track usable here is not that it is free to listen
to. Three things must hold at once, and a track failing any one of them is
refused rather than flagged:

1. **Commercial use allowed.** The channel is monetised.
2. **Modification allowed.** Looping, fading and levelling a track are
   modifications, so a No-Derivatives licence is out — the same reasoning
   the image sourcing already applies to a Ken Burns move.
3. **Attribution recorded.** A CC-BY track is free only if the credit
   travels with it, so the licence, the author and the page URL are written
   next to the file and never reconstructed later from memory.

Openverse is the source because its licence filter runs on the server:
`license_type=commercial,modification` eliminates before anything is
transferred, and every result carries a ready-made attribution string.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable

import requests

from .sources.base import Throttle, expects_json, is_free_licence, is_retryable

API = "https://api.openverse.org/v1/audio/"
USER_AGENT = "Fresque/0.1 (documentary pipeline; contact via repository)"

MIN_INTERVAL_S = 3.2
_throttle = Throttle(MIN_INTERVAL_S)

#: Commercial use AND modification. Looping and levelling a bed are
#: modifications; a No-Derivatives track cannot be used at all.
LICENCE_FILTER = "commercial,modification"

#: Un lit trop court s'entend boucler, un morceau trop long est un
#: téléchargement inutile — on n'en garde que les premières minutes.
DUREE_MIN_S = 45
DUREE_MAX_S = 900

Reporter = Callable[[str], None]


class MusiqueError(RuntimeError):
    pass


@dataclass(frozen=True)
class Piste:
    """Un morceau candidat, avec ce qu'il faut pour l'utiliser légalement."""
    titre: str
    auteur: str
    licence: str
    licence_url: str
    page_url: str
    fichier_url: str
    duree_s: float
    source: str
    credit: str

    @property
    def utilisable(self) -> bool:
        return bool(self.fichier_url) and is_free_licence(self.licence)


def _licence_label(item: dict[str, Any]) -> str:
    nom = (item.get("license") or "").upper()
    version = item.get("license_version") or ""
    return f"CC {nom} {version}".strip() if nom and nom != "CC0" else (
        f"CC0 {version}".strip() if nom == "CC0" else nom)


def _to_piste(item: dict[str, Any]) -> Piste:
    duree_ms = item.get("duration") or 0
    return Piste(
        titre=item.get("title") or "sans titre",
        auteur=item.get("creator") or "inconnu",
        licence=_licence_label(item),
        licence_url=item.get("license_url") or "",
        page_url=item.get("foreign_landing_url") or item.get("url") or "",
        fichier_url=item.get("url") or "",
        duree_s=float(duree_ms) / 1000.0,
        source=item.get("source") or item.get("provider") or "openverse",
        credit=item.get("attribution") or "",
    )


def chercher(requete: str, limite: int = 12, session=None,
             source: str | None = None) -> list[Piste]:
    """Cherche des pistes réutilisables commercialement, et modifiables."""
    session = session or requests.Session()
    params: dict[str, Any] = {
        "q": requete,
        "license_type": LICENCE_FILTER,
        "page_size": min(limite * 2, 40),
    }
    if source:
        params["source"] = source

    _throttle.wait()
    response = session.get(
        API, params=params, headers={"User-Agent": USER_AGENT}, timeout=40
    )
    if is_retryable(response.status_code):
        raise MusiqueError(f"Openverse indisponible ({response.status_code})")
    response.raise_for_status()
    expects_json(response)

    pistes = []
    for item in response.json().get("results", []):
        piste = _to_piste(item)
        # Le filtre serveur porte sur la licence déclarée ; on revérifie
        # nous-mêmes, parce qu'une licence non commerciale qui passerait
        # coûterait bien plus cher qu'un candidat perdu.
        if not piste.utilisable:
            continue
        if not (DUREE_MIN_S <= piste.duree_s <= DUREE_MAX_S):
            continue
        pistes.append(piste)
        if len(pistes) >= limite:
            break
    return pistes


def telecharger(piste: Piste, destination: Path, session=None) -> Path:
    session = session or requests.Session()
    destination.parent.mkdir(parents=True, exist_ok=True)
    reponse = session.get(
        piste.fichier_url, headers={"User-Agent": USER_AGENT},
        timeout=120, stream=True,
    )
    reponse.raise_for_status()
    with destination.open("wb") as fh:
        for morceau in reponse.iter_content(65536):
            fh.write(morceau)
    return destination


def ecrire_licences(pistes: dict[str, Piste], chemin: Path) -> None:
    """La licence voyage à côté du fichier, jamais dans une tête.

    Une piste CC-BY n'est libre que si le crédit la suit. Reconstituer
    l'attribution six mois plus tard, à partir d'un nom de fichier, n'est
    pas une option : c'est comme ça qu'une chaîne monétisée se fait retirer
    une vidéo.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(
        json.dumps({"pistes": {nom: asdict(p) for nom, p in pistes.items()}},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
