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

from fresque import pistes as pistes_mod, serveur  # noqa: E402

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
            # `existe` n'est pas `chemin.exists()` : un `alignment.json`
            # seulement estimé ne vaut pas une voix. Voir `_etape_faite`.
            "existe": serveur._etape_faite(dossier, relatif),
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


@app.get("/api/projets/{slug}/pistes")
def pistes(slug: str) -> dict[str, Any]:
    """`pistes.md` relu par le code, jamais par un modèle.

    L'interface a besoin de cartes cliquables ; le fichier reste la vérité.
    `retenue` dit laquelle a déjà été choisie, pour que rouvrir la page ne
    perde pas le choix — il est dans `projet.yaml`, pas dans le navigateur.
    """
    dossier = _dossier(slug)
    try:
        catalogue = pistes_mod.lire(dossier / "pistes.md")
    except FileNotFoundError:
        raise HTTPException(404, "pas encore de pistes")
    except pistes_mod.PistesError as erreur:
        raise HTTPException(422, str(erreur))
    catalogue["retenue"] = _projet_yaml(dossier).get("piste")
    return catalogue


def _projet_yaml(dossier: Path) -> dict[str, Any]:
    import yaml

    fiche = dossier / "projet.yaml"
    if not fiche.is_file():
        return {}
    return yaml.safe_load(fiche.read_text(encoding="utf-8")) or {}


@app.get("/api/projets/{slug}/hook")
def hook(slug: str) -> dict[str, Any]:
    """Le premier beat du script : ce qu'on lit, avant de l'entendre.

    Un script se valide en le lisant, alors qu'il sera entendu une seule
    fois, sans retour en arrière. Cet écran met les deux côte à côte.
    """
    from fresque import script_parser

    chemin = _dossier(slug) / "02-script.md"
    if not chemin.is_file():
        raise HTTPException(404, "pas encore de script")
    try:
        script = script_parser.parse(chemin)
    except script_parser.ScriptError as erreur:
        raise HTTPException(422, str(erreur))

    beat = script.beats[0]
    audio = _dossier(slug) / "04-audio" / f"essai-{beat.id}.wav"
    return {
        "beat": beat.id,
        "texte": beat.text,
        "intention": beat.intention,
        "mots": beat.word_count,
        "fichier": f"04-audio/essai-{beat.id}.wav" if audio.is_file() else None,
    }


@app.post("/api/projets/{slug}/hook")
def dire_le_hook(slug: str) -> dict[str, Any]:
    """Synthétise le hook, et rien d'autre.

    Trois secondes de voix, pas quinze minutes : c'est ce qui permet de
    l'entendre avant de décider. Synchrone parce que c'est court, et parce
    qu'un bouton qui ouvre un journal pour trois secondes d'audio demande
    plus d'attention qu'il n'en mérite.
    """
    _dossier(slug)
    try:
        return serveur.dire_beat(slug)
    except ValueError as erreur:
        raise HTTPException(400, str(erreur))


@app.get("/api/projets/{slug}/visuels")
def visuels(slug: str) -> dict[str, Any]:
    """Tous les éléments du montage, plan par plan.

    C'est la galerie : chaque plan avec son fichier réel, sa source et sa
    licence. Le seul endroit où l'on voit ce qui va entrer dans le film
    avant qu'il soit monté — et donc le seul endroit où le remplacer coûte
    encore trois secondes plutôt qu'un rendu.
    """
    dossier = _dossier(slug)
    shots = dossier / "03-shots.json"
    if not shots.is_file():
        raise HTTPException(404, "pas encore de plan visuel")

    plan = json.loads(shots.read_text(encoding="utf-8")).get("shots", [])
    assets: dict[str, Any] = {}
    fiche = dossier / "05-visuals" / "assets.json"
    if fiche.is_file():
        assets = json.loads(fiche.read_text(encoding="utf-8")).get("assets", {})

    sorties = []
    for index, brut in enumerate(plan):
        identifiant = f"S{index:03d}"
        acquis = assets.get(identifiant)
        sorties.append({
            "id": identifiant,
            "beat": brut.get("beat", ""),
            "type": brut.get("type", ""),
            "intention": brut.get("intention", ""),
            "requete": brut.get("requete") or brut.get("prompt", ""),
            "accroche": brut.get("accroche", ""),
            "panneau": (brut.get("motion") or {}).get("kind", ""),
            "fichier": acquis.get("fichier") if acquis else None,
            "titre": acquis.get("titre", "") if acquis else "",
            "auteur": acquis.get("auteur", "") if acquis else "",
            "licence": acquis.get("licence", "") if acquis else "",
            "source": acquis.get("source", "") if acquis else "",
            "url": acquis.get("url", "") if acquis else "",
            "largeur": acquis.get("largeur") if acquis else None,
            # Une requête élargie a pu ramener autre chose que ce qu'on
            # demandait : c'est le premier endroit où regarder.
            "relachee": bool(acquis.get("requete_relachee")) if acquis else False,
        })

    manquants = sum(1 for s in sorties
                    if s["type"] != "motion" and not s["fichier"])
    return {"plans": sorties, "manquants": manquants}


