"""Check what this machine can actually reach and run.

The pipeline depends on hosts that a restricted network may block, and on
models that may not be downloaded yet. Finding that out beat by beat, halfway
through a render, is expensive. This tells you up front, and prints the exact
allowlist to paste when something is blocked.
"""
from __future__ import annotations

import os
import socket
import ssl
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import config

TIMEOUT = 8.0


@dataclass
class Host:
    name: str
    why: str
    required_by: str


@dataclass
class Group:
    label: str
    hosts: list[Host]
    optional: bool = False
    #: Why this provider needs no file host of its own. A provider whose API
    #: is reachable but whose files are not looks healthy here and then fails
    #: at download time, so a single-host group has to justify itself.
    fichiers_ailleurs: str = ""
    results: dict[str, str] = field(default_factory=dict)


# Hosts grouped the way the network allowlist wants them: an archive provider
# is only usable when both its API host and its file host are reachable.
GROUPS = [
    Group("Archives — Wikimedia Commons", [
        Host("commons.wikimedia.org", "recherche d'images", "fetch"),
        Host("upload.wikimedia.org", "téléchargement des fichiers", "fetch"),
    ]),
    Group("Archives — Internet Archive", [
        Host("archive.org", "recherche", "fetch"),
        Host("ia800000.us.archive.org", "téléchargement (sous-domaines ia*)", "fetch"),
    ], optional=True),
    Group("Archives — Openverse (52 fonds agrégés)", [
        Host("api.openverse.org", "recherche multi-fonds", "fetch"),
    ], fichiers_ailleurs=(
        "les fichiers sont servis par les 52 fournisseurs d'origine "
        "(Flickr, Commons, musées) : impossible de tous les lister ici"
    )),
    Group("Archives — Smithsonian Open Access", [
        Host("api.si.edu", "recherche", "fetch"),
        Host("ids.si.edu", "téléchargement et IIIF", "fetch"),
    ], optional=True),
    Group("Archives — Library of Congress (vidéo 1080p)", [
        Host("www.loc.gov", "recherche", "fetch"),
        Host("tile.loc.gov", "téléchargement des MP4", "fetch"),
    ]),
    Group("B-roll générique — Pixabay", [
        Host("pixabay.com", "recherche et fichiers", "fetch"),
    ], optional=True, fichiers_ailleurs="même hôte que la recherche"),
    Group("Génération d'images — Vertex AI", [
        Host("aiplatform.googleapis.com", "génération (région `global`)", "images"),
        Host("oauth2.googleapis.com", "renouvellement du jeton d'accès", "images"),
    ], optional=True, fichiers_ailleurs=(
        "l'image revient encodée dans la réponse : aucun hôte de fichiers"
    )),
    Group("Génération d'images — Gemini", [
        Host("generativelanguage.googleapis.com", "génération", "images"),
    ], fichiers_ailleurs="images renvoyées dans la réponse"),
    Group("Voix — Microsoft Edge", [
        Host("speech.platform.bing.com", "synthèse", "voice"),
    ], fichiers_ailleurs="audio renvoyé dans le flux, aucun hôte de fichiers"),
]


def probe(hostname: str) -> str:
    """Return 'ok', 'bloqué', or a short failure description."""
    url = f"https://{hostname}/"
    request = Request(url, headers={"User-Agent": "Fresque/0.1 (doctor)"})
    try:
        with urlopen(request, timeout=TIMEOUT):
            return "ok"
    except HTTPError:
        # Any HTTP status means the connection itself succeeded.
        return "ok"
    except URLError as error:
        reason = str(error.reason)
        if "403" in reason or "Forbidden" in reason or "Tunnel" in reason:
            return "bloqué"
        if isinstance(error.reason, (socket.timeout, TimeoutError)):
            return "délai dépassé"
        if isinstance(error.reason, ssl.SSLError):
            return "erreur TLS"
        return f"injoignable ({reason[:40]})"
    except (socket.timeout, TimeoutError):
        return "délai dépassé"
    except OSError as error:  # pragma: no cover - environment dependent
        return f"erreur réseau ({error})"


def check_local() -> list[tuple[str, bool, str]]:
    """Things that must exist on disk, independent of the network.

    Ce que la voix exige dépend du moteur choisi : Kokoro veut 340 Mo de
    modèle sur le disque, Edge ne veut qu'un paquet et du réseau. Vérifier
    les deux enverrait télécharger un modèle dont on n'a pas besoin.
    """
    root = config.repo_root()
    fournisseur = str(config.get("voix", "provider", default="kokoro"))

    checks: list[tuple[str, bool, str]] = [
        ("Remotion installé", (root / "remotion" / "node_modules").is_dir(), "remotion/node_modules"),
        ("moteur de voix", True, fournisseur),
    ]

    if fournisseur == "kokoro":
        model = root / str(config.get("voix", "kokoro", "model", default="models/kokoro-v1.0.onnx"))
        voices = root / str(config.get("voix", "kokoro", "voices", default="models/voices-v1.0.bin"))
        checks.append(("modèle Kokoro", model.is_file(), str(model.relative_to(root))))
        checks.append(("voix Kokoro", voices.is_file(), str(voices.relative_to(root))))
        try:
            import kokoro_onnx  # noqa: F401
            checks.append(("paquet kokoro-onnx", True, "importable"))
        except ImportError:
            checks.append(("paquet kokoro-onnx", False, "pip install kokoro-onnx soundfile"))
    elif fournisseur == "edge":
        try:
            import edge_tts  # noqa: F401
            checks.append(("paquet edge-tts", True, "importable"))
        except ImportError:
            checks.append(("paquet edge-tts", False, "pip install edge-tts soundfile"))

    for key, needed_for in (
        ("GEMINI_API_KEY", "génération d'images"),
        ("PEXELS_API_KEY", "banque d'images (optionnel)"),
    ):
        checks.append((f"clé {key}", bool(os.environ.get(key)), needed_for))

    return checks


def run(report=print) -> tuple[bool, list[str]]:
    """Probe everything. Returns (essentials_ok, hosts to add to the allowlist)."""
    blocked: list[str] = []
    essentials_ok = True

    report("Réseau")
    for group in GROUPS:
        statuses = []
        for host in group.hosts:
            status = probe(host.name)
            group.results[host.name] = status
            statuses.append(status)
            mark = "✓" if status == "ok" else "✗"
            suffix = "" if status == "ok" else f"  ({status})"
            report(f"  {mark} {host.name:<38} {host.why}{suffix}")
            if status != "ok":
                blocked.append(host.name)
        usable = all(s == "ok" for s in statuses)
        if not usable and not group.optional:
            essentials_ok = False
        report(f"    → {group.label} : "
               + ("utilisable" if usable else
                  "INUTILISABLE" + (" (optionnel)" if group.optional else "")))

    report("")
    report("Local")
    for label, present, detail in check_local():
        report(f"  {'✓' if present else '·'} {label:<24} {detail}")

    return essentials_ok, blocked


def allowlist(blocked: list[str]) -> str:
    """The lines to paste into the environment's Custom allowed-domains field."""
    wildcards = {
        "ia800000.us.archive.org": "*.us.archive.org",
    }
    seen: list[str] = []
    for host in blocked:
        entry = wildcards.get(host, host)
        if entry not in seen:
            seen.append(entry)
    return "\n".join(seen)
