"""Script generation module — Gemini → JSON parse → validation.

Step 2 in the pipeline. Takes a topic from the queue, builds a prompt
from the 3-layer template (system + franchise + topic), sends it to
Gemini, parses the JSON script, and validates structure.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.browser.gemini import send_prompt, parse_json_response
from backend.config.config_loader import get_config

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE_PATH = Path("data/prompts/script_system.txt")

# Validation constants
MIN_WORDS = 100
MAX_WORDS = 155
MIN_SCENES = 3
MAX_SCENES = 8
MAX_DURATION = 60
VALID_SHOT_TYPES = {"narrator_with_characters", "narrator_alone", "characters_only"}
VALID_CLOSER_STYLES = {"style_cta", "style_teaser", "style_punchline", "style_question", "style_reveal"}


@dataclass
class ScriptScene:
    scene_number: int
    dialogue: str
    shot_type: str
    narrator_expression: Optional[str] = None
    action_characters: list[dict] = field(default_factory=list)
    environment: str = ""
    duration_seconds: float = 0


@dataclass
class GeneratedScript:
    title: str
    description: str
    tags: list[str]
    total_word_count: int
    estimated_duration_seconds: float
    closer_style: str
    scenes: list[ScriptScene]
    long_form_potential: dict = field(default_factory=dict)
    cross_platform: dict = field(default_factory=dict)
    raw_json: dict = field(default_factory=dict)

    @property
    def full_dialogue(self) -> str:
        return " ".join(s.dialogue for s in self.scenes)


@dataclass
class ScriptValidation:
    valid: bool
    errors: list[str]
    warnings: list[str]


async def generate_script(
    topic: dict,
    franchise_config: dict,
    narrator_archetype: str,
    closer_style: str = "style_punchline",
) -> tuple[Optional[GeneratedScript], ScriptValidation]:
    """Generate a script for a topic using Gemini.

    Returns (script, validation). Script is None if generation failed.
    """
    # Build the prompt
    prompt = _build_prompt(topic, franchise_config, narrator_archetype, closer_style)

    # Send to Gemini
    logger.info("Generating script for: %s", topic.get("title", "unknown"))
    raw_response = await send_prompt(prompt)

    if not raw_response:
        return None, ScriptValidation(
            valid=False, errors=["Empty response from Gemini"], warnings=[]
        )

    # Parse JSON
    parsed = parse_json_response(raw_response)
    if not parsed:
        return None, ScriptValidation(
            valid=False, errors=["Failed to parse JSON from Gemini response"], warnings=[]
        )

    # Convert to structured script
    script = _parse_script(parsed)
    if not script:
        return None, ScriptValidation(
            valid=False, errors=["Failed to parse script structure"], warnings=[]
        )

    # Validate
    validation = validate_script(script)
    return script, validation


def _build_prompt(
    topic: dict,
    franchise_config: dict,
    narrator_archetype: str,
    closer_style: str,
) -> str:
    """Build the 3-layer prompt from the template."""
    # Load template
    if PROMPT_TEMPLATE_PATH.exists():
        template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    else:
        template = _fallback_template()

    # Extract franchise context
    franchise_name = franchise_config.get("name", "Unknown")
    category = franchise_config.get("category", "gaming")

    archetypes = franchise_config.get("character_archetypes", [])
    narrator_data = {}
    for arch in archetypes:
        if arch.get("archetype_id") == narrator_archetype or arch.get("name", "").lower() == narrator_archetype.lower():
            narrator_data = arch
            break

    environments = franchise_config.get("environments", [])

    # Build character list
    char_lines = []
    for arch in archetypes:
        aid = arch.get("archetype_id", arch.get("name", ""))
        desc = arch.get("visual_description", arch.get("description", ""))
        char_lines.append(f"- Archetype ID: {aid}\n  Description: {desc}")

    # Build environment list
    env_lines = []
    for env in environments:
        eid = env.get("env_id", env.get("name", ""))
        edesc = env.get("description", "")
        env_lines.append(f"- Environment ID: {eid}\n  Description: {edesc}")

    # Fill variables
    filled = template
    replacements = {
        "{franchise_name}": franchise_name,
        "{franchise_category}": category,
        "{franchise_aesthetic}": franchise_config.get("visual_style", {}).get("aesthetic", "cinematic"),
        "{narrator_archetype_id}": narrator_archetype,
        "{narrator_visual_description}": narrator_data.get("visual_description", ""),
        "{narrator_personality_tone}": narrator_data.get("personality_tone", "confident, knowledgeable"),
        "{narrator_speech_style}": narrator_data.get("speech_style", "casual, conversational"),
        "{narrator_example_line}": narrator_data.get("example_line", ""),
        "{narrator_refers_to_others}": narrator_data.get("refers_to_others", "Uses their names naturally"),
        "{topic_title}": topic.get("title", ""),
        "{topic_description}": topic.get("description", ""),
        "{topic_source_excerpts}": json.dumps(topic.get("sources", []), indent=2) if topic.get("sources") else "No source excerpts available",
        "{characters_needed}": ", ".join(topic.get("characters_needed", [])) or "Any available characters",
        "{closer_style}": closer_style,
    }

    for key, value in replacements.items():
        filled = filled.replace(key, str(value))

    # Replace template blocks
    filled = filled.replace("{for_each_archetype}", "")
    filled = filled.replace("{end_for_each}", "")
    filled = filled.replace("{for_each_environment}", "")

    # Insert character and environment data
    if char_lines:
        filled = filled.replace("- Archetype ID: {archetype_id}\n  Description: {visual_description}\n  Bible: {character_bible_summary}", "\n".join(char_lines))
    if env_lines:
        filled = filled.replace("- Environment ID: {env_id}\n  Description: {env_description}", "\n".join(env_lines))

    return filled


def _parse_script(data: dict) -> Optional[GeneratedScript]:
    """Parse the JSON response into a GeneratedScript."""
    try:
        scenes = []
        for scene_data in data.get("scenes", []):
            scenes.append(ScriptScene(
                scene_number=scene_data.get("scene_number", 0),
                dialogue=scene_data.get("dialogue", ""),
                shot_type=scene_data.get("shot_type", "narrator_alone"),
                narrator_expression=scene_data.get("narrator_expression"),
                action_characters=scene_data.get("action_characters", []),
                environment=scene_data.get("environment", ""),
                duration_seconds=scene_data.get("duration_seconds", 0),
            ))

        return GeneratedScript(
            title=data.get("title", ""),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            total_word_count=data.get("total_word_count", 0),
            estimated_duration_seconds=data.get("estimated_duration_seconds", 0),
            closer_style=data.get("closer_style", ""),
            scenes=scenes,
            long_form_potential=data.get("long_form_potential", {}),
            cross_platform=data.get("cross_platform", {}),
            raw_json=data,
        )
    except Exception as e:
        logger.error("Failed to parse script: %s", e)
        return None


def validate_script(script: GeneratedScript) -> ScriptValidation:
    """Validate a generated script against all rules."""
    errors: list[str] = []
    warnings: list[str] = []

    # Word count
    actual_words = len(script.full_dialogue.split())
    if actual_words < MIN_WORDS:
        errors.append(f"Too few words: {actual_words} (min {MIN_WORDS})")
    elif actual_words > MAX_WORDS:
        errors.append(f"Too many words: {actual_words} (max {MAX_WORDS})")

    # Scene count
    if len(script.scenes) < MIN_SCENES:
        errors.append(f"Too few scenes: {len(script.scenes)} (min {MIN_SCENES})")
    elif len(script.scenes) > MAX_SCENES:
        warnings.append(f"Many scenes: {len(script.scenes)} (max recommended {MAX_SCENES})")

    # Duration
    total_duration = sum(s.duration_seconds for s in script.scenes)
    if total_duration > MAX_DURATION:
        errors.append(f"Total duration {total_duration:.1f}s exceeds {MAX_DURATION}s limit")

    # First scene must be narrator_with_characters
    if script.scenes and script.scenes[0].shot_type != "narrator_with_characters":
        warnings.append(f"First scene should be narrator_with_characters, got {script.scenes[0].shot_type}")

    # Shot type validation
    for scene in script.scenes:
        if scene.shot_type not in VALID_SHOT_TYPES:
            errors.append(f"Scene {scene.scene_number}: invalid shot type '{scene.shot_type}'")

    # No 3+ consecutive same shot type
    for i in range(len(script.scenes) - 2):
        if (script.scenes[i].shot_type == script.scenes[i + 1].shot_type == script.scenes[i + 2].shot_type):
            warnings.append(
                f"Scenes {i + 1}-{i + 3}: 3 consecutive '{script.scenes[i].shot_type}' shots"
            )

    # Closer style
    if script.closer_style and script.closer_style not in VALID_CLOSER_STYLES:
        warnings.append(f"Unknown closer style: {script.closer_style}")

    # Title and description
    if not script.title:
        errors.append("Missing title")
    if not script.description:
        errors.append("Missing description")

    # Each scene must have dialogue
    for scene in script.scenes:
        if not scene.dialogue.strip():
            errors.append(f"Scene {scene.scene_number}: empty dialogue")

    return ScriptValidation(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def _fallback_template() -> str:
    """Minimal fallback template if the full one isn't available."""
    return """You are a script writer for YouTube Shorts (45-55 seconds).
Write a script where {narrator_archetype_id} narrates a fact about {franchise_name}.

Topic: {topic_title}
Details: {topic_description}
Closer style: {closer_style}

Output ONLY a JSON object with: title, description, tags, total_word_count,
estimated_duration_seconds, closer_style, scenes (each with scene_number,
dialogue, shot_type, narrator_expression, action_characters, environment,
duration_seconds), long_form_potential, cross_platform.

100-155 words total. 4-6 scenes. First scene: narrator_with_characters."""
