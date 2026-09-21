"""L'API de l'atelier Fresque.

Elle n'implémente aucune étape du pipeline. Pour agir, elle appelle les
fonctions que `fresque.serveur` expose déjà — `lancer`, `arreter`,
`journal`, `projets` — qui lancent `python -m fresque <commande>` en
sous-processus et écrivent la sortie dans `projects/<slug>/journal/`.

Ce qui change par rapport à `fresque serve` : la page HTML rendue en Python
est remplacée par du JSON et une application React. Le reste est identique,
et les deux serveurs peuvent coexister.
"""
from __future__ import annotations

import asyncio
import json
import mimetypes
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "pipeline"))

from fresque import serveur  # noqa: E402

WEB = RACINE / "web" / "dist"

app = FastAPI(title="Fresque", docs_url="/api/docs")

# En développement, Vite sert l'interface sur un autre port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Lecture -----------------------------------------------------------------

@app.get("/api/commandes")
def commandes() -> dict[str, Any]:
    """Les commandes lançables. Liste close, définie dans `fresque.serveur`."""
    return {
        nom: {
            "nom": nom,
            "libelle": c.libelle,
            "exige": c.exige,
            "produit": c.produit,
            "depense": c.depense,
            "longue": c.longue,
            "options": [asdict(o) for o in c.options],
        }
        for nom, c in serveur.COMMANDES.items()
    }


@app.get("/api/projets")
def projets() -> list[dict[str, Any]]:
    return serveur.projets()


@app.get("/api/projets/{slug}")
def projet(slug: str) -> dict[str, Any]:
    fiche = next((p for p in serveur.projets() if p["slug"] == slug), None)
    if fiche is None:
        raise HTTPException(404, f"projet inconnu : {slug}")
    dossier = serveur._projet_dir(slug)
    fiche["fichiers"] = _fichiers(dossier)
    fiche["journaux"] = serveur.journaux(slug)
    fiche["composition"] = _composition(dossier)
    return fiche


def _fichiers(dossier: Path) -> list[dict[str, Any]]:
    """Une ligne par étape : le fichier attendu, et ce qu'on en sait."""
    sorties = []
    for nom, relatif in serveur.ETAPES:
        chemin = dossier / relatif
        sorties.append({
            "etape": nom,
            "fichier": relatif,
            "existe": chemin.exists(),
            "octets": chemin.stat().st_size if chemin.is_file() else None,
        })
    return sorties


