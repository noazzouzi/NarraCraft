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

TYPES = {"archive", "generated", "motion"}
MOVEMENTS = {
    "zoom_in", "zoom_out", "pan_left", "pan_right",
    "pan_up", "pan_down", "static",
}


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
        if kind == "motion" and not shot.motion:
            raise ShotsError(f"{where} : un plan `motion` exige un objet `motion`.")
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


def by_beat(shots: list[Shot]) -> dict[str, list[Shot]]:
    grouped: dict[str, list[Shot]] = {}
    for shot in shots:
        grouped.setdefault(shot.beat, []).append(shot)
    return grouped
