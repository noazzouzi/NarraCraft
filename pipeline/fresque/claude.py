"""L'appel à Claude — la moitié du pipeline qui juge.

Le CLI `claude` est déjà installé et déjà authentifié par l'abonnement. On
l'appelle en sous-processus, exactement comme le serveur appelle
`python -m fresque`. Pas de SDK, pas de clé d'API, pas de client HTTP : il
n'y a rien à réinventer.

Le prompt tient en une ligne — `/fresque-exploration <slug>` — parce que
tout le reste est déjà dans les fichiers : le skill porte les consignes,
`projet.yaml` porte le sujet et le template, `pistes.md` porte les choix.
Rien ne transite par la ligne de commande qui ne soit pas déjà sur le
disque, donc relancer une étape après un crash donne le même résultat.

Ce que Claude écrit, il l'écrit dans `projects/<slug>/`. Ce module ne
produit aucun fichier lui-même : il lance, relaie la sortie, et rend le
code de sortie.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import config


class ClaudeError(RuntimeError):
    """Claude n'a pas pu être lancé, ou n'a pas produit son fichier."""


@dataclass(frozen=True)
class Etape:
    """Une étape confiée à Claude.

    `outils` est ce que l'étape peut utiliser sans qu'on lui demande —
    personne ne regarde l'écran pendant une recherche de dix minutes, et un
    outil non pré-approuvé bloquerait la commande. Ce n'est pas une prison :
    le mode `acceptEdits` en laisse passer d'autres. C'est la liste de ce
    dont l'étape a besoin pour ne jamais s'arrêter. La recherche a `Task`
    parce qu'elle lance ses cinq axes en parallèle ; l'exploration ne l'a pas.

    `tours_max` est un garde-fou, pas un budget : une boucle qui part en
    vrille consomme des limites d'abonnement, pas des euros, mais elle les
    consomme quand même.
    """
    skill: str
    produit: str
    outils: tuple[str, ...]
    tours_max: int
    modele: str = "opus"


#: Liste close, comme `serveur.COMMANDES`. Un skill absent d'ici n'est
#: lançable ni depuis le terminal ni depuis le navigateur.
ETAPES: dict[str, Etape] = {
    "explorer": Etape(
        "fresque-exploration", "pistes.md",
        ("Read", "Write", "WebSearch", "WebFetch"), tours_max=40,
    ),
    "brief": Etape(
        "fresque-brief", "00-brief.md",
        ("Read", "Write", "WebSearch", "WebFetch"), tours_max=30,
    ),
    # Cinq axes en parallèle, donc `Task`. C'est la seule étape qui en a
    # besoin, et la seule qui dure assez longtemps pour qu'un crash coûte.
    "recherche": Etape(
        "fresque-recherche", "01-research.md",
        ("Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch", "Task"),
        tours_max=150,
    ),
    # Le nom d'une étape est celui de la commande qui la lance, pas celui
    # du skill : c'est la clé que `serveur.COMMANDES` et le navigateur
    # emploient, et une clé qui diverge lance un skill que personne ne lit.
    "ecrire": Etape(
        "fresque-script", "02-script.md",
        ("Read", "Write", "Edit", "Bash"), tours_max=80,
    ),
    "plans": Etape(
        "fresque-plan-visuel", "03-shots.json",
        ("Read", "Write", "Edit", "Bash", "Glob"), tours_max=80,
    ),
}


def binaire() -> str:
    """Le chemin du CLI `claude`, ou une erreur qui dit quoi faire."""
    chemin = shutil.which("claude")
    if chemin is None:
        raise ClaudeError(
            "le CLI `claude` est introuvable dans le PATH.\n"
            "  Installation : npm install -g @anthropic-ai/claude-code\n"
            "  Puis `claude` une fois, pour ouvrir la session de l'abonnement."
        )
    return chemin


def lancer(nom: str, slug: str, modele: str | None = None) -> int:
    """Confie une étape à Claude et relaie sa sortie. Rend son code."""
    etape = ETAPES[nom]
    racine = config.repo_root()
    dossier = racine / "projects" / slug
    if not dossier.is_dir():
        raise ClaudeError(f"projet introuvable : projects/{slug}")

    argv = [
        binaire(), "-p", f"/{etape.skill} {slug}",
        "--output-format", "stream-json", "--verbose",
        "--permission-mode", "acceptEdits",
        "--allowedTools", ",".join(etape.outils),
        "--max-turns", str(etape.tours_max),
        "--model", modele or etape.modele,
    ]

    print(f"· {etape.skill} · {modele or etape.modele} · {slug}", flush=True)
    processus = subprocess.Popen(
        argv, cwd=racine, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    echec = False
    assert processus.stdout is not None
    for ligne in processus.stdout:
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            evenement = json.loads(ligne)
        except json.JSONDecodeError:
            # Tout ce qui n'est pas du JSON vient du CLI lui-même — une
            # erreur d'authentification, par exemple. Ça se lit tel quel.
            print(ligne, flush=True)
            continue
        if _afficher(evenement):
            echec = True

    code = processus.wait()
    if code != 0 or echec:
        return code or 1

    produit = dossier / etape.produit
    if not produit.exists():
        print(f"✗ {etape.produit} n'a pas été écrit", file=sys.stderr)
        return 1
    print(f"✓ projects/{slug}/{etape.produit}", flush=True)
    return 0


def _afficher(evenement: dict) -> bool:
    """Écrit un événement du flux en clair. Rend True si c'est un échec.

    Le journal est ce que l'utilisateur regarde pendant qu'une recherche de
    dix minutes tourne. Du JSON brut n'est pas regardable : on en garde le
    texte de Claude et le nom de chaque outil appelé, rien d'autre.
    """
    genre = evenement.get("type")

    if genre == "assistant":
        for bloc in evenement.get("message", {}).get("content", []):
            if bloc.get("type") == "text" and bloc.get("text", "").strip():
                print(bloc["text"].strip(), flush=True)
            elif bloc.get("type") == "tool_use":
                detail = _resume(bloc.get("name", ""), bloc.get("input", {}))
                print(f"  → {bloc.get('name')}{detail}", flush=True)
        return False

    if genre == "result":
        secondes = evenement.get("duration_ms", 0) / 1000
        tours = evenement.get("num_turns", 0)
        if evenement.get("is_error"):
            print(f"✗ {evenement.get('subtype', 'échec')} "
                  f"· {tours} tours · {secondes:.0f} s", file=sys.stderr)
            return True
        print(f"· {tours} tours · {secondes:.0f} s", flush=True)
    return False


def _resume(outil: str, entree: dict) -> str:
    """Le nom de l'outil ne suffit pas : « WebSearch » vingt fois de suite
    ne dit rien, « WebSearch subway royalty rate » dit tout."""
    for cle in ("query", "url", "description", "prompt", "pattern"):
        valeur = entree.get(cle)
        if isinstance(valeur, str) and valeur.strip():
            return f" {valeur.strip()[:90]}"
    chemin = entree.get("file_path")
    if isinstance(chemin, str):
        try:
            return f" {Path(chemin).relative_to(config.repo_root())}"
        except ValueError:
            return f" {chemin}"
    commande = entree.get("command")
    if isinstance(commande, str):
        return f" {commande[:90]}"
    return ""
