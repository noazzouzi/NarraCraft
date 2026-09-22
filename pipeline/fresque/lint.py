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

#: Le plan temporel du script, tel que `voice.synthesize` le mesure. Les
#: règles qui parlent de durée le reçoivent au lieu de la recalculer : deux
#: arithmétiques parallèles divergent, et c'est toujours celle du lint qui
#: a tort au moment où ça compte.
#:
#: Il n'existe donc qu'une fois la voix synthétisée. Avant, les règles de
#: rythme ne tournent pas — elles préféraient jadis une durée déduite d'un
#: débit annoncé, ce qui revenait à vérifier le script contre une hypothèse
#: plutôt que contre le film.
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

    Cette règle a d'abord multiplié la durée cible par un débit annoncé en
    mots par minute, puis interrogé un estimateur qui faisait la même chose
    en mieux. Les deux prédisaient. Aucun ne mesurait.

    Elle lit maintenant la durée du film telle que la voix l'a produite. Le
    compte de mots ne prédit pas une durée : le moteur décide du débit et
    des silences, et lui seul.
    """
    target_min = float(config.get("production", "duree_cible_min", default=15))
    tolerance = float(config.get("production", "tolerance_duree_pct", default=15)) / 100

    cible_s = target_min * 60
    reelle_s = float(plan["duree_totale_s"])
    drift = (reelle_s - cible_s) / cible_s if cible_s else 0.0

    if abs(drift) > tolerance:
        yield Violation(
            "—", "budget",
            f"{align.format_duration(reelle_s)} mesurées pour une cible de "
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

    Les deux dernières se lisent dans le texte. La première demande une
    durée, donc la voix : sans elle, le hook n'est pas chronométré.
    """
    if not script.beats:
        return

    first = script.beats[0]
    hook_s = float(config.get("structure", "hook_s", default=20))
    tenu_s = float(plan["beats"][0]["duree_s"]) if plan and plan["beats"] else 0.0

    if tenu_s > hook_s:
        yield Violation(
            first.id, "hook-longueur",
            f"{tenu_s:.0f} s mesurées — le hook vise {hook_s:.0f} s. "
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


def _assez_long(script: Script) -> bool:
    """Un script assez long pour avoir une structure à vérifier.

    Un montage d'essai de deux minutes n'a ni boucles ni enchaînement : lui
    réclamer un tableau de contrôle ferait du lint un obstacle au lieu d'un
    garde-fou, et on apprendrait à passer outre.
    """
    seuil = int(config.get("structure", "boucles", "a_partir_de_beats", default=8))
    return len(script.beats) >= seuil


def rule_enchainement(script: Script, plan: Plan) -> Iterator[Violation]:
    """`mais` ou `donc`, jamais `et`.

    C'est la règle qui sépare un documentaire d'un exposé. Un beat qui ne
    s'enchaîne au précédent ni par une conséquence ni par un retournement
    est un élément de liste — et une liste de faits perd le spectateur en
    quatre minutes, quelle que soit la qualité des faits.

    La machine ne peut pas lire le lien dans le texte. L'auteur le déclare
    dans le tableau de contrôle, et on vérifie qu'il l'a fait pour chacun.
    """
    if not _assez_long(script):
        return

    suivants = script.beats[1:]
    if not any(beat.lien for beat in suivants):
        yield Violation(
            "—", "enchaînement",
            f"aucun lien déclaré sur {len(suivants)} beats — il manque le "
            "tableau `## Contrôle` en fin de fichier : une ligne par beat, "
            "avec « donc » ou « mais ».",
        )
        return

    for beat in suivants:
        if not beat.lien:
            yield Violation(
                beat.id, "enchaînement",
                "aucun lien au beat précédent. « donc » pour une "
                "conséquence, « mais » pour un retournement. Si seul « et » "
                "convient, ce beat est un élément de liste : le fusionner "
                "ou le couper.",
            )


def rule_boucles(script: Script, plan: Plan) -> Iterator[Violation]:
    """Ce qui fait rester un spectateur plusieurs minutes.

    Une boucle est une question posée à un beat et répondue bien plus loin.
    Tout se vérifie ici sauf la seule chose qui ne se vérifie pas : qu'elle
    soit intéressante.

    La structure — déclarée, ouverte, fermée, dans le bon ordre — se lit
    dans le tableau de contrôle. Sa longueur, elle, demande des durées :
    sans `plan`, ces deux contrôles-là ne tournent pas.
    """
    if not _assez_long(script):
        return

    min_s = float(config.get("structure", "boucles", "min_s", default=90))
    max_ouvertes = int(config.get("structure", "boucles", "max_simultanees", default=3))
    fin_s = float(config.get("structure", "boucles", "fin_sans_boucle_s", default=30))

    if not script.boucles:
        yield Violation(
            "—", "boucle",
            "aucune boucle déclarée — sans question en suspens, il n'y a "
            "aucune raison de regarder la minute suivante. Le hook ouvre L1, "
            "chaque acte ouvre la sienne.",
        )
        return

    durees = {b["id"]: float(b["duree_s"]) for b in plan["beats"]} if plan else {}
    rang = {beat.id: index for index, beat in enumerate(script.beats)}
    debut = {}
    cumul = 0.0
    for beat in script.beats:
        debut[beat.id] = cumul
        cumul += durees.get(beat.id, 0.0)
    totale = cumul

    for boucle in script.boucles:
        if not boucle.ouvre:
            yield Violation(
                boucle.ferme or "—", "boucle",
                f"{boucle.nom} est fermée sans avoir été ouverte.",
            )
            continue
        if not boucle.ferme:
            yield Violation(
                boucle.ouvre, "boucle",
                f"{boucle.nom} n'est jamais fermée — « {boucle.question} » "
                "reste sans réponse. Une promesse non tenue se paie en "
                "commentaires.",
            )
            continue
        if rang.get(boucle.ferme, 0) <= rang.get(boucle.ouvre, 0):
            yield Violation(
                boucle.ouvre, "boucle",
                f"{boucle.nom} se ferme avant de s'ouvrir.",
            )
            continue
        if not durees:
            continue
        tenue = debut[boucle.ferme] - debut[boucle.ouvre]
        if tenue < min_s:
            yield Violation(
                boucle.ouvre, "boucle-courte",
                f"{boucle.nom} tenue {tenue:.0f} s (minimum {min_s:.0f} s) — "
                "à cette distance ce n'est pas une boucle, c'est une phrase. "
                "La fermer plus tard, ou ne pas l'ouvrir.",
            )

    # Combien de questions restent en suspens, beat par beat.
    ouvertures: dict[str, list[str]] = {}
    fermetures: dict[str, list[str]] = {}
    for boucle in script.boucles:
        if boucle.ouvre and boucle.ferme:
            ouvertures.setdefault(boucle.ouvre, []).append(boucle.nom)
            fermetures.setdefault(boucle.ferme, []).append(boucle.nom)

    ouvertes: set[str] = set()
    signale_vide = signale_trop = False
    for beat in script.beats:
        ouvertes |= set(ouvertures.get(beat.id, []))
        if len(ouvertes) > max_ouvertes and not signale_trop:
            signale_trop = True
            yield Violation(
                beat.id, "boucle-trop",
                f"{len(ouvertes)} boucles ouvertes en même temps (maximum "
                f"{max_ouvertes}) — le spectateur ne retient plus ce qu'on "
                "lui a promis. En fermer une avant d'en ouvrir une autre.",
                blocking=False,
            )
        ouvertes -= set(fermetures.get(beat.id, []))
        if not durees:
            continue
        reste = totale - (debut[beat.id] + durees.get(beat.id, 0.0))
        if not ouvertes and reste > fin_s and not signale_vide:
            signale_vide = True
            yield Violation(
                beat.id, "boucle-vide",
                f"plus aucune question en suspens, et il reste "
                f"{align.format_duration(reste)} de film. C'est là qu'on "
                "décroche : ouvrir la boucle suivante avant de fermer "
                "celle-ci.",
            )


def rule_souffle(script: Script, plan: Plan) -> Iterator[Violation]:
    """Une phrase courte, régulièrement, ou le texte sonne plat.

    Le débit ne suffit pas : un script entier écrit en phrases de vingt
    mots respecte toutes les autres règles et reste illisible à l'oreille.
    """
    courte = int(config.get("controle", "phrase_courte_mots", default=0))
    fenetre = int(config.get("controle", "phrase_courte_tous_les_beats", default=5))
    if courte <= 0 or fenetre <= 0 or len(script.beats) < fenetre:
        return

    def a_du_souffle(beat: Beat) -> bool:
        return any(
            0 < len(_words(phrase)) <= courte
            for phrase in SENTENCE_SPLIT_RE.split(beat.text)
        )

    index = 0
    while index + fenetre <= len(script.beats):
        tranche = script.beats[index:index + fenetre]
        if any(a_du_souffle(beat) for beat in tranche):
            index += 1
            continue
        yield Violation(
            tranche[0].id, "souffle",
            f"{fenetre} beats sans une seule phrase de {courte} mots ou "
            "moins. Le silence est un outil : une phrase courte isolée "
            "frappe plus fort que n'importe quel adjectif.",
            blocking=False,
        )
        index += fenetre


#: Ce qui se vérifie sur le texte seul, à n'importe quel moment de
#: l'écriture. C'est le lint qu'on relance après chaque correction.
REGLES_TEXTE: list[Callable[[Script, Plan], Iterator[Violation]]] = [
    rule_beat_length,
    rule_sentence_length,
    rule_tts_hazards,
    rule_acronyms,
    rule_forbidden,
    rule_enchainement,
    rule_souffle,
    # Ces deux-là font les deux : leur part structurelle se lit dans le
    # texte, leur part chronométrée s'active quand `plan` arrive.
    rule_hook,
    rule_boucles,
]

#: Ce qui exige des durées, et donc la voix. Un débit annoncé ne les
#: remplace pas : c'est ce qu'on faisait, et le script « dans le budget »
#: sortait à côté de sa cible.
REGLES_RYTHME: list[Callable[[Script, Plan], Iterator[Violation]]] = [
    rule_word_budget,
    rule_air,
    rule_retention,
]

RULES = REGLES_TEXTE + REGLES_RYTHME


def check(script: Script, plan: Plan | None = None) -> list[Violation]:
    """Les violations du script. Avec `plan`, celles du rythme en plus.

    `plan` est l'alignement mesuré (`04-audio/alignment.json`). Sans lui,
    seules les règles de texte tournent — mieux vaut sept règles vraies que
    douze dont cinq reposent sur une durée supposée.
    """
    regles = REGLES_TEXTE + (REGLES_RYTHME if plan else [])
    found: list[Violation] = []
    for rule in regles:
        found.extend(rule(script, plan))
    # Blocking first, then in script order.
    order = {beat.id: index for index, beat in enumerate(script.beats)}
    return sorted(found, key=lambda v: (not v.blocking, order.get(v.beat, -1)))
