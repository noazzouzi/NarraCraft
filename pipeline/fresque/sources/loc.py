"""Library of Congress — the only free source of real archive footage in HD
that we found.

TWO THINGS MAKE THIS SOURCE DIFFERENT
=====================================

**It publishes no usable licence field.** `rights` and `rights_advisory` come
back null on every video item measured. The public-domain status comes from
the *collection*, not the item — so the trust is declared in
`fresque.config.yaml`, in a versioned file someone can read and argue with,
rather than guessed at in code. A collection that is not on the list is not
sourced, full stop.

**The files are whole films.** A 27-minute item measured at 1038 MB. Median
duration across a sample was 111 seconds, so most are manageable, but the tail
is not: a duration ceiling and a byte ceiling are both mandatory, checked
before the download rather than after.

It also answers 429 with a Cloudflare HTML page rather than JSON, which is
why every response goes through `expects_json` first.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterable

import requests

from .base import Throttle, expects_json, is_retryable, retry_delay

BASE = "https://www.loc.gov/collections"
USER_AGENT = "Fresque/0.1 (documentary pipeline; contact via repository)"

# Measured: a 429 Cloudflare page after three requests at one per six seconds,
# from a shared outbound address. Slower than Commons on purpose.
MIN_INTERVAL_S = 6.5
MAX_RETRIES = 2
_throttle = Throttle(MIN_INTERVAL_S)

#: Anything longer is a feature film, not a shot. Also the main defence
#: against downloading a gigabyte for seven seconds of screen time.
MAX_DUREE_S = 420
MAX_OCTETS = 220_000_000

MIN_HAUTEUR = 700


@dataclass
class Clip:
    """A sourceable piece of footage. Not a `Candidate`: it carries a duration
    and an in-point, which a still image has no use for."""
    provider: str
    title: str
    page_url: str
    file_url: str
    licence: str
    duree_s: float
    width: int
    height: int
    collection: str
    date: str = ""
    author: str = ""

    #: Le nom lisible d'un fonds, pour le crédit. `credit()` écrivait
    #: « Library of Congress » en dur, ce qui restait vrai tant qu'il n'y
    #: avait qu'un fonds — et devenait un faux crédit dès le deuxième.
    FONDS = {"loc": "Library of Congress", "pexels": "Pexels"}

    def credit(self) -> str:
        fonds = self.FONDS.get(self.provider, self.provider)
        # Un titre de banque d'images tient parfois trois lignes : c'est une
        # description, pas un titre. Le crédit doit rester lisible.
        titre = self.title.strip()
        if len(titre) > 90:
            titre = titre[:87].rstrip() + "…"
        # `Pexels — Pexels License` nomme deux fois le même acteur. On
        # laisse alors tomber le fonds, jamais la licence : la convention du
        # projet veut que tout asset porte la sienne.
        if fonds and fonds.lower() in self.licence.lower():
            fonds = ""
        parts = [titre, self.author.strip(), fonds, self.licence]
        return " — ".join(p for p in parts if p)


def _get(http: requests.Session, url: str, params: dict[str, str], timeout: float):
    for attempt in range(MAX_RETRIES + 1):
        _throttle.wait()
        response = http.get(
            url, params=params, timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        if is_retryable(response.status_code) and attempt < MAX_RETRIES:
            time.sleep(retry_delay(response, attempt, MIN_INTERVAL_S))
            continue
        response.raise_for_status()
        expects_json(response)
        return response
    response.raise_for_status()
    return response


@dataclass
class Resultat:
    """What a search found, and what it had to throw away.

    The distinction matters to the person reading the log: "nothing matched"
    and "twelve films matched but every one runs twenty minutes" call for
    different fixes, and only the second is worth rewording the query for.
    """
    clips: list["Clip"]
    vus: int = 0
    trop_longs: int = 0


def search(
    query: str,
    collections: Iterable[str],
    limit: int = 5,
    max_duree_s: float = MAX_DUREE_S,
    session: requests.Session | None = None,
    timeout: float = 45.0,
) -> Resultat:
    """Search the whitelisted collections. Never anything outside them."""
    http = session or requests.Session()
    resultat = Resultat(clips=[])

    for collection in collections:
        if len(resultat.clips) >= limit:
            break
        response = _get(
            http, f"{BASE}/{collection}/",
            {"q": query, "fo": "json", "c": "25", "at": "results"}, timeout,
        )
        retenus, vus, longs = _to_clips(
            response.json().get("results", []) or [],
            collection=collection, max_duree_s=max_duree_s,
        )
        resultat.clips.extend(retenus)
        resultat.vus += vus
        resultat.trop_longs += longs

    resultat.clips.sort(key=lambda c: c.duree_s)
    resultat.clips = resultat.clips[:limit]
    return resultat


def _to_clips(
    results: Iterable[dict[str, Any]], collection: str, max_duree_s: float
) -> tuple[list[Clip], int, int]:
    """Returns (kept, seen with video, rejected for length)."""
    clips: list[Clip] = []
    vus = trop_longs = 0
    for item in results:
        if item.get("access_restricted"):
            continue
        for resource in item.get("resources") or []:
            url = resource.get("video")
            duree = float(resource.get("duration") or 0)
            hauteur = int(resource.get("height") or 0)
            if not url or not duree or hauteur < MIN_HAUTEUR:
                continue
            vus += 1
            if duree > max_duree_s:
                trop_longs += 1
                break
            clips.append(Clip(
                provider=f"loc:{collection}",
                title=(item.get("title") or "").strip(),
                page_url=resource.get("url") or item.get("id", ""),
                file_url=url,
                # Declared here, from the collection whitelist, never guessed.
                licence=f"Domaine public — Library of Congress, {collection}",
                duree_s=duree,
                width=int(resource.get("width") or 0),
                height=hauteur,
                collection=collection,
                date=str(item.get("date") or ""),
            ))
            break  # one viewing copy per item is enough
    return clips, vus, trop_longs


def taille(clip: Clip, timeout: float = 30.0) -> int:
    """Bytes, from a HEAD. Zero when the server does not say."""
    _throttle.wait()
    response = requests.head(
        clip.file_url, headers={"User-Agent": USER_AGENT},
        timeout=timeout, allow_redirects=True,
    )
    response.raise_for_status()
    return int(response.headers.get("Content-Length") or 0)


def download(clip: Clip, destination, timeout: float = 300.0,
             max_octets: int = MAX_OCTETS) -> None:
    """Fetch the film, refusing anything oversized before spending the time."""
    poids = taille(clip)
    if poids and poids > max_octets:
        raise ValueError(
            f"{poids / 1e6:.0f} Mo pour {clip.duree_s:.0f} s — au-dessus du "
            f"plafond de {max_octets / 1e6:.0f} Mo. Chercher un extrait plus court."
        )

    _throttle.wait()
    recu = 0
    with requests.get(
        clip.file_url, stream=True, timeout=timeout,
        headers={"User-Agent": USER_AGENT},
    ) as response:
        response.raise_for_status()
        with open(destination, "wb") as fh:
            for chunk in response.iter_content(chunk_size=1 << 20):
                recu += len(chunk)
                if recu > max_octets:
                    raise ValueError(
                        "téléchargement interrompu au-dessus du plafond "
                        f"({max_octets / 1e6:.0f} Mo) — taille non annoncée"
                    )
                fh.write(chunk)


def point_de_depart(
    duree_s: float, fenetre_s: float, rang: int = 0, saut_pct: float = 0.1,
) -> float:
    """Where to start inside the film.

    Archive films open on titles, leaders and countdowns, so the first tenth
    is skipped. `rang` spreads successive shots taken from the same film
    across what is left — without it, reusing a rush shows the same seconds
    twice, which is worse than not reusing it at all.
    """
    amorce = max(duree_s * saut_pct, 2.0)
    utile = max(duree_s - amorce - fenetre_s, 0.0)
    # Golden-ratio stepping: successive ranks land far apart without ever
    # repeating, and without needing to know how many there will be.
    decalage = (utile * ((rang * 0.618) % 1.0)) if utile else 0.0
    return max(0.0, min(amorce + decalage, max(duree_s - fenetre_s, 0.0)))
