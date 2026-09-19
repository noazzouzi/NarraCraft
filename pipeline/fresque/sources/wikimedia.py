"""Wikimedia Commons — no API key, and the cleanest licence metadata around."""
from __future__ import annotations

import re
import threading
import time
from typing import Any, Iterable

import requests

from .base import Candidate

API = "https://commons.wikimedia.org/w/api.php"
# Commons asks identifiable clients to declare themselves.
USER_AGENT = "Fresque/0.1 (documentary pipeline; contact via repository)"

# Formats we can actually put on screen.
GOOD_MIME = ("image/jpeg", "image/png", "image/tiff", "image/webp")

# Commons is a free service and answers 429 when pushed. One request per
# second is well within what it tolerates, and the whole pipeline makes at
# most a couple of hundred.
MIN_INTERVAL_S = 1.1
MAX_RETRIES = 3

_throttle = threading.Lock()
_last_call = 0.0


def _wait_turn() -> None:
    global _last_call
    with _throttle:
        elapsed = time.monotonic() - _last_call
        if elapsed < MIN_INTERVAL_S:
            time.sleep(MIN_INTERVAL_S - elapsed)
        _last_call = time.monotonic()


def build_search(query: str, min_width: int) -> str:
    """Add the server-side filters that make the results usable.

    Plain full-text search on Commons is dominated by scanned books and
    newspapers: they are files too, and their OCR'd contents match almost any
    historical phrase. A search for `Titanic boiler room stokers 1912` comes
    back ten-elevenths PDF. `filetype:bitmap` removes them at the source, and
    `filew:` filters on width server-side so the result budget is spent on
    candidates we could actually use.
    """
    extra = []
    if "filetype:" not in query and "filemime:" not in query:
        extra.append("filetype:bitmap")
    if "filew:" not in query and min_width:
        extra.append(f"filew:>{min_width}")
    return " ".join([query, *extra])


# Wikimedia serves cached renderings at standard widths and rate-limits
# requests for unscaled originals hard — its own 429 body says to use these
# instead. So we always ask for a thumbnail at one of these widths, and only
# accept a file whose original is strictly larger, which guarantees the
# response is a cached rendering rather than the original itself.
STANDARD_WIDTHS = (1920, 1280, 800)
RELAXED_WIDTH = 1280
CORE_TERMS = 3


def variants(query: str, min_width: int) -> list[tuple[str, int]]:
    """Progressively looser attempts, most specific first.

    Commons combines search terms with AND, so a precise five-term query is
    the one most likely to return nothing at all: `Titanic boiler room stokers
    1912` finds zero files even with no width floor, while `Titanic engineers
    memorial Southampton` finds three good ones. Shortening to the leading
    terms is what rescues those, and lowering the width floor is the last
    resort — a smaller real photograph still beats a generated one, and it
    saves a paid generation.
    """
    terms = query.split()
    core = " ".join(terms[:CORE_TERMS])

    widths = [w for w in STANDARD_WIDTHS if w <= min_width] or [min_width]
    attempts = [(query, widths[0])]
    if core != query:
        attempts.append((core, widths[0]))
    for width in widths[1:]:
        attempts.append((query, width))
        if core != query:
            attempts.append((core, width))

    seen: set[tuple[str, int]] = set()
    return [a for a in attempts if not (a in seen or seen.add(a))]


def search_relaxed(
    query: str,
    limit: int = 6,
    min_width: int = 1280,
    session: requests.Session | None = None,
) -> tuple[list[Candidate], str, int]:
    """Try each variant in turn. Returns (candidates, query used, width used)."""
    http = session or requests.Session()
    for attempt_query, width in variants(query, min_width):
        found = search(attempt_query, limit=limit, min_width=width, session=http)
        if found:
            return found, attempt_query, width
    return [], query, min_width


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
        "gsrsearch": build_search(query, min_width),
        "gsrnamespace": "6",          # File: namespace
        "gsrlimit": str(max(limit * 3, limit)),
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        # Ask for a cached rendering at a standard width, never the original.
        "iiurlwidth": str(min_width),
    }

    response = _get(http, params, timeout)
    pages = response.json().get("query", {}).get("pages", []) or []

    return _to_candidates(pages, limit=limit, min_width=min_width)


