"""Read and validate 03-shots.json — the visual plan, checkpoint 2.

One beat carries one or more shots. A shot is either an archive lookup, a
generated image, or a motion graphic. The `poids` field splits a beat's
duration between its shots.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: `video` est distinct d'`archive` : le métrage bouge déjà, il n'a pas de
#: mouvement de caméra à recevoir, et il se source auprès d'autres fonds.
TYPES = {"archive", "generated", "motion", "video"}
MOVEMENTS = {
    "zoom_in", "zoom_out", "pan_left", "pan_right",
    "pan_up", "pan_down", "static",
}

#: Motion graphics, and the fields each one needs. They are validated here
#: rather than in the renderer: a missing field should stop the pipeline at
#: the visual-plan checkpoint, not produce an empty panel twenty minutes into
#: a render.
MOTION_FIELDS: dict[str, tuple[str, ...]] = {
    # Une frise de dates — le plan le plus utile sur un sujet judiciaire.
    "chronologie": ("evenements",),
    # Un extrait de jugement, de loi, de témoignage, avec sa source.
    "citation": ("texte", "source"),
    # Un chiffre isolé, et ce à quoi il se compare.
    "chiffre": ("valeur", "libelle"),
    # Une carte, avec des lieux nommés et un trajet éventuel.
    "carte": ("marqueurs",),
    # Une une de journal, construite et non photographiée : les unes de
    # presse sont sous droits et quasi jamais disponibles librement.
    "journal": ("journal", "date", "titre"),
    # Un document officiel, avec un passage surligné. Sur un sujet judiciaire
    # ou administratif, souvent le plan le plus fort disponible.
    "document": ("lignes",),
}

#: Écritures disponibles pour un document. Aucune police n'est embarquée :
#: ces familles existent sur tout système.
ECRITURES = {"dactylographie", "officiel"}


class ShotsError(ValueError):
    """Raised when 03-shots.json is malformed or incomplete."""


@dataclass
class Shot:
    index: int
    beat: str
    type: str
    intention: str = ""
    requete: str = ""
    prompt: str = ""
    mouvement: str = "zoom_in"
    poids: float = 1.0
    motion: dict[str, Any] | None = None

    @property
    def id(self) -> str:
        return f"S{self.index:03d}"


def load(path: Path, beat_ids: list[str]) -> list[Shot]:
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("shots")
    if not isinstance(raw, list) or not raw:
        raise ShotsError("`shots` doit être une liste non vide.")

    known = set(beat_ids)
    shots: list[Shot] = []
    for index, entry in enumerate(raw):
        where = f"shots[{index}]"
        beat = entry.get("beat")
        if beat not in known:
            raise ShotsError(f"{where} : beat inconnu {beat!r}.")

        kind = entry.get("type")
        if kind not in TYPES:
            raise ShotsError(
                f"{where} : type {kind!r} invalide "
                f"(attendu : {', '.join(sorted(TYPES))})."
            )

        movement = entry.get("mouvement", "zoom_in")
        if movement not in MOVEMENTS:
            raise ShotsError(
                f"{where} : mouvement {movement!r} invalide "
                f"(attendu : {', '.join(sorted(MOVEMENTS))})."
            )

        shot = Shot(
            index=index,
            beat=beat,
            type=kind,
            intention=entry.get("intention", ""),
            requete=entry.get("requete", ""),
            prompt=entry.get("prompt", ""),
            mouvement=movement,
            poids=float(entry.get("poids", 1.0)),
            motion=entry.get("motion"),
        )

        if kind == "archive" and not shot.requete:
            raise ShotsError(f"{where} : un plan `archive` exige une `requete`.")
        if kind == "generated" and not shot.prompt:
            raise ShotsError(f"{where} : un plan `generated` exige un `prompt`.")
        if kind == "video":
            if not shot.requete:
                raise ShotsError(f"{where} : un plan `video` exige une `requete`.")
            if movement != "static":
                raise ShotsError(
                    f"{where} : un plan `video` prend `\"mouvement\": \"static\"` — "
                    "le métrage bouge déjà, lui ajouter un travelling donne "
                    "deux mouvements qui se contrarient."
                )
        if kind == "motion":
            _validate_motion(shot.motion, where)
        if shot.poids <= 0:
            raise ShotsError(f"{where} : `poids` doit être strictement positif.")

        shots.append(shot)

    covered = {shot.beat for shot in shots}
    missing = [b for b in beat_ids if b not in covered]
    if missing:
        raise ShotsError(
            f"{len(missing)} beat(s) sans plan visuel : "
            f"{', '.join(missing[:8])}{'…' if len(missing) > 8 else ''}"
        )

    return shots


def _validate_motion(motion: dict[str, Any] | None, where: str) -> None:
    if not motion:
        raise ShotsError(f"{where} : un plan `motion` exige un objet `motion`.")

    kind = motion.get("kind")
    if kind not in MOTION_FIELDS:
        raise ShotsError(
            f"{where} : motion.kind {kind!r} inconnu "
            f"(attendu : {', '.join(sorted(MOTION_FIELDS))})."
        )

    missing = [f for f in MOTION_FIELDS[kind] if not motion.get(f)]
    if missing:
        raise ShotsError(
            f"{where} : motion `{kind}` — champ(s) manquant(s) : "
            f"{', '.join(missing)}."
        )

    if kind == "document":
        lignes = motion["lignes"]
        if not isinstance(lignes, list) or not lignes:
            raise ShotsError(f"{where} : `lignes` doit être une liste non vide.")
        if len(lignes) > 8:
            raise ShotsError(
                f"{where} : {len(lignes)} lignes — un spectateur ne lit pas "
                "une page entière en huit secondes. En garder au plus huit, "
                "et surligner celle qui compte."
            )
        surligne = motion.get("surligne")
        if surligne is not None and not (
            isinstance(surligne, int) and 0 <= surligne < len(lignes)
        ):
            raise ShotsError(
                f"{where} : `surligne` vaut {surligne!r} — attendu un index "
                f"entre 0 et {len(lignes) - 1}."
            )
        ecriture = motion.get("ecriture")
        if ecriture is not None and ecriture not in ECRITURES:
            raise ShotsError(
                f"{where} : `ecriture` {ecriture!r} inconnue "
                f"(attendu : {', '.join(sorted(ECRITURES))})."
            )

    if kind == "carte":
        marqueurs = motion["marqueurs"]
        if not isinstance(marqueurs, list) or not marqueurs:
            raise ShotsError(f"{where} : `marqueurs` doit être une liste non vide.")
        if len(marqueurs) > 5:
            raise ShotsError(
                f"{where} : {len(marqueurs)} marqueurs — au-delà de cinq, les "
                "étiquettes se chevauchent. Scinder en deux cartes."
            )
        for index, marqueur in enumerate(marqueurs):
            coord = (marqueur or {}).get("coord")
            if not (marqueur or {}).get("nom") or not isinstance(coord, list) \
                    or len(coord) != 2:
                raise ShotsError(
                    f"{where} : marqueurs[{index}] exige `nom` et "
                    "`coord: [longitude, latitude]`."
                )
            lon, lat = coord
            # L'ordre est le piège classique : GeoJSON veut longitude
            # d'abord, alors qu'on lit et qu'on écrit « 48,85 / 2,35 ».
            if not (-180 <= lon <= 180) or not (-90 <= lat <= 90):
                raise ShotsError(
                    f"{where} : marqueurs[{index}] coord {coord} hors limites "
                    "— l'ordre attendu est [longitude, latitude]."
                )

    if kind == "chronologie":
        events = motion["evenements"]
        if not isinstance(events, list) or len(events) < 2:
            raise ShotsError(
                f"{where} : une chronologie demande au moins deux événements "
                "— sinon c'est une date, pas une frise."
            )
        if len(events) > 7:
            raise ShotsError(
                f"{where} : {len(events)} événements — au-delà de sept, la "
                "frise devient illisible à l'écran. La scinder en deux plans."
            )
        for index, event in enumerate(events):
            if not isinstance(event, dict) or not event.get("date") \
                    or not event.get("texte"):
                raise ShotsError(
                    f"{where} : evenements[{index}] exige `date` et `texte`."
                )


def by_beat(shots: list[Shot]) -> dict[str, list[Shot]]:
    grouped: dict[str, list[Shot]] = {}
    for shot in shots:
        grouped.setdefault(shot.beat, []).append(shot)
    return grouped
