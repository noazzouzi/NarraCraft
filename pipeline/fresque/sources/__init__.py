"""Free-archive providers.

Every provider returns `Candidate` objects carrying a licence. An asset
without a usable licence never enters the pipeline — see CLAUDE.md.
"""
from .base import Candidate, FREE_LICENCES, is_free_licence
from . import wikimedia

PROVIDERS = {
    "wikimedia_commons": wikimedia.search,
}

__all__ = ["Candidate", "FREE_LICENCES", "is_free_licence", "PROVIDERS"]
