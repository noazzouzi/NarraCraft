"""Unit tests for compliance module utilities (no network/browser needed)."""

import pytest
from backend.services.pipeline.compliance import (
    _extract_words,
    _jaccard_similarity,
)


class TestExtractWords:
    """Tests for word extraction and normalization."""

    def test_basic_extraction(self):
        words = _extract_words("The cat sat on the mat")
        assert "cat" in words
        assert "sat" in words
        assert "mat" in words

    def test_removes_stop_words(self):
        words = _extract_words("The cat is on a mat and the dog")
        assert "the" not in words
        assert "is" not in words
        assert "on" not in words
        assert "and" not in words

    def test_lowercases(self):
        words = _extract_words("HELLO World")
        assert "hello" in words
        assert "world" in words
        assert "HELLO" not in words

    def test_removes_punctuation(self):
        words = _extract_words("hello! world? test... foo-bar")
        assert "hello" in words
        assert "world" in words

    def test_removes_short_words(self):
        words = _extract_words("I a x cat dog")
        assert "cat" in words
        assert "dog" in words

    def test_empty_string(self):
        words = _extract_words("")
        assert words == set()

    def test_only_stop_words(self):
        words = _extract_words("the a an is was")
        assert len(words) == 0


class TestJaccardSimilarity:
    """Tests for Jaccard similarity computation."""

    def test_identical_sets(self):
        assert _jaccard_similarity({"a", "b", "c"}, {"a", "b", "c"}) == 1.0

    def test_disjoint_sets(self):
        assert _jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        sim = _jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
        assert sim == pytest.approx(2.0 / 4.0)  # 2 intersection / 4 union

    def test_empty_sets(self):
        assert _jaccard_similarity(set(), set()) == 0.0
        assert _jaccard_similarity({"a"}, set()) == 0.0

    def test_subset(self):
        sim = _jaccard_similarity({"a", "b"}, {"a", "b", "c"})
        assert sim == pytest.approx(2.0 / 3.0)

    def test_real_script_comparison(self):
        """Test with realistic script-like content."""
        script_a = _extract_words("Did you know that the mansion in Resident Evil was inspired by a real building?")
        script_b = _extract_words("The mansion design in Resident Evil was based on a real world location")
        sim = _jaccard_similarity(script_a, script_b)
        assert 0.2 < sim < 0.8  # Similar but not identical

    def test_identical_scripts(self):
        script_a = _extract_words("The secret room contains a hidden weapon upgrade")
        script_b = _extract_words("The secret room contains a hidden weapon upgrade")
        assert _jaccard_similarity(script_a, script_b) == 1.0
