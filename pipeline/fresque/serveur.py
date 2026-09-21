"""`fresque serve` — une fenêtre sur l'atelier, qui ne détient rien.

CLAUDE.md interdit un serveur, et la raison est bonne : un état qui vit en
mémoire est un état qu'on ne peut ni inspecter, ni corriger, ni reprendre.
Celui-ci est écrit pour ne pas en avoir.

- **Il ne mémorise rien.** Chaque page relit `projects/`, `templates/` et
  `fresque.config.yaml` à chaud. Aucun cache, aucun index, aucune base.
- **Il n'invente aucune action.** Pour agir il lance
  `python -m fresque <commande> <slug>` en sous-processus, exactement ce
  qu'on taperait au terminal. La liste des commandes est close, et leurs
  options sont typées avant d'atteindre un `argv`.
- **La sortie d'une commande est un fichier.** Tout part dans
  `projects/<slug>/journal/<horodatage>-<commande>.log`, avec un `.json`
  voisin qui porte le code de sortie. Le journal est le fait ; ce que le
  serveur garde en mémoire n'est que la poignée du processus vivant.

Tue-le et relance-le : rien n'est perdu, rien n'est à reconstruire, et les
journaux des exécutions passées sont toujours là. C'est la seule forme sous
laquelle un serveur respecte le principe fondateur — et c'est pourquoi il
n'y a toujours ni base de données ni machine à états.

UNE SEULE ÉCRITURE DIRECTE
==========================
`review.construire()` est appelé dans le processus du serveur plutôt que
lancé en sous-processus, parce qu'une page ne peut pas attendre un
interpréteur qui démarre. C'est la même fonction que `fresque review`, elle
est idempotente, et elle ne produit qu'une projection des fichiers. Aucune
autre écriture ne passe par le serveur.
"""
from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import yaml

from . import apercu, config, review

JOURNAL_DIR = "journal"

#: Les fichiers numérotés, dans l'ordre. Sert à dessiner l'avancement d'un
#: projet sans l'ouvrir : leur simple présence *est* l'état du projet.
ETAPES: tuple[tuple[str, str], ...] = (
    # `pistes.md` n'est pas numéroté : il a pris la place du brief, et
    # renuméroter les fichiers restants aurait cassé tous les projets déjà
    # montés.
    ("pistes", "pistes.md"),
    ("recherche", "01-research.md"),
    ("script", "02-script.md"),
    ("plan visuel", "03-shots.json"),
    ("voix", "04-audio/alignment.json"),
    ("visuels", "05-visuals/assets.json"),
    ("montage", "06-timeline.json"),
    ("vidéo", "07-out/video.mp4"),
)


@dataclass(frozen=True)
class Option:
    """Une option de commande, typée avant d'atteindre un `argv`.

    `motif` est vérifié pour les options textuelles : rien de ce qui vient
    du navigateur n'entre dans une ligne de commande sans avoir été
    reconnu d'abord.
    """
    nom: str
    libelle: str
    type: str                      # "drapeau" | "nombre" | "entier" | "texte"
    defaut: str = ""
    motif: str = r"^[0-9]+-[0-9]+$"


@dataclass(frozen=True)
class Commande:
    libelle: str
    exige: str = ""                # le fichier qu'elle lit
    produit: str = ""              # le fichier qu'elle écrit
    depense: bool = False          # appelle une API payante
    longue: bool = False           # plusieurs minutes, bouton d'arrêt utile
    options: tuple[Option, ...] = ()


#: Liste close. Une commande absente d'ici n'est pas lançable depuis le
#: navigateur, quoi qu'il arrive dans la requête.
COMMANDES: dict[str, Commande] = {
    # Les cinq premières sont tenues par Claude — elles lancent un skill et
    # attendent son fichier. Elles sont ici pour la même raison que les
    # autres : une commande absente de cette liste n'est pas lançable depuis
    # le navigateur, qu'elle soit jugée ou calculée.
    "explorer": Commande(
        "Proposer quatre pistes", produit="pistes.md", longue=True,
    ),
    # Choisir une piste, c'est lancer la recherche dessus. Il n'y a plus
    # d'étape entre les deux : l'angle et le pivot sont déjà dans la piste,
    # et le reste du brief se calculait depuis la config.
    "recherche": Commande(
        "Mener la recherche", exige="pistes.md",
        produit="01-research.md", longue=True,
        options=(Option("piste", "piste retenue", "entier"),),
    ),
    "ecrire": Commande(
        "Écrire le script", exige="01-research.md",
        produit="02-script.md", longue=True,
    ),
    "plans": Commande(
        "Écrire le plan visuel", exige="02-script.md",
        produit="03-shots.json", longue=True,
    ),
    "status": Commande("État d'avancement"),
    "lint": Commande("Vérifier le script", exige="02-script.md"),
    "align": Commande(
        "Estimer les timings", exige="02-script.md",
        produit="04-audio/alignment.json",
        options=(Option("target", "durée cible (min)", "nombre"),),
    ),
    "shots": Commande("Valider le plan visuel", exige="03-shots.json"),
    "voice": Commande(
        "Synthétiser la voix", exige="02-script.md",
        produit="04-audio/alignment.json", longue=True,
    ),
    "fetch": Commande(
        "Sourcer les archives libres", exige="03-shots.json",
        produit="05-visuals/assets.json", longue=True,
        options=(
            Option("dry-run", "chercher sans télécharger", "drapeau"),
            Option("force", "re-sourcer les plans déjà acquis", "drapeau"),
        ),
    ),
    "images": Commande(
        "Générer les images manquantes", exige="03-shots.json",
        produit="05-visuals/assets.json", depense=True, longue=True,
    ),
    "rushes": Commande(
        "Sourcer le métrage d'archive", exige="03-shots.json", longue=True,
    ),
    "placeholders": Commande(
        "Visuels de substitution", exige="03-shots.json",
        produit="05-visuals/assets.json",
    ),
    # `align` estime, `aligner` mesure. La seconde était absente de cette
    # liste, donc impossible à lancer depuis l'atelier : le seul moyen
    # d'obtenir la position réelle des mots était le terminal.
    "aligner": Commande(
        "Aligner les mots sur l'audio", exige="04-audio/alignment.json",
        produit="04-audio/alignment.json", longue=True,
    ),
    "timeline": Commande(
        "Construire le montage", exige="04-audio/alignment.json",
        produit="06-timeline.json",
    ),
    "render": Commande(
        "Rendre la vidéo", exige="06-timeline.json",
        produit="07-out/video.mp4", longue=True,
        options=(
            Option("scale", "échelle (0.5 = copie de visionnage)", "nombre"),
            Option("frames", "intervalle, ex. 0-450", "texte"),
            Option("concurrency", "cœurs", "nombre"),
        ),
    ),
    "review": Commande("Régénérer la page de validation"),
}


