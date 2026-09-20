"""Vertex AI — l'autre porte d'entrée vers les mêmes modèles d'image.

POURQUOI DEUX PORTES
====================
Le crédit d'essai Google Cloud — 300 $ sur quatre-vingt-dix jours — **ne paie
plus l'API Gemini servie par AI Studio** pour les comptes ouverts après le
2 mars 2026. Il paie Vertex AI, qui sert exactement les mêmes modèles.

C'est donc une question de facturation, pas de capacité : le corps de requête
est identique à celui d'AI Studio, et la réponse aussi. Seules changent
l'adresse et l'authentification. Tout ce module ne fait que ça — le reste de
`images.py` ne sait pas quelle porte il a prise.

CE QUI CHANGE VRAIMENT
======================
| | AI Studio | Vertex |
|---|---|---|
| Adresse | `generativelanguage.googleapis.com` | `aiplatform.googleapis.com` |
| Identification | `?key=` dans l'URL | `Authorization: Bearer` |
| Portée | la clé | un projet et une région |
| Durée de vie | la clé | un jeton d'une heure, renouvelé |

Un jeton qui expire est la seule vraie différence de fond : une clé d'API se
lit une fois et sert toujours, un jeton se redemande. Il est donc résolu à
chaque appel et mis en cache jusqu'à un peu avant son échéance — sur cent
images d'un documentaire, redemander un jeton à chaque fois serait cent
aller-retours pour rien, et n'en redemander jamais ferait échouer la
soixantième.

D'OÙ VIENT LE JETON
===================
Deux chemins, essayés dans cet ordre, et aucun des deux n'est une dépendance
obligatoire du projet :

1. **`google-auth`**, s'il est installé : identifiants par défaut de
   l'application (compte de service via `GOOGLE_APPLICATION_CREDENTIALS`, ou
   `gcloud auth application-default login`, ou le serveur de métadonnées sur
   une machine Google Cloud). C'est le chemin propre, et il gère le
   renouvellement lui-même.
2. **`gcloud auth print-access-token`**, sinon. Beaucoup de machines ont
   `gcloud` sans avoir la bibliothèque, et un sous-processus d'une seconde
   une fois par heure ne coûte rien.

Si aucun des deux n'existe, on le dit en nommant les deux remèdes. Le
pipeline continue de tourner sans Vertex, comme il tourne sans `torch`.
"""
from __future__ import annotations

import os
import subprocess
import time
from typing import Any

import requests

from . import config

#: La région `global` couvre le monde entier et essuie nettement moins de
#: 429 qu'une région unique. On ne fait pas de traitement réglementé ici, donc
#: rien n'impose de savoir où le calcul a lieu — c'est la seule réserve que la
#: documentation attache à ce point d'entrée.
REGION_DEFAUT = "global"

PORTEE = "https://www.googleapis.com/auth/cloud-platform"

#: Marge avant l'échéance. Un jeton qui expire pendant que la requête voyage
#: rend un 401 qu'on ne saurait pas relire.
MARGE_JETON_S = 300.0
#: Durée supposée d'un jeton obtenu par `gcloud`, qui n'en annonce pas
#: l'échéance. Google en émet d'une heure ; on en garde cinquante minutes.
DUREE_GCLOUD_S = 3000.0

#: Identifiants de modèles d'image à sonder. Ce n'est PAS une liste de ce qui
#: existe — c'est une liste de ce qu'on va demander à l'API de confirmer, une
#: par une, par un GET gratuit. Le code de ce projet ne prétend jamais savoir
#: de mémoire ce qu'une API sert (voir `images.list_models`).
MODELES_CANDIDATS = (
    "gemini-3.1-flash-lite-image",
    "gemini-3.1-flash-image",
    "gemini-3-pro-image",
    "gemini-2.5-flash-image",
)

TIMEOUT = 30.0


class VertexError(RuntimeError):
    pass


def region() -> str:
    return str(config.get("visuels", "generation", "vertex", "region",
                          default=REGION_DEFAUT)).strip() or REGION_DEFAUT


def racine() -> str:
    """L'hôte de l'API. `global` n'a pas de préfixe de région, les autres si."""
    zone = region()
    hote = ("aiplatform.googleapis.com" if zone == "global"
            else f"{zone}-aiplatform.googleapis.com")
    return f"https://{hote}/v1"


