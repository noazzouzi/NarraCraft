"""Wikimedia Commons — no API key, and the cleanest licence metadata around.

NOT VERIFIED AGAINST THE LIVE API: commons.wikimedia.org is blocked by this
session's egress policy, so this module has only been exercised against
recorded fixtures. Run `python -m fresque sources --check` from a machine with
network access before trusting it.
"""
from __future__ import annotations

import re
import time
from typing import Any, Iterable

import requests

from .base import Candidate

API = "https://commons.wikimedia.org/w/api.php"
# Commons asks identifiable clients to declare themselves.
USER_AGENT = "Fresque/0.1 (documentary pipeline; contact via repository)"

# Formats we can actually put on screen.
GOOD_MIME = ("image/jpeg", "image/png", "image/tiff", "image/webp")


def _plain(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()


def _meta(info: dict[str, Any], key: str) -> str:
    return _plain(info.get("extmetadata", {}).get(key, {}).get("value", ""))


def search(
    query: str,
    limit: int = 12,
    min_width: int = 1280,
    session: requests.Session | None = None,
    timeout: float = 20.0,
) -> list[Candidate]:
    """Search Commons for usable images matching `query`."""
    http = session or requests.Session()
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",          # File: namespace
        "gsrlimit": str(max(limit * 3, limit)),
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "1920",
    }
    response = http.get(
        API, params=params, timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", []) or []

    return _to_candidates(pages, limit=limit, min_width=min_width)


def _to_candidates(
    pages: Iterable[dict[str, Any]], limit: int, min_width: int
) -> list[Candidate]:
    candidates: list[Candidate] = []
    for page in pages:
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]

        if info.get("mime") not in GOOD_MIME:
            continue
        if int(info.get("width") or 0) < min_width:
            continue

        candidate = Candidate(
            provider="wikimedia_commons",
            title=_plain(page.get("title", "")).removeprefix("File:"),
            page_url=info.get("descriptionurl", ""),
            # thumburl is the 1920px rendering; url is the original, often huge.
            file_url=info.get("thumburl") or info.get("url", ""),
            licence=_meta(info, "LicenseShortName") or _meta(info, "UsageTerms"),
            licence_url=_meta(info, "LicenseUrl"),
            author=_meta(info, "Artist"),
            width=int(info.get("thumbwidth") or info.get("width") or 0),
            height=int(info.get("thumbheight") or info.get("height") or 0),
            mime=info.get("mime", ""),
            extra={"description": _meta(info, "ImageDescription")[:400]},
        )

        if candidate.usable:
            candidates.append(candidate)
        if len(candidates) >= limit:
            break

    return candidates


def download(candidate: Candidate, destination, timeout: float = 60.0) -> None:
    """Stream a candidate's file to disk."""
    with requests.get(
        candidate.file_url, stream=True, timeout=timeout,
        headers={"User-Agent": USER_AGENT},
    ) as response:
        response.raise_for_status()
        with open(destination, "wb") as fh:
            for chunk in response.iter_content(chunk_size=65536):
                fh.write(chunk)
    time.sleep(0.2)  # be a good citizen on a free API
