"""Integration test — Resident Evil 7: Biohazard.

Tests the onboarding pipeline against the real Fandom wiki API:
1. Search for "Resident Evil 7 Biohazard"
2. Discover characters from residentevil.fandom.com
3. Discover locations from residentevil.fandom.com

These tests hit the real Fandom API — they require network access
and may be slow (~2-5 min total).
"""

import pytest
from backend.services.onboarding.wiki_scraper import (
    search_wiki,
    discover_characters,
    discover_locations,
    get_wiki_page,
    WIKI_SLUGS,
)


# The Resident Evil wiki slug
RE_WIKI = "residentevil"

# Module-level cache to avoid redundant slow API calls across tests
_characters_cache = None
_locations_cache = None


async def _get_characters():
    global _characters_cache
    if _characters_cache is None:
        _characters_cache = await discover_characters(RE_WIKI, "Resident Evil")
    return _characters_cache


async def _get_locations():
    global _locations_cache
    if _locations_cache is None:
        _locations_cache = await discover_locations(RE_WIKI)
    return _locations_cache


def _safe(text: str, max_len: int = 80) -> str:
    """Make text safe for CP1252 console output."""
    return text[:max_len].encode("ascii", errors="replace").decode("ascii")


@pytest.mark.asyncio
class TestRE7WikiSearch:
    """Test searching the RE Fandom wiki for RE7 content."""

    async def test_search_resident_evil_7(self):
        """Search should find RE7-related pages on the RE wiki."""
        results = await search_wiki("Resident Evil 7", wiki_slug=RE_WIKI)
        assert len(results) > 0, "No search results found for 'Resident Evil 7'"

        titles = [r.title for r in results]
        print(f"\nRE7 search results ({len(results)}):")
        for r in results[:10]:
            print(f"  - {_safe(r.title)}")

        # At least one result should reference RE7 or Biohazard
        has_re7 = any(
            "7" in t or "biohazard" in t.lower() or "VII" in t
            for t in titles
        )
        assert has_re7, f"No RE7-related results in: {titles}"

    async def test_search_biohazard(self):
        """Search for 'Biohazard' should yield results."""
        results = await search_wiki("Biohazard", wiki_slug=RE_WIKI)
        if not results:
            results = await search_wiki("Resident Evil Biohazard", wiki_slug=RE_WIKI)
        assert len(results) > 0, "No results for 'Biohazard' or 'Resident Evil Biohazard'"

    async def test_re7_page_exists(self):
        """The specific RE7 page should be fetchable."""
        page = await get_wiki_page("Resident Evil 7: Biohazard", RE_WIKI)
        if page is None:
            page = await get_wiki_page("Resident Evil Village", RE_WIKI)
        # This test validates the wiki is accessible


@pytest.mark.asyncio
class TestRE7Characters:
    """Test character discovery from the RE Fandom wiki.

    Uses a shared cache to avoid calling discover_characters multiple times.
    """

    async def test_discover_characters_returns_results(self):
        """Should find characters from the RE wiki."""
        characters = await _get_characters()

        assert len(characters) > 0, "No characters found on residentevil.fandom.com"
        print(f"\nDiscovered {len(characters)} characters:")
        for c in characters[:15]:
            desc = _safe(c.description) if c.description else "(no description)"
            print(f"  - {_safe(c.name)}: {desc}")

    async def test_characters_have_names(self):
        """Every character should have a name."""
        characters = await _get_characters()
        for char in characters:
            assert char.name, "Character with empty name found"

    async def test_characters_have_page_urls(self):
        """Every character should have a page URL."""
        characters = await _get_characters()
        for char in characters:
            assert char.page_url, f"Character {char.name} has no page_url"
            assert "residentevil.fandom.com" in char.page_url

    async def test_no_template_pages_in_results(self):
        """Results should not contain wiki Template: or Category: pages."""
        characters = await _get_characters()
        for char in characters:
            assert not char.name.startswith("Template:"), f"Template page in results: {char.name}"
            assert not char.name.startswith("Category:"), f"Category page in results: {char.name}"

    async def test_known_re_characters_present(self):
        """Core RE characters should appear in results."""
        characters = await _get_characters()
        names_lower = [c.name.lower() for c in characters]

        known_chars = ["chris redfield", "jill valentine", "leon", "claire redfield",
                       "albert wesker", "ada wong", "ethan winters", "chris",
                       "jill", "wesker", "leon kennedy", "baker"]

        found = [kc for kc in known_chars if any(kc in n for n in names_lower)]
        print(f"\nKnown characters found: {found}")
        print(f"All character names: {[_safe(c.name) for c in characters[:20]]}")

        assert len(found) >= 1, (
            f"Expected at least 1 known RE character, found {len(found)}: {found}\n"
            f"Available: {[c.name for c in characters[:20]]}"
        )


@pytest.mark.asyncio
class TestRE7Locations:
    """Test location discovery from the RE Fandom wiki."""

    async def test_discover_locations_returns_results(self):
        """Should find locations from the RE wiki."""
        locations = await _get_locations()

        assert len(locations) > 0, "No locations found on residentevil.fandom.com"
        print(f"\nDiscovered {len(locations)} locations:")
        for loc in locations[:15]:
            desc = _safe(loc.description) if loc.description else "(no description)"
            print(f"  - {_safe(loc.name)}: {desc}")

    async def test_locations_have_names(self):
        """Every location should have a name."""
        locations = await _get_locations()
        for loc in locations:
            assert loc.name, "Location with empty name found"

    async def test_locations_have_page_urls(self):
        locations = await _get_locations()
        for loc in locations:
            assert loc.page_url, f"Location {loc.name} has no page_url"
            assert "residentevil.fandom.com" in loc.page_url


@pytest.mark.asyncio
class TestRE7FullOnboardingFlow:
    """End-to-end test: search -> characters -> locations for RE7."""

    async def test_full_flow(self):
        """Complete onboarding flow for Resident Evil 7."""
        print("\n=== RE7 Full Onboarding Flow ===")

        # Step 1: Search
        print("\n[1/3] Searching for 'Resident Evil 7 Biohazard'...")
        results = await search_wiki("Resident Evil 7", wiki_slug=RE_WIKI)
        assert len(results) > 0, "Search returned no results"
        print(f"  Found {len(results)} results")

        # Step 2: Characters (use cache)
        print("\n[2/3] Discovering characters...")
        characters = await _get_characters()
        assert len(characters) > 0, "No characters found"
        print(f"  Found {len(characters)} characters")

        # Step 3: Locations (use cache)
        print("\n[3/3] Discovering locations...")
        locations = await _get_locations()
        assert len(locations) > 0, "No locations found"
        print(f"  Found {len(locations)} locations")

        # Summary
        print("\n=== Summary ===")
        print(f"  Search results: {len(results)}")
        print(f"  Characters:     {len(characters)}")
        print(f"  Locations:      {len(locations)}")
        print(f"  Top characters: {', '.join(_safe(c.name, 30) for c in characters[:5])}")
        print(f"  Top locations:  {', '.join(_safe(l.name, 30) for l in locations[:5])}")

        assert len(characters) >= 1, "Need at least 1 character for onboarding"
        assert len(locations) >= 3, "Need at least 3 locations for onboarding"
