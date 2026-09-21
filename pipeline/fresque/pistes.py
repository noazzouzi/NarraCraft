"""Lecture de `pistes.md`.

Claude écrit le fichier, le code le lit. L'interface a besoin de cartes
cliquables, pas de markdown : c'est ici qu'on passe de l'un à l'autre, et
nulle part ailleurs. Aucun modèle ne relit ce fichier pour le résumer.

Le format est celui que le skill `fresque-exploration` impose. S'il n'est
pas respecté, on le dit : mieux vaut une erreur nette qu'une carte à moitié
vide dans le navigateur.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

#: `## Piste 2 — Le contrat qui payait le siège`
_TITRE_PISTE = re.compile(r"^##\s+Piste\s+(\d+)\s*[—–-]\s*(.+?)\s*$")
#: `- **angle** : ...`
_CHAMP = re.compile(r"^[-*]\s+\*\*(angle|pivot|risque)\*\*\s*:\s*(.+?)\s*$", re.I)
#: `**Preuves**` / `**Titres**`
_BLOC = re.compile(r"^\*\*(Preuves|Titres)\*\*\s*$", re.I)
#: `1. Le fait précis — [source](url)`
_PREUVE = re.compile(r"^(\d+)\.\s+(.+?)\s*$")
#: `- Le titre — preuve 2`
_TITRE = re.compile(r"^[-*]\s+(.+?)\s*[—–-]\s*preuve\s+(\d+)\s*$", re.I)
#: `[Le Monde](https://…)` — la dernière du texte tient la source.
_LIEN = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")


class PistesError(ValueError):
    """`pistes.md` ne dit pas ce que le format promet."""


def lire(chemin: Path) -> dict[str, Any]:
    """`pistes.md` → un dictionnaire prêt pour l'interface."""
    if not chemin.is_file():
        raise FileNotFoundError(chemin)
    return analyser(chemin.read_text(encoding="utf-8"))


def analyser(texte: str) -> dict[str, Any]:
    sujet = ""
    pistes: list[dict[str, Any]] = []
    courante: dict[str, Any] | None = None
    bloc = ""

    for ligne in texte.splitlines():
        nue = ligne.strip()

        if nue.startswith("# ") and not sujet:
            sujet = re.sub(r"^Pistes\s*[—–-]\s*", "", nue[2:]).strip()
            continue

        entete = _TITRE_PISTE.match(nue)
        if entete:
            courante = {
                "numero": int(entete.group(1)),
                "resume": entete.group(2),
                "angle": "", "pivot": "", "risque": "",
                "preuves": [], "titres": [],
            }
            pistes.append(courante)
            bloc = ""
            continue

        if courante is None:
            continue

        marqueur = _BLOC.match(nue)
        if marqueur:
            bloc = marqueur.group(1).lower()
            continue

        champ = _CHAMP.match(nue)
        if champ:
            courante[champ.group(1).lower()] = champ.group(2)
            continue

        if bloc == "preuves":
            preuve = _PREUVE.match(nue)
            if preuve:
                corps = preuve.group(2)
                liens = _LIEN.findall(corps)
                courante["preuves"].append({
                    "numero": int(preuve.group(1)),
                    # Le lien sert de source : on le retire du texte pour
                    # ne pas afficher deux fois la même chose sur la carte.
                    "texte": _LIEN.sub("", corps).strip(" —–-\t"),
                    "source": liens[-1][0] if liens else "",
                    "url": liens[-1][1] if liens else "",
                })
        elif bloc == "titres":
            titre = _TITRE.match(nue)
            if titre:
                courante["titres"].append({
                    "texte": titre.group(1).strip(" *"),
                    "preuve": int(titre.group(2)),
                })

    if not pistes:
        raise PistesError("aucune piste trouvée — attendu « ## Piste 1 — … »")

    for piste in pistes:
        _verifier(piste)

    return {"sujet": sujet, "pistes": pistes}


def _verifier(piste: dict[str, Any]) -> None:
    """Les règles du skill, vérifiées par le code plutôt que par le prompt.

    Un titre qui cite une preuve absente est le défaut que le format existe
    pour empêcher : une accroche agressive sans rien dessous.
    """
    numero = piste["numero"]
    if not piste["angle"]:
        raise PistesError(f"piste {numero} : pas d'angle")
    if not piste["pivot"]:
        raise PistesError(f"piste {numero} : pas de pivot")
    if len(piste["preuves"]) < 3:
        raise PistesError(
            f"piste {numero} : {len(piste['preuves'])} preuve(s), il en faut 3")

    numeros = {p["numero"] for p in piste["preuves"]}
    for titre in piste["titres"]:
        if titre["preuve"] not in numeros:
            raise PistesError(
                f"piste {numero} : le titre « {titre['texte']} » cite la "
                f"preuve {titre['preuve']}, qui n'existe pas")
    if not piste["titres"]:
        raise PistesError(f"piste {numero} : aucun titre")


def choisie(piste: dict[str, Any]) -> str:
    """Le titre le plus agressif — le dernier, par construction du format."""
    return piste["titres"][-1]["texte"] if piste["titres"] else piste["resume"]