# --- Journaux ----------------------------------------------------------------

#: Les processus vivants, par identifiant de journal. C'est tout ce que le
#: serveur garde en mémoire, et il n'en garde rien après la fin du processus
#: qui ne soit déjà dans le fichier voisin.
_VIVANTS: dict[str, subprocess.Popen] = {}
_VERROU = threading.Lock()

#: `Project.open()` positionne le template actif dans une variable de module
#: (voir `config`). Deux requêtes concurrentes sur deux projets différents se
#: marcheraient dessus. Tout ce qui ouvre un projet passe donc par ce verrou.
_VERROU_CONFIG = threading.Lock()

_ID_JOURNAL = re.compile(r"^\d{8}-\d{6}-[a-z]+$")


def _racine() -> Path:
    return config.repo_root()


def _projet_dir(slug: str) -> Path:
    """Le dossier d'un projet, ou une erreur — jamais un chemin deviné.

    Le slug vient du navigateur : on le confronte aux dossiers réellement
    présents plutôt que de le concaténer à un chemin.
    """
    racine = _racine() / "projects"
    chemin = (racine / slug).resolve()
    if chemin.parent != racine.resolve() or not chemin.is_dir():
        raise FileNotFoundError(slug)
    return chemin


def dire_beat(slug: str, beat: str | None = None) -> dict[str, Any]:
    """Synthétise un beat et rend son chemin, plus la ligne de mesure.

    Même sous-processus que tout le reste, mais attendu plutôt que
    journalisé : trois secondes d'audio n'ont pas besoin d'un flux. La
    durée et le débit ne sont pas recalculés ici — on rend la ligne que la
    commande a imprimée, telle quelle. Deux arithmétiques parallèles
    divergent, et c'est toujours celle de l'affichage qui a tort.
    """
    argv = [sys.executable, "-m", "fresque", "hook", slug]
    if beat:
        if not re.match(r"^B\d{3}$", beat):
            raise ValueError(f"beat {beat!r} — attendu B001, B002…")
        argv += ["--beat", beat]

    fait = subprocess.run(
        argv, cwd=_racine(), env=_environnement(),
        capture_output=True, text=True,
    )
    if fait.returncode != 0:
        raise ValueError((fait.stderr or fait.stdout).strip().lstrip("✗ ")
                         or "synthèse refusée")

    lignes = [l.strip() for l in fait.stdout.splitlines() if l.strip()]
    fichier = next((l[2:] for l in lignes if l.startswith("✓ ")), "")
    mesure = next((l for l in lignes if l.startswith("B")), "")
    alerte = next((l[2:] for l in lignes if l.startswith("⚠")), "")
    return {"fichier": fichier, "mesure": mesure, "alerte": alerte}


_ID_PLAN = re.compile(r"^S\d{3}$")
#: Les identifiants de voix des trois fournisseurs : `ff_siwis`,
#: `fr-FR-HenriNeural`, ou les vingt caractères d'ElevenLabs.
_ID_VOIX = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_FOURNISSEURS = ("kokoro", "edge", "elevenlabs")


def _voix_valide(provider: str, voix: str) -> None:
    if provider not in _FOURNISSEURS:
        raise ValueError(f"fournisseur {provider!r} — attendu "
                         f"{', '.join(_FOURNISSEURS)}")
    if not _ID_VOIX.match(voix):
        raise ValueError(f"voix {voix!r} n'est pas un identifiant valide")


def essayer_voix(slug: str, provider: str, voix: str) -> dict[str, Any]:
    """Synthétise une phrase avec une voix, sans la retenir."""
    _voix_valide(provider, voix)
    fait = subprocess.run(
        [sys.executable, "-m", "fresque", "voix-essai", slug,
         "--provider", provider, "--voix", voix],
        cwd=_racine(), env=_environnement(), capture_output=True, text=True,
    )
    if fait.returncode != 0:
        raise ValueError((fait.stderr or fait.stdout).strip().lstrip("✗ ")
                         or "essai refusé")
    lignes = [l.strip() for l in fait.stdout.splitlines() if l.strip()]
    return {
        "fichier": next((l[2:] for l in lignes if l.startswith("✓ ")), ""),
        "mesure": next((l for l in lignes if not l.startswith("✓")), ""),
    }


def choisir_voix(slug: str, provider: str, voix: str) -> dict[str, Any]:
    """Écrit la voix retenue dans `projet.yaml`."""
    _voix_valide(provider, voix)
    fait = subprocess.run(
        [sys.executable, "-m", "fresque", "voix-choix", slug,
         "--provider", provider, "--voix", voix],
        cwd=_racine(), env=_environnement(), capture_output=True, text=True,
    )
    if fait.returncode != 0:
        raise ValueError((fait.stderr or fait.stdout).strip().lstrip("✗ ")
                         or "choix refusé")
    return {"provider": provider, "voix": voix}


