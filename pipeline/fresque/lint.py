"""Mechanically enforce what the writing skills can only recommend.

A skill can say "no sentence over 25 words" and "write the hours out in
full". Nothing checks it. On a 2200-word script something always slips
through, and it is discovered by hearing it in the finished voice-over.

So the rules move here, where they are binding. The skill writes, this
refuses, the skill fixes, and only output that already clears the bar
reaches the human checkpoint.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterator

from . import align, config
from .script_parser import Beat, Script

#: Le plan temporel estimé du script, tel que `align.estimate` le produit.
#: Les règles qui parlent de durée le reçoivent au lieu de la recalculer :
#: deux arithmétiques parallèles divergent, et c'est toujours celle du lint
#: qui a tort au moment où ça compte.
Plan = dict

WORD_RE = re.compile(r"\b[\w'’-]+\b", re.UNICODE)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
ACRONYM_RE = re.compile(r"\b[A-ZÀ-Ý]{2,}\b")


@dataclass(frozen=True)
class Violation:
    beat: str
    rule: str
    message: str
    blocking: bool = True
    excerpt: str = ""


def _words(text: str) -> list[str]:
    return WORD_RE.findall(text)


# --- Rules -------------------------------------------------------------------
#
# Each rule takes the whole script and yields violations. Keeping them
# separate means a new rule is a new function, not an edit to a big one.

def rule_beat_length(script: Script, plan: Plan) -> Iterator[Violation]:
    low, high = config.get("controle", "mots_par_beat", default=[25, 60])
    for beat in script.beats:
        count = beat.word_count
        if count < low:
            yield Violation(
                beat.id, "longueur-beat",
                f"{count} mots — sous le minimum de {low}. Un plan aussi court "
                "hache le montage.",
            )
        elif count > high:
            yield Violation(
                beat.id, "longueur-beat",
                f"{count} mots — au-dessus du maximum de {high}. Une image "
                "tenue aussi longtemps fait décrocher.",
            )


def rule_sentence_length(script: Script, plan: Plan) -> Iterator[Violation]:
    limit = int(config.get("controle", "mots_par_phrase_max", default=25))
    for beat in script.beats:
        for sentence in SENTENCE_SPLIT_RE.split(beat.text):
            count = len(_words(sentence))
            if count > limit:
                yield Violation(
                    beat.id, "longueur-phrase",
                    f"phrase de {count} mots (max {limit}) — le spectateur ne "
                    "peut pas relire.",
                    excerpt=sentence.strip()[:90],
                )


#: Patterns the French speech synthesiser mispronounces or reads flat.
#: Each entry is (label, regex, what to write instead).
TTS_HAZARDS: list[tuple[str, re.Pattern[str], str]] = [
    ("heure", re.compile(r"\b\d{1,2}\s?h\s?\d{2}\b"), "écrire l'heure en toutes lettres"),
    ("pourcentage", re.compile(r"%"), "écrire « pour cent »"),
    ("unité", re.compile(r"\b\d+\s?(km/h|kg|m²|m2|°C|°)\b"), "écrire l'unité en toutes lettres"),
    ("civilité", re.compile(r"\bM\.\s+[A-ZÀ-Ý]"), "écrire « Monsieur »"),
    ("abréviation", re.compile(r"n°|N°|§"), "écrire « numéro », « paragraphe »"),
    ("ordinal", re.compile(r"\b\d+(er|ère|ème|e)\b"), "écrire « premier », « deuxième »"),
    ("esperluette", re.compile(r"[&+=]"), "écrire « et », « plus », « égale »"),
    ("parenthèse", re.compile(r"[()\[\]]"), "lue à plat : faire une phrase à part ou supprimer"),
    ("suspension", re.compile(r"\.{3}|…"), "résultat imprévisible : faire une phrase courte"),
    ("tiret cadratin", re.compile(r"[—–]"), "résultat imprévisible : ponctuer autrement"),
]


def rule_tts_hazards(script: Script, plan: Plan) -> Iterator[Violation]:
    for beat in script.beats:
        for label, pattern, remedy in TTS_HAZARDS:
            match = pattern.search(beat.text)
            if match:
                yield Violation(
                    beat.id, f"synthèse-{label}",
                    f"{match.group(0)!r} — {remedy}.",
                    excerpt=beat.text[max(0, match.start() - 30):match.end() + 30].strip(),
                )


def rule_acronyms(script: Script, plan: Plan) -> Iterator[Violation]:
    spoken = {a.upper() for a in config.get("controle", "acronymes_prononces", default=[])}
    for beat in script.beats:
        for found in ACRONYM_RE.findall(beat.text):
            if found in spoken:
                continue
            yield Violation(
                beat.id, "synthèse-acronyme",
                f"{found} — s'il s'épelle, le ponctuer ("
                f"{'.'.join(found)}.) ; sinon l'ajouter à "
                "`controle.acronymes_prononces`.",
            )


def rule_forbidden(script: Script, plan: Plan) -> Iterator[Violation]:
    banned = [b.lower() for b in config.get("controle", "interdits", default=[])]
    for beat in script.beats:
        lowered = beat.text.lower()
        for phrase in banned:
            if phrase in lowered:
                yield Violation(
                    beat.id, "interdit",
                    f"« {phrase} » — formule proscrite par la charte.",
                )


def rule_word_budget(script: Script, plan: Plan) -> Iterator[Violation]:
    """La cible est une durée, alors on compare des durées.

    Cette règle multipliait la durée cible par `mots_par_minute`. C'était
    juste tant que la narration était continue : `mots_par_minute` est le
    débit **parlé**, et les silences s'ajoutent par-dessus. Dès qu'on laisse
    de l'air — ce que la mesure de Frontier impose, 34 % du temps sans voix —
    le compte de mots cesse de prédire la durée, et un script « dans le
    budget » dépasse sa cible d'un tiers.

    On demande donc la durée à `align.estimate`, c'est-à-dire au code même
    qui la calculera ensuite. Une seule source de vérité temporelle, comme
    partout ailleurs dans ce pipeline.
    """
    target_min = float(config.get("production", "duree_cible_min", default=15))
    tolerance = float(config.get("production", "tolerance_duree_pct", default=15)) / 100

    cible_s = target_min * 60
    reelle_s = float(plan["duree_totale_s"])
    drift = (reelle_s - cible_s) / cible_s if cible_s else 0.0

    if abs(drift) > tolerance:
        yield Violation(
            "—", "budget",
            f"{align.format_duration(reelle_s)} estimées pour une cible de "
            f"{target_min:g} min ({drift:+.0%}, tolérance ±{tolerance:.0%}) — "
            f"{script.word_count} mots, silences compris.",
            # Length is a judgement call the human owns; flag it, don't block.
            blocking=False,
        )


def rule_air(script: Script, plan: Plan) -> Iterator[Violation]:
    """Le silence est un élément du script, pas un reste.

    Mesuré sur les documentaires Frontier : la voix se tait 34 % du temps
    dans l'un, 21 % dans l'autre (`docs/analyse-frontier.md`). C'est là que
    le rythme se joue — un plan tient parce qu'on ne parle pas dessus.

    La part de silence n'est pas qu'un réglage : elle dépend de l'écriture.
    Un beat fait d'une seule longue phrase ne respire nulle part, quelles que
    soient les pauses configurées. Cette règle attrape exactement ça.
    """
    minimum = float(config.get("controle", "part_silence_min", default=0.0))
    if minimum <= 0:
        return

    totale = float(plan["duree_totale_s"])
    parlee = sum(
        mot["fin_s"] - mot["debut_s"]
        for beat in plan["beats"] for mot in beat["mots"]
    )
    if totale <= 0:
        return

    part = 1 - parlee / totale
    if part < minimum:
        yield Violation(
            "—", "silence",
            f"{part:.0%} de silence pour un minimum de {minimum:.0%} — "
            "couper les phrases plus court. Chaque point produit une pause ; "
            "une phrase de vingt mots n'en produit qu'une.",
            blocking=False,
        )


def rule_retention(script: Script, plan: Plan) -> Iterator[Violation]:
    """A stretch with no change of state is where viewers leave.

    A relance cannot be recognised from the text: a revelation and a piece of
    exposition are the same words to a machine. So the writer declares one
    with a `> relance:` line, and this rule only checks the spacing between
    them. A script that declares none is measured act by act, which is the
    weakest useful reading of the rule rather than a silent pass.
    """
    every_s = float(config.get("structure", "relance_retention_s", default=90))
    durees = {b["id"]: float(b["duree_s"]) for b in plan["beats"]}

    run = 0.0
    start: Beat | None = None
    for index, beat in enumerate(script.beats):
        if start is None:
            start = beat
        run += durees.get(beat.id, 0.0)

        # A declared relance, or an act boundary, is a change of state.
        suivant = script.beats[index + 1] if index + 1 < len(script.beats) else None
        if beat.relance or (suivant is not None and suivant.act != beat.act):
            run, start = 0.0, None
            continue

        if run > every_s:
            yield Violation(
                start.id if start else beat.id, "rétention",
                f"{run:.0f} s sans relance déclarée (limite {every_s:.0f} s) — "
                "marquer le beat qui change l'état du récit avec une ligne "
                "`> relance: <nature>`, ou en écrire un.",
                blocking=False,
            )
            run, start = 0.0, None


def rule_hook(script: Script, plan: Plan) -> Iterator[Violation]:
    """The opening decides whether the rest is watched at all.

    Three things are checkable here, and all three were wrong in the first
    documentary this pipeline produced: the hook ran long, its first sentence
    unfolded across three clauses before landing a fact, and it opened on a
    setting rather than on the person the story is about.
    """
    if not script.beats:
        return

    first = script.beats[0]
    hook_s = float(config.get("structure", "hook_s", default=20))
    tenu_s = float(plan["beats"][0]["duree_s"]) if plan["beats"] else 0.0

    if tenu_s > hook_s:
        yield Violation(
            first.id, "hook-longueur",
            f"{tenu_s:.0f} s estimées — le hook vise {hook_s:.0f} s. "
            f"Ce qui dépasse appartient au beat suivant. "
            f"({first.word_count} mots, silences compris.)",
        )

    sentences = [s for s in SENTENCE_SPLIT_RE.split(first.text) if s.strip()]
    if sentences:
        limit = int(config.get("structure", "ouverture", "phrase_mots_max", default=20))
        count = len(_words(sentences[0]))
        if count > limit:
            yield Violation(
                first.id, "hook-phrase",
                f"première phrase de {count} mots (max {limit}) — le fait qui "
                "fait rester doit tomber d'un bloc, pas au bout de trois "
                "subordonnées.",
                excerpt=sentences[0].strip()[:90],
            )

    if "?" in first.text:
        yield Violation(
            first.id, "hook-question",
            "le hook pose une question. Il pose un fait : une question "
            "d'ouverture est la signature sonore du contenu générique, et "
            "elle ne promet rien de vérifiable.",
        )


RULES: list[Callable[[Script, Plan], Iterator[Violation]]] = [
    rule_word_budget,
    rule_air,
    rule_hook,
    rule_beat_length,
    rule_sentence_length,
    rule_tts_hazards,
    rule_acronyms,
    rule_forbidden,
    rule_retention,
]


def check(script: Script) -> list[Violation]:
    # Le plan temporel est estimé une fois, ici, et prêté aux règles qui en
    # ont besoin. Le calculer dans chacune coûterait trois fois le travail
    # et laisserait trois occasions de diverger.
    plan = align.estimate(script)
    found: list[Violation] = []
    for rule in RULES:
        found.extend(rule(script, plan))
    # Blocking first, then in script order.
    order = {beat.id: index for index, beat in enumerate(script.beats)}
    return sorted(found, key=lambda v: (not v.blocking, order.get(v.beat, -1)))
