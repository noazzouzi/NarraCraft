"""Génération d'images — deux portes vers les mêmes modèles.

On ne génère que ce que les archives n'ont pas fourni. Le prompt de chaque
plan est préfixé de la direction artistique du projet : cinq images dans cinq
styles différents détruisent l'illusion bien plus vite qu'une image moyenne.

Les noms de modèles sont découverts auprès de l'API vivante plutôt que tenus
de mémoire — `list_models()` est là pour ça, et la CLI l'expose.

DEUX FOURNISSEURS, UN SEUL CORPS DE REQUÊTE
===========================================
`visuels.generation.provider` vaut `gemini` (AI Studio) ou `vertex`. Les deux
servent les mêmes modèles, avec le même corps de requête et la même forme de
réponse. Seules changent l'adresse et l'identification, et c'est tout ce que
`_acces()` résout — le reste de ce module ne sait pas quelle porte il a prise.

Le choix n'est pas technique, il est comptable : le crédit d'essai Google
Cloud de 300 $ ne paie plus AI Studio pour les comptes ouverts après le
2 mars 2026, mais il paie Vertex. Voir `vertex.py`.
"""
from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import requests

from . import config, vertex
from .shots import Shot

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
FOURNISSEURS = ("gemini", "vertex")
TIMEOUT = 120.0

IMAGE_MIMES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}

MINUTE_QUOTA_RETRIES = 3
BACKOFF_S = 20.0


class ImageError(RuntimeError):
    pass


def fournisseur() -> str:
    nom = str(config.get("visuels", "generation", "provider",
                         default="gemini")).strip()
    if nom not in FOURNISSEURS:
        raise ImageError(
            f"`visuels.generation.provider` vaut {nom!r} — attendu "
            f"{' ou '.join(FOURNISSEURS)}."
        )
    return nom


@dataclass(frozen=True)
class Acces:
    """Où frapper, et avec quoi. Le seul endroit où les deux portes diffèrent."""

    url: str
    entetes: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)


def _acces(modele: str, methode: str = "generateContent") -> Acces:
    if fournisseur() == "vertex":
        try:
            url, entetes, params = vertex.acces(modele, methode)
            return Acces(url=url, entetes=entetes, params=params)
        except vertex.VertexError as erreur:
            # Remontée sous le type du module : `generate_all` et la CLI
            # n'ont pas à connaître les deux familles d'erreurs.
            raise ImageError(str(erreur)) from erreur
    return Acces(url=f"{API_ROOT}/models/{modele}:{methode}",
                 params={"key": api_key()})


def api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise ImageError(
            "GEMINI_API_KEY absente.\n"
            "  · en local : la mettre dans .env\n"
            "  · en session cloud : variable d'environnement ou API credential "
            "sur l'environnement (l'identifiant n'atteint alors jamais la session)"
        )
    return key


def list_models(session: requests.Session | None = None) -> list[dict[str, Any]]:
    """Ask the API what it actually serves, instead of trusting a hardcoded name."""
    http = session or requests.Session()
    response = http.get(
        f"{API_ROOT}/models", params={"key": api_key()}, timeout=TIMEOUT
    )
    response.raise_for_status()
    return response.json().get("models", [])


def image_models(session: requests.Session | None = None) -> list[str]:
    """Les modèles d'image que CE compte peut réellement servir.

    Vertex n'expose pas de catalogue équivalent à celui d'AI Studio : on y
    sonde une fiche de modèle par identifiant candidat, ce qui est gratuit et
    vérifie d'un coup le jeton, le projet, la région et le modèle. C'est donc
    aussi la commande qui dit si une installation Vertex est bonne, avant
    d'avoir dépensé un centime.
    """
    if fournisseur() == "vertex":
        try:
            return vertex.modeles_image(session)
        except vertex.VertexError as erreur:
            raise ImageError(str(erreur)) from erreur

    names = []
    for model in list_models(session):
        name = model.get("name", "").removeprefix("models/")
        if "image" in name.lower():
            names.append(name)
    return names


def _art_direction() -> str:
    return str(config.get("visuels", "generation", "direction_artistique", default="")).strip()


def _interdits() -> str:
    return str(config.get("visuels", "generation", "interdits", default="")).strip()