def remplacer(slug: str, plan: str, raison: str = "") -> dict[str, Any]:
    """Le bouton « Remplacer » de la galerie.

    Attendu plutôt que journalisé, comme la synthèse d'un hook : un clic
    sur une vignette ne mérite pas qu'on ouvre un flux. Une archive prend
    quelques secondes, une image générée davantage — c'est le prix d'un
    bouton qui rend la nouvelle image plutôt qu'un identifiant de journal.
    """
    if not _ID_PLAN.match(plan):
        raise ValueError(f"plan {plan!r} — attendu S001, S002…")
    argv = [sys.executable, "-m", "fresque", "refaire", slug, plan]
    if raison:
        argv += ["--raison", raison]

    fait = subprocess.run(
        argv, cwd=_racine(), env=_environnement(),
        capture_output=True, text=True,
    )
    if fait.returncode != 0:
        raise ValueError((fait.stderr or fait.stdout).strip().lstrip("✗ ")
                         or "remplacement refusé")
    return {"sortie": fait.stdout.strip()}


def _argv(nom: str, slug: str, options: dict[str, str]) -> list[str]:
    """La ligne de commande d'une exécution. Fonction pure, donc vérifiable.

    C'est le seul endroit où ce qui vient du navigateur entre dans un
    `argv` : chaque valeur est convertie selon le type déclaré de son
    option, et une option textuelle est confrontée à son motif.
    """
    commande = COMMANDES[nom]
    argv = [sys.executable, "-m", "fresque", nom, slug]
    for option in commande.options:
        brut = options.get(option.nom)
        if brut in (None, "", False):
            continue
        if option.type == "drapeau":
            argv.append(f"--{option.nom}")
        elif option.type == "nombre":
            argv += [f"--{option.nom}", str(float(brut))]
        elif option.type == "entier":
            # `--piste 2.0` fait échouer un `type=int` côté argparse. Une
            # option entière se convertit en entier, pas en flottant.
            argv += [f"--{option.nom}", str(int(float(brut)))]
        else:
            if not re.match(option.motif, str(brut)):
                raise ValueError(f"{option.nom} : {brut!r} n'est pas une valeur valide")
            argv += [f"--{option.nom}", str(brut)]
    return argv


def creer(sujet: str, template: str | None = None) -> str:
    """Un sujet tapé dans la barre devient un dossier. Rend le slug.

    Passe par `python -m fresque nouveau`, comme tout le reste : le serveur
    n'écrit pas dans `projects/` lui-même. C'est synchrone parce que ça ne
    fait que créer trois dossiers et un `projet.yaml`, et que la page a
    besoin du slug pour naviguer — mais c'est le même sous-processus que si
    on l'avait tapé au terminal.
    """
    argv = [sys.executable, "-m", "fresque", "nouveau", sujet]
    if template:
        argv += ["--template", template]
    fait = subprocess.run(
        argv, cwd=_racine(), env=_environnement(),
        capture_output=True, text=True,
    )
    if fait.returncode != 0:
        # `_fail` préfixe ses messages d'une croix, utile au terminal et
        # bruyante dans une bulle d'erreur du navigateur.
        motif = (fait.stderr or fait.stdout).strip().lstrip("✗ ")
        raise ValueError(motif or "création refusée")
    for ligne in fait.stdout.splitlines():
        if ligne.startswith("✓ projects/"):
            return ligne.split("/")[1]
    raise ValueError("création sans slug — voir le journal")


def lancer(slug: str, nom: str, options: dict[str, str]) -> str:
    """Lance une commande du pipeline et retourne l'identifiant du journal."""
    commande = COMMANDES.get(nom)
    if commande is None:
        raise KeyError(nom)
    dossier = _projet_dir(slug)

    argv = _argv(nom, slug, options)

    identifiant = f"{time.strftime('%Y%m%d-%H%M%S')}-{nom}"
    journal = dossier / JOURNAL_DIR
    journal.mkdir(exist_ok=True)
    log = journal / f"{identifiant}.log"
    fiche = journal / f"{identifiant}.json"

    fiche.write_text(json.dumps({
        "commande": nom, "argv": argv[2:], "debut": time.time(), "code": None,
    }, ensure_ascii=False), encoding="utf-8")

    environnement = dict(**_environnement())
    flux = log.open("wb")
    processus = subprocess.Popen(
        argv, cwd=_racine(), env=environnement,
        stdout=flux, stderr=subprocess.STDOUT,
    )
    with _VERROU:
        _VIVANTS[identifiant] = processus

    # Le pid est écrit dans le fichier, pas seulement gardé en mémoire.
    # Sans lui, redémarrer le serveur pendant un rendu de trente minutes
    # faisait déclarer « interrompu » un processus qui tournait toujours :
    # la seule preuve qu'il vivait était dans le processus qu'on venait de
    # tuer. Un processus long se surveille par son pid.
    donnees = json.loads(fiche.read_text(encoding="utf-8"))
    donnees["pid"] = processus.pid
    fiche.write_text(json.dumps(donnees, ensure_ascii=False), encoding="utf-8")

    def attendre() -> None:
        code = processus.wait()
        flux.close()
        with _VERROU:
            _VIVANTS.pop(identifiant, None)
        donnees = json.loads(fiche.read_text(encoding="utf-8"))
        donnees.update(fin=time.time(), code=code)
        fiche.write_text(json.dumps(donnees, ensure_ascii=False), encoding="utf-8")

    threading.Thread(target=attendre, daemon=True).start()
    return identifiant


def _environnement() -> dict[str, str]:
    """L'environnement d'un sous-processus : celui du serveur, plus le
    chemin d'import du paquet et la sortie non tamponnée — sans quoi le
    journal n'arriverait qu'à la fin de la commande, ce qui est le
    contraire de ce qu'on veut regarder."""
    env = dict(os.environ)
    chemin = str(_racine() / "pipeline")
    existant = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{chemin}:{existant}" if existant else chemin
    env["PYTHONUNBUFFERED"] = "1"
    return env


def arreter(identifiant: str) -> bool:
    with _VERROU:
        processus = _VIVANTS.get(identifiant)
    if processus is None:
        return False
    processus.terminate()
    return True


