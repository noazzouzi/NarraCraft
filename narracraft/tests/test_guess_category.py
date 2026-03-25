"""Unit tests for the _guess_category helper in topics API."""

import pytest

# Import the private function from the topics API module
from backend.api.topics import _guess_category


class TestGuessCategory:
    """Tests for text-based category guessing."""

    def test_easter_egg_keywords(self):
        assert _guess_category("This is a hidden easter egg in the game") == "easter_egg"
        assert _guess_category("A secret reference to another franchise") == "easter_egg"

    def test_cut_content_keywords(self):
        assert _guess_category("Scrapped content that was removed from the final build") == "cut_content"
        assert _guess_category("Unused beta version had different mechanics") == "cut_content"

    def test_dev_design_keywords(self):
        assert _guess_category("The developer talked about the design process") == "dev_design"
        assert _guess_category("Game mechanic development choices") == "dev_design"

    def test_lore_keywords(self):
        assert _guess_category("Deep lore about the mythology of the world") == "lore"
        assert _guess_category("The story contains symbolism and foreshadowing") == "lore"

    def test_memes_keywords(self):
        assert _guess_category("A hilarious bug that became a meme") == "memes"
        assert _guess_category("The funniest joke in the series") == "memes"

    def test_characters_keywords(self):
        assert _guess_category("The protagonist was born in a small town") == "characters"
        assert _guess_category("The main villain grew up as an orphan") == "characters"

    def test_default_to_lore(self):
        """When no keywords match, should default to lore."""
        assert _guess_category("Something completely generic and normal") == "lore"

    def test_case_insensitive(self):
        assert _guess_category("HIDDEN SECRET EASTER EGG") == "easter_egg"
        assert _guess_category("CUT CONTENT removed from game") == "cut_content"

    def test_priority_order(self):
        """Easter egg keywords should be checked before others."""
        # "hidden" matches easter_egg first
        result = _guess_category("A hidden easter egg character")
        assert result == "easter_egg"

    def test_empty_string(self):
        result = _guess_category("")
        assert result == "lore"  # default
