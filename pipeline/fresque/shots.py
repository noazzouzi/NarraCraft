"""Read and validate 03-shots.json — the visual plan, checkpoint 2.

One beat carries one or more shots. A shot is either an archive lookup, a
generated image, or a motion graphic. The `poids` field splits a beat's
duration between its shots.
"""
from __future__ import annotations

import json
import math
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
    # Lignes et colonnes. Quatre chefs d'accusation en face de quatre
    # décisions disent en une image ce que la narration met trente secondes
    # à établir.
    "tableau": ("colonnes", "lignes"),
    # Des quantités comparées, en barres horizontales.
    "barres": ("series",),
    # Une part dans un tout. Un chiffre isolé ne dit rien tant qu'on ne sait
    # pas de quoi il est la part.
    "proportion": ("valeur", "total", "libelle"),
    # Deux colonnes opposées : ce qu'on croit, ce qui a été établi.
    "comparaison": ("gauche", "droite"),
    # Des personnes et ce qui les relie. Sur une association de malfaiteurs,
    # c'est une illustration littérale de l'infraction retenue.
    "reseau": ("noeuds",),
    # Une fenêtre de navigateur, construite et jamais capturée. La source
    # est obligatoire, comme pour un journal.
    "maquette": ("site", "titre", "source"),
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
    #: Une phrase incrustée en grand sur le plan. C'est l'accroche : le
    #: spectateur lit avant d'avoir fini d'entendre, et il reste pour la
    #: raison que la phrase lui donne.
    accroche: str = ""

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
            accroche=(entry.get("accroche") or "").strip(),
        )

        if shot.accroche:
            _validate_accroche(shot, where)

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


def _validate_accroche(shot: Shot, where: str) -> None:
    from . import config

    limit = int(config.get("structure", "ouverture", "accroche_mots_max", default=12))
    count = len(shot.accroche.split())
    if count > limit:
        raise ShotsError(
            f"{where} : accroche de {count} mots (max {limit}) — une phrase "
            "incrustée se lit en une seconde et demie, pendant que la voix "
            "dit autre chose. Au-delà, personne ne la lit."
        )
    if shot.type == "motion":
        raise ShotsError(
            f"{where} : une accroche se pose sur une image, pas sur un "
            "panneau graphique qui porte déjà son propre texte."
        )


