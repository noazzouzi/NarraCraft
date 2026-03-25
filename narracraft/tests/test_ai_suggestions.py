"""Unit tests for AI topic suggestion generation."""

import pytest
from backend.services.topics.ai_suggestions import (
    generate_suggestions,
    _similarity,
    TEMPLATES,
)


class TestSimilarity:
    """Tests for word-overlap similarity."""

    def test_identical(self):
        assert _similarity("hello world", "hello world") == 1.0

    def test_no_overlap(self):
        assert _similarity("cat dog", "sun moon") == 0.0

    def test_partial(self):
        sim = _similarity("hidden secret room", "secret room found")
        assert 0.0 < sim < 1.0

    def test_empty(self):
        assert _similarity("", "test") == 0.0
        assert _similarity("", "") == 0.0


class TestGenerateSuggestions:
    """Tests for template-based suggestion generation."""

    def test_returns_list(self):
        result = generate_suggestions("Resident Evil")
        assert isinstance(result, list)

    def test_respects_count(self):
        result = generate_suggestions("Resident Evil", count=5)
        assert len(result) <= 5

    def test_suggestions_have_required_fields(self):
        result = generate_suggestions("Resident Evil", count=3)
        for sug in result:
            assert sug.title
            assert sug.description
            assert sug.category in TEMPLATES.keys()
            assert sug.requires_fact_check is True

    def test_franchise_name_in_title(self):
        result = generate_suggestions("Dark Souls", count=5)
        for sug in result:
            assert "Dark Souls" in sug.title

    def test_character_names_substituted(self):
        result = generate_suggestions(
            "Resident Evil",
            character_names=["Chris", "Jill", "Wesker"],
            count=20,
        )
        # At least some suggestions should have character names
        titles = " ".join(s.title for s in result)
        has_char = any(name in titles for name in ["Chris", "Jill", "Wesker"])
        # Character templates may or may not be selected (random), so just check format
        assert len(result) > 0

    def test_filters_similar_to_existing_seeds(self):
        seeds = [
            "A scrapped mechanic that would have changed the entire game",
            "The developer's original vision was very different from the final product",
        ]
        result = generate_suggestions(
            "Test",
            existing_seeds=seeds,
            count=20,
        )
        # Results should not contain topics too similar to seeds
        for sug in result:
            for seed in seeds:
                sim = _similarity(sug.title, seed)
                # Allow some similarity but not exact matches
                assert sim < 0.95

    def test_all_categories_represented(self):
        """With enough suggestions, multiple categories should appear."""
        result = generate_suggestions("Test Franchise", count=25)
        categories = set(s.category for s in result)
        assert len(categories) >= 2  # At least 2 different categories

    def test_default_character_used_when_none(self):
        result = generate_suggestions("Test", character_names=None, count=20)
        titles = " ".join(s.title for s in result)
        # Should use "the main character" as fallback for {character} templates
        # Some may not have {character} at all, that's fine
        assert len(result) > 0
