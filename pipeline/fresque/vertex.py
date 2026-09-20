"""Vertex AI — l'autre porte d'entrée vers les mêmes modèles d'image.

POURQUOI DEUX PORTES
====================
Le crédit d'essai Google Cloud — 300 $ sur quatre-vingt-dix jours — **ne paie
plus l'API Gemini servie par AI Studio** pour les comptes ouverts après le
2 mars 2026. Il paie Vertex AI, qui sert exactement les mêmes modèles.

C'est donc une question de facturation, pas de capacité : la réponse est de
même forme, et le corps de requête l'est presque. Une seule divergence a été
constatée au premier appel réel — Vertex exige un `role` sur chaque entrée de
`contents`, qu'AI Studio rend facultatif. Elle est absorbée dans
`images._corps()`, qui l'émet pour les deux : un corps unique est ce qui rend
les deux portes interchangeables.

Pour le reste, seules changent l'adresse et l'authentification, et tout ce
module ne fait que ça — `images.py` ne sait pas quelle porte il a prise.

UNE SEULE ADRESSE, DEUX JUSTIFICATIFS
=====================================
Ce module a d'abord porté deux « modes » : `express` (clé d'API, adresse
globale sans projet) et `projet` (jeton OAuth, adresse portée par un projet).
C'était une supposition, et elle était fausse. Cinq sondes contre l'API réelle
(`docs/etude-vertex.md`, section 3) :

    v1/publishers/…/{m}:generateContent                      clé  → 200
    v1/projects/{P}/locations/global/publishers/…  ?key=     clé  → 200
    v1/projects/{P}/locations/global/publishers/…  en-tête   clé  → 200

**Une clé d'API porte un projet.** Il n'y a donc pas deux modes mais une seule
adresse et deux façons de présenter ses papiers. Le `mode` a disparu : ce qui
reste est de savoir si l'on connaît le projet, et avec quoi l'on s'identifie.

La clé voyage en **en-tête** `x-goog-api-key` et non en `?key=`. Les deux
rendent 200 ; un secret dans une URL est recopié par chaque journal de proxy
sur le trajet, un en-tête ne l'est pas.

LA RÉGION
=========
`global` est le défaut. `us-central1` a été sondée et rend `NOT_FOUND` sur le
modèle essayé — la requête était bien identifiée, c'est le couple modèle ×
région qui n'existe pas. Un modèle n'est pas publié partout.

D'OÙ VIENT LE JUSTIFICATIF
==========================
Une clé d'abord si elle est là, un jeton sinon. L'ordre n'est pas un jugement
de valeur : une clé posée dans l'environnement est un geste explicite, alors
qu'un jeton peut venir d'un `gcloud auth login` oublié ou du serveur de
métadonnées d'une machine. L'explicite l'emporte sur l'ambiant.

Une clé est un secret durable qui ouvre le quota du projet ; un jeton expire
seul et se rattache à des rôles. Pour produire, le jeton vaut mieux — mais
c'est un conseil, pas une contrainte du code.

Le jeton est mis en cache jusqu'à un peu avant son échéance : sur cent images
d'un documentaire, le redemander à chaque fois serait cent aller-retours pour
rien, et ne jamais le redemander ferait échouer la soixantième. Deux chemins,
essayés dans cet ordre, et aucun des deux n'est une dépendance obligatoire :

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


#: Les noms sous lesquels on accepte la clé.
#:
#: Plusieurs, et c'est délibéré : ce secret est posé à la main dans
#: l'environnement d'une machine, souvent par quelqu'un qui ne lit pas le
#: code juste avant. Un nom qui ne correspond pas rend « clé absente » alors
#: que la clé est là — le pire message possible, parce qu'il envoie la
#: chercher du côté de Google. Le projet suit déjà la même règle pour son
#: identifiant (`projet()`).
NOMS_CLE = ("VERTEX_API_KEY", "GOOGLE_CLOUD_KEY", "GOOGLE_API_KEY")


def cle() -> str | None:
    """La clé d'API, ou `None`. Son absence n'est pas une erreur : c'est le
    cas normal d'une machine qui s'identifie par un jeton."""
    for nom in NOMS_CLE:
        valeur = os.environ.get(nom, "").strip()
        if valeur:
            return valeur
    return None


def porteur_de_cle() -> str | None:
    """Le NOM de la variable qui porte la clé — jamais son contenu.

    C'est l'information utile quand trois noms conviennent, et elle
    s'affiche sans rien révéler.
    """
    return next((n for n in NOMS_CLE if os.environ.get(n, "").strip()), None)


def region() -> str:
    return str(config.get("visuels", "generation", "vertex", "region",
                          default=REGION_DEFAUT)).strip() or REGION_DEFAUT


def racine() -> str:
    """L'hôte de l'API. `global` n'a pas de préfixe de région, les autres si."""
    zone = region()
    hote = ("aiplatform.googleapis.com" if zone == "global"
            else f"{zone}-aiplatform.googleapis.com")
    return f"https://{hote}/v1"