class PromptSansDirection(ValueError):
    """Le template n'a pas dit comment ses images doivent avoir l'air."""


def build_prompt(shot: Shot) -> str:
    """Direction artistique, puis le sujet, puis les interdits.

    Le partage est la règle du projet : **Claude n'écrit que le sujet.**
    « un homme de dos devant un restaurant aux rideaux baissés » est un
    jugement éditorial. « collage découpé, aplats francs sur papier crème »
    est la direction artistique du template — c'est de la donnée, elle
    s'applique à tous les plans, et changer de template la change partout.

    Sans ce partage, la cohérence dépend de ce que Claude a pensé à
    répéter dans cent vingt prompts. Mesuré sur le premier film : le
    template collage n'avait aucun bloc `generation`, donc ses images
    sortaient en « photographie documentaire, grain argentique » — soit
    l'exact opposé de sa direction artistique.
    """
    direction = _art_direction()
    if not direction:
        raise PromptSansDirection(
            "`visuels.generation.direction_artistique` est vide — le "
            "template ne dit pas de quoi ses images ont l'air. Cinq styles "
            "différents détruisent l'illusion bien plus vite qu'une image "
            "moyenne."
        )
    parts = [direction, shot.prompt, _interdits()]
    return ". ".join(p.strip().rstrip(".") for p in parts if p.strip()) + "."


def quota_kind(payload: dict[str, Any]) -> tuple[str, str]:
    """Classify a 429 body as ('minute'|'day'|'inconnu', quota id).

    The distinction decides what to do, so it is worth reading properly:
    a per-minute quota clears on its own and deserves a backoff, a per-day
    quota does not and must fail loudly instead of retrying for an hour.
    """
    for detail in payload.get("error", {}).get("details", []) or []:
        if not isinstance(detail, dict):
            continue
        for violation in detail.get("violations", []) or []:
            quota_id = violation.get("quotaId", "")
            if "PerDay" in quota_id:
                return "day", quota_id
            if "PerMinute" in quota_id:
                return "minute", quota_id
            if quota_id:
                return "inconnu", quota_id
    return "inconnu", ""


class QuotaExhausted(ImageError):
    """A quota that will not clear by waiting a few seconds."""


def _raise_for_quota(payload: dict[str, Any], model: str) -> None:
    kind, quota_id = quota_kind(payload)
    free_tier = "FreeTier" in quota_id
    if kind == "day":
        raise QuotaExhausted(
            f"{model} : quota journalier épuisé ({quota_id}).\n"
            + ("  Le palier gratuit ne suffit pas pour la génération d'images. "
               "Activer la facturation sur le projet Google Cloud de la clé, "
               "ou attendre la remise à zéro quotidienne."
               if free_tier else
               "  Attendre la remise à zéro, ou relever le quota du projet.")
        )
    raise ImageError(f"{model} : quota atteint ({quota_id or 'non précisé'})")


def _extract_image(payload: dict[str, Any]) -> tuple[bytes, str]:
    candidates = payload.get("candidates") or []
    for candidate in candidates:
        for part in candidate.get("content", {}).get("parts", []) or []:
            inline = part.get("inlineData") or part.get("inline_data")
            if not inline:
                continue
            mime = inline.get("mimeType") or inline.get("mime_type") or ""
            if mime in IMAGE_MIMES:
                return base64.b64decode(inline["data"]), IMAGE_MIMES[mime]

    # No image came back — say why, using whatever the API reported.
    reasons = [c.get("finishReason") for c in candidates if c.get("finishReason")]
    feedback = payload.get("promptFeedback", {}).get("blockReason")
    detail = ", ".join(filter(None, [*reasons, feedback])) or "aucune raison fournie"
    raise ImageError(f"aucune image dans la réponse ({detail})")


