"""Synthèse de la voix, et l'alignement qui en découle.

Un fichier audio par beat, puis une piste unique concaténée. Synthétiser
beat par beat achète deux choses : un beat se refait seul, et — surtout —
la durée **réelle** de chaque beat est mesurée au lieu d'être devinée.

Ces durées réelles deviennent les points de coupe du montage, donc chaque
coupe tombe exactement là où la narration passe à autre chose. La position
d'un mot *à l'intérieur* d'un beat reste répartie au poids syllabique :
aucun des moteurs n'expose de timing par mot, et sur une trentaine de mots
la répartition pondérée suffit aux sous-titres. `alignment.json` dit lequel
est lequel dans son champ `source`.

DEUX MOTEURS
============
`voix.provider` choisit :

- `kokoro` — local, gratuit, sans réseau. Une seule voix française.
- `edge` — les voix neuronales de Microsoft Edge, gratuites et sans clé,
  mais par le réseau. Sept voix masculines francophones.

Ce qu'ils ne font pas pareil, et qui compte : le silence qu'ils laissent
autour d'une phrase. Mesuré sur trois phrases courtes —

    moteur                          tête    queue
    kokoro ff_siwis                0,042 s  0,149 s
    fr-FR-RemyMultilingualNeural   0,174 s  0,587 s
    fr-FR-HenriNeural              0,213 s  0,918 s

Edge emballe donc chaque phrase dans plus d'une seconde de vide. Sur les
quatre cents phrases d'un documentaire de quinze minutes, c'est plusieurs
minutes de blanc que personne n'a demandées, et un rythme qu'aucun réglage
ne rattrape ensuite. Le moteur Edge rogne donc son propre silence, et le
pipeline pose lui-même la pause qu'il veut (`narration.pause_phrase_s`).

Kokoro n'est pas touché : son silence est court, il est déjà compensé, et
changer sa mesure décalerait les montages existants.
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


# --- Les moteurs -------------------------------------------------------------

class Moteur:
    """Ce qu'un moteur de voix doit savoir faire : dire une phrase.

    `pause_naturelle_s` est le silence que le moteur laisse déjà après un
    point. Le pipeline l'ôte de celui qu'il ajoute, sinon les deux
    s'additionnent et la pause réelle dépasse celle qui est demandée.
    """

    nom: str = ""
    pause_naturelle_s: float = 0.0

    def dire(self, phrase: str):  # pragma: no cover - interface
        raise NotImplementedError

    def fiche(self) -> dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError


class MoteurKokoro(Moteur):
    nom = "kokoro"
    #: Mesuré sur ff_siwis : 0,10 s à vitesse 0,75, 0,12 s à 0,82 — à peine
    #: plus qu'après une virgule.
    pause_naturelle_s = 0.10

    def __init__(self) -> None:
        self.kokoro = _engine()
        self.voice = str(config.get("voix", "kokoro", "voice", default="ff_siwis"))
        self.lang = str(config.get("voix", "kokoro", "lang", default="fr-fr"))
        self.speed = float(config.get("voix", "kokoro", "speed", default=0.82))

    def dire(self, phrase: str):
        return self.kokoro.create(
            phrase, voice=self.voice, speed=self.speed, lang=self.lang
        )

    def fiche(self) -> dict[str, Any]:
        return {
            "provider": "kokoro",
            "voice": self.voice,
            "lang": self.lang,
            "speed": self.speed,
        }


#: Sous ce niveau, on considère que le moteur ne dit rien. Relevé sur les
#: deux voix Edge : leur silence est un vrai zéro numérique, pas un souffle.
_SEUIL_SILENCE = 0.01

#: Ce qu'on laisse de part et d'autre après avoir rogné. Sans marge, une
#: occlusive initiale — un « p », un « t » — se fait couper net.
_MARGE_ROGNAGE_S = 0.03


def _rogner(samples, rate: int):
    """Ôte le silence de tête et de queue, en gardant une marge."""
    import numpy as np

    x = np.asarray(samples, dtype="float32")
    fort = np.abs(x) > _SEUIL_SILENCE
    if not fort.any():
        return x
    marge = int(_MARGE_ROGNAGE_S * rate)
    debut = max(int(np.argmax(fort)) - marge, 0)
    fin = min(len(x) - int(np.argmax(fort[::-1])) + marge, len(x))
    return x[debut:fin]


class MoteurEdge(Moteur):
    """Les voix neuronales de Microsoft Edge. Gratuites, sans clé, en ligne.

    Le silence est rogné à la sortie : voir la mesure en tête de module.
    Après rognage il ne reste rien à compenser, donc la pause que pose le
    pipeline est celle qu'il demande.
    """

    nom = "edge"
    pause_naturelle_s = 0.0

    def __init__(self) -> None:
        self.voice = str(config.get("voix", "edge", "voice", default="fr-FR-HenriNeural"))
        self.rate = str(config.get("voix", "edge", "rate", default="+0%"))
        self.volume = str(config.get("voix", "edge", "volume", default="+0%"))
        self.pitch = str(config.get("voix", "edge", "pitch", default="+0Hz"))
        try:
            import edge_tts  # noqa: F401
            import soundfile  # noqa: F401
        except ImportError as error:  # pragma: no cover - environment dependent
            raise VoiceError(
                "edge-tts n'est pas installé : pip install edge-tts soundfile"
            ) from error

    def dire(self, phrase: str):
        import asyncio
        import io
        import os

        import edge_tts
        import soundfile as sf

        async def chercher() -> bytes:
            # `proxy` sert les réseaux d'entreprise ; sans variable
            # d'environnement il vaut None et ne change rien.
            parole = edge_tts.Communicate(
                phrase, self.voice, rate=self.rate,
                volume=self.volume, pitch=self.pitch,
                proxy=os.environ.get("HTTPS_PROXY"),
            )
            tampon = io.BytesIO()
            async for morceau in parole.stream():
                if morceau["type"] == "audio":
                    tampon.write(morceau["data"])
            return tampon.getvalue()

        brut = asyncio.run(chercher())
        if not brut:
            raise VoiceError(
                f"Edge n'a rien rendu pour « {phrase[:40]}… » — "
                f"vérifier la voix `{self.voice}` et la connexion."
            )
        samples, rate = sf.read(io.BytesIO(brut), dtype="float32", always_2d=False)
        return _rogner(samples, rate), rate

    def fiche(self) -> dict[str, Any]:
        return {
            "provider": "edge",
            "voice": self.voice,
            "rate": self.rate,
            "volume": self.volume,
            "pitch": self.pitch,
        }


MOTEURS: dict[str, type[Moteur]] = {"kokoro": MoteurKokoro, "edge": MoteurEdge}


def moteur() -> Moteur:
    """Le moteur que `voix.provider` désigne."""
    nom = str(config.get("voix", "provider", default="kokoro"))
    classe = MOTEURS.get(nom)
    if classe is None:
        raise VoiceError(
            f"`voix.provider: {nom}` n'existe pas. "
            f"Choisir parmi : {', '.join(sorted(MOTEURS))}."
        )
    return classe()


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

def _say_beat(machine: Moteur, texte: str, phrase_gap: float):
    """Synthétise un beat, phrase par phrase, avec du vrai silence entre.

    Aucun des moteurs ne marque une vraie respiration après un point : Kokoro
    laisse un dixième de seconde, à peine plus qu'après une virgule, et
    aucun réglage ne l'allonge. Edge, lui, en laisse trop — c'est pourquoi
    il rogne.

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
        return machine.dire(texte)

    morceaux: list[Any] = []
    rate = SAMPLE_RATE
    for index, phrase in enumerate(phrases):
        samples, rate = machine.dire(phrase)
        morceaux.append(np.asarray(samples, dtype="float32"))
        manquant = phrase_gap - machine.pause_naturelle_s
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

    machine = moteur()
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

        samples, rate = _say_beat(machine, beat.text, phrase_gap)
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
        # `source` dit d'où viennent les nombres, pas quel moteur a parlé :
        # les deux moteurs donnent des bornes de beat mesurées, donc la même
        # qualité temporelle. `voix.provider` dit qui a parlé.
        "source": "kokoro",
        "avertissement": (
            "Durées de beat mesurées sur l'audio réel. Position des mots à "
            "l'intérieur d'un beat répartie par syllabes : les coupes du "
            "montage sont exactes, les sous-titres sont au mot près."
        ),
        "voix": machine.fiche(),
        "duree_totale_s": round(len(track) / SAMPLE_RATE, 3),
        "nb_beats": len(entries),
        "nb_mots": sum(len(e["mots"]) for e in entries),
        "beats": entries,
    }
