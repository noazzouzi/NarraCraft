"""Shared types for archive providers."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Licences we accept. Anything else is refused rather than guessed at:
# a monetised channel cannot afford an optimistic reading of a licence.
FREE_LICENCES = (
    "public domain", "pd-", "cc0", "cc-zero", "no restrictions",
    "cc by", "cc-by", "cc by-sa", "cc-by-sa", "attribution",
)

REFUSED = ("fair use", "non-free", "no license", "copyright", "all rights")


def is_free_licence(label: str | None) -> bool:
    if not label:
        return False
    text = re.sub(r"<[^>]+>", " ", label).strip().lower()
    if any(bad in text for bad in REFUSED) and "public domain" not in text:
        return False
    return any(good in text for good in FREE_LICENCES)


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
