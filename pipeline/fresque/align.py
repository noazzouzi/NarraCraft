"""Word-level timing — the spine the whole montage hangs from.

Two producers, one format:

  * `estimate()`  derives timings from word counts. No audio, no API, no cost.
  * forced alignment (jalon 3) will realign the known script text onto real
    audio and write the same structure.

Everything downstream reads `alignment.json` and nothing else. In particular
it never reads timestamps returned by a TTS engine — see CLAUDE.md.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import config
from .script_parser import Beat, Script

WORD_RE = re.compile(r"[\w'’-]+|[^\w\s]", re.UNICODE)
VOWEL_GROUP_RE = re.compile(r"[aeiouyàâäéèêëîïôöùûüœæ]+", re.IGNORECASE)
SENTENCE_END = set(".!?…")
CLAUSE_END = set(",;:")


def syllables(word: str) -> int:
    """Approximate French syllable count.

    Vowel groups, minus the silent final `e`. Crude, but it only has to rank
    words against each other inside a beat — and it is dramatically better
    than spreading time uniformly, which makes subtitles drift on long words.
    """
    count = len(VOWEL_GROUP_RE.findall(word))
    lowered = word.lower()
    if count > 1 and len(lowered) > 2 and lowered.endswith("e") and not lowered.endswith(("ée", "ie", "ue", "oue")):
        count -= 1
    return max(count, 1)


def _tokenize(text: str) -> list[tuple[str, str, float]]:
    """Return (word, display, pause_after) triples.

    `word` is bare, for timing and for the speech engine. `display` keeps the
    trailing punctuation, because subtitles stripped of their commas read as
    machine output — which is exactly the impression we are avoiding.
    """
    phrase_pause = float(config.get("narration", "pause_phrase_s", default=0.45))
    clause_pause = float(config.get("narration", "pause_virgule_s", default=0.18))

    tokens = WORD_RE.findall(text)
    words: list[tuple[str, str, float]] = []
    for token in tokens:
        if VOWEL_GROUP_RE.search(token) or token.isalnum():
            words.append((token, token, 0.0))
        elif words:
            word, display, existing = words[-1]
            pause = phrase_pause if token in SENTENCE_END else (
                clause_pause if token in CLAUSE_END else 0.0
            )
            glue = "" if token in ")]}»,;:.!?…" else " "
            words[-1] = (word, f"{display}{glue}{token}", max(existing, pause))
    return words


def _time_beat(beat: Beat, clock: float, wpm: float) -> dict[str, Any]:
    words = _tokenize(beat.text)
    if not words:
        raise ValueError(f"{beat.id} : aucun mot exploitable.")

    speech_s = len(words) / wpm * 60.0
    weights = [syllables(word) for word, _, _ in words]
    total_weight = sum(weights)

    start = clock
    timed: list[dict[str, Any]] = []
    for (word, display, pause_after), weight in zip(words, weights):
        duration = speech_s * weight / total_weight
        timed.append({
            "t": word,
            "tx": display,
            "debut_s": round(clock, 3),
            "fin_s": round(clock + duration, 3),
        })
        clock += duration + pause_after

    # Trailing pause belongs to the inter-beat gap, not to the beat itself.
    clock -= words[-1][2]

    return {
        "id": beat.id,
        "acte": beat.act,
        "debut_s": round(start, 3),
        "fin_s": round(clock, 3),
        "duree_s": round(clock - start, 3),
        "mots": timed,
    }


def estimate(script: Script) -> dict[str, Any]:
    wpm = float(config.get("narration", "mots_par_minute", default=140))
    beat_gap = float(config.get("narration", "pause_entre_beats_s", default=0.4))
    act_gap = float(config.get("narration", "pause_entre_actes_s", default=1.2))

    clock = 0.0
    previous_act: str | None = None
    beats: list[dict[str, Any]] = []

    for beat in script.beats:
        if previous_act is not None:
            clock += act_gap if beat.act != previous_act else beat_gap
        previous_act = beat.act
        entry = _time_beat(beat, clock, wpm)
        beats.append(entry)
        clock = entry["fin_s"]

    return {
        "source": "estimate",
        "avertissement": (
            "Timings estimés à partir du compte de mots, sans audio. "
            "Remplacés par l'alignement forcé dès que la voix est générée."
        ),
        "mots_par_minute": wpm,
        "duree_totale_s": round(clock, 3),
        "nb_beats": len(beats),
        "nb_mots": sum(len(b["mots"]) for b in beats),
        "beats": beats,
    }


def write(alignment: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(alignment, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def format_duration(seconds: float) -> str:
    minutes, secs = divmod(int(round(seconds)), 60)
    return f"{minutes} min {secs:02d} s"