def _corps(prompt: str, avec_image_config: bool) -> dict[str, Any]:
    """Le corps de la requête, identique sur les deux portes.

    `imageConfig` porte le format. Il était réglé dans
    `visuels.generation.ratio` depuis le début et **n'était jamais envoyé** :
    le modèle rendait donc du carré pendant que la config annonçait 16:9, et
    le montage recadrait. C'est exactement le défaut relevé sur les essais
    locaux, à ceci près qu'ici il venait de notre code.
    """
    generation: dict[str, Any] = {"responseModalities": ["IMAGE"]}
    if avec_image_config:
        image: dict[str, Any] = {}
        ratio = str(config.get("visuels", "generation", "ratio", default="")).strip()
        if ratio:
            image["aspectRatio"] = ratio
        taille = str(config.get("visuels", "generation", "taille", default="")).strip()
        if taille:
            image["imageSize"] = taille
        if image:
            generation["imageConfig"] = image
    # `role` est OBLIGATOIRE sur Vertex et facultatif sur AI Studio. Omis, la
    # génération rendait « Please use a valid role: user, model » en 400 — un
    # message qui ne nomme pas le champ manquant mais les valeurs attendues,
    # donc difficile à rattacher à un `contents` sans rôle.
    #
    # Relevé au premier appel réel. `vertex.py` annonçait un corps identique
    # sur les deux portes : c'était faux, et c'est la seule divergence
    # constatée à ce jour. L'ajouter partout plutôt que le conditionner —
    # AI Studio l'accepte, et un corps unique est ce qui rend les deux portes
    # interchangeables.
    return {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": generation}


def _sans_image_config(reponse: requests.Response) -> bool:
    """Un 400 qui NOMME `imageConfig`.

    Le champ n'est alors pas compris du tout par ce modèle, et réessayer sans
    lui vaut mieux que de faire échouer le premier plan d'une série payante
    sur une option de confort. On le signale, sinon le format redeviendrait
    silencieusement celui du modèle.

    Cette reprise ne couvre PAS le cas où le champ est compris mais la valeur
    refusée — voir `_diagnostic()`. Mesuré sur Vertex : un modèle qui ne sait
    pas faire la définition demandée rend le même 400 qu'une requête
    malformée, sans nommer quoi que ce soit.
    """
    return reponse.status_code == 400 and "imageConfig" in (reponse.text or "")


def _diagnostic(reponse: requests.Response, modele: str, formate: bool) -> str:
    """Le message d'échec, et ce qu'on peut en dire de plus que l'API.

    Mesuré le 2026-09-20 (`docs/etude-vertex.md`) :
    `gemini-3.1-flash-lite-image` rend `400 · Request contains an invalid
    argument.` pour `2K` comme pour `4K`, et réussit cinq fois de suite en
    `1K`. Le corps ne nomme ni `imageConfig`, ni `imageSize`, ni la valeur
    attendue — il est identique à celui d'une requête réellement malformée.
    Sans le témoin en `1K`, rien ne désignait la définition.

    On ne réessaie pas sans le format, et c'est un choix. Une définition
    refusée est une erreur de RÉGLAGE : elle échoue de la même façon sur les
    cent images du documentaire. Retomber en silence sur le format du modèle
    produirait cent images au mauvais cadrage, qu'on découvrirait au montage ;
    échouer sur la première coûte une correction dans le fichier de config,
    une fois.
    """
    base = f"{modele} a répondu {reponse.status_code} : {reponse.text[:300]}"
    if reponse.status_code != 400 or not formate:
        return base

    taille = str(config.get("visuels", "generation", "taille", default="")).strip()
    ratio = str(config.get("visuels", "generation", "ratio", default="")).strip()
    return (
        f"{base}\n"
        f"  Ce 400 ne nomme aucun champ, mais la requête demandait "
        f"`taille: \"{taille}\"` et `ratio: \"{ratio}\"`.\n"
        "  Mesuré : un modèle qui ne sait pas rendre la définition demandée "
        "répond exactement ceci.\n"
        "  · baisser `visuels.generation.taille`, ou\n"
        "  · prendre un modèle qui monte plus haut — `gemini-3.1-flash-image` "
        "tient `2K`.\n"
        "  On ne réessaie pas sans le format : cent images au mauvais cadrage "
        "coûtent plus qu'un échec net."
    )


def generate(
    shot: Shot,
    destination_dir: Path,
    model: str | None = None,
    session: requests.Session | None = None,
    report: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Generate one image and write it. Returns its asset record."""
    http = session or requests.Session()
    say = report or (lambda _: None)
    model = model or str(
        config.get("visuels", "generation", "model", default="gemini-2.5-flash-image")
    )
    prompt = build_prompt(shot)
    acces = _acces(model)
    formate = True

    # A per-minute quota clears on its own; anything else is pointless to retry.
    for attempt in range(MINUTE_QUOTA_RETRIES + 1):
        response = http.post(
            acces.url, params=acces.params, headers=acces.entetes,
            json=_corps(prompt, formate), timeout=TIMEOUT,
        )
        if response.status_code == 429:
            payload = response.json() if response.content else {}
            kind, _ = quota_kind(payload)
            # Vertex ne détaille pas ses quotas comme AI Studio : sa réponse
            # ne porte pas de `quotaId`. Un 429 y est le plus souvent une
            # saturation passagère, donc il mérite la même attente qu'un
            # quota à la minute plutôt qu'un échec sec.
            patienter = kind == "minute" or (
                kind == "inconnu" and fournisseur() == "vertex")
            if patienter and attempt < MINUTE_QUOTA_RETRIES:
                time.sleep(BACKOFF_S * (2 ** attempt))
                continue
            _raise_for_quota(payload, model)
        if formate and _sans_image_config(response):
            say(f"  · {model} n'accepte pas `imageConfig` — format laissé "
                "au modèle, le recadrage se fera au montage.")
            formate = False
            continue
        if response.status_code >= 400:
            raise ImageError(_diagnostic(response, model, formate))
        break

    data, extension = _extract_image(response.json())
    destination_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{shot.id}{extension}"
    chemin = destination_dir / filename
    chemin.write_bytes(data)

    # Les dimensions RÉELLES, mesurées sur le fichier — même règle que pour
    # une archive téléchargée : « une métadonnée est une promesse, le fichier
    # sur le disque est le fait ».
    #
    # Elles ne sont pas décoratives. Un modèle peut ignorer la définition
    # demandée sans le dire : mesuré, `gemini-2.5-flash-image` rend 1344 px
    # quand on lui demande du `2K`, sans erreur ni avertissement. Sans ce
    # relevé, la dégradation ne se verrait qu'au montage. Le montage s'en sert
    # aussi pour son `ratio`, qui décide du cadrage d'une image non 16:9.
    from .fetch import real_size

    largeur, hauteur = real_size(chemin)

    return {
        "fichier": f"05-visuals/{filename}",
        "largeur": largeur,
        "hauteur": hauteur,
        "shot": shot.id,
        "beat": shot.beat,
        "source": fournisseur(),
        "modele": model,
        "prompt": prompt,
        # Generated images carry no third-party rights, but the field stays
        # mandatory so nothing downstream has to special-case them.
        "licence": "généré (aucun droit tiers)",
        "credit": None,
        "url": None,
    }


def generate_all(
    shots: list[Shot],
    destination_dir: Path,
    report: Callable[[str], None] | None = None,
    pause: float = 0.5,
) -> tuple[dict[str, dict[str, Any]], list[tuple[str, str]]]:
    """Generate every `generated` shot. Returns (assets, failures)."""
    say = report or (lambda _: None)
    cap = int(config.get("visuels", "generation", "max_images_par_projet", default=120))
    todo = [s for s in shots if s.type == "generated"]

    if len(todo) > cap:
        raise ImageError(
            f"{len(todo)} images demandées, plafond à {cap} "
            "(`visuels.generation.max_images_par_projet`). "
            "Arbitrer le plan visuel avant de dépenser."
        )

    http = requests.Session()
    assets: dict[str, dict[str, Any]] = {}
    failures: list[tuple[str, str]] = []

    for index, shot in enumerate(todo, start=1):
        try:
            assets[shot.id] = generate(shot, destination_dir, session=http,
                                       report=say)
            say(f"  ✓ {shot.id} ({index}/{len(todo)})")
        except QuotaExhausted as error:
            # Nothing will succeed today — stop rather than burn through the
            # remaining shots collecting the same error.
            say(f"  ✗ {shot.id} : {error}")
            failures.append((shot.id, str(error)))
            remaining = len(todo) - index
            if remaining:
                say(f"  · {remaining} plan(s) non tentés : quota épuisé")
            break
        except (ImageError, requests.RequestException) as error:
            say(f"  ✗ {shot.id} : {error}")
            failures.append((shot.id, str(error)))
        if index < len(todo):
            time.sleep(pause)

    return assets, failures
