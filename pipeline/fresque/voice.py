"""Voice synthesis with Kokoro, and the alignment derived from it.

One audio file per beat, then a single concatenated track. Synthesising beat
by beat buys two things: a beat can be regenerated alone, and — more
importantly — each beat's **real** duration is measured rather than guessed.

Those real durations become the cut points of the montage, so every cut lands
exactly where the narration moves on. Word positions inside a beat are still
distributed by syllable weight: Kokoro's ONNX build exposes no per-word
timings, and over a 30-word span the weighted split is accurate enough for
subtitles. `alignment.json` records which is which in its `source` field.
"""
from __future__ import annotations

import re
import wave
from pathlib import Path
from typing import Any, Callable

from . import config
from .align import syllables, _tokenize  # noqa: PLC2701 — same module family
from .script_parser import Beat, Script

SAMPLE_RATE = 24_000


class VoiceError(RuntimeError):
    pass


def _paths() -> tuple[Path, Path]:
    root = config.repo_root()
    model = root / str(config.get("voix", "kokoro", "model", default="models/kokoro-v1.0.onnx"))
    voices = root / str(config.get("voix", "kokoro", "voices", default="models/voices-v1.0.bin"))
    missing = [p for p in (model, voices) if not p.is_file()]
    if missing:
        raise VoiceError(
            "Modèle Kokoro absent :\n  "
            + "\n  ".join(str(p) for p in missing)
            + "\n\nLes télécharger depuis les releases de kokoro-onnx :\n"
            "  https://github.com/thewh1teagle/kokoro-onnx/releases"
        )
    return model, voices


def _engine():
    try:
        from kokoro_onnx import Kokoro
    except ImportError as error:  # pragma: no cover - environment dependent
        raise VoiceError(
            "kokoro-onnx n'est pas installé : pip install kokoro-onnx soundfile"
        ) from error
    model, voices = _paths()
    return Kokoro(str(model), str(voices))


def _write_wav(path: Path, samples, rate: int) -> None:
    import numpy as np

    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(np.asarray(samples, dtype="float32"), -1.0, 1.0)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(rate)
        fh.writeframes((pcm * 32767).astype("<i2").tobytes())


def _time_words(beat: Beat, start: float, duration: float) -> list[dict[str, Any]]:
    """Spread a beat's words across its measured duration.

    Punctuation pauses are taken out first, then the remaining time is split
    between words in proportion to their syllable count.
    """
    words = _tokenize(beat.text)
    pauses = [pause for _, _, pause in words]
    pause_total = sum(pauses[:-1]) if len(pauses) > 1 else 0.0
    speech = max(duration - pause_total, duration * 0.35)
    # If punctuation would eat the whole beat, scale the pauses down instead.
    scale = (duration - speech) / pause_total if pause_total else 0.0

    weights = [syllables(word) for word, _, _ in words]
    total_weight = sum(weights) or 1

    clock = start
    timed: list[dict[str, Any]] = []
    for index, ((word, display, pause), weight) in enumerate(zip(words, weights)):
        span = speech * weight / total_weight
        timed.append({
            "t": word,
            "tx": display,
            "debut_s": round(clock, 3),
            "fin_s": round(clock + span, 3),
        })
        clock += span
        if index < len(words) - 1:
            clock += pause * scale
    return timed


#: Fin de phrase. Le point d'un « M. » ou d'un « 1. » n'en est pas une, d'où
#: l'exigence d'un espace et d'une majuscule — et le script, de toute façon,
#: ne doit plus contenir ni l'un ni l'autre (voir `lint.TTS_HAZARDS`).
_FIN_PHRASE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý])")

#: Ce que Kokoro laisse lui-même après un point, mesuré sur ff_siwis :
#: 0,10 s à vitesse 0,75, 0,12 s à 0,82 — à peine plus qu'après une virgule.
#: On l'ôte du silence qu'on ajoute, sinon les deux s'additionnent et la
#: pause réelle dépasse celle qui est demandée, de huit pour cent sur un
#: texte à phrases courtes.
_PAUSE_KOKORO_S = 0.10