def projet() -> str:
    """L'identifiant du projet Google Cloud qui sera facturé.

    Il vient de l'environnement et jamais du dépôt : c'est une donnée de
    compte, comme une clé. `fresque.config.yaml` est versionné.
    """
    for nom in ("VERTEX_PROJECT", "GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT"):
        valeur = os.environ.get(nom, "").strip()
        if valeur:
            return valeur

    # Les identifiants par défaut en portent souvent un : un compte de service
    # nomme son projet, et `gcloud` enregistre le projet courant.
    try:
        import google.auth  # type: ignore

        _, decouvert = google.auth.default(scopes=[PORTEE])
        if decouvert:
            return str(decouvert)
    except Exception:  # noqa: BLE001 — l'absence de la lib est un cas normal
        pass

    raise VertexError(
        "projet Google Cloud inconnu.\n"
        "  · le mettre dans .env : VERTEX_PROJECT=mon-projet\n"
        "  · ou `gcloud config set project mon-projet`"
    )


#: (jeton, échéance). Process-wide, comme le template actif : une commande
#: traite un projet, et faire circuler un objet de session dans chaque
#: fonction serait du cérémonial pour rien.
_cache: tuple[str, float] | None = None


def _par_bibliotheque() -> tuple[str, float] | None:
    """Le jeton via `google-auth`, ou `None` si cette voie n'est pas ouverte.

    Deux échecs qu'il ne faut surtout pas confondre : *pas d'identifiants
    configurés* est un cas normal — on passe alors à `gcloud` — tandis qu'un
    renouvellement refusé veut dire que des identifiants existent et ne
    marchent pas. Retomber silencieusement sur `gcloud` dans ce second cas
    ferait porter le diagnostic sur le mauvais compte.
    """
    try:
        import google.auth  # type: ignore
        import google.auth.exceptions  # type: ignore
        import google.auth.transport.requests  # type: ignore
    except ImportError:
        return None

    try:
        identifiants, _ = google.auth.default(scopes=[PORTEE])
    except google.auth.exceptions.DefaultCredentialsError:
        return None

    try:
        identifiants.refresh(google.auth.transport.requests.Request())
    except google.auth.exceptions.GoogleAuthError as erreur:
        raise VertexError(
            f"identifiants Google Cloud trouvés mais refusés : {erreur}\n"
            "  · `gcloud auth application-default login` pour les refaire"
        ) from erreur

    if not identifiants.token:
        return None
    echeance = getattr(identifiants, "expiry", None)
    if echeance is None:
        return identifiants.token, time.time() + DUREE_GCLOUD_S
    # `expiry` est un datetime naïf en UTC.
    from datetime import timezone

    return identifiants.token, echeance.replace(tzinfo=timezone.utc).timestamp()


def _par_gcloud() -> tuple[str, float] | None:
    import shutil

    if not shutil.which("gcloud"):
        return None
    try:
        sortie = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    jeton_brut = sortie.stdout.strip()
    if sortie.returncode != 0 or not jeton_brut:
        return None
    return jeton_brut, time.time() + DUREE_GCLOUD_S


def jeton(force: bool = False) -> str:
    """Un jeton d'accès valide, renouvelé seulement quand il le faut."""
    global _cache

    if not force and _cache and _cache[1] - MARGE_JETON_S > time.time():
        return _cache[0]

    # Chaque source signale elle-même ce qui la concerne : `None` veut dire
    # « cette voie n'est pas ouverte, essaie la suivante », et une VertexError
    # veut dire « celle-ci était la bonne et elle a échoué ». Un `except
    # Exception` ici masquerait une faute de programmation derrière un
    # message d'authentification, ce qui envoie chercher le problème sur le
    # compte Google plutôt que dans le code.
    for source in (_par_bibliotheque, _par_gcloud):
        obtenu = source()
        if obtenu:
            _cache = obtenu
            return obtenu[0]

    raise VertexError(
        "aucun identifiant Google Cloud.\n"
        "  · `gcloud auth application-default login`, ou\n"
        "  · GOOGLE_APPLICATION_CREDENTIALS=/chemin/compte-de-service.json\n"
        "  · la bibliothèque est optionnelle : "
        "`pip install google-auth` la rend plus propre, `gcloud` seul suffit"
    )


