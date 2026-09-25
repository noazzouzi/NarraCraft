"""Shared types and courtesies for archive providers."""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field

# Licences we accept. Anything else is refused rather than guessed at:
# a monetised channel cannot afford an optimistic reading of a licence.
FREE_LICENCES = (
    "public domain", "pd-", "cc0", "cc-zero", "no restrictions",
    "cc by", "cc-by", "cc by-sa", "cc-by-sa", "attribution",
    # Nommées une à une, et jamais devinées. Ces deux-là ne sont pas des
    # Creative Commons — aucun test par mot-clé ne les reconnaîtrait — mais
    # leurs conditions autorisent l'usage commercial et la modification,
    # ce qui est la seule question que pose cette fonction. Les ajouter
    # élargit le fonds sans rien relâcher : une licence absente de cette
    # liste reste refusée.
    "pexels license", "pixabay license",
)

REFUSED = ("fair use", "non-free", "no license", "copyright", "all rights")

#: Checked before anything else, and matched on word boundaries.
#:
#: `NC` forbids the commercial use the channel depends on. `ND` forbids
#: derivative works, and a Ken Burns move over a cropped frame is one.
#:
#: The boundary matters: a plain substring test reads "cc by-nc 4.0" as
#: containing "cc by" and lets it through. That is exactly what this filter
#: did until a test caught it.
NON_COMMERCIAL_RE = re.compile(r"\b(nc|non[-\s]?commercial\w*)\b", re.IGNORECASE)
NO_DERIVATIVES_RE = re.compile(r"\b(nd|no[-\s]?deriv\w*)\b", re.IGNORECASE)


def is_free_licence(label: str | None) -> bool:
    """True only for licences allowing commercial use AND modification."""
    if not label:
        return False
    text = re.sub(r"<[^>]+>", " ", label).strip().lower()

    if NON_COMMERCIAL_RE.search(text) or NO_DERIVATIVES_RE.search(text):
        return False
    if any(bad in text for bad in REFUSED) and "public domain" not in text:
        return False
    return any(good in text for good in FREE_LICENCES)


class Throttle:
    """One rate limiter per provider.

    Every free archive answers 429 when pushed, and behind a shared outbound
    address they answer it readily. This was written once inside the Wikimedia
    adapter and pulled up here before the second one existed — rate limiting
    turned out to be the real engineering risk, not the APIs themselves.
    """

    def __init__(self, min_interval_s: float) -> None:
        self.min_interval_s = min_interval_s
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        with self._lock:
            elapsed = time.monotonic() - self._last
            if elapsed < self.min_interval_s:
                time.sleep(self.min_interval_s - elapsed)
            self._last = time.monotonic()


def retry_delay(response, attempt: int, floor: float) -> float:
    """Seconds to wait before retrying, honouring Retry-After when sent."""
    header = (response.headers.get("Retry-After") or "").strip()
    if header.isdigit():
        return min(float(header), 30.0)
    return min(floor * (2 ** (attempt + 1)), 30.0)


def is_retryable(status: int) -> bool:
    return status == 429 or status >= 500


def expects_json(response) -> None:
    """Guard before `.json()`.

    Some providers answer errors with an HTML page — Library of Congress
    serves a Cloudflare block page on 429. Calling `.json()` on that raises a
    decoding error that says nothing about what actually happened.
    """
    content_type = response.headers.get("Content-Type", "")
    if "json" not in content_type.lower():
        raise ValueError(
            f"réponse non-JSON ({content_type or 'type absent'}, "
            f"HTTP {response.status_code}) — probablement une page d'erreur"
        )


@dataclass
class Candidate:
    """One sourceable image, with everything needed to credit it."""
    provider: str
    title: str
    page_url: str
    file_url: str
    licence: str
    licence_url: str = ""
    author: str = ""
    width: int = 0
    height: int = 0
    mime: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def usable(self) -> bool:
        return bool(self.file_url) and is_free_licence(self.licence)

    def credit(self) -> str:
        parts = [self.title.strip()]
        if self.author:
            parts.append(re.sub(r"<[^>]+>", "", self.author).strip())
        parts.append(re.sub(r"<[^>]+>", "", self.licence).strip())
        return " — ".join(p for p in parts if p)