def ouverture(shots: list[Shot]) -> list[str]:
    """What is wrong with the opening shot, if anything.

    The first shot decides whether anyone sees the second. Measured on the
    first full documentary this pipeline produced: it opened on a prison
    façade while the narration named a former president. The viewer had
    nothing to attach the sentence to.

    This is an editorial contract, not a structural one, so it is reported
    at the checkpoint rather than raised while parsing — a test fixture with
    three shots in it has no opening to speak of.
    """
    from . import config

    if not config.get("structure", "ouverture", "accroche_obligatoire", default=True):
        return []
    if not shots:
        return []

    limit = config.get("structure", "ouverture", "accroche_mots_max", default=12)
    problems: list[str] = []
    first = shots[0]

    if first.type == "motion":
        problems.append(
            "le documentaire ouvre sur un panneau graphique. Le premier plan "
            "montre le sujet — le visage, l'objet, le lieu dont l'histoire "
            "parle — jamais une abstraction."
        )
    if not first.accroche:
        problems.append(
            "le premier plan n'a pas d'`accroche`. Il porte la phrase qui "
            f'fait rester, incrustée à l\'écran : `"accroche": "…"`, au plus '
            f"{limit} mots, un fait, pas une question."
        )
    return problems


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

    if kind == "tableau":
        colonnes, lignes = motion["colonnes"], motion["lignes"]
        if not isinstance(colonnes, list) or len(colonnes) < 2:
            raise ShotsError(f"{where} : un tableau demande au moins deux colonnes.")
        if len(colonnes) > 4:
            raise ShotsError(
                f"{where} : {len(colonnes)} colonnes — au-delà de quatre, le "
                "texte devient illisible à l'écran. Scinder le tableau."
            )
        if not isinstance(lignes, list) or not lignes:
            raise ShotsError(f"{where} : `lignes` doit être une liste non vide.")
        if len(lignes) > 6:
            raise ShotsError(
                f"{where} : {len(lignes)} lignes — un spectateur n'en lit pas "
                "plus de six pendant que la voix parle."
            )
        for index, ligne in enumerate(lignes):
            if not isinstance(ligne, list) or len(ligne) != len(colonnes):
                raise ShotsError(
                    f"{where} : lignes[{index}] a {len(ligne) if isinstance(ligne, list) else '?'} "
                    f"cellules pour {len(colonnes)} colonnes."
                )
        accent = motion.get("colonne_accent")
        if accent is not None and not (
            isinstance(accent, int) and 0 <= accent < len(colonnes)
        ):
            raise ShotsError(
                f"{where} : `colonne_accent` vaut {accent!r} — attendu un index "
                f"entre 0 et {len(colonnes) - 1}."
            )

    if kind == "barres":
        series = motion["series"]
        if not isinstance(series, list) or len(series) < 2:
            raise ShotsError(
                f"{where} : deux séries au minimum — en dessous c'est un "
                "chiffre, pas un graphique."
            )
        if len(series) > 6:
            raise ShotsError(f"{where} : {len(series)} barres, six au maximum.")
        for index, serie in enumerate(series):
            if not isinstance(serie, dict) or not serie.get("libelle"):
                raise ShotsError(f"{where} : series[{index}] exige un `libelle`.")
            try:
                valeur = float(serie.get("valeur"))
            except (TypeError, ValueError):
                raise ShotsError(
                    f"{where} : series[{index}].valeur doit être un nombre."
                ) from None
            if valeur < 0:
                raise ShotsError(f"{where} : series[{index}].valeur est négative.")

    if kind == "proportion":
        try:
            valeur, total = float(motion["valeur"]), float(motion["total"])
        except (TypeError, ValueError):
            raise ShotsError(
                f"{where} : `valeur` et `total` doivent être des nombres."
            ) from None
        if total <= 0:
            raise ShotsError(f"{where} : `total` doit être strictement positif.")
        if not 0 <= valeur <= total:
            raise ShotsError(
                f"{where} : une part de {valeur:g} sur {total:g} n'est pas une "
                "part. Vérifier l'ordre des deux valeurs."
            )

    if kind == "comparaison":
        for cote in ("gauche", "droite"):
            bloc = motion[cote]
            if not isinstance(bloc, dict) or not bloc.get("titre"):
                raise ShotsError(f"{where} : `{cote}` exige un `titre`.")
            points = bloc.get("points")
            if not isinstance(points, list) or not points:
                raise ShotsError(f"{where} : `{cote}.points` doit être non vide.")
            if len(points) > 4:
                raise ShotsError(
                    f"{where} : {len(points)} points à {cote} — quatre au "
                    "maximum, les deux colonnes se lisent en parallèle."
                )

    if kind == "reseau":
        noeuds = motion["noeuds"]
        if not isinstance(noeuds, list) or len(noeuds) < 2:
            raise ShotsError(f"{where} : un réseau demande au moins deux nœuds.")
        if len(noeuds) > 8:
            raise ShotsError(
                f"{where} : {len(noeuds)} nœuds — au-delà de huit, les noms se "
                "chevauchent sur le cercle."
            )
        for index, noeud in enumerate(noeuds):
            if not isinstance(noeud, dict) or not noeud.get("nom"):
                raise ShotsError(f"{where} : noeuds[{index}] exige un `nom`.")
        for index, lien in enumerate(motion.get("liens") or []):
            if not isinstance(lien, dict):
                raise ShotsError(f"{where} : liens[{index}] doit être un objet.")
            for bout in ("de", "a"):
                cible = lien.get(bout)
                if not (isinstance(cible, int) and 0 <= cible < len(noeuds)):
                    raise ShotsError(
                        f"{where} : liens[{index}].{bout} vaut {cible!r} — "
                        f"attendu un index de nœud entre 0 et {len(noeuds) - 1}."
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


def density(shots: list[Shot], beats: list[Any]) -> list[str]:
    """Beats whose visual plan would hold one image too long.

    The real check happens on the timeline, once the voice exists and the
    durations are measured. But by then the archives are downloaded and the
    generated images are paid for. Estimating from the word count here costs
    nothing and catches the same problem at the checkpoint, which is the
    point of having a checkpoint.
    """
    from . import config

    wpm = float(config.get("narration", "mots_par_minute", default=140))
    longest = float(config.get("montage", "duree_plan_max_s", default=10))
    grouped = by_beat(shots)

    slow: list[str] = []
    for beat in beats:
        planned = grouped.get(beat.id, [])
        if not planned:
            continue
        seconds = beat.word_count / wpm * 60
        # The longest shot of the beat is the one that decides, not the
        # average: a beat split 1/1/4 still holds its last image forever.
        weight_total = sum(s.poids for s in planned)
        held = seconds * max(s.poids for s in planned) / weight_total
        if held > longest:
            needed = math.ceil(seconds / longest)
            slow.append(
                f"{beat.id} : {len(planned)} plan(s) pour {seconds:.0f} s — "
                f"un plan tenu ~{held:.1f} s (max {longest:g} s). "
                f"En prévoir {max(needed, len(planned) + 1)}."
            )
    return slow


def by_beat(shots: list[Shot]) -> dict[str, list[Shot]]:
    grouped: dict[str, list[Shot]] = {}
    for shot in shots:
        grouped.setdefault(shot.beat, []).append(shot)
    return grouped