def entetes() -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton()}",
            "Content-Type": "application/json"}


def url_modele(modele: str, methode: str = "generateContent") -> str:
    return (f"{racine()}/projects/{projet()}/locations/{region()}"
            f"/publishers/google/models/{modele}:{methode}")


def _url_region() -> str:
    """La fiche de la région, dans le projet. Gratuite, et elle prouve le
    jeton, le projet, la région et l'activation de l'API d'un seul coup."""
    return f"{racine()}/projects/{projet()}/locations/{region()}"


def _url_fiche(modele: str) -> str:
    """La fiche publique d'un modèle.

    Elle n'est PAS portée par le projet, et elle n'existe qu'en `v1beta1` —
    les deux ont été vérifiés contre l'API réelle, et les deux m'avaient
    échappé : la forme que j'avais écrite d'abord
    (`v1/projects/…/publishers/google/models/…`) rend un 404 en HTML, c'est-
    à-dire une route inexistante déguisée en modèle introuvable.
    """
    zone = region()
    hote = ("aiplatform.googleapis.com" if zone == "global"
            else f"{zone}-aiplatform.googleapis.com")
    return f"https://{hote}/v1beta1/publishers/google/models/{modele}"


def _refus(reponse: requests.Response) -> VertexError:
    return VertexError(
        f"accès refusé (HTTP {reponse.status_code}) sur le projet "
        f"{projet()!r}, région {region()!r}.\n"
        "  · l'API Vertex AI est-elle activée sur ce projet ?\n"
        "    `gcloud services enable aiplatform.googleapis.com`\n"
        "  · le compte a-t-il le rôle `roles/aiplatform.user` ?\n"
        f"  · réponse : {reponse.text[:200]}"
    )


def modeles_image(session: requests.Session | None = None) -> list[str]:
    """Les modèles d'image utilisables, en deux vérifications gratuites.

    Aucune des deux ne génère d'image, donc aucune ne coûte quoi que ce soit.
    Elles ne prouvent pas la même chose, et c'est pour ça qu'il en faut deux :

    1. la fiche de la **région dans le projet** prouve le jeton, le projet,
       la région et l'activation de l'API — tout ce qui est propre au compte ;
    2. la fiche **publique d'un modèle** prouve que l'identifiant existe.
       Elle ne dit rien du projet : elle n'est pas portée par lui.

    Ce qu'aucune des deux ne prouve, c'est le droit d'appeler CE modèle sur CE
    projet. Seul un vrai appel le dirait, et il se paierait — on s'arrête donc
    là, en le disant, plutôt que de laisser croire à une garantie.
    """
    http = session or requests.Session()

    try:
        reponse = http.get(_url_region(), headers=entetes(), timeout=TIMEOUT)
    except requests.RequestException as erreur:
        raise VertexError(f"{racine()} injoignable : {erreur}") from erreur
    if reponse.status_code in (401, 403, 404):
        raise _refus(reponse)
    if reponse.status_code >= 400:
        raise VertexError(
            f"région {region()!r} refusée (HTTP {reponse.status_code}) : "
            f"{reponse.text[:200]}"
        )

    servis: list[str] = []
    refus: list[str] = []
    for modele in MODELES_CANDIDATS:
        try:
            fiche = http.get(_url_fiche(modele), headers=entetes(),
                             timeout=TIMEOUT)
        except requests.RequestException as erreur:
            raise VertexError(f"{_url_fiche(modele)} injoignable : {erreur}") \
                from erreur
        if fiche.status_code == 200:
            servis.append(modele)
        else:
            refus.append(f"{modele} → {fiche.status_code}")

    if not servis:
        raise VertexError(
            "le projet répond, mais aucun des modèles d'image connus n'a de "
            "fiche.\n  " + "\n  ".join(refus)
            + "\n  · les identifiants de `vertex.MODELES_CANDIDATS` ont "
              "peut-être changé."
        )
    return servis


def etat() -> dict[str, Any]:
    """De quoi afficher où l'on en est sans rien générer."""
    return {"projet": projet(), "region": region(), "racine": racine()}
