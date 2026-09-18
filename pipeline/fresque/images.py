"""Image generation with the Gemini API.

Only what the archives could not provide is generated. Each shot's prompt is
prefixed with the project's art direction, because five images in five
different styles destroy the illusion faster than one mediocre image does.

The exact model names are discovered from the live API rather than hardcoded
from memory — `list_models()` exists for that, and the CLI exposes it.
"""
from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any, Callable

import requests

from . import config
from .shots import Shot

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
TIMEOUT = 120.0

IMAGE_MIMES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


class ImageError(RuntimeError):
    pass


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
    names = []
    for model in list_models(session):
        name = model.get("name", "").removeprefix("models/")
        if "image" in name.lower():
            names.append(name)
    return names


def _art_direction() -> str:
    return str(config.get("visuels", "generation", "direction_artistique", default="")).strip()


def build_prompt(shot: Shot) -> str:
    """Art direction first, then the shot. Never a real person's name, never
    text in the image — both are set in the fresque-plan-visuel skill, this is
    the mechanical belt-and-braces."""
    direction = _art_direction()
    parts = [direction, shot.prompt] if direction else [shot.prompt]
    return ". ".join(p.strip().rstrip(".") for p in parts if p.strip()) + "."


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


def generate(
    shot: Shot,
    destination_dir: Path,
    model: str | None = None,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Generate one image and write it. Returns its asset record."""
    http = session or requests.Session()
    model = model or str(
        config.get("visuels", "generation", "model", default="gemini-2.5-flash-image")
    )
    prompt = build_prompt(shot)

    response = http.post(
        f"{API_ROOT}/models/{model}:generateContent",
        params={"key": api_key()},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        },
        timeout=TIMEOUT,
    )
    if response.status_code >= 400:
        message = response.text[:300]
        raise ImageError(f"{model} a répondu {response.status_code} : {message}")

    data, extension = _extract_image(response.json())
    destination_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{shot.id}{extension}"
    (destination_dir / filename).write_bytes(data)

    return {
        "fichier": f"05-visuals/{filename}",
        "shot": shot.id,
        "beat": shot.beat,
        "source": "gemini",
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
            assets[shot.id] = generate(shot, destination_dir, session=http)
            say(f"  ✓ {shot.id} ({index}/{len(todo)})")
        except (ImageError, requests.RequestException) as error:
            say(f"  ✗ {shot.id} : {error}")
            failures.append((shot.id, str(error)))
        if index < len(todo):
            time.sleep(pause)

    return assets, failures
