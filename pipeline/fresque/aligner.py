"""Alignement forcé — où chaque mot tombe vraiment dans l'audio.

CLAUDE.md sépare la voix de l'alignement, et c'est ce module qui justifie
la séparation. Le moteur TTS produit un fichier par beat ; cet aligneur
reprend le texte qu'on possède déjà — on ne devine aucune transcription —
et cherche où chaque mot est tombé.

Ce que ça change, concrètement :

| `source` | Bornes de beat | Position des mots |
|---|---|---|
| `kokoro` | mesurées | **estimées par syllabes** |
| `forced` | mesurées | **mesurées** |

Les coupes du montage tombaient déjà au bon endroit avec `kokoro`, parce
qu'elles ne dépendent que des bornes de beat. Ce qui était faux, c'est la
position d'un mot *à l'intérieur* d'un beat — donc les sous-titres. Un
surlignage mot à mot, comme celui mesuré chez Frontier
(`docs/analyse-frontier.md`), ne tient pas sur une estimation syllabique :
sur une phrase de six mots l'erreur cumulée se voit immédiatement.

COMMENT
=======
Un modèle CTC multilingue (MMS, 1 100 langues) produit une matrice de
probabilités par trame ; `forced_align` cherche le chemin le plus probable
qui passe par les lettres qu'on lui donne, dans l'ordre. Il ne peut donc
pas inventer un mot : il ne fait que placer ceux qu'on a écrits.

Le dictionnaire du modèle ne connaît que `a-z` et l'apostrophe. Les
accents sont dépouillés, et **les nombres sont écrits en lettres** — parce
que la voix, elle, a bien prononcé « deux mille vingt-cinq ». Aligner un
joker à cet endroit reviendrait à jeter deux secondes d'audio.

Le modèle pèse 1,2 Go et se télécharge une fois. Tout tourne en local, sans
clé ni réseau ensuite.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Callable

from . import config
from .align import syllables
from .script_parser import Script

SOURCE = "forced"

#: Le score du modèle est gardé dans le fichier, mais il ne sert PAS à
#: détecter une erreur, et c'est une conclusion mesurée.
#:
#: Le modèle aligne des lettres. Sur « vingt », dont le g et le t sont
#: muets et dont la voyelle est nasale, il score 0,25 alors que le mot est
#: parfaitement placé. Test contrôlé : « Le vingt-cinq septembre » écrit en
#: toutes lettres score 0,250 — exactement comme la même phrase écrite
#: « Le 25 septembre » (0,278). Un seuil absolu à 0,40 signalait donc du
#: français normal, et une règle qui crie au loup ne sert à rien.
#:
#: Ce qui se mesure vraiment, c'est la géométrie : un mot correctement
#: placé dure à peu près le temps de ses syllabes. Un mot que l'aligneur
#: n'a pas su poser est écrasé à quelques millisecondes.
DUREE_MIN_S = 0.03
#: Bornes de durée par syllabe. Médiane relevée sur un montage réel :
#: 0,14 s/syllabe à 124 mots/minute.
SECONDES_PAR_SYLLABE = (0.035, 0.55)

MOT_RE = re.compile(r"[\w'’-]+", re.UNICODE)


class AlignError(RuntimeError):
    pass


# --- Texte -> lettres que le modèle connaît ---------------------------------

_UNITES = ("zero", "un", "deux", "trois", "quatre", "cinq", "six", "sept",
           "huit", "neuf", "dix", "onze", "douze", "treize", "quatorze",
           "quinze", "seize")
_DIZAINES = {20: "vingt", 30: "trente", 40: "quarante", 50: "cinquante",
             60: "soixante", 80: "quatre vingt"}


def en_lettres(n: int) -> str:
    """Un entier en français, de 0 à 9999.

    Couvre ce qu'un script de documentaire contient réellement : des
    années, des quantièmes, des peines en années. Au-delà, le skill
    d'écriture demande déjà d'écrire en toutes lettres.
    """
    if n < 0 or n > 9999:
        return ""
    if n < 17:
        return _UNITES[n]
    if n < 20:
        return f"dix {_UNITES[n - 10]}"
    if n < 100:
        # Le français n'a pas de dizaine à 70 ni à 90 : « soixante-douze »
        # et « quatre-vingt-treize » se comptent depuis 60 et 80.
        base = 80 if n >= 80 else (60 if n >= 60 else (n // 10) * 10)
        reste = n - base
        mot = _DIZAINES[base]
        if reste == 0:
            return mot
        if reste == 1 and base < 80:
            return f"{mot} et un"
        return f"{mot} {en_lettres(reste)}"
    if n < 1000:
        cent, reste = divmod(n, 100)
        tete = "cent" if cent == 1 else f"{_UNITES[cent]} cent"
        return tete if reste == 0 else f"{tete} {en_lettres(reste)}"
    mille, reste = divmod(n, 1000)
    tete = "mille" if mille == 1 else f"{en_lettres(mille)} mille"
    return tete if reste == 0 else f"{tete} {en_lettres(reste)}"


def _lettres(texte: str) -> str:
    """Dépouille accents et ponctuation ; ne laisse que a-z et l'apostrophe."""
    plat = unicodedata.normalize("NFKD", texte.lower())
    plat = "".join(c for c in plat if not unicodedata.combining(c))
    return re.sub(r"[^a-z' ]", " ", plat)


