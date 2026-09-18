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

        samples, rate = kokoro.create(beat.text, voice=voice, speed=speed, lang=lang)
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
