"""Video generation module — Kling AI image-to-video.

Step 5 in the pipeline. Takes generated scene images + voice segments
and creates animated video clips.
- Narrator scenes: lip sync (image + audio)
- Action scenes: motion only (no audio)
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from backend.browser.kling import generate_video
from backend.config.config_loader import get_config

logger = logging.getLogger(__name__)

# Motion prompts for different scene types
MOTION_PRESETS = {
    "narrator_with_characters": "subtle head movement, natural expression shift, slight body sway, characters in background with gentle motion",
    "narrator_alone": "subtle head turn, natural blinking, slight expression change, gentle breathing motion",
    "characters_only": "character performing action, dynamic movement, cinematic camera pan",
}


@dataclass
class VideoClip:
    scene_number: int
    video_path: str
    shot_type: str
    duration_seconds: float
    has_lip_sync: bool


@dataclass
class VideoGenResult:
    clips: list[VideoClip]
    failed_scenes: list[int]
    total_credits_used: int


async def generate_video_clips(
    scene_images: list[dict],
    voice_segments: list[dict],
    franchise_id: str,
    topic_id: str,
) -> VideoGenResult:
    """Generate animated video clips from scene images.

    For narrator scenes (narrator_alone, narrator_with_characters):
        Uses lip sync mode — uploads image + audio segment → Kling generates video
        where the character's mouth moves with the audio.

    For action scenes (characters_only):
        Uses motion mode — uploads image + motion prompt → Kling generates video
        with character movement. Voice-over is added later in assembly.
    """
    config = get_config()
    vis_config = config.get("channel", {}).get("visuals", {}).get("asset_library", {}).get("image_to_video", {})
    mode = vis_config.get("mode", "standard")
    clip_duration = vis_config.get("clip_duration_seconds", 5)
    max_clips = vis_config.get("max_clips_per_video", 6)

    output_dir = Path(f"data/output/{franchise_id}/{topic_id}/clips")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build voice segment lookup
    voice_map: dict[int, dict] = {}
    for vs in voice_segments:
        voice_map[vs.get("scene_number", 0)] = vs

    clips: list[VideoClip] = []
    failed_scenes: list[int] = []
    credits_used = 0
    credits_per_clip = 10 if mode == "standard" else 35

    for img_data in scene_images[:max_clips]:
        scene_num = img_data.get("scene_number", 0)
        image_path = img_data.get("image_path", "")
        shot_type = img_data.get("shot_type", "narrator_alone")

        if not image_path or not Path(image_path).exists():
            failed_scenes.append(scene_num)
            continue

        # Determine if this is a lip sync scene
        is_narrator = shot_type in ("narrator_alone", "narrator_with_characters")
        voice_seg = voice_map.get(scene_num)
        audio_path = voice_seg.get("audio_path", "") if voice_seg else None

        # Build motion prompt
        motion_prompt = MOTION_PRESETS.get(shot_type, "subtle natural movement")
        preferred_motions = vis_config.get("preferred_motions", [])
        if preferred_motions:
            motion_prompt += f", {', '.join(preferred_motions[:2])}"

        try:
            video_path = await generate_video(
                image_path=image_path,
                prompt=motion_prompt,
                audio_path=audio_path if is_narrator else None,
                mode=mode,
                duration=clip_duration,
                output_dir=str(output_dir),
            )

            if video_path:
                clips.append(VideoClip(
                    scene_number=scene_num,
                    video_path=video_path,
                    shot_type=shot_type,
                    duration_seconds=clip_duration,
                    has_lip_sync=is_narrator and audio_path is not None,
                ))
                credits_used += credits_per_clip
                logger.info(
                    "Generated video clip for scene %d (%s, lip_sync=%s)",
                    scene_num, shot_type, is_narrator,
                )
            else:
                failed_scenes.append(scene_num)

        except Exception as e:
            failed_scenes.append(scene_num)
            logger.error("Video generation failed for scene %d: %s", scene_num, e)

    return VideoGenResult(
        clips=clips,
        failed_scenes=failed_scenes,
        total_credits_used=credits_used,
    )
