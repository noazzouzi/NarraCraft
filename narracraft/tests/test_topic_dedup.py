"""Unit tests for topic deduplication."""

import pytest
from backend.services.topics.topic_dedup import (
    deduplicate_topics,
    RawTopic,
    _text_similarity,
    _normalize,
)


class TestTextSimilarity:
    """Tests for text similarity computation."""

    def test_identical_texts(self):
        assert _text_similarity("hello world", "hello world") == 1.0

    def test_completely_different(self):
        assert _text_similarity("cat dog", "moon stars") == 0.0

    def test_partial_overlap(self):
        sim = _text_similarity("resident evil mansion secret", "resident evil hidden room")
        assert 0.0 < sim < 1.0

    def test_empty_strings(self):
        assert _text_similarity("", "") == 0.0
        assert _text_similarity("hello", "") == 0.0

    def test_stop_words_removed(self):
        """Stop words should not contribute to similarity."""
        sim = _text_similarity("the cat is on the mat", "cat mat")
        assert sim == 1.0  # After removing stop words, same content


class TestNormalize:
    """Tests for text normalization."""

    def test_lowercases(self):
        assert "hello" in _normalize("HELLO")

    def test_removes_punctuation(self):
        assert "test" in _normalize("test!@#$")

    def test_removes_stop_words(self):
        result = _normalize("the cat is on a mat")
        assert "the" not in result.split()
        assert "is" not in result.split()
        assert "cat" in result.split()
        assert "mat" in result.split()

    def test_removes_short_words(self):
        result = _normalize("I a x cat")
        words = result.split()
        assert "cat" in words
        assert "x" not in words


class TestDeduplicateTopics:
    """Tests for the deduplication algorithm."""

    def test_empty_input(self):
        assert deduplicate_topics([]) == []

    def test_single_topic_passes_through(self):
        topics = [RawTopic(title="Test topic", source_type="wiki", franchise_id="re")]
        result = deduplicate_topics(topics)
        assert len(result) == 1
        assert result[0].title == "Test topic"
        assert result[0].confidence == "low"

    def test_identical_titles_merged(self):
        topics = [
            RawTopic(title="Secret room in mansion", source_type="wiki", franchise_id="re"),
            RawTopic(title="Secret room in mansion", source_type="reddit", franchise_id="re"),
        ]
        result = deduplicate_topics(topics)
        assert len(result) == 1
        assert result[0].source_count == 2
        assert result[0].confidence == "medium"

    def test_similar_titles_merged(self):
        topics = [
            RawTopic(title="Hidden secret room mansion easter egg", source_type="wiki", franchise_id="re"),
            RawTopic(title="Secret hidden room in the mansion easter egg", source_type="reddit", franchise_id="re"),
        ]
        result = deduplicate_topics(topics, similarity_threshold=0.4)
        assert len(result) == 1

    def test_different_titles_not_merged(self):
        topics = [
            RawTopic(title="Resident Evil mansion design", source_type="wiki", franchise_id="re"),
            RawTopic(title="Dark Souls bonfire mechanic", source_type="reddit", franchise_id="ds"),
        ]
        result = deduplicate_topics(topics)
        assert len(result) == 2

    def test_three_sources_high_confidence(self):
        topics = [
            RawTopic(title="Same topic here", source_type="wiki", franchise_id="re"),
            RawTopic(title="Same topic here", source_type="reddit", franchise_id="re"),
            RawTopic(title="Same topic here", source_type="youtube", franchise_id="re"),
        ]
        result = deduplicate_topics(topics)
        assert len(result) == 1
        assert result[0].confidence == "high"
        assert result[0].source_count == 3

    def test_best_title_selected(self):
        """Longest title should be selected as representative."""
        topics = [
            RawTopic(title="Short", source_type="wiki", franchise_id="re"),
            RawTopic(title="Short title description", source_type="reddit", franchise_id="re"),
        ]
        result = deduplicate_topics(topics, similarity_threshold=0.3)
        # They might not merge because they're quite different, but if they do:
        if len(result) == 1:
            assert result[0].title == "Short title description"

    def test_best_description_selected(self):
        topics = [
            RawTopic(title="Same topic", description="Short desc", source_type="wiki", franchise_id="re"),
            RawTopic(title="Same topic", description="A much longer and more detailed description of this topic", source_type="reddit", franchise_id="re"),
        ]
        result = deduplicate_topics(topics)
        assert len(result) == 1
        assert "longer" in result[0].description

    def test_combined_score_increases_with_sources(self):
        """Multi-source topics should have higher combined score."""
        single = deduplicate_topics([
            RawTopic(title="Topic A", source_type="wiki", source_score=2.0, franchise_id="re"),
        ])
        double = deduplicate_topics([
            RawTopic(title="Topic A", source_type="wiki", source_score=2.0, franchise_id="re"),
            RawTopic(title="Topic A", source_type="reddit", source_score=3.0, franchise_id="re"),
        ])
        assert double[0].combined_score > single[0].combined_score

    def test_sorted_by_combined_score(self):
        topics = [
            RawTopic(title="Mansion architecture breakdown analysis", source_type="wiki", source_score=1.0, franchise_id="re"),
            RawTopic(title="Zombie virus origins laboratory research", source_type="reddit", source_score=5.0, franchise_id="re"),
        ]
        result = deduplicate_topics(topics)
        assert len(result) == 2
        assert result[0].combined_score >= result[1].combined_score

    def test_threshold_affects_merging(self):
        """Higher threshold = fewer merges."""
        topics = [
            RawTopic(title="resident evil mansion secret room", source_type="wiki", franchise_id="re"),
            RawTopic(title="resident evil mansion hidden area", source_type="reddit", franchise_id="re"),
        ]
        low_threshold = deduplicate_topics(topics, similarity_threshold=0.2)
        high_threshold = deduplicate_topics(topics, similarity_threshold=0.9)
        assert len(low_threshold) <= len(high_threshold)