def _get(http: requests.Session, params: dict[str, str], timeout: float):
    """One throttled request, retried on 429 and 5xx."""
    for attempt in range(MAX_RETRIES + 1):
        _wait_turn()
        response = http.get(
            API, params=params, timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        retryable = response.status_code == 429 or response.status_code >= 500
        if retryable and attempt < MAX_RETRIES:
            # Honour Retry-After when Commons sends one; back off otherwise.
            header = response.headers.get("Retry-After", "")
            delay = float(header) if header.isdigit() else MIN_INTERVAL_S * (2 ** (attempt + 1))
            time.sleep(min(delay, 30.0))
            continue
        response.raise_for_status()
        return response
    response.raise_for_status()
    return response


# A 16:9 frame fills itself from the centre of the source image, so a tall
# scan — a book page, a poster, a portrait plate — survives on screen as a
# narrow vertical slice of itself. Landscape candidates come first.
MIN_LANDSCAPE_RATIO = 1.15


def _prefer_landscape(candidates: list[Candidate]) -> list[Candidate]:
    """Reorder without discarding: search relevance is preserved inside each
    group, and a portrait plate is still better than nothing when it is all
    the archive has."""
    def ratio(candidate: Candidate) -> float:
        return candidate.width / candidate.height if candidate.height else 0.0

    landscape = [c for c in candidates if ratio(c) >= MIN_LANDSCAPE_RATIO]
    rest = [c for c in candidates if ratio(c) < MIN_LANDSCAPE_RATIO]
    return landscape + rest


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

        # Strictly larger: if the original is at or below the requested width,
        # MediaWiki hands back the original itself, which is the path
        # Wikimedia rate-limits. Skipping those keeps every download on a
        # cached thumbnail.
        if int(info.get("width") or 0) <= min_width:
            continue
        thumb = info.get("thumburl") or ""
        if not thumb or "thumbnail_unscaled" in thumb:
            continue

        candidate = Candidate(
            provider="wikimedia_commons",
            title=_plain(page.get("title", "")).removeprefix("File:"),
            page_url=info.get("descriptionurl", ""),
            file_url=thumb,
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
        # Gather more than asked for, so the landscape preference below has
        # something to choose between rather than reordering a single result.
        if len(candidates) >= limit * 2:
            break

    return _prefer_landscape(candidates)[:limit]


def download(candidate: Candidate, destination, timeout: float = 60.0) -> None:
    """Stream a candidate's file to disk, with the same courtesy as searching.

    The file host rate-limits independently of the API, and behind a shared
    outbound address it answers 429 readily. A download is also the one place
    where giving up costs a real asset, so it retries rather than failing the
    whole run.
    """
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        _wait_turn()
        try:
            with requests.get(
                candidate.file_url, stream=True, timeout=timeout,
                headers={"User-Agent": USER_AGENT},
            ) as response:
                if (response.status_code == 429 or response.status_code >= 500) \
                        and attempt < MAX_RETRIES:
                    header = response.headers.get("Retry-After", "")
                    delay = float(header) if header.isdigit() else 2.0 * (2 ** attempt)
                    time.sleep(min(delay, 30.0))
                    continue
                response.raise_for_status()
                with open(destination, "wb") as fh:
                    for chunk in response.iter_content(chunk_size=65536):
                        fh.write(chunk)
                return
        except requests.RequestException as error:
            last_error = error
            if attempt >= MAX_RETRIES:
                raise
            time.sleep(2.0 * (2 ** attempt))
    if last_error:
        raise last_error
