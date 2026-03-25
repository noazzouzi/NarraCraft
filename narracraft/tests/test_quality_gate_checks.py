"""Unit tests for quality gate check functions (synchronous only)."""

import pytest
from backend.services.pipeline.quality_gate import (
    _check_script_originality,
    _check_voiceover,
    _check_no_copyright,
    _check_advertiser_friendly,
    _check_metadata,
)


class TestScriptOriginality:
    """Tests for similarity threshold check."""

    def test_original_script_passes(self):
        result = _check_script_originality(0.30)
        assert result.passed is True
        assert result.name == "script_is_original"

    def test_similar_script_fails(self):
        result = _check_script_originality(0.85)
        assert result.passed is False
        assert "0.85" in result.message

    def test_exact_threshold_fails(self):
        """Score equal to threshold should fail (need < threshold)."""
        result = _check_script_originality(0.70)
        assert result.passed is False

    def test_zero_similarity_passes(self):
        result = _check_script_originality(0.0)
        assert result.passed is True


class TestVoiceover:
    """Tests for voiceover duration check."""

    def test_long_enough_passes(self):
        result = _check_voiceover(45.0)
        assert result.passed is True
        assert result.name == "voiceover_present"

    def test_too_short_fails(self):
        result = _check_voiceover(5.0)
        assert result.passed is False
        assert "too short" in result.message

    def test_exactly_ten_fails(self):
        """10s is not > 10, so it fails."""
        result = _check_voiceover(10.0)
        assert result.passed is False

    def test_just_over_ten_passes(self):
        result = _check_voiceover(10.1)
        assert result.passed is True

    def test_zero_duration_fails(self):
        result = _check_voiceover(0.0)
        assert result.passed is False


class TestNoCopyright:
    """Tests for copyright material check."""

    def test_always_passes_for_now(self):
        """Current implementation always passes (placeholder)."""
        result = _check_no_copyright({"scenes": []})
        assert result.passed is True
        assert result.name == "no_copyrighted_material"


class TestAdvertiserFriendly:
    """Tests for content safety check."""

    def test_clean_script_passes(self):
        script = {"scenes": [
            {"dialogue": "Did you know that the developers changed the design three times?"},
        ]}
        result = _check_advertiser_friendly(script)
        assert result.passed is True

    def test_violent_content_fails(self):
        script = {"scenes": [
            {"dialogue": "This scene contains graphic violence and blood everywhere"},
        ]}
        result = _check_advertiser_friendly(script)
        assert result.passed is False
        assert "violence" in result.message or "blood" in result.message

    def test_nsfw_fails(self):
        script = {"scenes": [{"dialogue": "This has nsfw explicit content"}]}
        result = _check_advertiser_friendly(script)
        assert result.passed is False

    def test_empty_script_passes(self):
        result = _check_advertiser_friendly({"scenes": []})
        assert result.passed is True

    def test_case_insensitive(self):
        script = {"scenes": [{"dialogue": "VIOLENCE and GORE"}]}
        result = _check_advertiser_friendly(script)
        assert result.passed is False


class TestMetadata:
    """Tests for metadata completeness check."""

    def test_complete_metadata_passes(self):
        script = {
            "title": "Did You Know?",
            "description": "A fascinating fact about RE",
            "tags": ["resident_evil", "gaming", "facts"],
        }
        result = _check_metadata(script)
        assert result.passed is True
        assert result.name == "metadata_complete"

    def test_missing_title_fails(self):
        script = {"title": "", "description": "desc", "tags": ["tag"]}
        result = _check_metadata(script)
        assert result.passed is False
        assert "title" in result.message

    def test_missing_description_fails(self):
        script = {"title": "Title", "description": "", "tags": ["tag"]}
        result = _check_metadata(script)
        assert result.passed is False
        assert "description" in result.message

    def test_missing_tags_fails(self):
        script = {"title": "Title", "description": "desc", "tags": []}
        result = _check_metadata(script)
        assert result.passed is False
        assert "tags" in result.message

    def test_all_missing_fails(self):
        result = _check_metadata({})
        assert result.passed is False
        # Should list all missing items
        assert "title" in result.message
        assert "description" in result.message
        assert "tags" in result.message