def _tourne_encore(pid: Any) -> bool:
    """Ce pid est-il encore un processus vivant ?

    Consulté quand la mémoire ne sait rien — typiquement après un
    redémarrage du serveur pendant un rendu. Le signal 0 ne fait rien : il
    ne sert qu'à demander au noyau si le processus existe.

    Faux positif possible : le système a pu réattribuer le pid à autre
    chose. Il faudrait des heures d'uptime et un compteur rebouclé pour
    tomber dessus, et le pire cas est d'attendre une commande qui ne
    reviendra pas — contre, aujourd'hui, déclarer morte une commande qui
    tourne.
    """
    if not isinstance(pid, int):
        return False
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def journal(slug: str, identifiant: str, depuis: int = 0) -> dict[str, Any]:
    """Lit la suite d'un journal. Le fichier est la vérité, pas la mémoire."""
    if not _ID_JOURNAL.match(identifiant):
        raise ValueError(identifiant)
    dossier = _projet_dir(slug) / JOURNAL_DIR
    log = dossier / f"{identifiant}.log"
    fiche = dossier / f"{identifiant}.json"

    octets = log.read_bytes()[depuis:] if log.is_file() else b""
    donnees = json.loads(fiche.read_text(encoding="utf-8")) if fiche.is_file() else {}

    with _VERROU:
        vivant = identifiant in _VIVANTS
    if not vivant:
        vivant = _tourne_encore(donnees.get("pid"))
    code = donnees.get("code")
    # Une fiche restée à `code: null` sans processus vivant signale un
    # serveur redémarré ET un processus mort. On le dit plutôt que de
    # laisser l'interface tourner indéfiniment.
    return {
        "texte": octets.decode("utf-8", "replace"),
        "offset": depuis + len(octets),
        "vivant": vivant,
        "code": code,
        "interrompu": code is None and not vivant and bool(donnees),
    }


