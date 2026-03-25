"""Unit tests for script validation logic."""

import pytest
from backend.services.pipeline.script_gen import (
    validate_script,
    GeneratedScript,
    ScriptScene,
    _parse_script,
    MIN_WORDS, MAX_WORDS, MIN_SCENES, MAX_SCENES,
    VALID_SHOT_TYPES, VALID_CLOSER_STYLES,
)


def _make_scene(num: int, dialogue: str = "Test dialogue words here", shot_type: str = "narrator_alone") -> ScriptScene:
    return ScriptScene(
        scene_number=num,
        dialogue=dialogue,
        shot_type=shot_type,
        duration_seconds=8.0,
    )


def _make_script(
    word_count: int = 120,
    scene_count: int = 5,
    first_shot: str = "narrator_with_characters",
    closer_style: str = "style_punchline",
) -> GeneratedScript:
    """Create a valid script with specified parameters."""
    words_per_scene = word_count // scene_count
    scenes = []
    for i in range(scene_count):
        shot = first_shot if i == 0 else "narrator_alone"
        dialogue = " ".join([f"word{j}" for j in range(words_per_scene)])
        scenes.append(_make_scene(i + 1, dialogue, shot))

    return GeneratedScript(
        title="Test Title",
        description="Test description",
        tags=["test", "gaming"],
        total_word_count=word_count,
        estimated_duration_seconds=45.0,
        closer_style=closer_style,
        scenes=scenes,
    )


class TestValidateScript:
    """Tests for script validation rules."""

    def test_valid_script_passes(self):
        script = _make_script()
        result = validate_script(script)
        assert result.valid is True
        assert result.errors == []

    def test_too_few_words_fails(self):
        script = _make_script(word_count=50)
        result = validate_script(script)
        assert result.valid is False
        assert any("Too few words" in e for e in result.errors)

    def test_too_many_words_fails(self):
        script = _make_script(word_count=200)
        result = validate_script(script)
        assert result.valid is False
        assert any("Too many words" in e for e in result.errors)

    def test_too_few_scenes_fails(self):
        script = _make_script(scene_count=2, word_count=120)
        result = validate_script(script)
        assert result.valid is False
        assert any("Too few scenes" in e for e in result.errors)

    def test_too_many_scenes_warning(self):
        script = _make_script(scene_count=10, word_count=120)
        result = validate_script(script)
        assert any("Many scenes" in w for w in result.warnings)

    def test_invalid_shot_type_fails(self):
        script = _make_script()
        script.scenes[1].shot_type = "invalid_type"
        result = validate_script(script)
        assert result.valid is False
        assert any("invalid shot type" in e for e in result.errors)

    def test_first_scene_shot_type_warning(self):
        script = _make_script(first_shot="narrator_alone")
        result = validate_script(script)
        assert any("First scene should be" in w for w in result.warnings)

    def test_three_consecutive_same_shots_warning(self):
        script = _make_script(scene_count=5)
        for i in range(3):
            script.scenes[i].shot_type = "narrator_alone"
        result = validate_script(script)
        assert any("consecutive" in w for w in result.warnings)

    def test_missing_title_fails(self):
        script = _make_script()
        script.title = ""
        result = validate_script(script)
        assert result.valid is False
        assert any("Missing title" in e for e in result.errors)

    def test_missing_description_fails(self):
        script = _make_script()
        script.description = ""
        result = validate_script(script)
        assert result.valid is False
        assert any("Missing description" in e for e in result.errors)

    def test_empty_dialogue_fails(self):
        script = _make_script()
        script.scenes[2].dialogue = ""
        result = validate_script(script)
        assert result.valid is False
        assert any("empty dialogue" in e for e in result.errors)

    def test_duration_over_60s_fails(self):
        script = _make_script()
        for scene in script.scenes:
            scene.duration_seconds = 15.0  # 5 * 15 = 75s
        result = validate_script(script)
        assert result.valid is False
        assert any("duration" in e.lower() for e in result.errors)

    def test_unknown_closer_style_warning(self):
        script = _make_script(closer_style="style_unknown")
        result = validate_script(script)
        assert any("closer style" in w.lower() for w in result.warnings)

    def test_valid_closer_styles(self):
        for style in VALID_CLOSER_STYLES:
            script = _make_script(closer_style=style)
            result = validate_script(script)
            assert not any("closer style" in w.lower() for w in result.warnings)


class TestParseScript:
    """Tests for JSON → GeneratedScript parsing."""

    def test_valid_json_parses(self):
        data = {
            "title": "Test",
            "description": "Desc",
            "tags": ["tag1"],
            "total_word_count": 120,
            "estimated_duration_seconds": 45,
            "closer_style": "style_cta",
            "scenes": [
                {"scene_number": 1, "dialogue": "Hello", "shot_type": "narrator_alone", "duration_seconds": 8},
                {"scene_number": 2, "dialogue": "World", "shot_type": "characters_only", "duration_seconds": 8},
                {"scene_number": 3, "dialogue": "End", "shot_type": "narrator_alone", "duration_seconds": 8},
            ],
        }
        result = _parse_script(data)
        assert result is not None
        assert result.title == "Test"
        assert len(result.scenes) == 3

    def test_empty_scenes(self):
        data = {"title": "Test", "description": "D", "tags": [], "scenes": []}
        result = _parse_script(data)
        assert result is not None
        assert len(result.scenes) == 0

    def test_full_dialogue_property(self):
        data = {
            "title": "T", "description": "D", "tags": [],
            "scenes": [
                {"scene_number": 1, "dialogue": "Hello"},
                {"scene_number": 2, "dialogue": "World"},
            ],
        }
        result = _parse_script(data)
        assert result.full_dialogue == "Hello World"
