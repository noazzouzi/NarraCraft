"""Word-level timing — the spine the whole montage hangs from.

Une seule source : l'audio. `voice.synthesize` mesure la durée de chaque
beat sur le fichier qu'il vient d'écrire, `aligner.force` affine ensuite la
position des mots à l'intérieur. Les deux écrivent la même structure.

Ce module a longtemps porté un troisième producteur, `estimate()`, qui
déduisait les durées d'un débit annoncé en mots par minute. Il a été
supprimé : un débit visé n'a jamais décrit ce que le moteur de voix fait
vraiment, et l'écart se payait en aval. On demande au moteur, on mesure.

Everything downstream reads `alignment.json` and nothing else. In particular
it never reads timestamps returned by a TTS engine — see CLAUDE.md.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import config

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
