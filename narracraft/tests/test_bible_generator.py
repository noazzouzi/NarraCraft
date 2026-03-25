"""Unit tests for character bible generator."""

import pytest
from backend.services.onboarding.bible_generator import (
    generate_archetype_id,
    generate_bible_from_wiki,
    _extract_appearance_from_text,
    CharacterBible,
)


class TestGenerateArchetypeId:
    """Tests for archetype ID generation."""

    def test_simple_name(self):
        assert generate_archetype_id("Chris") == "chris"

    def test_two_word_name(self):
        assert generate_archetype_id("Chris Redfield") == "chris_redfield"

    def test_three_word_name_truncated(self):
        """Only first two words used."""
        result = generate_archetype_id("Albert Wesker III")
        assert result == "albert_wesker"

    def test_strips_punctuation(self):
        result = generate_archetype_id("O'Brien-Smith")
        assert "'" not in result
        assert "-" not in result

    def test_lowercases(self):
        result = generate_archetype_id("JILL VALENTINE")
        assert result == "jill_valentine"

    def test_empty_name(self):
        assert generate_archetype_id("") == "unknown_character"

    def test_whitespace_only(self):
        assert generate_archetype_id("   ") == "unknown_character"


class TestExtractAppearanceFromText:
    """Tests for appearance extraction from wiki text."""

    def test_finds_wearing_keywords(self):
        text = "The character is tall and muscular. He wears a green combat vest. His eyes are brown."
        result = _extract_appearance_from_text(text)
        assert len(result) >= 2
        assert any("wears" in s.lower() or "muscular" in s.lower() for s in result)

    def test_skips_short_sentences(self):
        text = "Tall. Short hair. A complex character who wears distinctive armor and carries weapons."
        result = _extract_appearance_from_text(text)
        # Short sentences (<20 chars) should be skipped
        assert all(len(s) >= 20 for s in result)

    def test_empty_text(self):
        assert _extract_appearance_from_text("") == []

    def test_no_appearance_keywords(self):
        text = "The franchise was released in 1996. It sold millions of copies worldwide."
        result = _extract_appearance_from_text(text)
        assert result == []

    def test_max_five_sentences(self):
        text = ". ".join([f"Character wears outfit number {i} and looks distinctive" for i in range(10)])
        result = _extract_appearance_from_text(text)
        assert len(result) <= 5

    def test_removes_citations(self):
        text = "The character wears a blue uniform [1][2] and has short hair [citation needed]."
        result = _extract_appearance_from_text(text)
        for s in result:
            assert "[1]" not in s
            assert "[2]" not in s


class TestGenerateBibleFromWiki:
    """Tests for full bible generation."""

    def test_basic_generation(self):
        bible = generate_bible_from_wiki(
            character_name="Chris Redfield",
            wiki_summary="Chris is a BSAA agent known for his muscular build.",
            infobox={"gender": "Male", "hair_color": "Brown"},
        )
        assert isinstance(bible, CharacterBible)
        assert bible.archetype_id == "chris_redfield"
        assert bible.source_character_name == "Chris Redfield"
        assert "Male" in bible.visual_description
        assert "brown hair" in bible.visual_description.lower()

    def test_with_full_infobox(self):
        bible = generate_bible_from_wiki(
            character_name="Jill Valentine",
            wiki_summary="Jill wears a blue beret and appears athletic.",
            infobox={
                "gender": "Female",
                "age": "23",
                "hair": "Brown",
                "eyes": "Blue",
                "occupation": "S.T.A.R.S. Alpha Team member",
            },
        )
        assert "Female" in bible.visual_description
        assert "23" in bible.visual_description
        assert "brown hair" in bible.visual_description.lower()
        assert "blue eyes" in bible.visual_description.lower()
        assert "Occupation" in bible.character_bible

    def test_empty_infobox_still_works(self):
        bible = generate_bible_from_wiki(
            character_name="Unknown Guy",
            wiki_summary="A mysterious figure from the game.",
            infobox={},
        )
        assert bible.archetype_id
        assert bible.visual_description  # Should have fallback

    def test_bible_text_truncated_to_600(self):
        long_summary = "Character wears armor. " * 100  # Very long text
        bible = generate_bible_from_wiki(
            character_name="Test",
            wiki_summary=long_summary,
            infobox={},
        )
        assert len(bible.character_bible) <= 600

    def test_appearance_info_extracted(self):
        bible = generate_bible_from_wiki(
            character_name="Wesker",
            wiki_summary="Wesker wears dark sunglasses and a black leather trench coat. He appears cold and calculating.",
            infobox={"gender": "Male", "hair_color": "Blond"},
        )
        # Should include appearance from summary
        assert len(bible.character_bible) > 0