def jetons(mot: str) -> list[str]:
    """Les jetons d'alignement d'un mot affiché.

    Un mot en donne souvent un seul. Un nombre en donne plusieurs : « 2025 »
    a été prononcé « deux mille vingt cinq », et c'est là-dessus qu'il faut
    aligner. Les bornes du mot affiché sont alors le début du premier jeton
    et la fin du dernier.
    """
    if mot.isdigit():
        mot = en_lettres(int(mot))
    return [j for j in _lettres(mot).split() if j]


# --- Alignement --------------------------------------------------------------

def _moteur():
    try:
        import torch
        import torchaudio
        from torchaudio.pipelines import MMS_FA
    except ImportError as erreur:  # pragma: no cover - dépend de l'install
        raise AlignError(
            "L'alignement forcé demande torch et torchaudio :\n"
            "  pip install torch torchaudio "
            "--index-url https://download.pytorch.org/whl/cpu\n"
            "Ils sont optionnels : sans eux le pipeline tourne en "
            "`source: kokoro`, avec des positions de mot estimées."
        ) from erreur
    return torch, torchaudio, MMS_FA


def _lire_mono(chemin: Path):
    import numpy as np
    import soundfile as sf

    x, sr = sf.read(str(chemin), dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    return np.ascontiguousarray(x), sr


def force(script: Script, audio_dir: Path, bases: dict[str, float],
          report: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Réaligne le script sur l'audio réel, beat par beat.

    `bases` donne l'instant de début de chaque beat, tel que la synthèse
    l'a mesuré : on ne recalcule pas les bornes, on ne raffine que
    l'intérieur. Un beat qui échoue garde ses positions estimées plutôt que
    de faire tomber tout le fichier.
    """
    torch, torchaudio, MMS_FA = _moteur()
    beats_dir = audio_dir / "beats"
    if not beats_dir.is_dir():
        raise AlignError(
            f"{beats_dir} absent — lancer `fresque voice` d'abord : "
            "l'alignement forcé a besoin de l'audio réel."
        )

    modele = MMS_FA.get_model()
    tokenizer = MMS_FA.get_tokenizer()
    aligneur = MMS_FA.get_aligner()

    sorties: list[dict[str, Any]] = []
    suspects: list[dict[str, Any]] = []
    echecs: list[str] = []
    fin_totale = 0.0

    for beat in script.beats:
        chemin = beats_dir / f"{beat.id}.wav"
        depart = float(bases.get(beat.id, 0.0))
        affiches = MOT_RE.findall(beat.text)

        if not chemin.is_file():
            echecs.append(f"{beat.id} : {chemin.name} absent")
            continue

        onde, sr = _lire_mono(chemin)
        duree = len(onde) / sr
        # Les jetons d'alignement, et de quel mot affiché chacun provient.
        suite: list[str] = []
        appartenance: list[int] = []
        for index, mot in enumerate(affiches):
            for jeton in jetons(mot):
                suite.append(jeton)
                appartenance.append(index)

        if not suite:
            echecs.append(f"{beat.id} : aucun mot alignable")
            continue

        try:
            w = torch.from_numpy(onde)[None, :]
            w16 = torchaudio.functional.resample(w, sr, MMS_FA.sample_rate)
            with torch.inference_mode():
                emission, _ = modele(w16)
                spans = aligneur(emission[0], tokenizer(suite))
            # Une trame d'émission couvre plusieurs échantillons ; le rapport
            # les reconvertit en secondes.
            pas = w16.shape[1] / emission.shape[1] / MMS_FA.sample_rate
        except Exception as erreur:            # noqa: BLE001
            echecs.append(f"{beat.id} : {type(erreur).__name__} — {erreur}")
            continue

        # Regrouper les jetons par mot affiché.
        par_mot: dict[int, list] = {}
        for index, span in zip(appartenance, spans):
            par_mot.setdefault(index, []).extend(span)

        mots: list[dict[str, Any]] = []
        for index, mot in enumerate(affiches):
            morceaux = par_mot.get(index)
            if not morceaux:
                continue
            debut = depart + morceaux[0].start * pas
            fin = depart + morceaux[-1].end * pas
            poids = sum(m.end - m.start for m in morceaux) or 1
            score = sum(m.score * (m.end - m.start) for m in morceaux) / poids

            # La plausibilité se juge sur les jetons réellement prononcés :
            # « 2025 » a été dit « deux mille vingt cinq », donc quatre
            # syllabes, pas la seule que son orthographe en chiffres laisse
            # compter.
            syll = max(sum(syllables(j) for j in jetons(mot)), 1)
            tenue = fin - debut
            par_syllabe = tenue / syll
            bas, haut = SECONDES_PAR_SYLLABE
            if tenue < DUREE_MIN_S or not (bas <= par_syllabe <= haut):
                suspects.append({
                    "beat": beat.id, "mot": mot,
                    "duree_s": round(tenue, 3), "syllabes": syll,
                    "s_par_syllabe": round(par_syllabe, 3),
                    "score": round(float(score), 3),
                })
            mots.append({
                "t": mot,
                "tx": _affichage(beat.text, mot, index, affiches),
                "debut_s": round(debut, 3),
                "fin_s": round(fin, 3),
                "score": round(float(score), 3),
            })

        fin_beat = depart + duree
        fin_totale = max(fin_totale, fin_beat)
        sorties.append({
            "id": beat.id,
            "acte": beat.act,
            "debut_s": round(depart, 3),
            "fin_s": round(fin_beat, 3),
            "duree_s": round(duree, 3),
            "mots": mots,
        })
        if report:
            report(f"  {beat.id} · {len(mots)} mots · {duree:.2f} s")

    if not sorties:
        raise AlignError("Aucun beat n'a pu être aligné.\n  " + "\n  ".join(echecs))

    return {
        "source": SOURCE,
        "avertissement": (
            "Positions de mot mesurées sur l'audio par alignement forcé. "
            "Le champ `score` dit la confiance du modèle mot à mot."
        ),
        "mots_par_minute": round(
            sum(len(b["mots"]) for b in sorties) / max(fin_totale, 1e-9) * 60, 1),
        "duree_totale_s": round(fin_totale, 3),
        "nb_beats": len(sorties),
        "nb_mots": sum(len(b["mots"]) for b in sorties),
        "confiance_min": round(min(
            (m["score"] for b in sorties for m in b["mots"]), default=1.0), 3),
        # Des mots posés à une durée invraisemblable. C'est le seul
        # signalement qui veut dire quelque chose : le score du modèle est
        # gardé par mot, mais il mesure l'orthographe autant que le calage.
        "mots_invraisemblables": sorted(
            suspects, key=lambda s: s["s_par_syllabe"])[:30],
        "beats_non_alignes": echecs,
        "beats": sorties,
    }


def _affichage(texte: str, mot: str, index: int, tous: list[str]) -> str:
    """Le mot avec la ponctuation qui le suit.

    Les sous-titres dépouillés de leurs virgules se lisent comme une sortie
    de machine, ce qui est précisément l'impression qu'on évite. On retrouve
    donc la ponctuation collée au mot dans le texte d'origine.
    """
    depart = 0
    for precedent in tous[:index]:
        trouve = texte.find(precedent, depart)
        depart = (trouve + len(precedent)) if trouve >= 0 else depart
    position = texte.find(mot, depart)
    if position < 0:
        return mot
    apres = texte[position + len(mot):]
    suite = re.match(r"[)\]}»,;:.!?…]+", apres)
    return mot + (suite.group(0) if suite else "")


def bases_depuis(alignement: dict[str, Any]) -> dict[str, float]:
    """Les instants de début de beat d'un alignement déjà mesuré."""
    if alignement.get("source") not in ("kokoro", SOURCE):
        raise AlignError(
            f"alignment.json est en `source: {alignement.get('source')}` — "
            "ses bornes de beat sont estimées, pas mesurées. Lancer "
            "`fresque voice` avant l'alignement forcé."
        )
    return {b["id"]: float(b["debut_s"]) for b in alignement["beats"]}
