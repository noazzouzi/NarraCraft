"""Voice generation module — Chatterbox (local) or ElevenLabs (browser).

Step 4a in the pipeline (runs in parallel with image generation).
Generates full voiceover from script dialogue, then splits into per-scene segments.
"""

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx

from backend.config.config_loader import get_config

logger = logging.getLogger(__name__)


@dataclass
class VoiceSegment:
    scene_number: int
    audio_path: str
    duration_seconds: float
    word_timestamps: list[dict] = field(default_factory=list)
    # Each timestamp: {"word": "hello", "start": 0.5, "end": 0.8}


@dataclass
class VoiceResult:
    full_audio_path: str
    segments: list[VoiceSegment]
    provider: str
    total_duration_seconds: float


async def generate_voice(
    scenes: list[dict],
    narrator_config: dict,
    franchise_id: str,
    topic_id: str,
) -> Optional[VoiceResult]:
    """Generate voiceover for all scenes.

    Chooses provider based on settings (chatterbox or elevenlabs).
    """
    config = get_config()
    provider = config.get("channel", {}).get("voice", {}).get("active_provider", "chatterbox")

    output_dir = Path(f"data/output/{franchise_id}/{topic_id}/audio")
    output_dir.mkdir(parents=True, exist_ok=True)

    if provider == "chatterbox":
        return await _generate_chatterbox(scenes, narrator_config, output_dir)
    elif provider == "elevenlabs":
        return await _generate_elevenlabs(scenes, narrator_config, output_dir)
    else:
        logger.error("Unknown voice provider: %s", provider)
        return None


async def _generate_chatterbox(
    scenes: list[dict],
    narrator_config: dict,
    output_dir: Path,
) -> Optional[VoiceResult]:
    """Generate voice using local Chatterbox TTS service.

    Chatterbox runs as a Docker service with a REST API.
    """
    config = get_config()
    chatterbox_config = config.get("channel", {}).get("voice", {}).get("chatterbox", {})

    # Reference audio for voice cloning
    ref_audio = narrator_config.get("voice_reference_path", "")
    if not ref_audio or not Path(ref_audio).exists():
        logger.warning("No voice reference audio found for narrator")

    segments: list[VoiceSegment] = []
    all_audio_paths: list[str] = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        for scene in scenes:
            scene_num = scene.get("scene_number", 0)
            dialogue = scene.get("dialogue", "")
            if not dialogue:
                continue

            ts = int(time.time())
            out_path = str(output_dir / f"scene_{scene_num}_{ts}.wav")

            try:
                # Call Chatterbox TTS API
                # Expected endpoint: POST /tts
                data = {
                    "text": dialogue,
                    "reference_audio": ref_audio,
                    "exaggeration": narrator_config.get("chatterbox_exaggeration", 0.5),
                    "cfg_weight": narrator_config.get("chatterbox_cfg_weight", 0.5),
                }

                resp = await client.post(
                    "http://localhost:8001/tts",
                    json=data,
                    timeout=60.0,
                )

                if resp.status_code == 200:
                    Path(out_path).write_bytes(resp.content)
                    duration = _get_audio_duration(out_path)

                    segments.append(VoiceSegment(
                        scene_number=scene_num,
                        audio_path=out_path,
                        duration_seconds=duration,
                    ))
                    all_audio_paths.append(out_path)
                    logger.info("Generated voice for scene %d: %.1fs", scene_num, duration)
                else:
                    logger.error("Chatterbox TTS failed for scene %d: %s", scene_num, resp.status_code)

            except Exception as e:
                logger.error("Chatterbox TTS error for scene %d: %s", scene_num, e)

    if not segments:
        return None

    # Concatenate all segments into a full audio file
    full_path = str(output_dir / "full_voiceover.wav")
    _concatenate_audio(all_audio_paths, full_path)
    total_duration = sum(s.duration_seconds for s in segments)

    return VoiceResult(
        full_audio_path=full_path,
        segments=segments,
        provider="chatterbox",
        total_duration_seconds=total_duration,
    )


async def _generate_elevenlabs(
    scenes: list[dict],
    narrator_config: dict,
    output_dir: Path,
) -> Optional[VoiceResult]:
    """Generate voice using ElevenLabs browser automation."""
    from backend.browser.elevenlabs import generate_speech

    voice_name = narrator_config.get("elevenlabs_voice_name", "")

    segments: list[VoiceSegment] = []
    all_audio_paths: list[str] = []

    for scene in scenes:
        scene_num = scene.get("scene_number", 0)
        dialogue = scene.get("dialogue", "")
        if not dialogue:
            continue

        audio_path = await generate_speech(
            text=dialogue,
            voice_name=voice_name or None,
            output_dir=str(output_dir),
        )

        if audio_path:
            duration = _get_audio_duration(audio_path)
            segments.append(VoiceSegment(
                scene_number=scene_num,
                audio_path=audio_path,
                duration_seconds=duration,
            ))
            all_audio_paths.append(audio_path)
            logger.info("Generated voice for scene %d via ElevenLabs: %.1fs", scene_num, duration)
        else:
            logger.error("ElevenLabs generation failed for scene %d", scene_num)

    if not segments:
        return None

    # Concatenate
    full_path = str(output_dir / "full_voiceover.wav")
    _concatenate_audio(all_audio_paths, full_path)
    total_duration = sum(s.duration_seconds for s in segments)

    return VoiceResult(
        full_audio_path=full_path,
        segments=segments,
        provider="elevenlabs",
        total_duration_seconds=total_duration,
    )


def _get_audio_duration(path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        # Estimate from file size (WAV: ~96KB/s at 24kHz 16bit mono)
        try:
            size = Path(path).stat().st_size
            return size / 96000
        except Exception:
            return 0.0


def _concatenate_audio(paths: list[str], output: str) -> None:
    """Concatenate audio files using ffmpeg."""
    if not paths:
        return
    if len(paths) == 1:
        import shutil
        shutil.copy2(paths[0], output)
        return

    # Create concat list file
    list_path = Path(output).parent / "concat_list.txt"
    with open(list_path, "w") as f:
        for p in paths:
            f.write(f"file '{Path(p).resolve()}'\n")

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", output],
            capture_output=True, timeout=30,
        )
    except Exception as e:
        logger.warning("ffmpeg concat failed: %s", e)
    finally:
        list_path.unlink(missing_ok=True)