def projet() -> str | None:
    """L'identifiant du projet Google Cloud, ou `None` si on l'ignore.

    Il vient de l'environnement et jamais du dépôt : c'est une donnée de
    compte, comme une clé. `fresque.config.yaml` est versionné.

    Son absence n'est PAS une erreur. Mesuré : l'adresse globale, sans projet,
    rend 200 avec une clé — le serveur retrouve le projet depuis la clé. Le
    connaître ne sert qu'à le rendre explicite dans l'URL, ce qui vaut mieux
    quand on veut lire ses journaux, mais ne conditionne rien.
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
    return None


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
    """De quoi s'identifier : une clé si elle est là, un jeton sinon.

    La clé part en en-tête `x-goog-api-key`, jamais en `?key=`. Les deux
    rendent 200 (mesuré) ; un secret dans une URL est recopié par chaque
    journal de proxy sur le trajet, un en-tête ne l'est pas.
    """
    papiers = {"Content-Type": "application/json"}
    trouvee = cle()
    if trouvee:
        papiers["x-goog-api-key"] = trouvee
    else:
        papiers["Authorization"] = f"Bearer {jeton()}"
    return papiers


def url_modele(modele: str, methode: str = "generateContent") -> str:
    """L'adresse du modèle, portée par le projet quand on le connaît.

    Sans projet, l'adresse globale fait le même travail — le serveur le
    retrouve depuis le justificatif. Le nommer ne change pas la réponse ;
    ça rend seulement l'appel lisible dans les journaux.
    """
    identifiant = projet()
    if not identifiant:
        return f"{racine()}/publishers/google/models/{modele}:{methode}"
    return (f"{racine()}/projects/{identifiant}/locations/{region()}"
            f"/publishers/google/models/{modele}:{methode}")


def acces(modele: str, methode: str = "generateContent"
          ) -> tuple[str, dict[str, str], dict[str, str]]:
    """(adresse, en-têtes, paramètres) — tout ce que Vertex impose.

    Rendu d'un bloc pour qu'`images.py` n'ait à connaître ni le projet, ni la
    région, ni la façon dont on s'identifie : la même raison qui lui fait
    ignorer qu'il existe deux fournisseurs.
    """
    return url_modele(modele, methode), entetes(), {}


def _url_region() -> str | None:
    """La fiche de la région dans le projet, quand il y a un projet.

    Gratuite, et elle prouve d'un coup le justificatif, le projet, la région
    et l'activation de l'API.
    """
    identifiant = projet()
    return f"{racine()}/projects/{identifiant}/locations/{region()}" \
        if identifiant else None


def _sonde(session: requests.Session, url: str) -> requests.Response:
    return session.get(url, headers=entetes(), timeout=TIMEOUT)


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

    # Une clé d'API n'a pas cours sur la route des fiches de modèle : mesuré,
    # elle y rend 401 `CREDENTIALS_MISSING` sur `GetPublisherModel`. C'est une
    # propriété de cette route, pas un défaut de la clé — et ça veut dire
    # qu'avec une clé, il n'existe aucune vérification gratuite.
    if cle():
        raise VertexError(
            "aucune vérification gratuite n'est possible avec une clé d'API.\n"
            "  La route des fiches de modèle n'accepte qu'un jeton OAuth ; "
            "mesuré, elle rend 401 `CREDENTIALS_MISSING` avec une clé.\n"
            "  · le seul essai concluant est une génération : "
            "`fresque essai-image \"...\"`\n"
            "  · ou s'identifier par un jeton — `gcloud auth "
            "application-default login` — et relancer cette commande."
        )

    adresse = _url_region()
    if adresse:
        try:
            reponse = http.get(adresse, headers=entetes(), timeout=TIMEOUT)
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
            fiche = _sonde(http, _url_fiche(modele))
        except requests.RequestException as erreur:
            raise VertexError(f"{_url_fiche(modele)} injoignable : {erreur}") \
                from erreur
        if fiche.status_code == 200:
            servis.append(modele)
        else:
            refus.append(f"{modele} → {fiche.status_code}")

    if servis:
        return servis

    # Le diagnostic dépend du code, et les confondre envoie chercher au
    # mauvais endroit. Relevé au premier essai réel : quatre 401 étaient
    # rendus comme « les identifiants de modèle ont peut-être changé », alors
    # qu'un 401 ne dit rien des identifiants — il dit que la requête n'est
    # pas identifiée.
    codes = {ligne.rsplit(" → ", 1)[1] for ligne in refus}
    detail = "\n  ".join(refus)

    if codes <= {"401", "403"}:
        raise VertexError(
            "jeton refusé sur les fiches de modèle (401/403).\n  " + detail
            + "\n  · le jeton a-t-il la portée `cloud-platform` ?"
        )

    raise VertexError(
        "le projet répond, mais aucun des modèles d'image connus n'a de "
        "fiche.\n  " + detail
        + "\n  · les identifiants de `vertex.MODELES_CANDIDATS` ont "
          "peut-être changé."
    )


def etat() -> dict[str, Any]:
    """Ce qui va réellement se passer, sans rien générer ni rien révéler.

    On nomme la variable qui porte la clé, jamais son contenu : cet état est
    imprimé avant chaque génération et finirait sinon recopié dans
    `journal/`, qui est un fichier du projet.
    """
    return {"cle": porteur_de_cle(), "projet": projet(), "region": region(),
            "racine": racine()}
