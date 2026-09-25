"""Openverse — 52 archive collections behind one API, with a licence filter
that runs on the server.

WHAT IT IS GOOD FOR, AND WHAT IT IS NOT
=======================================
The licence handling is the best of any source we looked at: `license_type=
commercial,modification` applies our eliminating criterion before anything is
transferred, and every result carries a ready-made attribution string.

The resolution is the problem, and it is not fixable from our side. Measured
on a hundred results, excluding Wikimedia:

    ≥1600px :   0 %
    ≥1200px :   0 %
    ≥900px  :  69 %

Openverse indexes a rendition, not the original. Flickr — 96 % of results —
is stored at 1024px and answers **410 Gone** for `_h`, `_k` and `_3k`.
Rawpixel declares 6999px and serves `editor_1024`; `editor_2048` is 404.
Europeana is honest about its dimensions but sits around 1200px.

So this is a **fallback below Wikimedia**, not a replacement for it. It earns
its place on the shots Commons cannot cover at all, where a soft real
photograph still beats a generated one — and it saves a paid generation.

The declared/served gap is also why `fetch` verifies the real dimensions of
what it downloaded instead of trusting any provider's metadata.
"""
from __future__ import annotations

from typing import Any, Iterable

import requests

from .base import Candidate, Throttle, expects_json, is_retryable, retry_delay

API = "https://api.openverse.org/v1/images/"
USER_AGENT = "Fresque/0.1 (documentary pipeline; contact via repository)"

# Measured on the live API: 20 requests/min and 200/day without a token.
# A free token raises both; supply it through OPENVERSE_TOKEN.
MIN_INTERVAL_S = 3.2
MAX_RETRIES = 2
_throttle = Throttle(MIN_INTERVAL_S)

#: Only licences that allow commercial use AND modification. A Ken Burns move
#: is a modification, so a No-Derivatives licence is not usable either.
LICENCE_FILTER = "commercial,modification"

#: Already searched directly, with proper thumbnails and far better
#: resolution. Asking Openverse for it again would spend our quota on
#: duplicates of results we can serve better ourselves.
EXCLUDED_SOURCES = "wikimedia"

GOOD_FILETYPES = ("jpg", "jpeg", "png", "webp", "tiff")


def _token_header(token: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"} if token else {}


def search(
    query: str,
    limit: int = 6,
    min_width: int = 900,
    session: requests.Session | None = None,
    token: str | None = None,
    timeout: float = 30.0,
) -> list[Candidate]:
    """Search Openverse for commercially usable images."""
    http = session or requests.Session()
    params = {
        "q": query,
        "license_type": LICENCE_FILTER,
        "excluded_source": EXCLUDED_SOURCES,
        # `size=large` filters on Openverse's own categorisation, which almost
        # nothing carries: it returned zero results on every query tried.
        "page_size": str(min(limit * 4, 20)),
    }
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json",
               **_token_header(token)}

    for attempt in range(MAX_RETRIES + 1):
        _throttle.wait()
        response = http.get(API, params=params, headers=headers, timeout=timeout)
        if is_retryable(response.status_code) and attempt < MAX_RETRIES:
            import time
            time.sleep(retry_delay(response, attempt, MIN_INTERVAL_S))
            continue
        response.raise_for_status()
        break

    expects_json(response)
    return _to_candidates(response.json().get("results", []) or [],
                          limit=limit, min_width=min_width)


def _licence_label(entry: dict[str, Any]) -> str:
    """`by-sa` + `3.0` -> `CC BY-SA 3.0`, the form is_free_licence expects."""
    code = (entry.get("license") or "").strip()
    if not code:
        return ""
    version = (entry.get("license_version") or "").strip()
    if code.lower() in ("cc0", "pdm"):
        label = "CC0" if code.lower() == "cc0" else "Public domain"
    else:
        label = f"CC {code.upper()}"
    return f"{label} {version}".strip()


def _to_candidates(
    entries: Iterable[dict[str, Any]], limit: int, min_width: int
) -> list[Candidate]:
    candidates: list[Candidate] = []
    for entry in entries:
        if (entry.get("filetype") or "").lower() not in GOOD_FILETYPES:
            continue
        # Declared width, not served width — the gap is verified after the
        # download, where it can actually be measured.
        if int(entry.get("width") or 0) < min_width:
            continue
        url = entry.get("url") or ""
        if not url:
            continue

        candidate = Candidate(
            provider=f"openverse:{entry.get('source', '?')}",
            title=(entry.get("title") or "").strip(),
            page_url=entry.get("foreign_landing_url", ""),
            file_url=url,
            licence=_licence_label(entry),
            licence_url=entry.get("license_url", ""),
            author=(entry.get("creator") or "").strip(),
            width=int(entry.get("width") or 0),
            height=int(entry.get("height") or 0),
            mime=f"image/{entry.get('filetype')}",
            extra={"attribution": (entry.get("attribution") or "")[:300]},
        )
        if candidate.usable:
            candidates.append(candidate)
        if len(candidates) >= limit:
            break
    return candidates


def download(candidate: Candidate, destination, timeout: float = 60.0) -> None:
    """Stream a candidate's file to disk, from the provider that holds it."""
    last: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        _throttle.wait()
        try:
            with requests.get(
                candidate.file_url, stream=True, timeout=timeout,
                headers={"User-Agent": USER_AGENT},
            ) as response:
                if is_retryable(response.status_code) and attempt < MAX_RETRIES:
                    import time
                    time.sleep(retry_delay(response, attempt, 2.0))
                    continue
                response.raise_for_status()
                with open(destination, "wb") as fh:
                    for chunk in response.iter_content(chunk_size=65536):
                        fh.write(chunk)
                return
        except requests.RequestException as error:
            last = error
            if attempt >= MAX_RETRIES:
                raise
    if last:
        raise last