class Refus(BaseModel):
    raison: str = ""


@app.post("/api/projets/{slug}/visuels/{plan}/remplacer")
def remplacer(slug: str, plan: str, corps: Refus | None = None) -> dict[str, Any]:
    """Refuser un visuel et en chercher un autre pour ce plan.

    Le refus est écrit dans `05-visuals/rejets.jsonl` avant la nouvelle
    recherche, donc deux clics ne rendent jamais la même image.
    """
    _dossier(slug)
    try:
        return serveur.remplacer(slug, plan, (corps.raison if corps else ""))
    except ValueError as erreur:
        raise HTTPException(400, str(erreur))


@app.get("/api/voix")
def bibliotheque(provider: str = "edge", langue: str = "",
                 genre: str = "") -> dict[str, Any]:
    """La bibliothèque d'un fournisseur, filtrable par langue et par sexe.

    Les trois catalogues sont incompatibles — deux lettres de préfixe chez
    Kokoro, du JSON Microsoft chez Edge, des étiquettes libres chez
    ElevenLabs. `voice.catalogue` les normalise, donc cette route n'en
    connaît qu'un seul format.
    """
    from fresque import voice as voice_mod

    try:
        toutes = voice_mod.catalogue(provider)
    except voice_mod.VoiceError as erreur:
        # Clé absente, réseau coupé, modèle non téléchargé : ce sont des
        # états normaux d'installation, pas des pannes du serveur.
        raise HTTPException(422, str(erreur))

    retenues = voice_mod.filtrer(toutes, langue, genre)
    return {
        "provider": provider,
        "total": len(toutes),
        "langues": sorted({v.langue for v in toutes if v.langue}),
        "voix": [
            {"id": v.id, "nom": v.nom, "langue": v.langue,
             "genre": v.genre, "detail": v.detail}
            for v in retenues
        ],
    }


@app.get("/api/fournisseurs")
def fournisseurs() -> list[dict[str, Any]]:
    """Les trois moteurs, et ce qu'ils coûtent. Liste close."""
    return [
        {"nom": "edge", "titre": "Microsoft Edge",
         "note": "gratuit, sans clé, par le réseau"},
        {"nom": "kokoro", "titre": "Kokoro",
         "note": "local, gratuit, sans réseau"},
        {"nom": "elevenlabs", "titre": "ElevenLabs",
         "note": "payant, clé requise"},
    ]


@app.get("/api/projets/{slug}/voix")
def voix_du_projet(slug: str) -> dict[str, Any]:
    """La voix retenue pour ce projet, telle que le moteur la verra."""
    reglages = _projet_yaml(_dossier(slug)).get("reglages") or {}
    voix = reglages.get("voix") or {}
    provider = voix.get("provider") or ""
    bloc = voix.get(provider) or {}
    return {"provider": provider, "voix": bloc.get("voice", "")}


class ChoixVoix(BaseModel):
    provider: str
    voix: str


@app.post("/api/projets/{slug}/voix/essai")
def essayer_la_voix(slug: str, corps: ChoixVoix) -> dict[str, Any]:
    """Écouter une voix sans la retenir.

    L'essai dit le hook du script quand il existe : c'est sur lui qu'une
    voix se juge, pas sur une phrase neutre.
    """
    _dossier(slug)
    try:
        return serveur.essayer_voix(slug, corps.provider, corps.voix)
    except ValueError as erreur:
        raise HTTPException(400, str(erreur))


@app.post("/api/projets/{slug}/voix")
def choisir_la_voix(slug: str, corps: ChoixVoix) -> dict[str, Any]:
    """Retenir une voix. Elle s'écrit dans `projet.yaml`, pas ailleurs."""
    _dossier(slug)
    try:
        return serveur.choisir_voix(slug, corps.provider, corps.voix)
    except ValueError as erreur:
        raise HTTPException(400, str(erreur))


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

class Sujet(BaseModel):
    sujet: str
    template: str | None = None


@app.post("/api/projets")
def creer(corps: Sujet) -> dict[str, str]:
    """La barre de saisie. Un sujet entre, l'exploration part.

    Deux gestes en un appel, parce que c'est un seul geste pour
    l'utilisateur : le dossier est créé, puis `explorer` est lancé comme
    n'importe quelle autre commande — même sous-processus, même journal,
    même flux. Fermer l'onglet n'interrompt rien.
    """
    try:
        slug = serveur.creer(corps.sujet.strip(), corps.template)
    except ValueError as erreur:
        raise HTTPException(400, str(erreur))
    return {"slug": slug, "id": serveur.lancer(slug, "explorer", {})}


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
