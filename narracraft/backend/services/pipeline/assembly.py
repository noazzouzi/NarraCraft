"""Assembly module — VectCutAPI → CapCut project.

Step 6 in the pipeline. Takes video clips, audio, and metadata →
sends to VectCutAPI to create a CapCut project or render directly.
"""

import json
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from backend.config.config_loader import get_config
from backend.db.database import get_db

logger = logging.getLogger(__name__)


@dataclass
class AssemblyResult:
    video_path: str
    project_path: Optional[str] = None
    duration_seconds: float = 0
    render_mode: str = "cloud"


async def assemble_video(
    clips: list[dict],
    voice_segments: list[dict],
    script: dict,
    franchise_id: str,
    franchise_config: dict,
    topic_id: str,
) -> Optional[AssemblyResult]:
    """Assemble final video from clips, audio, and metadata via VectCutAPI."""
    config = get_config()
    assembly_config = config.get("channel", {}).get("assembly", {}).get("vectcutapi", {})
    audio_config = config.get("channel", {}).get("audio", {})

    server_url = assembly_config.get("server_url", "http://localhost:9001")
    render_mode = assembly_config.get("render_mode", "cloud")
    project_settings = assembly_config.get("project_settings", {
        "width": 1080, "height": 1920, "fps": 30,
    })

    output_dir = Path(f"data/output/{franchise_id}/{topic_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Select background music
    music_path = await _select_music(franchise_config, audio_config)

    # Select SFX
    sfx_placements = _plan_sfx(script, audio_config)

    # Build the VectCutAPI project payload
    payload = {
        "project_settings": project_settings,
        "render_mode": render_mode,
        "tracks": [],
    }

    # Video track — ordered clips
    video_track = {
        "type": "video",
        "clips": [],
    }
    current_time = 0
    for clip in sorted(clips, key=lambda c: c.get("scene_number", 0)):
        duration = clip.get("duration_seconds", 5)
        video_track["clips"].append({
            "file_path": clip.get("video_path", ""),
            "start_time": current_time,
            "duration": duration,
            "transition": random.choice(
                assembly_config.get("effects", {}).get("transition_presets", ["fade_in"])
            ),
            "keyframes": _get_keyframe_preset(assembly_config),
        })
        current_time += duration
    payload["tracks"].append(video_track)

    # Audio track — voice segments
    audio_track = {
        "type": "audio",
        "label": "voiceover",
        "clips": [],
    }
    vo_time = 0
    for seg in sorted(voice_segments, key=lambda s: s.get("scene_number", 0)):
        duration = seg.get("duration_seconds", 5)
        audio_track["clips"].append({
            "file_path": seg.get("audio_path", ""),
            "start_time": vo_time,
            "duration": duration,
            "volume": 1.0,
        })
        vo_time += duration
    payload["tracks"].append(audio_track)

    # Background music track
    if music_path:
        music_config = audio_config.get("background_music", {})
        payload["tracks"].append({
            "type": "audio",
            "label": "music",
            "clips": [{
                "file_path": music_path,
                "start_time": 0,
                "duration": current_time,
                "volume": music_config.get("volume", 0.08),
                "fade_in": music_config.get("fade_in_seconds", 1.0),
                "fade_out": music_config.get("fade_out_seconds", 2.0),
            }],
        })

    # SFX track
    if sfx_placements:
        sfx_track = {
            "type": "audio",
            "label": "sfx",
            "clips": sfx_placements,
        }
        payload["tracks"].append(sfx_track)

    # Captions track
    caption_config = config.get("channel", {}).get("visuals", {}).get("composition", {}).get("caption_style", {})
    if caption_config.get("enabled", True):
        caption_track = _build_caption_track(voice_segments, caption_config, franchise_config)
        if caption_track:
            payload["tracks"].append(caption_track)

    # Send to VectCutAPI
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{server_url}/api/render",
                json=payload,
            )
            resp.raise_for_status()
            result = resp.json()

            video_path = result.get("output_path", "")
            if not video_path:
                # Poll for completion
                job_id = result.get("job_id", "")
                if job_id:
                    video_path = await _poll_render(client, server_url, job_id)

            if video_path:
                # Copy to our output directory
                final_path = str(output_dir / "final_video.mp4")
                if Path(video_path).exists():
                    import shutil
                    shutil.copy2(video_path, final_path)
                    video_path = final_path

                return AssemblyResult(
                    video_path=video_path,
                    duration_seconds=current_time,
                    render_mode=render_mode,
                )

    except httpx.ConnectError:
        logger.error("VectCutAPI not reachable at %s", server_url)
    except Exception as e:
        logger.error("Assembly failed: %s", e)

    return None