def _say_beat(kokoro, texte: str, voice: str, speed: str, lang: str,
              phrase_gap: float):
    """Synthétise un beat, phrase par phrase, avec du vrai silence entre.

    Kokoro ne marque qu'un dixième de seconde après un point — mesuré à
    0,10 s à vitesse 0,75, à peine plus qu'après une virgule. Ce n'est pas
    une respiration, et aucun réglage du moteur ne l'allonge.

    Or le silence est la moitié du rythme : la voix de Frontier se tait un
    tiers du temps (`docs/analyse-frontier.md`). On découpe donc le beat à
    la phrase et on insère le silence nous-mêmes.

    Effet de bord voulu : chaque phrase reçoit sa propre intonation de fin,
    ce qui est exactement ce qu'on cherche pour des phrases de quatre mots.

    Et effet de bord utile : `align.estimate` modélisait déjà ces pauses
    comme du temps réel. Elles le deviennent, donc l'estimation cesse d'être
    optimiste — elle dépassait la durée réelle de 12 % sur un texte à
    phrases courtes.
    """
    import numpy as np

    phrases = [p.strip() for p in _FIN_PHRASE.split(texte) if p.strip()]
    if len(phrases) <= 1:
        return kokoro.create(texte, voice=voice, speed=speed, lang=lang)

    morceaux: list[Any] = []
    rate = SAMPLE_RATE
    for index, phrase in enumerate(phrases):
        samples, rate = kokoro.create(phrase, voice=voice, speed=speed, lang=lang)
        morceaux.append(np.asarray(samples, dtype="float32"))
        manquant = phrase_gap - _PAUSE_KOKORO_S
        if index < len(phrases) - 1 and manquant > 0:
            morceaux.append(np.zeros(int(manquant * rate), dtype="float32"))
    return np.concatenate(morceaux), rate


def synthesize(
    script: Script,
    audio_dir: Path,
    progress: Callable[[int, int, float], None] | None = None,
) -> dict[str, Any]:
    """Render every beat, concatenate, and return the alignment."""
    import numpy as np

    kokoro = _engine()
    voice = str(config.get("voix", "kokoro", "voice", default="ff_siwis"))
    lang = str(config.get("voix", "kokoro", "lang", default="fr-fr"))
    speed = float(config.get("voix", "kokoro", "speed", default=0.82))
    beat_gap = float(config.get("narration", "pause_entre_beats_s", default=0.4))
    act_gap = float(config.get("narration", "pause_entre_actes_s", default=1.2))
    phrase_gap = float(config.get("narration", "pause_phrase_s", default=0.45))

    beats_dir = audio_dir / "beats"
    beats_dir.mkdir(parents=True, exist_ok=True)

    pieces: list[Any] = []
    entries: list[dict[str, Any]] = []
    clock = 0.0
    previous_act: str | None = None

    for index, beat in enumerate(script.beats):
        if previous_act is not None:
            gap = act_gap if beat.act != previous_act else beat_gap
            pieces.append(np.zeros(int(gap * SAMPLE_RATE), dtype="float32"))
            clock += gap
        previous_act = beat.act

        samples, rate = _say_beat(kokoro, beat.text, voice, speed, lang, phrase_gap)
        if rate != SAMPLE_RATE:
            raise VoiceError(f"Fréquence inattendue : {rate} Hz (attendu {SAMPLE_RATE}).")

        samples = np.asarray(samples, dtype="float32")
        duration = len(samples) / rate
        _write_wav(beats_dir / f"{beat.id}.wav", samples, rate)
        pieces.append(samples)

        entries.append({
            "id": beat.id,
            "acte": beat.act,
            "debut_s": round(clock, 3),
            "fin_s": round(clock + duration, 3),
            "duree_s": round(duration, 3),
            "mots": _time_words(beat, clock, duration),
        })
        clock += duration

        if progress:
            progress(index + 1, len(script.beats), clock)

    track = np.concatenate(pieces) if pieces else np.zeros(0, dtype="float32")
    _write_wav(audio_dir / "voix.wav", track, SAMPLE_RATE)

    return {
        "source": "kokoro",
        "avertissement": (
            "Durées de beat mesurées sur l'audio réel. Position des mots à "
            "l'intérieur d'un beat répartie par syllabes : les coupes du "
            "montage sont exactes, les sous-titres sont au mot près."
        ),
        "voix": {"provider": "kokoro", "voice": voice, "lang": lang, "speed": speed},
        "duree_totale_s": round(len(track) / SAMPLE_RATE, 3),
        "nb_beats": len(entries),
        "nb_mots": sum(len(e["mots"]) for e in entries),
        "beats": entries,
    }