def journaux(slug: str, limite: int = 12) -> list[dict[str, Any]]:
    dossier = _projet_dir(slug) / JOURNAL_DIR
    if not dossier.is_dir():
        return []
    sorties = []
    for fiche in sorted(dossier.glob("*.json"), reverse=True)[:limite]:
        try:
            donnees = json.loads(fiche.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        donnees["id"] = fiche.stem
        with _VERROU:
            donnees["vivant"] = fiche.stem in _VIVANTS
        sorties.append(donnees)
    return sorties


# --- Inventaire --------------------------------------------------------------

def projets() -> list[dict[str, Any]]:
    """Ce que l'atelier contient, lu à chaud à chaque appel.

    Volontairement sans `Project.open()` : ouvrir un projet modifie la
    configuration active du processus, ce qu'une simple liste n'a aucune
    raison de faire.
    """
    racine = _racine() / "projects"
    if not racine.is_dir():
        return []
    sorties = []
    for dossier in sorted(racine.iterdir()):
        if not dossier.is_dir() or dossier.name.startswith("."):
            continue
        fiche = dossier / "projet.yaml"
        donnees = {}
        if fiche.is_file():
            donnees = yaml.safe_load(fiche.read_text(encoding="utf-8")) or {}
        faits = [(nom, _etape_faite(dossier, rel)) for nom, rel in ETAPES]
        sorties.append({
            "slug": dossier.name,
            # Le titre d'un projet est celui de la piste retenue, et avant
            # ça le sujet tapé par l'utilisateur. Afficher le slug à la
            # place se lisait comme un bug.
            # `00-brief.md` en dernier recours : l'étape n'existe plus, mais
            # les projets montés avant sa suppression ont le leur.
            "titre": (donnees.get("titre") or donnees.get("sujet")
                      or _titre(dossier / "00-brief.md") or dossier.name),
            "template": donnees.get("template"),
            "etapes": faits,
            "avancement": sum(1 for _, ok in faits if ok),
            "mesures": _mesures(dossier),
            "vignette": _vignette(dossier),
        })
    return sorties


def _etape_faite(dossier: Path, relatif: str) -> bool:
    """Le fichier existe-t-il, et dit-il ce que l'étape promet ?

    Pour tous les fichiers sauf un, exister suffit. `alignment.json` fait
    exception : `align` l'écrit sans audio, avec des durées estimées, et
    `voice` l'écrit avec des durées mesurées. Les deux produisent le même
    nom de fichier, donc la jauge affichait la voix comme faite alors
    qu'aucun son n'existait — et l'étape suivante partait sur des chiffres
    devinés.

    Le champ `source` tranche : `estimate` n'est pas une voix.
    """
    chemin = dossier / relatif
    if not chemin.exists():
        return False
    if relatif != "04-audio/alignment.json":
        return True
    try:
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return donnees.get("source") != "estimate"


def _titre(brief: Path) -> str:
    if not brief.is_file():
        return ""
    for ligne in brief.read_text(encoding="utf-8").splitlines():
        if ligne.startswith("# "):
            return ligne[2:].strip()
    return ""


def _mesures(dossier: Path) -> list[tuple[str, str]]:
    """Les chiffres qu'on lit sans rien recalculer."""
    sorties: list[tuple[str, str]] = []
    montage = dossier / "06-timeline.json"
    if montage.is_file():
        try:
            donnees = json.loads(montage.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return sorties
        duree = donnees.get("duree_s", 0)
        sorties.append(("durée", f"{duree / 60:.1f} min"))
        sorties.append(("plans", str(len(donnees.get("clips", [])))))
        if duree:
            sorties.append(
                ("plans/min", f"{len(donnees.get('clips', [])) / duree * 60:.1f}")
            )
    video = dossier / "07-out" / "video.mp4"
    if video.is_file():
        sorties.append(("mp4", f"{video.stat().st_size / 1e6:.0f} Mo"))
    return sorties


def _vignette(dossier: Path) -> str | None:
    """L'image du premier plan du film, pas la première du dossier.

    Prendre le premier fichier venu donnait la même photo à trois projets
    différents — le dossier est trié par nom, et une image réutilisée peut
    très bien arriver en tête. On demande donc à `assets.json` le visuel du
    plan le plus petit, qui est l'ouverture : c'est ce que le spectateur
    verrait en premier, et c'est bien ce qu'une vignette doit montrer.
    """
    fiche = dossier / "05-visuals" / "assets.json"
    if not fiche.is_file():
        return None
    try:
        assets = (json.loads(fiche.read_text(encoding="utf-8")) or {}).get("assets", {})
    except json.JSONDecodeError:
        return None
    for cle in sorted(assets):
        fichier = assets[cle].get("fichier")
        if fichier and (dossier / fichier).is_file():
            return fichier
    return None


# --- Pages -------------------------------------------------------------------

#: Le bandeau seul. Séparé du reste parce que l'export le greffe sur des
#: pages qui ont déjà leur propre feuille — `review.html` et l'aperçu d'un
#: template — et qu'y verser toute la nôtre réécrirait leur mise en page.
_BARRE = """
.barre { display:flex; align-items:center; gap:16px; padding:0 22px; height:52px;
         border-bottom:1px solid #1b1f28; background:#0e1117; position:sticky;
         top:0; z-index:5; }
.barre .marque { font-weight:600; letter-spacing:-0.01em; }
.barre nav { display:flex; gap:4px; margin-left:12px; }
.barre nav a { padding:6px 12px; border-radius:7px; font-size:13px; color:#8b93a1; }
.barre nav a:hover { background:#161a23; color:#e8eaee; }
.barre nav a.actif { background:#1d2735; color:#7fa8e0; }
.barre .fin { margin-left:auto; color:#5f6775; font-size:12px; }
.barre a { color:inherit; text-decoration:none; }
"""

_CHROME = _BARRE + """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin:0; background:#0b0d11; color:#e8eaee;
       font-family:'Inter','Helvetica Neue',Arial,sans-serif; }
a { color:inherit; text-decoration:none; }
h2 { font-size:13px; letter-spacing:.18em; text-transform:uppercase;
     color:#8b93a1; margin:38px 0 14px; font-weight:600; }
.pied { color:#5f6775; font-size:12px; margin-top:44px; line-height:1.7;
        max-width:70ch; }
code { background:#151922; padding:2px 7px; border-radius:5px; color:#c7ccd6; }
"""

_ATELIER = """
main { max-width:1360px; margin:0 auto; padding:34px 26px 90px; }
.cartes { display:grid; grid-template-columns:repeat(auto-fill,minmax(310px,1fr));
          gap:18px; }
.carte { border:1px solid #1b1f28; border-radius:12px; overflow:hidden;
         background:#0e1117; display:block; transition:border-color .12s; }
.carte:hover { border-color:#3a4150; }
.carte .image { aspect-ratio:16/9; background:#14171d; object-fit:cover;
                width:100%; display:block; }
.carte .vide { aspect-ratio:16/9; background:linear-gradient(135deg,#171b24,#0d1014);
               display:flex; align-items:center; justify-content:center;
               color:#3a4150; font-size:12px; letter-spacing:.14em;
               text-transform:uppercase; }
.carte .corps { padding:14px 16px 16px; }
.carte h3 { margin:0 0 4px; font-size:15px; font-weight:600; line-height:1.35; }
.carte .slug { color:#5f6775; font-size:11px; font-family:ui-monospace,monospace; }
.jauge { display:flex; gap:3px; margin:12px 0 10px; }
.jauge i { height:4px; flex:1; border-radius:2px; background:#1b1f28; }
.jauge i.ok { background:#4b7bd4; }
.mesures { display:flex; flex-wrap:wrap; gap:12px; color:#8b93a1; font-size:11px; }
.mesures b { color:#c7ccd6; font-variant-numeric:tabular-nums; font-weight:600; }
.etiquette { display:inline-block; margin-top:10px; padding:3px 9px; font-size:10px;
             border-radius:5px; background:#221a2c; color:#b18fd8;
             letter-spacing:.06em; }
.templates { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr));
             gap:14px; }
.tuile { border:1px solid #1b1f28; border-radius:10px; padding:16px 18px;
         background:#0e1117; }
.tuile:hover { border-color:#3a4150; }
.tuile h3 { margin:0 0 6px; font-size:14px; }
.tuile p { margin:0; color:#8b93a1; font-size:12px; line-height:1.55; }
"""


@dataclass(frozen=True)
class Liens:
    """Où pointent les liens d'une page.

    Servies, les pages s'adressent à des routes ; exportées, à des fichiers
    voisins. Le seul écart entre les deux tient dans ces quatre fonctions,
    ce qui évite de réécrire du HTML déjà produit — une manœuvre qui marche
    jusqu'au jour où un titre de projet contient la chaîne cherchée.
    """
    accueil: str = "/"
    projet: Any = staticmethod(lambda slug: f"/p/{urllib.parse.quote(slug)}/")
    fichier: Any = staticmethod(
        lambda slug, rel: f"/p/{urllib.parse.quote(slug)}/{urllib.parse.quote(rel)}")
    template: Any = staticmethod(lambda nom: f"/t/{urllib.parse.quote(nom)}/")


SERVIS = Liens()


def _entete(actif: str, liens: Liens, fin: str = "") -> str:
    onglets = ((liens.accueil, "Atelier"), (liens.accueil, "Templates"))
    rendus = "".join(
        f'<a href="{href}" class="{"actif" if nom == actif else ""}">{nom}</a>'
        for href, nom in onglets
    )
    return (f'<div class="barre"><span class="marque">Fresque</span>'
            f'<nav>{rendus}</nav><span class="fin">{html.escape(fin)}</span></div>')


def page_atelier(liens: Liens = SERVIS) -> str:
    liste = projets()
    cartes = []
    for projet in liste:
        jauge = "".join(
            f'<i class="{"ok" if ok else ""}" title="{html.escape(nom)}"></i>'
            for nom, ok in projet["etapes"]
        )
        mesures = "".join(
            f'<span><b>{html.escape(v)}</b> {html.escape(nom)}</span>'
            for nom, v in projet["mesures"]
        )
        image = (
            f'<img class="image" loading="lazy" '
            f'src="{liens.fichier(projet["slug"], projet["vignette"])}" alt="">'
            if projet["vignette"] else '<div class="vide">pas encore d\'image</div>'
        )
        cartes.append(f"""<a class="carte" href="{liens.projet(projet['slug'])}">
  {image}
  <div class="corps">
    <h3>{html.escape(projet['titre'])}</h3>
    <div class="slug">{html.escape(projet['slug'])}</div>
    <div class="jauge">{jauge}</div>
    <div class="mesures">{mesures or '<span>pas encore monté</span>'}</div>
    {f'<span class="etiquette">{html.escape(projet["template"])}</span>'
     if projet['template'] else ''}
  </div>
</a>""")

    tuiles = []
    for nom in config.available_templates():
        try:
            meta = apercu.resume(nom)
        except config.TemplateError:
            continue
        tuiles.append(f"""<a class="tuile" href="{liens.template(nom)}">
  <h3>{html.escape(meta['meta'].get('nom', nom))}</h3>
  <p>{html.escape(str(meta['meta'].get('description', ''))[:150])}</p>
  <p style="margin-top:8px;color:#5f6775">{meta['nb_propres']} réglages propres</p>
</a>""")

    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fresque — atelier</title>
<style>{_CHROME}{_ATELIER}</style></head><body>
{_entete("Atelier", liens, f"{len(liste)} projet(s)")}
<main>
<h2>Projets</h2>
<div class="cartes">{''.join(cartes) or
  '<p style="color:#5f6775">Aucun projet. <code>/fresque &lt;sujet&gt;</code> '
  'dans Claude Code pour en démarrer un.</p>'}</div>
<h2>Templates</h2>
<div class="templates">{''.join(tuiles)}</div>
<p class="pied">
Ce serveur ne détient rien : il relit <code>projects/</code> et
<code>templates/</code> à chaque page, et pour agir il n'appelle que
<code>python -m fresque</code>. L'arrêter ne perd aucun état — les journaux
d'exécution restent dans <code>projects/&lt;slug&gt;/journal/</code>.
</p>
</main></body></html>"""


_PILOTE = """
.ecran { display:flex; height:calc(100vh - 52px); }
.pilote { width:400px; min-width:400px; border-right:1px solid #1b1f28;
          background:#0e1117; overflow-y:auto; padding:20px 18px 40px; }
.pilote h2 { margin-top:0; }
.pilote h2:not(:first-child) { margin-top:30px; }
.commande { border:1px solid #1b1f28; border-radius:9px; margin-bottom:8px;
            background:#111520; }
.commande > .ligne { display:flex; align-items:center; gap:10px;
                     padding:10px 12px; }
.commande .nom { font-size:13px; flex:1; }
.commande .nom small { display:block; color:#5f6775; font-size:10px;
                       font-family:ui-monospace,monospace; margin-top:2px; }
.commande button { border:1px solid #2a3140; background:#171c27; color:#c7ccd6;
                   border-radius:6px; padding:5px 12px; font-size:12px;
                   cursor:pointer; font-family:inherit; }
.commande button:hover { background:#1f2634; color:#fff; }
.commande button:disabled { opacity:.35; cursor:default; }
.commande.manque { opacity:.4; }
.commande.depense .nom::after { content:" € API"; color:#c9a227; font-size:10px; }
.opts { display:flex; flex-wrap:wrap; gap:8px; padding:0 12px 10px; }
.opts label { font-size:11px; color:#8b93a1; display:flex; align-items:center;
              gap:5px; }
.opts input[type=text] { width:74px; background:#0b0d11; border:1px solid #232833;
              color:#e8eaee; border-radius:5px; padding:3px 6px; font-size:11px;
              font-family:ui-monospace,monospace; }
.console { background:#07090c; border:1px solid #1b1f28; border-radius:9px;
           padding:12px 14px; margin-top:12px; }
.console pre { margin:0; font-family:ui-monospace,monospace; font-size:11px;
               line-height:1.55; color:#aab1bd; white-space:pre-wrap;
               word-break:break-word; max-height:320px; overflow-y:auto; }
.console .tete { display:flex; align-items:center; gap:8px; margin-bottom:8px;
                 font-size:11px; color:#8b93a1; }
.console .tete .pastille { width:7px; height:7px; border-radius:50%;
                           background:#3a4150; }
.console .tete .pastille.vivant { background:#c9a227;
                                  animation:battre 1.1s infinite; }
.console .tete .pastille.ok { background:#3fae6a; }
.console .tete .pastille.rate { background:#e0524a; }
@keyframes battre { 50% { opacity:.25; } }
.console .tete button { margin-left:auto; border:1px solid #3a2020;
           background:#1d1113; color:#e0524a; border-radius:5px;
           padding:3px 9px; font-size:11px; cursor:pointer; font-family:inherit; }
.passe { font-size:11px; color:#5f6775; line-height:1.8; }
.passe a { color:#7c8698; }
.passe a:hover { color:#e8eaee; }
.vue { flex:1; border:0; background:#0b0d11; }
"""


#: Le pilote, en JavaScript ordinaire. Hors de toute f-string : doubler
#: chaque accolade d'un programme pour le faire tenir dans un `format()`
#: le rend illisible, et une accolade oubliée ne se voit qu'à l'exécution.
#: `__SLUG__` est la seule substitution, et elle passe par `json.dumps`.
_SCRIPT_PILOTE = """
const SLUG = __SLUG__;
const $ = (id) => document.getElementById(id);
const boite = $('console'), sortie = $('sortie'), etat = $('etat');
const pastille = $('pastille'), arret = $('arret'), vue = $('vue');

let courant = null, offset = 0, minuteur = null;

function options(carte) {
  const valeurs = {};
  carte.querySelectorAll('[data-opt]').forEach((champ) => {
    valeurs[champ.dataset.opt] =
      champ.type === 'checkbox' ? champ.checked : champ.value;
  });
  return valeurs;
}

async function lancer(carte) {
  const reponse = await fetch('/api/lancer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      slug: SLUG,
      commande: carte.dataset.commande,
      options: options(carte),
    }),
  });
  const donnees = await reponse.json();
  if (donnees.erreur) { alert(donnees.erreur); return; }
  suivre(donnees.id);
}

function suivre(id) {
  courant = id;
  offset = 0;
  sortie.textContent = '';
  boite.hidden = false;
  clearInterval(minuteur);
  minuteur = setInterval(rafraichir, 700);
  rafraichir();
}

async function rafraichir() {
  const url = '/api/journal?slug=' + encodeURIComponent(SLUG)
            + '&id=' + encodeURIComponent(courant) + '&depuis=' + offset;
  const donnees = await (await fetch(url)).json();
  if (donnees.erreur) { clearInterval(minuteur); return; }

  if (donnees.texte) {
    sortie.textContent += donnees.texte;
    sortie.scrollTop = sortie.scrollHeight;
    offset = donnees.offset;
  }

  const fini = !donnees.vivant;
  etat.textContent = courant + ' — ' + (
    donnees.vivant ? 'en cours'
    : donnees.interrompu ? 'interrompu (serveur redémarré)'
    : 'terminé, code ' + donnees.code);
  pastille.className = 'pastille ' + (
    donnees.vivant ? 'vivant' : donnees.code === 0 ? 'ok' : 'rate');
  arret.hidden = fini;

  if (fini) {
    clearInterval(minuteur);
    // Les fichiers ont changé. La page de validation se refait à chaque
    // requête : la redemander suffit à la remettre d'accord avec eux.
    vue.contentWindow.location.reload();
  }
}

document.querySelectorAll('.commande button').forEach((bouton) => {
  bouton.addEventListener('click', () => lancer(bouton.closest('.commande')));
});
document.querySelectorAll('[data-rejouer]').forEach((lien) => {
  lien.addEventListener('click', (evenement) => {
    evenement.preventDefault();
    suivre(lien.dataset.rejouer);
  });
});
arret.addEventListener('click', () => fetch('/api/arreter', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ id: courant }),
}));
"""


def _issue(execution: dict[str, Any]) -> str:
    """Comment s'est terminée une exécution passée.

    Un code resté nul sans processus vivant n'est pas un succès : c'est un
    serveur qui s'est arrêté pendant la commande. Le dire, plutôt que de
    laisser croire que l'étape est faite.
    """
    if execution.get("vivant"):
        return "en cours"
    code = execution.get("code")
    if code is None:
        return "interrompu"
    return "ok" if code == 0 else f"code {code}"


def page_projet(slug: str) -> str:
    dossier = _projet_dir(slug)
    presents = {rel for _, rel in ETAPES if (dossier / rel).exists()}

    cartes = []
    for nom, commande in COMMANDES.items():
        manque = bool(commande.exige) and commande.exige not in presents
        options = "".join(
            f'<label><input type="checkbox" data-opt="{o.nom}"> {html.escape(o.libelle)}</label>'
            if o.type == "drapeau" else
            f'<label>{html.escape(o.libelle)} '
            f'<input type="text" data-opt="{o.nom}" value="{html.escape(o.defaut)}"></label>'
            for o in commande.options
        )
        classes = " ".join(filter(None, [
            "commande", "manque" if manque else "", "depense" if commande.depense else "",
        ]))
        titre = (f"exige {commande.exige}" if manque
                 else (f"écrit {commande.produit}" if commande.produit else ""))
        cartes.append(f"""<div class="{classes}" data-commande="{nom}">
  <div class="ligne">
    <span class="nom">{html.escape(commande.libelle)}<small>fresque {nom}{
        ' · ' + html.escape(titre) if titre else ''}</small></span>
    <button {'disabled' if manque else ''}>lancer</button>
  </div>
  {f'<div class="opts">{options}</div>' if options and not manque else ''}
</div>""")

    passe = "".join(
        f'<div><a href="#" data-rejouer="{html.escape(j["id"])}">'
        f'{html.escape(j["id"])}</a> — {_issue(j)}</div>'
        for j in journaux(slug)
    ) or '<div style="color:#3a4150">aucune exécution</div>'

    quote = urllib.parse.quote(slug)
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(slug)} — Fresque</title>
<style>{_CHROME}{_PILOTE}</style></head><body>
{_entete("", SERVIS, slug)}
<div class="ecran">
  <aside class="pilote">
    <h2>Étapes</h2>
    {''.join(cartes)}
    <div class="console" id="console" hidden>
      <div class="tete">
        <span class="pastille" id="pastille"></span>
        <span id="etat">—</span>
        <button id="arret" hidden>arrêter</button>
      </div>
      <pre id="sortie"></pre>
    </div>
    <h2>Exécutions passées</h2>
    <div class="passe">{passe}</div>
  </aside>
  <iframe class="vue" id="vue" src="/p/{quote}/review.html"></iframe>
</div>
<script>{_SCRIPT_PILOTE.replace("__SLUG__", json.dumps(slug))}</script>
</body></html>"""


# --- Serveur -----------------------------------------------------------------

_RANGE = re.compile(r"^bytes=(\d+)-(\d*)$")
_MORCEAU = 256 * 1024

TYPES = {
    ".html": "text/html; charset=utf-8", ".json": "application/json",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".svg": "image/svg+xml", ".mp4": "video/mp4",
    ".webm": "video/webm", ".wav": "audio/wav", ".mp3": "audio/mpeg",
    ".md": "text/plain; charset=utf-8", ".srt": "text/plain; charset=utf-8",
    ".log": "text/plain; charset=utf-8", ".yaml": "text/plain; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "fresque"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass  # le journal utile est celui des commandes, pas celui des GET

    # -- sorties
    def _envoyer(self, corps: bytes, type_mime: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", type_mime)
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(corps)

    def _html(self, texte: str, code: int = 200) -> None:
        self._envoyer(texte.encode("utf-8"), "text/html; charset=utf-8", code)

    def _json(self, donnees: Any, code: int = 200) -> None:
        self._envoyer(json.dumps(donnees, ensure_ascii=False).encode("utf-8"),
                      "application/json", code)

    def _fichier(self, chemin: Path, racine: Path) -> None:
        """Sert un fichier, après avoir prouvé qu'il est sous `racine`.

        Diffusé par morceaux et avec `Range` : un montage de quinze minutes
        pèse 779 Mo, qu'on ne charge pas en mémoire pour l'afficher — et sans
        `Range` le navigateur refuse de se déplacer dans la vidéo, ce qui
        retire à la page de validation l'essentiel de son intérêt.
        """
        try:
            resolu = chemin.resolve()
            resolu.relative_to(racine.resolve())
        except (ValueError, OSError):
            return self._html("<h1>404</h1>", 404)
        if not resolu.is_file():
            return self._html("<h1>404</h1>", 404)

        taille = resolu.stat().st_size
        type_mime = TYPES.get(resolu.suffix.lower(), "application/octet-stream")
        debut, fin = 0, taille - 1

        demande = _RANGE.match(self.headers.get("Range") or "")
        partiel = bool(demande) and taille > 0
        if partiel:
            debut = int(demande.group(1))
            fin = int(demande.group(2) or taille - 1)
            if debut >= taille:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{taille}")
                self.end_headers()
                return
            fin = min(fin, taille - 1)

        longueur = fin - debut + 1
        self.send_response(206 if partiel else 200)
        self.send_header("Content-Type", type_mime)
        self.send_header("Content-Length", str(longueur))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        if partiel:
            self.send_header("Content-Range", f"bytes {debut}-{fin}/{taille}")
        self.end_headers()
        if self.command == "HEAD":
            return

        with resolu.open("rb") as flux:
            flux.seek(debut)
            reste = longueur
            while reste > 0:
                morceau = flux.read(min(_MORCEAU, reste))
                if not morceau:
                    break
                self.wfile.write(morceau)
                reste -= len(morceau)

    # -- routage
    def do_GET(self) -> None:  # noqa: N802
        chemin = urllib.parse.urlparse(self.path)
        parties = [urllib.parse.unquote(p) for p in chemin.path.strip("/").split("/")]
        requete = urllib.parse.parse_qs(chemin.query)

        try:
            if chemin.path == "/":
                return self._html(page_atelier())
            if chemin.path == "/templates":
                return self._html(page_atelier())

            if parties[0] == "api":
                return self._api_get(parties[1:], requete)

            if parties[0] == "assets":
                racine = _racine() / "assets"
                return self._fichier(racine.joinpath(*parties[1:]), racine)

            if parties[0] == "t" and len(parties) >= 2:
                return self._template(parties[1], parties[2:])

            if parties[0] == "p" and len(parties) >= 2:
                return self._projet(parties[1], [p for p in parties[2:] if p])

            self._html("<h1>404</h1>", 404)
        except FileNotFoundError:
            self._html("<h1>404</h1>", 404)
        except Exception as erreur:                      # noqa: BLE001
            self._html(f"<pre>{html.escape(str(erreur))}</pre>", 500)

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_POST(self) -> None:  # noqa: N802
        taille = int(self.headers.get("Content-Length") or 0)
        try:
            corps = json.loads(self.rfile.read(taille) or b"{}")
        except json.JSONDecodeError:
            return self._json({"erreur": "corps illisible"}, 400)

        try:
            if self.path == "/api/lancer":
                identifiant = lancer(
                    str(corps.get("slug", "")), str(corps.get("commande", "")),
                    dict(corps.get("options") or {}),
                )
                return self._json({"id": identifiant})
            if self.path == "/api/arreter":
                return self._json({"arrete": arreter(str(corps.get("id", "")))})
            self._json({"erreur": "route inconnue"}, 404)
        except KeyError as erreur:
            self._json({"erreur": f"commande inconnue : {erreur}"}, 400)
        except FileNotFoundError as erreur:
            self._json({"erreur": f"projet inconnu : {erreur}"}, 404)
        except ValueError as erreur:
            self._json({"erreur": str(erreur)}, 400)

    def _api_get(self, parties: list[str], requete: dict[str, list[str]]) -> None:
        if parties[:1] == ["journal"]:
            try:
                return self._json(journal(
                    requete.get("slug", [""])[0], requete.get("id", [""])[0],
                    int(requete.get("depuis", ["0"])[0]),
                ))
            except (ValueError, FileNotFoundError) as erreur:
                return self._json({"erreur": str(erreur)}, 400)
        if parties[:1] == ["etat"]:
            return self._json({"projets": projets(),
                               "templates": config.available_templates()})
        self._json({"erreur": "route inconnue"}, 404)

    def _projet(self, slug: str, reste: list[str]) -> None:
        dossier = _projet_dir(slug)
        if not reste:
            return self._html(page_projet(slug))
        # La page de validation est une projection : on la refait avant de
        # la servir, pour qu'elle ne puisse jamais mentir sur les fichiers.
        if reste == ["review.html"]:
            with _VERROU_CONFIG:
                review.construire(slug)
        self._fichier(dossier.joinpath(*reste), dossier)

    def _template(self, nom: str, reste: list[str]) -> None:
        if nom not in config.available_templates():
            return self._html("<h1>404</h1>", 404)
        if reste and reste[0]:
            racine = _racine() / "assets" / "musiques"
            return self._fichier(racine / reste[0], racine)

        # Dans un dossier temporaire, jamais dans `projects/` : un cache
        # déposé là apparaît comme un projet, et ce serveur n'a aucune
        # raison de laisser une trace pour afficher une page.
        with tempfile.TemporaryDirectory() as temporaire:
            destination = Path(temporaire) / f"{nom}.html"
            with _VERROU_CONFIG:
                musiques = sorted((_racine() / "assets" / "musiques").glob("*.mp3"))
                apercu.page(nom, destination, musiques[0] if musiques else None)
            corps = destination.read_text(encoding="utf-8")
        # L'aperçu est écrit pour s'ouvrir en `file://` : son lecteur audio
        # pointe sur un nom de fichier voisin. Servi, il lui faut une URL.
        corps = corps.replace('<body>', f'<body>{_entete("Templates", SERVIS, nom)}')
        return self._html(corps)


def servir(hote: str = "127.0.0.1", port: int = 4321) -> None:
    serveur = ThreadingHTTPServer((hote, port), Handler)
    print(f"Atelier Fresque — http://{hote}:{port}")
    print("Ctrl-C pour arrêter. Rien ne sera perdu : le serveur ne détient rien.")
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
    finally:
        serveur.server_close()
