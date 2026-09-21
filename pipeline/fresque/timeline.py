"""Build 06-timeline.json — the single source of truth for the montage.

All timing arithmetic happens here, in code, from the real numbers in
`alignment.json`. No language model ever computes a timecode (CLAUDE.md).

The output is renderer-neutral on purpose: Remotion consumes it today, and an
NLE exporter can consume the same file tomorrow.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import collage, config
from .shots import Shot, by_beat, plafond_s

#: Ken Burns applied identically to every shot reads as a template. Varying it
#: per shot — but deterministically, so a re-render is identical — is what
#: makes the movement feel authored rather than generated. La composition des
#: planches de collage s'en sert pour la même raison, d'où le partage.
_jitter = collage.jitter


def _movement(shot: Shot, duree_s: float) -> dict[str, Any]:
    """Le mouvement de caméra d'un plan, dérivé de sa durée.

    C'est une **vitesse**, pas une amplitude. Une plage fixe parcourue quelle
    que soit la durée du plan fait qu'un plan court est traversé à toute
    allure et qu'un plan long rampe : le même réglage produit deux mouvements
    qui n'ont rien à voir. En raisonnant en pourcentage par seconde, le
    mouvement reste le même à l'œil quand on change le rythme du montage —
    ce qui est exactement ce qu'on vient de faire.

    La valeur par défaut vient d'une mesure : sur les documentaires Frontier,
    l'échelle croît de 2,1 à 3,1 % par seconde (voir `docs/analyse-frontier.md`).
    Notre réglage précédent, 1,06 → 1,30 sur un plan de 6,5 s, valait 3,5 %/s
    — et 9,4 %/s dès que le plan tombait à 2,4 s, soit un zoom qui se voit.
    """
    kb = config.get("montage", "ken_burns", default={}) or {}
    depart = float(kb.get("echelle_depart", 1.04))
    zoom_max = float(kb.get("zoom_max", 1.18))
    vitesse = float(kb.get("vitesse_pct_s", 2.5)) / 100.0
    derive_s = float(kb.get("derive_pct_s", 3.0)) / 100.0
    drift_max = float(kb.get("derive_max_pct", 6)) / 100.0
    rotation_max = float(kb.get("micro_rotation_deg", 0.4))
    easing = kb.get("easing", "easeInOutCubic")

    # Le grain varie la vitesse, plus les bornes : un plan reste plus vif ou
    # plus posé qu'un autre, sans jamais sortir de la plage mesurée.
    course = vitesse * duree_s * (0.75 + 0.5 * _jitter(shot.id, "vitesse"))
    low = depart
    high = min(depart * (1.0 + course), zoom_max)
    # Une dérive se parcourt elle aussi dans le temps du plan, et reste
    # bornée : au-delà, le sujet sort du cadre.
    drift = min(derive_s * duree_s * (0.6 + 0.8 * _jitter(shot.id, "drift")),
                drift_max)
    rotation = rotation_max * (_jitter(shot.id, "rot") * 2 - 1)
    mid = (low + high) / 2

    kind = shot.mouvement
    if kind == "zoom_in":
        start, end = {"scale": low, "x": 0.0, "y": 0.0}, {"scale": high, "x": 0.0, "y": 0.0}
    elif kind == "zoom_out":
        start, end = {"scale": high, "x": 0.0, "y": 0.0}, {"scale": low, "x": 0.0, "y": 0.0}
    elif kind in ("pan_left", "pan_right"):
        sign = -1.0 if kind == "pan_left" else 1.0
        start = {"scale": mid, "x": -sign * drift, "y": 0.0}
        end = {"scale": mid, "x": sign * drift, "y": 0.0}
    elif kind in ("pan_up", "pan_down"):
        sign = -1.0 if kind == "pan_up" else 1.0
        start = {"scale": mid, "x": 0.0, "y": -sign * drift}
        end = {"scale": mid, "x": 0.0, "y": sign * drift}
    else:  # static — still never pixel-frozen, which reads as a broken player
        souffle = 0.004 * duree_s
        start = {"scale": low, "x": 0.0, "y": 0.0}
        end = {"scale": low + souffle, "x": 0.0, "y": 0.0}

    return {
        "kind": kind,
        "easing": easing,
        "rotation_deg": round(rotation, 3),
        "debut": {k: round(v, 4) for k, v in start.items()},
        "fin": {k: round(v, 4) for k, v in end.items()},
    }


#: How a shot arrives, and the sound that leads it in. The renderer knows how
#: to draw each of these and nothing else.
#:
#: They are entry effects rather than cross-dissolves on purpose: clips are
#: contiguous, non-overlapping sequences, and keeping them that way is what
#: makes the timeline readable by something other than Remotion. A hard cut
#: with a whoosh under it is also more alive than a dissolve, which is what
#: was actually asked for.
TRANSITIONS = {
    "coupe": None,
    "flash": "souffle",
    "glisse": "souffle_inverse",
    "fondu_noir": "impact",
    "ouverture": "sub",
}


def _transition(position: int, clip_beat: str, clip_act: str,
                previous: dict[str, Any] | None, shot_type: str,
                previous_type: str | None, style: str = "effets") -> str:
    """Pick how this shot arrives, from where it sits in the story.

    The rule is deliberately coarse, because a fine one would be a taste
    engine and taste is not what code is for here. What the code knows for
    certain is the structure: whether the idea continues, changes, or the act
    turns over. That is enough to stop every cut looking the same, which was
    the actual complaint.

    `style` décide de l'inventaire disponible, et c'est un réglage de
    template parce que c'est une question de genre :

    - `effets` garde le flash, la glisse et leurs souffles.
    - `coupe` ne laisse que la coupe franche. Sur vingt et une transitions
      relevées dans deux documentaires Frontier, **toutes** étaient des
      coupes d'une image, et l'énergie au-dessus de 3 kHz y est plus faible
      qu'ailleurs dans le film : ni fondu, ni souffle.

    Le fondu au noir de changement d'acte survit aux deux. Les échantillons
    mesurés duraient vingt et trente-quatre secondes et ne contenaient aucun
    changement d'acte : nous n'avons donc rien observé qui dise de le
    supprimer, et une bascule d'acte reste la seule respiration du récit.
    """
    if position == 0:
        return "ouverture"
    if previous is None:
        return "coupe"

    if clip_act != previous.get("acte"):
        return "fondu_noir"

    if style == "coupe":
        return "coupe"

    # A graphic panel is a different medium arriving; sliding it in says so,
    # and a hard cut into one reads as a glitch. Une planche de collage est
    # le même cas : on passe de la photographie au papier composé.
    if {shot_type, previous_type} & {"motion", "collage"}:
        return "glisse"

    if clip_beat != previous["beat"]:
        return "flash"

    # Inside a beat the idea continues, so the cut is bare. This is most of
    # them, and it is what makes the flashes count.
    return "coupe"


def _subtitle_lines(words: list[dict[str, Any]], per_line: int) -> list[list[dict[str, Any]]]:
    """Group words into subtitle lines, breaking on punctuation where possible.

    A line that ends mid-clause forces the eye to hold an incomplete thought
    while the voice moves on. Breaking one or two words early, at a comma or a
    full stop, costs nothing and reads far better.
    """
    slack = max(1, per_line // 3)
    plafond = per_line + slack

    # 1. Une ligne par phrase. C'est la règle, et elle est courte parce que
    #    les phrases le sont : le skill d'écriture plafonne à douze mots et
    #    vise trois à huit (`docs/analyse-frontier.md`). Une phrase entière à
    #    l'écran est ce qui se lit le mieux, et le surlignage mot à mot dit
    #    déjà où la voix en est.
    #
    #    L'ancienne version coupait à longueur fixe et ne respectait la
    #    ponctuation que si elle tombait dans une fenêtre étroite. Le rendu
    #    l'a montré tel quel : « cinq ans de prison. Il est » — deux mots
    #    d'une idée dont la suite n'était pas encore affichée.
    phrases: list[list[dict[str, Any]]] = []
    courante: list[dict[str, Any]] = []
    for mot in words:
        courante.append(mot)
        if mot.get("tx", mot["t"]).rstrip().endswith((".", "!", "?", "…")):
            phrases.append(courante)
            courante = []
    if courante:
        phrases.append(courante)

    # 2. Une phrase trop longue pour tenir se découpe, à la virgule si elle
    #    en a une, à la longueur sinon.
    lines: list[list[dict[str, Any]]] = []
    for phrase in phrases:
        while len(phrase) > plafond:
            fenetre = phrase[:plafond]
            coupe = None
            for offset in range(len(fenetre) - 1, 0, -1):
                if fenetre[offset].get("tx", "").rstrip().endswith((",", ";", ":")):
                    coupe = offset + 1
                    break
            coupe = coupe or per_line
            lines.append(phrase[:coupe])
            phrase = phrase[coupe:]
        if phrase:
            lines.append(phrase)

    return [line for line in lines if line]


def _fenetres(chunk: list[dict[str, Any]], fin_ligne: int, fps: int,
              plancher: int) -> list[dict[str, Any]]:
    """La fenêtre de surlignage de chaque mot d'une ligne.

    Un mot reste surligné **jusqu'à ce que le suivant commence**, pas
    jusqu'à ce qu'il se taise. C'est ce qui supprime les trous : entre deux
    mots la voix respire, et un surlignage qui s'éteindrait pendant cette
    respiration donnerait un texte qui clignote.

    Ça règle aussi le cas des mots avalés. L'aligneur pose « a » et « à » à
    une seule trame de 20 ms — ce qu'aucune voyelle prononcée ne dure ;
    mesurés à sept sur trois cent dix-sept. En prenant le départ du mot
    suivant, ils héritent d'une fenêtre lisible, et le plancher n'a plus
    qu'à couvrir les derniers cas.

    Sur un mot avalé, le plancher peut pousser la fenêtre un peu au-delà du
    départ du suivant : deux mots sont alors pleinement surlignés pendant
    une ou deux images. C'est assumé. L'autre choix serait un surlignage de
    20 ms, c'est-à-dire invisible — un scintillement plutôt qu'une
    indication. Le chevauchement est borné par le plancher, donc petit.

    Les frames sont calculées ici, jamais dans le moteur de rendu : c'est la
    même règle que pour les coupes.
    """
    departs = [round(m["debut_s"] * fps) for m in chunk]
    fenetres: list[dict[str, Any]] = []
    for index, mot in enumerate(chunk):
        debut = departs[index]
        suivant = departs[index + 1] if index + 1 < len(departs) else fin_ligne
        fenetres.append({
            "tx": mot.get("tx", mot["t"]),
            "debut_frame": debut,
            "fin_frame": max(suivant, debut + plancher),
        })
    return fenetres


def _subtitles(beat: dict[str, Any], fps: int, per_line: int,
               plancher: int) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for chunk in _subtitle_lines(beat["mots"], per_line):
        first, last = chunk[0]["debut_s"], chunk[-1]["fin_s"]
        debut = round(first * fps)
        fin = max(round(last * fps), debut + 1)
        lines.append({
            "texte": " ".join(w.get("tx", w["t"]) for w in chunk),
            "debut_frame": debut,
            "duree_frames": fin - debut,
            # Les fenêtres sont en frames absolues, comme tout le reste du
            # fichier ; le moteur les ramène au début de sa séquence.
            "mots": _fenetres(chunk, fin, fps, plancher),
        })
    return lines


def _mots_nus(texte: str) -> list[str]:
    """Les mots d'un texte, dépouillés pour être comparables."""
    import re
    import unicodedata

    plat = unicodedata.normalize("NFKD", texte.lower())
    plat = "".join(c for c in plat if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9']+", plat)


def _instant_de(phrase: str, mots: list[dict[str, Any]]) -> float | None:
    """Quand la narration dit `phrase`, en secondes. `None` si absente.

    Le plan visuel déclare une poignée de mots du beat ; on retrouve leur
    place dans l'alignement. C'est la même division du travail que partout
    ailleurs : le jugement dit **quoi**, le code calcule **quand**.

    Le retour `None` est important. Une phrase qui ne se retrouve pas est
    presque toujours une faute de frappe dans le plan visuel, et on préfère
    le dire au checkpoint plutôt que de poser le surligneur au hasard.
    """
    cible = _mots_nus(phrase)
    if not cible:
        return None
    suite = [_mots_nus(m.get("t", ""))[:1] for m in mots]
    plats = [s[0] if s else "" for s in suite]

    for debut in range(len(plats) - len(cible) + 1):
        if plats[debut:debut + len(cible)] == cible:
            return float(mots[debut]["debut_s"])
    return None


def _motion_calee(shot: Shot, beat: dict[str, Any], debut_frame: int, fps: int,
                  introuvables: list[str]) -> dict[str, Any] | None:
    """Le panneau du plan, avec son surligneur calé sur la narration.

    `surligne_a` porte un bout du texte du beat. On en tire la frame, et on
    la donne au moteur en relatif — il dessine un balayage à partir d'une
    frame, il ne cherche rien dans un texte.

    Sans `surligne_a`, rien n'est ajouté et le moteur garde son retard par
    défaut. C'est ce qui permet d'adopter ce calage panneau par panneau.
    """
    if shot.motion is None:
        return None
    phrase = shot.motion.get("surligne_a")
    if not phrase:
        return shot.motion

    instant = _instant_de(str(phrase), beat.get("mots", []))
    if instant is None:
        introuvables.append(f"{shot.id} : « {phrase} » absent de {beat['id']}")
        return shot.motion

    # Relatif au plan : une séquence Remotion compte à partir de zéro.
    return {**shot.motion,
            "surligne_frame": max(round(instant * fps) - debut_frame, 0)}


#: Les licences qui n'obligent à rien. Tout le reste exige une attribution,
#: et une chaîne monétisée ne peut pas s'en dispenser.
_SANS_OBLIGATION = ("cc0", "public domain", "domaine public", "pdm")


def _sans_obligation(licence: str) -> bool:
    nue = (licence or "").strip().lower()
    return any(nue.startswith(l) for l in _SANS_OBLIGATION)


#: Le nom d'affichage des fonds. L'identifiant technique voyage dans les
#: fichiers ; il n'a rien à faire à l'écran.
_FONDS = {
    "wikimedia_commons": "Wikimedia Commons",
    "openverse": "Openverse",
    "pexels": "Pexels",
    "pixabay": "Pixabay",
    "loc": "Library of Congress",
    "smithsonian": "Smithsonian",
    "archive_org": "Archive.org",
}

#: Au-delà, ce n'est plus un nom. Le champ « auteur » de Wikimedia Commons
#: est libre : un contributeur y avait écrit quatre-vingt-dix mots de
#: conditions d'utilisation, qui prenaient cinq lignes du carton à eux
#: seuls. On coupe à la première phrase, puis net.
_NOM_MAX = 42


def _nom(brut: str) -> str:
    """Un champ « auteur » ramené à quelque chose qui ressemble à un nom."""
    nu = " ".join((brut or "").split())
    for coupure in (". ", " (", " - ", " — "):
        if coupure in nu:
            nu = nu.split(coupure, 1)[0]
    nu = nu.rstrip(" .,;")
    return nu[:_NOM_MAX - 1] + "…" if len(nu) > _NOM_MAX else nu


def generique(credits: list[dict[str, Any]], fps: int) -> dict[str, Any] | None:
    """Le carton de fin, groupé par licence.

    `timeline.py` construisait déjà ce tableau `credits`, et personne ne le
    lisait : aucun composant ne l'affichait. Sur le premier film complet,
    258 images sur 329 étaient sous une licence qui exige l'attribution, et
    aucune n'était créditée. Ce n'est pas un défaut de finition.

    Un carton ne peut pas porter 258 noms lisibles. Il porte donc les
    licences, les fonds, et autant d'auteurs qu'il en tient ; la liste
    entière part dans `07-out/credits.md`, pour la description de la vidéo.
    C'est l'usage du médium, et c'est ce que « attribution raisonnable au
    support » veut dire pour un film.
    """
    if not credits or not config.get("montage", "generique", "actif", default=True):
        return None

    budget = int(config.get("montage", "generique", "signes_max", default=1200))
    duree_s = float(config.get("montage", "generique", "duree_s", default=12))

    groupes: dict[str, dict[str, Any]] = {}
    libres = 0
    for entree in credits:
        licence = (entree.get("licence") or "").strip() or "licence inconnue"
        if _sans_obligation(licence):
            libres += 1
            continue
        groupe = groupes.setdefault(licence, {"licence": licence, "nombre": 0,
                                              "auteurs": [], "fonds": []})
        groupe["nombre"] += 1
        auteur = _nom(entree.get("auteur") or "")
        if auteur and auteur not in groupe["auteurs"]:
            groupe["auteurs"].append(auteur)
        fonds = (entree.get("source") or "").strip()
        joli = _FONDS.get(fonds, fonds)
        if joli and joli not in groupe["fonds"]:
            groupe["fonds"].append(joli)

    # Les licences les plus représentées d'abord : c'est l'ordre dans lequel
    # un lecteur cherche, et celui qui survit à une troncature.
    ordonnes = sorted(groupes.values(), key=lambda g: -g["nombre"])

    # Le budget se compte en SIGNES, pas en noms : trois noms longs prennent
    # plus de place que dix courts, et c'est la place qui manque. Il se
    # répartit au prorata, sinon la licence la plus fournie mange le carton
    # et les suivantes n'ont plus personne.
    total = sum(len(" · ".join(g["auteurs"])) for g in ordonnes) or 1
    for groupe in ordonnes:
        ecrit = len(" · ".join(groupe["auteurs"]))
        part = max(_NOM_MAX, round(budget * ecrit / total))
        montres: list[str] = []
        pris = 0
        for nom in groupe["auteurs"]:
            if pris + len(nom) > part and montres:
                break
            montres.append(nom)
            pris += len(nom) + 3
        groupe["reste"] = len(groupe["auteurs"]) - len(montres)
        groupe["auteurs"] = montres

    return {
        "duree_frames": round(duree_s * fps),
        "titre": str(config.get("montage", "generique", "titre",
                                default="Sources et licences")),
        "groupes": ordonnes,
        "libres": libres,
        "mention": str(config.get(
            "montage", "generique", "mention",
            default="Liste complète des auteurs dans la description.")),
    }


def _recoller(lignes: list[dict[str, Any]], seuil_frames: int) -> list[dict[str, Any]]:
    """Tient une ligne jusqu'à la suivante quand le trou est un artefact.

    Une ligne s'arrêtait à la fin acoustique de son dernier mot. Entre deux
    moitiés d'une même phrase, ça laissait le temps d'une respiration inter-
    mots — quelques images — pendant lesquelles le texte disparaissait puis
    revenait. Vu au rendu : un clignotement.

    Mais tous les trous ne sont pas des artefacts. Entre deux phrases, la
    voix se tait vraiment, et ce blanc-là est voulu : c'est la pause que
    `voice` insère. Le seuil est donc cette pause elle-même, pas un réglage
    de plus — un trou plus court qu'un silence de phrase n'en est pas un.
    """
    for index, ligne in enumerate(lignes[:-1]):
        fin = ligne["debut_frame"] + ligne["duree_frames"]
        trou = lignes[index + 1]["debut_frame"] - fin
        if 0 < trou < seuil_frames:
            ligne["duree_frames"] += trou
    return lignes


def build(
    alignment: dict[str, Any],
    shots: list[Shot],
    assets: dict[str, dict[str, Any]],
    audio: str | None = None,
    sons_dir: str | None = None,
    musique: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fps = int(config.get("montage", "fps", default=30))
    width, height = config.get("montage", "resolution", default=[1920, 1080])
    per_line = int(config.get("montage", "sous_titres", "mots_par_ligne", default=7))
    subtitles_on = bool(config.get("montage", "sous_titres", "actifs", default=True))
    plancher = int(config.get("montage", "sous_titres", "surlignage",
                              "duree_min_frames", default=3))

    transition_s = float(config.get("montage", "transitions", "duree_s", default=0.3))
    fondu_noir_s = float(config.get("montage", "transitions", "fondu_noir_s", default=0.55))
    amorce_s = float(config.get("montage", "transitions", "amorce_s", default=0.12))
    gain = float(config.get("montage", "transitions", "gain", default=0.22))
    sons_on = bool(config.get("montage", "transitions", "sons", default=True)) and sons_dir
    style_transition = str(config.get("montage", "transitions", "style", default="effets"))

    beats = alignment["beats"]
    total_s = float(alignment["duree_totale_s"])
    grouped = by_beat(shots)

    clips: list[dict[str, Any]] = []
    subtitles: list[dict[str, Any]] = []
    #: Les `surligne_a` qu'on n'a pas retrouvés dans la narration. Signalés
    #: par `check()` plutôt que corrigés en silence.
    introuvables: list[str] = []

    for index, beat in enumerate(beats):
        # A beat owns the screen until the next one starts, so the inter-beat
        # breath holds the last image instead of cutting to black.
        window_start = float(beat["debut_s"])
        window_end = (
            float(beats[index + 1]["debut_s"]) if index + 1 < len(beats) else total_s
        )
        beat_shots = grouped[beat["id"]]
        weight_total = sum(s.poids for s in beat_shots)

        cursor = window_start
        for position, shot in enumerate(beat_shots):
            share = (window_end - window_start) * shot.poids / weight_total
            is_last = position == len(beat_shots) - 1
            end = window_end if is_last else cursor + share

            start_frame = round(cursor * fps)
            end_frame = max(round(end * fps), start_frame + 1)
            asset = assets.get(shot.id, {})
            width_px = int(asset.get("largeur") or 0)
            height_px = int(asset.get("hauteur") or 0)

            est_video = asset.get("media") == "video"
            arrivee = _transition(
                len(clips), beat["id"], beat.get("acte", ""),
                clips[-1] if clips else None, shot.type,
                clips[-1]["type"] if clips else None, style_transition,
            )
            clips.append({
                "id": shot.id,
                "beat": beat["id"],
                "acte": beat.get("acte", ""),
                "type": shot.type,
                "entree": {
                    "type": arrivee,
                    "duree_frames": round(
                        (fondu_noir_s if arrivee in ("fondu_noir", "ouverture")
                         else transition_s) * fps
                    ),
                },
                "debut_frame": start_frame,
                "duree_frames": end_frame - start_frame,
                "image": None if est_video else asset.get("fichier"),
                # Archive footage: the file plus where to start inside it.
                # The clip keeps the beat's window; the source is trimmed.
                "video": asset.get("fichier") if est_video else None,
                "depart_s": asset.get("depart_s") if est_video else None,
                # Lets the renderer letterbox a tall archive document instead
                # of cropping it to a vertical slice of itself.
                # Also set for footage: archive film is almost always 4:3,
                # and cropping it to 16:9 costs a quarter of the height.
                "ratio": round(width_px / height_px, 4) if height_px else None,
                "mouvement": _movement(shot, (end_frame - start_frame) / fps),
                "motion": _motion_calee(shot, beat, start_frame, fps, introuvables),
                # La mise en page de la planche, calculée ici et non dans le
                # moteur : elle atterrit donc dans ce fichier, où elle se
                # relit et se corrige à la main. Déplacer une flèche, c'est
                # éditer un nombre et relancer `fresque render`.
                "collage": collage.compose(
                    shot, round(width_px / height_px, 4) if height_px else None,
                ) if shot.type == "collage" else None,
                "intention": shot.intention,
                # A sentence burned over the image. The viewer reads it while
                # the voice is saying something else — which is why it is
                # short, and why it is not a subtitle.
                "accroche": shot.accroche or None,
            })
            cursor = end

        if subtitles_on:
            subtitles.extend(_subtitles(beat, fps, per_line, plancher))

    # Chaque panneau graphique reçoit l'image du plan photographique le plus
    # proche, qui lui servira de texture de fond. C'est ce qui rattache un
    # panneau au film au lieu de le poser à côté — et c'est une décision du
    # pipeline, pas du moteur de rendu, au même titre qu'une coupe.
    #
    # Le plan qui précède d'abord : le spectateur vient de le voir, la
    # continuité est immédiate. À défaut le suivant, pour qu'un panneau en
    # ouverture ne se retrouve pas sur du noir.
    if config.get("montage", "motion", "scene", "opacite", default=0):
        derniere: str | None = None
        for clip in clips:
            if clip["type"] != "motion":
                derniere = clip.get("image") or derniere
            clip["fond_image"] = derniere if clip["type"] == "motion" else None
        suivante: str | None = None
        for clip in reversed(clips):
            if clip["type"] != "motion":
                suivante = clip.get("image") or suivante
            elif not clip["fond_image"]:
                clip["fond_image"] = suivante
    else:
        for clip in clips:
            clip["fond_image"] = None

    duration_frames = max(
        (c["debut_frame"] + c["duree_frames"] for c in clips), default=0
    )

    # The sound leads the cut rather than landing on it: the ear announces to
    # the eye what is coming. Clamped at zero, so the opening sound is not
    # pushed off the front of the film.
    sound_track: list[dict[str, Any]] = []
    if sons_on:
        amorce = round(amorce_s * fps)
        for clip in clips:
            name = TRANSITIONS[clip["entree"]["type"]]
            if not name:
                continue
            sound_track.append({
                "fichier": f"{sons_dir}/{name}.wav",
                "debut_frame": max(clip["debut_frame"] - amorce, 0),
                "gain": gain,
            })

    montage = {
        "version": 1,
        "fps": fps,
        "width": int(width),
        "height": int(height),
        "duree_frames": duration_frames,
        "duree_s": round(duration_frames / fps, 3),
        "source_timings": alignment.get("source", "inconnu"),
        # Un `surligne_a` qui ne se retrouve pas dans la narration est une
        # faute de frappe du plan visuel. On la porte jusqu'à `check()`
        # plutôt que de poser le surligneur au hasard.
        "surligne_introuvables": introuvables,
        "audio": audio,
        "template": config.active_template(),
        # The renderer decides nothing about how it looks: the art direction
        # travels with the montage, and a template redefines it wholesale.
        "style": {
            "palette": config.get("montage", "palette", default={}),
            "typographie": config.get("montage", "typographie", default={}),
            "traitement": config.get("montage", "traitement", default={}),
            "motion": config.get("montage", "motion", default={}),
            # Le moteur dessine les transitions, il n'en choisit ni la force
            # ni la couleur : un flash à pleine puissance sur une façade en
            # plein soleil blanchit l'écran, et c'est au template de dire
            # jusqu'où il va.
            "transitions": {
                "flash_opacite": float(config.get(
                    "montage", "transitions", "flash_opacite", default=0.35)),
                "glisse_pct": float(config.get(
                    "montage", "transitions", "glisse_pct", default=9)),
                "punch_pct": float(config.get(
                    "montage", "transitions", "punch_pct", default=5)),
            },
            # Le surlignage mot à mot. Le moteur interpole une couleur entre
            # deux bornes ; il ne décide ni laquelle, ni quand, ni combien de
            # temps — les fenêtres sont déjà dans `sous_titres[].mots`.
            "surlignage": {
                "actif": bool(config.get("montage", "sous_titres", "surlignage",
                                         "actif", default=False)),
                "couleur": str(config.get("montage", "sous_titres", "surlignage",
                                          "couleur", default="#F5BC4D")),
                "fondu_frames": int(config.get("montage", "sous_titres",
                                               "surlignage", "fondu_frames",
                                               default=3)),
            },
            "sous_titres": {
                "ligne_de_base_pct": float(config.get(
                    "montage", "sous_titres", "ligne_de_base_pct", default=90.8)),
                "voile": bool(config.get(
                    "montage", "sous_titres", "voile", default=True)),
            },
            # Papier, encres, trame, adhésif, profondeur de parallaxe. Le
            # moteur trace un bord déchiré et une trame d'impression ; il ne
            # décide d'aucune couleur, sans quoi une deuxième thématique
            # demanderait un deuxième composant.
            "collage": collage.style(),
        },
        "clips": clips,
        # Le lit sonore. Le moteur le boucle : il n'a pas à savoir combien de
        # fois, seulement à quel volume et sur quelle durée de fondu.
        "musique": {
            **musique,
            "fondu_entree_frames": round(float(config.get(
                "montage", "musique", "fondu_entree_s",
                default=config.get("montage", "musique", "fondu_s", default=0.0),
            )) * fps),
            "fondu_sortie_frames": round(float(config.get(
                "montage", "musique", "fondu_sortie_s",
                default=config.get("montage", "musique", "fondu_s", default=3.0),
            )) * fps),
        } if musique and config.get("montage", "musique", "actif", default=True)
        else None,
        "sons": sound_track,
        "sous_titres": _recoller(subtitles, round(float(config.get(
            "narration", "pause_phrase_s", default=0.45)) * fps)),
        # Les crédits voyagent avec le montage, pas dans une tête. Une piste
        # CC-BY n'est libre que si l'attribution suit jusqu'à la description
        # de la vidéo — la musique y figure donc au même titre qu'une image.
        "credits": [
            {
                "asset": asset.get("fichier"),
                "credit": asset.get("credit"),
                "url": asset.get("url"),
                "licence": asset.get("licence"),
                # Le carton groupe par licence et nomme les auteurs : il lui
                # faut les deux champs séparément, pas seulement la chaîne
                # de crédit toute faite.
                "auteur": asset.get("auteur"),
                "source": asset.get("source"),
            }
            for asset in assets.values()
            if asset.get("credit")
        ] + ([
            {
                "asset": musique.get("fichier"),
                "credit": config.get("montage", "musique", "credit"),
                "url": config.get("montage", "musique", "page_url"),
                "licence": config.get("montage", "musique", "licence"),
            }
        ] if musique and config.get("montage", "musique", "credit") else []),
    }

    # Le carton de fin prolonge le film. Sa durée entre dans `duree_frames`,
    # sinon le rendu s'arrête avant lui — et la musique se tairait à
    # l'ancienne fin, au milieu des crédits.
    carton = generique(montage["credits"], fps)
    if carton:
        carton["debut_frame"] = duration_frames
        montage["generique"] = carton
        montage["duree_frames"] = duration_frames + carton["duree_frames"]
        montage["duree_s"] = round(montage["duree_frames"] / fps, 3)
    return montage


def write(timeline: dict[str, Any], path: Path) -> None:
    path.write_text(
        json.dumps(timeline, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def check(timeline: dict[str, Any]) -> list[str]:
    """Structural problems that would show up as visible glitches."""
    problems: list[str] = []
    for ligne in timeline.get("surligne_introuvables", []):
        problems.append(
            f"{ligne} — `surligne_a` doit citer la narration du beat mot pour "
            "mot ; le surligneur garde son retard par défaut.")
    clips = timeline["clips"]
    cursor = 0
    fps = timeline["fps"]
    for clip in clips:
        # `plans_par_minute` is an intention the visual plan may or may not
        # honour; this is the same rule measured on the real audio, which is
        # the only place a slow montage can actually be caught.
        held = clip["duree_frames"] / fps
        plafond = plafond_s(clip["type"])
        if held > plafond:
            problems.append(
                f"{clip['id']} : plan tenu {held:.1f} s (max {plafond:g} s) — "
                "découper le beat en plans supplémentaires."
            )
        if clip["debut_frame"] != cursor:
            problems.append(
                f"{clip['id']} : trou ou chevauchement — attendu à la frame "
                f"{cursor}, commence à {clip['debut_frame']}."
            )
        if clip["duree_frames"] < timeline["fps"] // 2:
            problems.append(
                f"{clip['id']} : plan de {clip['duree_frames']} frames, "
                "trop court pour être lisible."
            )
        if not clip.get("image") and not clip.get("video") \
                and clip["type"] != "motion":
            problems.append(f"{clip['id']} : aucun visuel associé.")
        cursor = clip["debut_frame"] + clip["duree_frames"]
    return problems
