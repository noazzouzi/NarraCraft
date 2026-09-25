"""Les verdicts du contrôle visuel.

Claude regarde les images et écrit `05-visuals/controle.jsonl` ; ce module
le relit. C'est la même séparation que partout : le modèle juge, le code
exécute — ici, exécuter veut dire re-sourcer ce qui a été refusé.

Le fichier est append-only, comme le journal de sources de la recherche.
Un contrôle de quatre-vingts images qui s'interrompt au soixantième garde
ses soixante verdicts, et la reprise ne rejuge que le reste.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FICHIER = "controle.jsonl"

#: Les trois seuls verdicts. Un quatrième mot dans le fichier est une
#: faute de frappe du modèle, pas une nuance : on le refuse plutôt que de
#: le traiter comme un « garde » par défaut.
VERDICTS = ("garde", "refaire", "doute")


class ControleError(ValueError):
    """`controle.jsonl` ne dit pas ce que le format promet."""


def lire(visuals_dir: Path) -> dict[str, dict[str, str]]:
    """Le dernier verdict de chaque plan.

    « Le dernier » et non « le premier » : le fichier s'ajoute, donc une
    deuxième passe sur un plan re-sourcé doit l'emporter sur la première.
    """
    chemin = visuals_dir / FICHIER
    verdicts: dict[str, dict[str, str]] = {}
    if not chemin.is_file():
        return verdicts

    for numero, ligne in enumerate(
            chemin.read_text(encoding="utf-8").splitlines(), start=1):
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            donnees = json.loads(ligne)
        except json.JSONDecodeError:
            raise ControleError(
                f"{FICHIER} ligne {numero} : ce n'est pas du JSON.") from None
        shot = donnees.get("shot")
        verdict = donnees.get("verdict")
        if not shot:
            raise ControleError(f"{FICHIER} ligne {numero} : pas de `shot`.")
        if verdict not in VERDICTS:
            raise ControleError(
                f"{FICHIER} ligne {numero} : verdict {verdict!r} — attendu "
                f"{', '.join(VERDICTS)}.")
        verdicts[shot] = {"verdict": verdict,
                          "raison": str(donnees.get("raison") or "")}
    return verdicts


def refuses(visuals_dir: Path) -> list[str]:
    """Les plans à re-sourcer, dans l'ordre."""
    verdicts = lire(visuals_dir)
    return sorted(s for s, v in verdicts.items() if v["verdict"] == "refaire")


def bilan(visuals_dir: Path) -> dict[str, int]:
    compte = {nom: 0 for nom in VERDICTS}
    for verdict in lire(visuals_dir).values():
        compte[verdict["verdict"]] += 1
    return compte


def noter(visuals_dir: Path, shot: str, verdict: str, raison: str = "") -> None:
    """Ajoute un verdict. Sert au code, pas au modèle — lui écrit le
    fichier directement, c'est le sens de l'étape."""
    if verdict not in VERDICTS:
        raise ControleError(f"verdict {verdict!r} — attendu "
                            f"{', '.join(VERDICTS)}.")
    visuals_dir.mkdir(parents=True, exist_ok=True)
    with (visuals_dir / FICHIER).open("a", encoding="utf-8") as flux:
        flux.write(json.dumps({"shot": shot, "verdict": verdict,
                               "raison": raison}, ensure_ascii=False) + "\n")


def oublier(visuals_dir: Path, shots: list[str]) -> None:
    """Retire des plans du fichier, après leur remplacement.

    Sans ça, un plan re-sourcé garderait son verdict `refaire` et la
    galerie le signalerait encore alors que l'image a changé. C'est la
    seule écriture qui ne soit pas un ajout, et elle est délibérée : un
    verdict qui porte sur une image disparue n'est pas une archive, c'est
    une fausse alerte.
    """
    chemin = visuals_dir / FICHIER
    if not chemin.is_file() or not shots:
        return
    vises = set(shots)
    gardees = [
        ligne for ligne in chemin.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and _shot_de(ligne) not in vises
    ]
    chemin.write_text(
        "\n".join(gardees) + ("\n" if gardees else ""), encoding="utf-8")


def _shot_de(ligne: str) -> str:
    try:
        return str(json.loads(ligne).get("shot", ""))
    except json.JSONDecodeError:
        return ""


def a_controler(shots: list[Any], assets: dict[str, dict]) -> list[str]:
    """Les plans qui ont une image à regarder.

    Un panneau graphique n'en a pas — il est construit au rendu — et un
    plan sans visuel n'a rien à contrôler.
    """
    return [s.id for s in shots
            if s.type != "motion" and assets.get(s.id, {}).get("fichier")]