async def _poll_render(client: httpx.AsyncClient, server_url: str, job_id: str) -> str:
    """Poll VectCutAPI for render job completion."""
    import asyncio

    for _ in range(60):  # Max 5 minutes
        await asyncio.sleep(5)
        try:
            resp = await client.get(f"{server_url}/api/render/{job_id}")
            data = resp.json()
            status = data.get("status", "")
            if status == "completed":
                return data.get("output_path", "")
            elif status == "failed":
                logger.error("Render job failed: %s", data.get("error", ""))
                return ""
        except Exception:
            continue
    return ""


async def _select_music(franchise_config: dict, audio_config: dict) -> Optional[str]:
    """Select a background music track from the library."""
    music_config = audio_config.get("background_music", {})
    if not music_config.get("enabled", True):
        return None

    library_path = Path(music_config.get("library_path", "data/audio/music"))
    mood = franchise_config.get("audio_profile", {}).get("music_mood", "neutral_curious")
    mood_dir = library_path / mood

    if not mood_dir.exists():
        # Fallback to any music
        mood_dir = library_path
        if not mood_dir.exists():
            return None

    # Get all available tracks
    tracks = list(mood_dir.glob("*.mp3")) + list(mood_dir.glob("*.wav"))
    if not tracks:
        return None

    # Exclude recently used tracks
    lookback = music_config.get("dedup_lookback", 10)
    recent_tracks = await _get_recent_tracks(lookback)
    eligible = [t for t in tracks if str(t) not in recent_tracks]

    if not eligible:
        eligible = tracks  # All used recently, allow repeats

    return str(random.choice(eligible))


async def _get_recent_tracks(lookback: int) -> set[str]:
    """Get recently used music track paths."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT track_path FROM audio_usage WHERE track_type = 'music' ORDER BY used_at DESC LIMIT ?",
            (lookback,),
        )
        rows = await cursor.fetchall()
        return {row["track_path"] for row in rows}
    finally:
        await db.close()


def _plan_sfx(script: dict, audio_config: dict) -> list[dict]:
    """Plan SFX placements based on scene structure."""
    sfx_config = audio_config.get("sound_effects", {})
    if not sfx_config.get("enabled", True):
        return []

    library_path = Path(sfx_config.get("library_path", "data/audio/sfx"))
    placements: list[dict] = []
    scenes = script.get("scenes", [])

    for i, scene in enumerate(scenes):
        scene_start = sum(s.get("duration_seconds", 5) for s in scenes[:i])

        # Hook SFX
        if i == 0:
            sfx = _pick_sfx(library_path / "impacts")
            if sfx:
                placements.append({
                    "file_path": sfx,
                    "start_time": scene_start,
                    "duration": 1.0,
                    "volume": 0.3,
                })

        # Transition SFX between scenes
        if i > 0:
            sfx = _pick_sfx(library_path / "transitions")
            if sfx:
                placements.append({
                    "file_path": sfx,
                    "start_time": scene_start - 0.3,
                    "duration": 0.8,
                    "volume": 0.2,
                })

    return placements


def _pick_sfx(sfx_dir: Path) -> Optional[str]:
    """Pick a random SFX from a directory."""
    if not sfx_dir.exists():
        return None
    files = list(sfx_dir.glob("*.mp3")) + list(sfx_dir.glob("*.wav"))
    return str(random.choice(files)) if files else None


def _get_keyframe_preset(assembly_config: dict) -> Optional[dict]:
    """Get a random keyframe animation preset."""
    presets = assembly_config.get("effects", {}).get("keyframe_presets", [])
    if not presets:
        return None
    return random.choice(presets)


def _build_caption_track(
    voice_segments: list[dict],
    caption_config: dict,
    franchise_config: dict,
) -> Optional[dict]:
    """Build a caption/subtitle track from voice segments."""
    mood = franchise_config.get("audio_profile", {}).get("music_mood", "")
    presets = caption_config.get("presets", {})
    style = presets.get(mood, caption_config.get("default", {}))

    clips = []
    current_time = 0
    for seg in sorted(voice_segments, key=lambda s: s.get("scene_number", 0)):
        duration = seg.get("duration_seconds", 5)
        # Word timestamps if available
        word_ts = seg.get("word_timestamps", [])

        clips.append({
            "type": "caption",
            "start_time": current_time,
            "duration": duration,
            "text": "",  # Filled from word timestamps or dialogue
            "word_timestamps": word_ts,
            "style": style,
        })
        current_time += duration

    if not clips:
        return None

    return {
        "type": "caption",
        "label": "captions",
        "clips": clips,
    }