def _composition(dossier: Path) -> dict[str, int]:
    """Le compte de plans par type, lu dans le plan visuel."""
    shots = dossier / "03-shots.json"
    if not shots.is_file():
        return {}
    try:
        donnees = json.loads(shots.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    compte: dict[str, int] = {}
    for plan in donnees.get("shots", []):
        type_de_plan = plan.get("type", "inconnu")
        compte[type_de_plan] = compte.get(type_de_plan, 0) + 1
    return compte


@app.get("/api/projets/{slug}/timeline")
def timeline(slug: str) -> Any:
    """`06-timeline.json`, tel quel.

    C'est ce que le moteur de rendu consomme, et c'est aussi ce que le
    lecteur du navigateur consomme : une seule source, donc un aperçu qui
    ne peut pas diverger du film.
    """
    chemin = _dossier(slug) / "06-timeline.json"
    if not chemin.is_file():
        raise HTTPException(404, "pas encore de montage")
    return json.loads(chemin.read_text(encoding="utf-8"))


@app.get("/api/templates")
def templates() -> list[dict[str, Any]]:
    import yaml

    sorties = []
    for fichier in sorted((RACINE / "templates").glob("*.yaml")):
        donnees = yaml.safe_load(fichier.read_text(encoding="utf-8")) or {}
        meta = donnees.get("meta", {})
        montage = donnees.get("montage", {})
        sorties.append({
            "nom": fichier.stem,
            "titre": meta.get("nom", fichier.stem),
            "description": meta.get("description", ""),
            "palette": montage.get("collage", {}),
            "rythme": {
                "mots_par_minute": donnees.get("narration", {}).get("mots_par_minute"),
                "plans_par_minute": donnees.get("visuels", {}).get("plans_par_minute"),
                "duree_plan_max_s": montage.get("duree_plan_max_s"),
            },
        })
    return sorties


@app.get("/api/projets/{slug}/media/{chemin:path}")
def media(slug: str, chemin: str) -> FileResponse:
    """Un fichier du projet, servi tel quel — vignette, mp4, audio.

    Le chemin vient du navigateur : il est résolu puis confronté au dossier
    du projet, jamais concaténé à l'aveugle.
    """
    dossier = _dossier(slug)
    cible = (dossier / chemin).resolve()
    if not str(cible).startswith(str(dossier.resolve())) or not cible.is_file():
        raise HTTPException(404, chemin)
    type_mime, _ = mimetypes.guess_type(cible.name)
    return FileResponse(cible, media_type=type_mime or "application/octet-stream")


# --- Action ------------------------------------------------------------------

class Lancement(BaseModel):
    nom: str
    options: dict[str, str] = {}


@app.post("/api/projets/{slug}/lancer")
def lancer(slug: str, corps: Lancement) -> dict[str, str]:
    _dossier(slug)
    try:
        identifiant = serveur.lancer(slug, corps.nom, corps.options)
    except KeyError:
        raise HTTPException(400, f"commande inconnue : {corps.nom}")
    except ValueError as erreur:
        raise HTTPException(400, str(erreur))
    return {"id": identifiant}


@app.post("/api/journaux/{identifiant}/arreter")
def arreter(identifiant: str) -> dict[str, bool]:
    return {"arrete": serveur.arreter(identifiant)}


@app.get("/api/projets/{slug}/journal/{identifiant}")
def journal(slug: str, identifiant: str, depuis: int = 0) -> dict[str, Any]:
    _dossier(slug)
    try:
        return serveur.journal(slug, identifiant, depuis)
    except ValueError:
        raise HTTPException(400, identifiant)


@app.get("/api/projets/{slug}/flux/{identifiant}")
async def flux(slug: str, identifiant: str, request: Request) -> StreamingResponse:
    """La sortie d'une commande, poussée au navigateur pendant qu'elle tourne.

    Le fichier reste la vérité : ce flux ne fait que relire le journal et
    envoyer ce qui s'y est ajouté. Fermer l'onglet n'interrompt rien.
    """
    _dossier(slug)

    async def evenements():
        offset = 0
        while True:
            if await request.is_disconnected():
                return
            try:
                etat = serveur.journal(slug, identifiant, offset)
            except ValueError:
                return
            offset = etat["offset"]
            yield f"data: {json.dumps(etat, ensure_ascii=False)}\n\n"
            if not etat["vivant"] and etat["code"] is not None:
                return
            if etat["interrompu"]:
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(
        evenements(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _dossier(slug: str) -> Path:
    try:
        return serveur._projet_dir(slug)
    except FileNotFoundError:
        raise HTTPException(404, f"projet inconnu : {slug}")


# --- L'interface -------------------------------------------------------------

if WEB.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")

    @app.get("/{chemin:path}")
    def interface(chemin: str) -> FileResponse:
        """Toute adresse inconnue rend l'application.

        Sans ça, ouvrir `/projets/<slug>` directement — ou recharger la page —
        renvoie un 404 : le routage vit dans le navigateur, pas ici.
        """
        fichier = (WEB / chemin) if chemin else None
        if fichier and fichier.is_file():
            return FileResponse(fichier)
        return FileResponse(WEB / "index.html")
else:
    @app.get("/")
    def accueil() -> dict[str, str]:
        return {
            "message": "L'interface n'est pas construite.",
            "faire": "cd web && npm install && npm run build",
            "developper": "cd web && npm run dev",
        }
