"""Image generation module — Google Flow → scene images.

Step 4b in the pipeline (runs in parallel with voice generation).
Generates images for each scene using approved assets as reference anchors.
"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.browser.google_flow import generate_image
from backend.db.database import get_db

logger = logging.getLogger(__name__)


@dataclass
class SceneImage:
    scene_number: int
    image_path: str
    shot_type: str
    characters_shown: list[str]
    environment: str


@dataclass
class ImageGenResult:
    scene_images: list[SceneImage]
    failed_scenes: list[int]


async def generate_scene_images(
    scenes: list[dict],
    franchise_id: str,
    franchise_config: dict,
    topic_id: str,
) -> ImageGenResult:
    """Generate images for each scene in the script.

    For each scene:
    1. Look up approved character/environment assets
    2. Build a prompt using character bibles (no real names)
    3. Upload reference images to Flow for consistency
    4. Generate and download the result
    """
    output_dir = Path(f"data/output/{franchise_id}/{topic_id}/images")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load approved assets from DB
    asset_map = await _load_approved_assets(franchise_id)

    scene_images: list[SceneImage] = []
    failed_scenes: list[int] = []

    for scene in scenes:
        scene_num = scene.get("scene_number", 0)
        shot_type = scene.get("shot_type", "narrator_alone")
        action_chars = scene.get("action_characters", [])
        environment = scene.get("environment", "")
        narrator_expression = scene.get("narrator_expression", "")

        # Build prompt (using character bibles, NOT real names)
        prompt = _build_image_prompt(
            shot_type=shot_type,
            action_chars=action_chars,
            environment=environment,
            narrator_expression=narrator_expression,
            franchise_config=franchise_config,
        )

        # Gather reference images from asset library
        ref_images = _gather_references(
            shot_type=shot_type,
            action_chars=action_chars,
            environment=environment,
            franchise_id=franchise_id,
            asset_map=asset_map,
        )

        # Generate
        try:
            image_paths = await generate_image(
                prompt=prompt,
                reference_images=ref_images,
                output_dir=str(output_dir),
                timeout=120000,
            )

            if image_paths:
                chars_shown = [c.get("archetype_id", "") for c in action_chars]
                scene_images.append(SceneImage(
                    scene_number=scene_num,
                    image_path=image_paths[0],
                    shot_type=shot_type,
                    characters_shown=chars_shown,
                    environment=environment,
                ))
                logger.info("Generated image for scene %d", scene_num)
            else:
                failed_scenes.append(scene_num)
                logger.warning("No images generated for scene %d", scene_num)

        except Exception as e:
            failed_scenes.append(scene_num)
            logger.error("Image generation failed for scene %d: %s", scene_num, e)

    return ImageGenResult(scene_images=scene_images, failed_scenes=failed_scenes)


async def _load_approved_assets(franchise_id: str) -> dict[str, dict]:
    """Load approved assets from the database for a franchise."""
    asset_map: dict[str, dict] = {}
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, asset_type, archetype_id, model_dir, metadata_json FROM assets WHERE franchise_id = ? AND status = 'approved'",
            (franchise_id,),
        )
        rows = await cursor.fetchall()
        for row in rows:
            key = row["archetype_id"] or row["id"]
            asset_map[key] = dict(row)
    finally:
        await db.close()
    return asset_map


def _build_image_prompt(
    shot_type: str,
    action_chars: list[dict],
    environment: str,
    narrator_expression: str,
    franchise_config: dict,
) -> str:
    """Build an image generation prompt from scene data.

    Uses character bibles (abstract descriptions) — NEVER real character names.
    """
    archetypes = {
        a.get("archetype_id", ""): a
        for a in franchise_config.get("character_archetypes", [])
    }
    env_data = {
        e.get("env_id", ""): e
        for e in franchise_config.get("environments", [])
    }

    parts = []

    # Visual style from franchise
    style = franchise_config.get("visual_style", {})
    aesthetic = style.get("aesthetic", "cinematic, detailed")
    style_suffix = style.get("prompt_suffix", "")
    parts.append(f"Style: {aesthetic}. {style_suffix}")

    # Shot type framing
    if shot_type == "narrator_with_characters":
        parts.append("Scene composition: main character facing camera in foreground, other characters visible behind.")
        if narrator_expression:
            parts.append(f"Main character expression: {narrator_expression}")
    elif shot_type == "narrator_alone":
        parts.append("Close-up portrait, character facing camera directly.")
        if narrator_expression:
            parts.append(f"Expression: {narrator_expression}")
    elif shot_type == "characters_only":
        parts.append("Action scene, characters performing actions.")

    # Characters (using bible descriptions)
    for char in action_chars:
        arch_id = char.get("archetype_id", "")
        action = char.get("action", "")
        arch_data = archetypes.get(arch_id, {})
        desc = arch_data.get("visual_description", arch_data.get("description", ""))
        if desc:
            parts.append(f"Character: {desc}. Action: {action}")
        elif action:
            parts.append(f"Character performing: {action}")

    # Environment
    if environment:
        env_info = env_data.get(environment, {})
        env_desc = env_info.get("description", environment)
        parts.append(f"Setting: {env_desc}")

    parts.append("Vertical composition (9:16), cinematic lighting, high detail.")

    return " ".join(parts)


def _gather_references(
    shot_type: str,
    action_chars: list[dict],
    environment: str,
    franchise_id: str,
    asset_map: dict[str, dict],
) -> list[str]:
    """Gather reference image paths from the asset library."""
    refs: list[str] = []
    library_base = Path(f"data/library/{franchise_id}")

    # Character reference images
    for char in action_chars:
        arch_id = char.get("archetype_id", "")
        if arch_id in asset_map:
            model_dir = asset_map[arch_id].get("model_dir", "")
            if model_dir and Path(model_dir).exists():
                refs.append(model_dir)
        else:
            # Try standard library paths
            portrait = library_base / "characters" / arch_id / "portrait.png"
            full_body = library_base / "characters" / arch_id / "full_body.png"
            if portrait.exists():
                refs.append(str(portrait))
            elif full_body.exists():
                refs.append(str(full_body))

    # Environment reference
    if environment:
        env_path = library_base / "environments" / environment / "wide_shot.png"
        if env_path.exists():
            refs.append(str(env_path))

    return refs[:4]  # Kling Elements supports up to 4 reference images
