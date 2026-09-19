"""Build 06-timeline.json — the single source of truth for the montage.

All timing arithmetic happens here, in code, from the real numbers in
`alignment.json`. No language model ever computes a timecode (CLAUDE.md).

The output is renderer-neutral on purpose: Remotion consumes it today, and an
NLE exporter can consume the same file tomorrow.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import config
from .shots import Shot, by_beat


def _jitter(seed: str, salt: str) -> float:
    """Stable pseudo-random in [0, 1).

    Ken Burns applied identically to every shot reads as a template. Varying
    it per shot — but deterministically, so a re-render is identical — is what
    makes the movement feel authored rather than generated.
    """
    digest = hashlib.sha256(f"{seed}:{salt}".encode()).digest()
    return int.from_bytes(digest[:4], "big") / 2**32


def _movement(shot: Shot) -> dict[str, Any]:
    kb = config.get("montage", "ken_burns", default={}) or {}
    zoom_min = float(kb.get("zoom_min", 1.04))
    zoom_max = float(kb.get("zoom_max", 1.18))
    drift_max = float(kb.get("derive_max_pct", 6)) / 100.0
    rotation_max = float(kb.get("micro_rotation_deg", 0.4))
    easing = kb.get("easing", "easeInOutCubic")

    span = zoom_max - zoom_min
    low = zoom_min + span * 0.25 * _jitter(shot.id, "low")
    high = zoom_max - span * 0.25 * _jitter(shot.id, "high")
    drift = drift_max * (0.4 + 0.6 * _jitter(shot.id, "drift"))
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
        start = {"scale": low, "x": 0.0, "y": 0.0}
        end = {"scale": low + 0.012, "x": 0.0, "y": 0.0}

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
                previous_type: str | None) -> str:
    """Pick how this shot arrives, from where it sits in the story.

    The rule is deliberately coarse, because a fine one would be a taste
    engine and taste is not what code is for here. What the code knows for
    certain is the structure: whether the idea continues, changes, or the act
    turns over. That is enough to stop every cut looking the same, which was
    the actual complaint.
    """
    if position == 0:
        return "ouverture"
    if previous is None:
        return "coupe"

    if clip_act != previous.get("acte"):
        return "fondu_noir"

    # A graphic panel is a different medium arriving; sliding it in says so,
    # and a hard cut into one reads as a glitch.
    if "motion" in (shot_type, previous_type):
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
    lines: list[list[dict[str, Any]]] = []
    index = 0
    slack = max(1, per_line // 3)

    while index < len(words):
        remaining = len(words) - index
        if remaining <= per_line + slack:
            lines.append(words[index:])
            break

        window = words[index:index + per_line + slack]
        cut = None
        # Prefer the latest clean break inside the window, never earlier than
        # a line too short to be worth its own card.
        for offset in range(len(window) - 1, max(per_line - slack, 1) - 1, -1):
            if window[offset]["tx"].rstrip().endswith((".", "!", "?", "…", ",", ";", ":")):
                cut = offset + 1
                break
        cut = cut or per_line
        lines.append(words[index:index + cut])
        index += cut

    return [line for line in lines if line]


def _subtitles(beat: dict[str, Any], fps: int, per_line: int) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for chunk in _subtitle_lines(beat["mots"], per_line):
        first, last = chunk[0]["debut_s"], chunk[-1]["fin_s"]
        debut = round(first * fps)
        fin = max(round(last * fps), debut + 1)
        lines.append({
            "texte": " ".join(w.get("tx", w["t"]) for w in chunk),
            "debut_frame": debut,
            "duree_frames": fin - debut,
        })
    return lines


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

    transition_s = float(config.get("montage", "transitions", "duree_s", default=0.3))
    fondu_noir_s = float(config.get("montage", "transitions", "fondu_noir_s", default=0.55))
    amorce_s = float(config.get("montage", "transitions", "amorce_s", default=0.12))
    gain = float(config.get("montage", "transitions", "gain", default=0.22))
    sons_on = bool(config.get("montage", "transitions", "sons", default=True)) and sons_dir

    beats = alignment["beats"]
    total_s = float(alignment["duree_totale_s"])
    grouped = by_beat(shots)

    clips: list[dict[str, Any]] = []
    subtitles: list[dict[str, Any]] = []

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
                clips[-1]["type"] if clips else None,
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
                "mouvement": _movement(shot),
                "motion": shot.motion,
                "intention": shot.intention,
                # A sentence burned over the image. The viewer reads it while
                # the voice is saying something else — which is why it is
                # short, and why it is not a subtitle.
                "accroche": shot.accroche or None,
            })
            cursor = end

        if subtitles_on:
            subtitles.extend(_subtitles(beat, fps, per_line))

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

    return {
        "version": 1,
        "fps": fps,
        "width": int(width),
        "height": int(height),
        "duree_frames": duration_frames,
        "duree_s": round(duration_frames / fps, 3),
        "source_timings": alignment.get("source", "inconnu"),
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
        },
        "clips": clips,
        # Le lit sonore. Le moteur le boucle : il n'a pas à savoir combien de
        # fois, seulement à quel volume et sur quelle durée de fondu.
        "musique": {
            **musique,
            "fondu_frames": round(
                float(config.get("montage", "musique", "fondu_s", default=3.0)) * fps
            ),
        } if musique and config.get("montage", "musique", "actif", default=True)
        else None,
        "sons": sound_track,
        "sous_titres": subtitles,
        # Les crédits voyagent avec le montage, pas dans une tête. Une piste
        # CC-BY n'est libre que si l'attribution suit jusqu'à la description
        # de la vidéo — la musique y figure donc au même titre qu'une image.
        "credits": [
            {
                "asset": asset.get("fichier"),
                "credit": asset.get("credit"),
                "url": asset.get("url"),
                "licence": asset.get("licence"),
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


def write(timeline: dict[str, Any], path: Path) -> None:
    path.write_text(
        json.dumps(timeline, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def check(timeline: dict[str, Any]) -> list[str]:
    """Structural problems that would show up as visible glitches."""
    problems: list[str] = []
    clips = timeline["clips"]
    cursor = 0
    fps = timeline["fps"]
    longest = float(config.get("montage", "duree_plan_max_s", default=10))
    for clip in clips:
        # `plans_par_minute` is an intention the visual plan may or may not
        # honour; this is the same rule measured on the real audio, which is
        # the only place a slow montage can actually be caught.
        held = clip["duree_frames"] / fps
        if held > longest:
            problems.append(
                f"{clip['id']} : plan tenu {held:.1f} s (max {longest:g} s) — "
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
