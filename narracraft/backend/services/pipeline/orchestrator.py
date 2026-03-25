"""Pipeline orchestrator — chains all modules, manages state, reports progress.

This is the main pipeline runner. It:
1. Pulls the next queued topic
2. Runs script generation (Gemini)
3. Runs compliance check
4. Runs voice + image generation IN PARALLEL
5. Runs video generation (sequential — needs both voice + images)
6. Runs assembly (VectCutAPI)
7. Runs quality gate (9-point checklist)
8. Publishes (YouTube + social platforms)

Progress is reported via callback for WebSocket broadcasting.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from backend.config.config_loader import get_config
from backend.db.database import get_db
from backend.services.pipeline.script_gen import generate_script, GeneratedScript
from backend.services.pipeline.compliance import check_compliance
from backend.services.pipeline.voice_gen import generate_voice
from backend.services.pipeline.image_gen import generate_scene_images
from backend.services.pipeline.video_gen import generate_video_clips
from backend.services.pipeline.assembly import assemble_video
from backend.services.pipeline.quality_gate import run_quality_gate
from backend.services.pipeline.publisher import publish_video

logger = logging.getLogger(__name__)

# Pipeline steps in order
STEPS = [
    "research",
    "script",
    "compliance",
    "voice_images",
    "animate",
    "assemble",
    "quality_gate",
    "publish",
]

STEP_LABELS = {
    "research": "Research — Pull topic from queue",
    "script": "Script — Generate with Gemini",
    "compliance": "Compliance — Similarity + content filter",
    "voice_images": "Voice + Images — Parallel generation",
    "animate": "Animate — Kling AI video clips",
    "assemble": "Assemble — VectCutAPI → CapCut",
    "quality_gate": "Quality Gate — 9-point checklist",
    "publish": "Publish — Upload to platforms",
}


@dataclass
class StepLog:
    step: str
    status: str  # running, completed, failed, skipped
    duration_seconds: float = 0
    message: str = ""
    error: Optional[str] = None


@dataclass
class PipelineState:
    run_id: int = 0
    topic_id: str = ""
    franchise_id: str = ""
    status: str = "idle"  # idle, running, completed, failed, aborted
    current_step: str = ""
    steps_log: list[StepLog] = field(default_factory=list)
    started_at: float = 0
    completed_at: float = 0
    error: Optional[str] = None
    aborted: bool = False


# Global pipeline state
_state = PipelineState()

# Progress callback type
ProgressCallback = Callable[[dict], None]


def get_state() -> PipelineState:
    """Get current pipeline state."""
    return _state


def is_running() -> bool:
    return _state.status == "running"


def request_abort() -> None:
    """Request pipeline abort (checked between steps)."""
    _state.aborted = True


async def run_pipeline(
    on_progress: Optional[ProgressCallback] = None,
) -> PipelineState:
    """Run the full pipeline for the next queued topic."""
    global _state

    if _state.status == "running":
        raise RuntimeError("Pipeline is already running")

    _state = PipelineState(status="running", started_at=time.time())
    config = get_config()
    retry_config = config.get("pipeline", {}).get("retry", {})
    max_retries = retry_config.get("max_retries_per_module", 3)

    def emit(data: dict) -> None:
        if on_progress:
            try:
                on_progress(data)
            except Exception:
                pass

    try:
        # Create a pipeline run record in DB
        db = await get_db()
        try:
            cursor = await db.execute(
                "INSERT INTO pipeline_runs (status, current_step, started_at) VALUES ('running', 'research', CURRENT_TIMESTAMP)"
            )
            _state.run_id = cursor.lastrowid
            await db.commit()
        finally:
            await db.close()

        # ─── STEP 1: RESEARCH ───
        await _run_step("research", emit, lambda: _step_research(emit))

        if _state.aborted:
            return await _finalize("aborted", "Pipeline aborted by user", emit)

        # ─── STEP 2: SCRIPT GENERATION ───
        script_result = await _run_step("script", emit, lambda: _step_script(emit))
        if not script_result:
            return await _finalize("failed", "Script generation failed", emit)

        if _state.aborted:
            return await _finalize("aborted", "Pipeline aborted by user", emit)

        # ─── STEP 3: COMPLIANCE ───
        compliance_ok = await _run_step("compliance", emit, lambda: _step_compliance(script_result, emit))
        if not compliance_ok:
            return await _finalize("failed", "Compliance check failed", emit)

        if _state.aborted:
            return await _finalize("aborted", "Pipeline aborted by user", emit)

        # ─── STEP 4: VOICE + IMAGES (PARALLEL) ───
        voice_result, image_result = await _run_step(
            "voice_images", emit, lambda: _step_voice_images(script_result, emit)
        )
        if not voice_result or not image_result:
            return await _finalize("failed", "Voice/Image generation failed", emit)

        if _state.aborted:
            return await _finalize("aborted", "Pipeline aborted by user", emit)

        # ─── STEP 5: ANIMATE (SEQUENTIAL) ───
        video_result = await _run_step(
            "animate", emit, lambda: _step_animate(image_result, voice_result, emit)
        )
        if not video_result:
            return await _finalize("failed", "Video generation failed", emit)

        if _state.aborted:
            return await _finalize("aborted", "Pipeline aborted by user", emit)

        # ─── STEP 6: ASSEMBLE ───
        assembly_result = await _run_step(
            "assemble", emit, lambda: _step_assemble(video_result, voice_result, script_result, emit)
        )
        if not assembly_result:
            return await _finalize("failed", "Assembly failed", emit)

        if _state.aborted:
            return await _finalize("aborted", "Pipeline aborted by user", emit)

        # ─── STEP 7: QUALITY GATE ───
        gate_result = await _run_step(
            "quality_gate", emit,
            lambda: _step_quality_gate(assembly_result, script_result, voice_result, emit)
        )
        if not gate_result:
            return await _finalize("failed", "Quality gate failed — video quarantined", emit)

        if _state.aborted:
            return await _finalize("aborted", "Pipeline aborted by user", emit)

        # ─── STEP 8: PUBLISH ───
        publish_result = await _run_step(
            "publish", emit, lambda: _step_publish(assembly_result, script_result, emit)
        )

        return await _finalize("completed", "Pipeline completed successfully", emit)

    except Exception as e:
        logger.exception("Pipeline crashed")
        return await _finalize("failed", str(e), emit)


async def _run_step(step: str, emit: Callable, fn: Callable):
    """Run a pipeline step with timing, state tracking, and retry logic."""
    config = get_config()
    retry_cfg = config.get("pipeline", {}).get("retry", {})
    max_retries = retry_cfg.get("max_retries_per_module", 3)
    retry_delay = retry_cfg.get("retry_delay_seconds", 30)
    on_failure = retry_cfg.get("on_failure", "skip_and_log")

    _state.current_step = step
    emit({
        "type": "step_start",
        "step": step,
        "label": STEP_LABELS.get(step, step),
        "run_id": _state.run_id,
    })

    start = time.time()
    step_log = StepLog(step=step, status="running")
    _state.steps_log.append(step_log)

    last_error: Optional[str] = None

    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                emit({
                    "type": "info",
                    "message": f"Retrying {step} (attempt {attempt}/{max_retries})...",
                    "run_id": _state.run_id,
                })
                await asyncio.sleep(retry_delay)

            result = await fn()
            elapsed = time.time() - start
            step_log.status = "completed"
            step_log.duration_seconds = round(elapsed, 1)
            step_log.message = f"Completed in {elapsed:.1f}s" + (f" (attempt {attempt})" if attempt > 1 else "")

            emit({
                "type": "step_complete",
                "step": step,
                "duration": elapsed,
                "run_id": _state.run_id,
            })

            await _update_db_step(step, "completed", elapsed)
            return result

        except Exception as e:
            last_error = str(e)
            logger.warning("Step %s attempt %d/%d failed: %s", step, attempt, max_retries, e)

            if attempt < max_retries and on_failure == "retry_with_fallback":
                continue
            elif attempt < max_retries and on_failure != "halt_pipeline":
                continue
            else:
                break

    # All retries exhausted
    elapsed = time.time() - start
    step_log.status = "failed"
    step_log.duration_seconds = round(elapsed, 1)
    step_log.error = last_error

    emit({
        "type": "step_failed",
        "step": step,
        "error": last_error,
        "duration": elapsed,
        "run_id": _state.run_id,
        "retries_attempted": max_retries,
    })

    await _update_db_step(step, "failed", elapsed, last_error)
    logger.error("Step %s failed after %d attempts: %s", step, max_retries, last_error)
    return None


async def _step_research(emit: Callable) -> dict:
    """Pull the next queued topic from the database."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT t.*, f.config_json, f.name as franchise_name
               FROM topics t
               JOIN franchises f ON f.id = t.franchise_id
               WHERE t.status = 'queued'
               ORDER BY t.score DESC
               LIMIT 1"""
        )
        row = await cursor.fetchone()
        if not row:
            raise RuntimeError("No queued topics found")

        topic = dict(row)
        _state.topic_id = topic["id"]
        _state.franchise_id = topic["franchise_id"]

        # Mark topic as in_production
        await db.execute(
            "UPDATE topics SET status = 'in_production' WHERE id = ?",
            (topic["id"],),
        )
        await db.commit()

        emit({"type": "info", "message": f"Topic: {topic['title']}"})
        return topic

    finally:
        await db.close()


async def _step_script(emit: Callable):
    """Generate a script for the topic."""
    # Load topic and franchise data
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT t.*, f.config_json FROM topics t JOIN franchises f ON f.id = t.franchise_id WHERE t.id = ?",
            (_state.topic_id,),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    if not row:
        raise RuntimeError(f"Topic not found: {_state.topic_id}")

    topic = dict(row)
    franchise_config = json.loads(topic.get("config_json", "{}"))
    franchise_config["name"] = topic.get("franchise_name", _state.franchise_id)

    narrator = topic.get("narrator_archetype", "")
    if not narrator:
        # Pick default narrator from franchise config
        archetypes = franchise_config.get("character_archetypes", [])
        narrators = [a for a in archetypes if a.get("is_narrator")]
        narrator = narrators[0].get("archetype_id", "") if narrators else ""

    closer = topic.get("closer_style", "style_punchline")

    script, validation = await generate_script(
        topic=topic,
        franchise_config=franchise_config,
        narrator_archetype=narrator,
        closer_style=closer,
    )

    if not script or not validation.valid:
        errors = validation.errors if validation else ["Unknown error"]
        raise RuntimeError(f"Script validation failed: {'; '.join(errors)}")

    if validation.warnings:
        emit({"type": "warning", "message": f"Script warnings: {'; '.join(validation.warnings)}"})

    # Save script to DB
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO scripts (topic_id, script_json, word_count, total_duration_seconds, status)
               VALUES (?, ?, ?, ?, 'generated')""",
            (
                _state.topic_id,
                json.dumps(script.raw_json),
                script.total_word_count,
                script.estimated_duration_seconds,
            ),
        )
        await db.commit()
        script_id = cursor.lastrowid
    finally:
        await db.close()

    return {
        "script": script,
        "script_id": script_id,
        "franchise_config": franchise_config,
    }


async def _step_compliance(script_result: dict, emit: Callable) -> bool:
    """Run compliance checks on the generated script."""
    script: GeneratedScript = script_result["script"]

    result = await check_compliance(
        script_text=script.full_dialogue,
        script_json=script.raw_json,
        franchise_id=_state.franchise_id,
    )

    if not result.passed:
        emit({"type": "error", "message": f"Compliance failed: {'; '.join(result.errors)}"})

        # Update script status to rejected
        db = await get_db()
        try:
            await db.execute(
                "UPDATE scripts SET status = 'rejected', similarity_score = ? WHERE id = ?",
                (result.similarity_score, script_result["script_id"]),
            )
            await db.commit()
        finally:
            await db.close()

        return False

    # Update similarity score
    db = await get_db()
    try:
        await db.execute(
            "UPDATE scripts SET similarity_score = ? WHERE id = ?",
            (result.similarity_score, script_result["script_id"]),
        )
        await db.commit()
    finally:
        await db.close()

    return True


async def _step_voice_images(script_result: dict, emit: Callable):
    """Run voice and image generation in parallel."""
    script: GeneratedScript = script_result["script"]
    franchise_config = script_result["franchise_config"]
    scenes = [
        {
            "scene_number": s.scene_number,
            "dialogue": s.dialogue,
            "shot_type": s.shot_type,
            "narrator_expression": s.narrator_expression,
            "action_characters": s.action_characters,
            "environment": s.environment,
            "duration_seconds": s.duration_seconds,
        }
        for s in script.scenes
    ]

    # Get narrator config
    narrator_id = ""
    archetypes = franchise_config.get("character_archetypes", [])
    narrator_config = {}
    for arch in archetypes:
        if arch.get("is_narrator"):
            narrator_id = arch.get("archetype_id", "")
            narrator_config = arch
            break

    emit({"type": "info", "message": "Starting parallel voice + image generation..."})

    # Run in parallel
    voice_task = asyncio.create_task(
        generate_voice(scenes, narrator_config, _state.franchise_id, _state.topic_id)
    )
    image_task = asyncio.create_task(
        generate_scene_images(scenes, _state.franchise_id, franchise_config, _state.topic_id)
    )

    voice_result, image_result = await asyncio.gather(voice_task, image_task)

    if not voice_result:
        raise RuntimeError("Voice generation failed")
    if not image_result or not image_result.scene_images:
        raise RuntimeError("Image generation failed — no images produced")

    emit({
        "type": "info",
        "message": f"Voice: {voice_result.total_duration_seconds:.1f}s, Images: {len(image_result.scene_images)} scenes",
    })

    return voice_result, image_result


async def _step_animate(image_result, voice_result, emit: Callable):
    """Generate animated video clips from images."""
    scene_images = [
        {
            "scene_number": si.scene_number,
            "image_path": si.image_path,
            "shot_type": si.shot_type,
        }
        for si in image_result.scene_images
    ]

    voice_segments = [
        {
            "scene_number": vs.scene_number,
            "audio_path": vs.audio_path,
            "duration_seconds": vs.duration_seconds,
        }
        for vs in voice_result.segments
    ]

    result = await generate_video_clips(
        scene_images, voice_segments, _state.franchise_id, _state.topic_id
    )

    if not result.clips:
        raise RuntimeError("No video clips generated")

    emit({
        "type": "info",
        "message": f"Generated {len(result.clips)} clips, {result.total_credits_used} credits used",
    })

    return result


async def _step_assemble(video_result, voice_result, script_result: dict, emit: Callable):
    """Assemble final video."""
    script: GeneratedScript = script_result["script"]
    franchise_config = script_result["franchise_config"]

    clips = [
        {
            "scene_number": c.scene_number,
            "video_path": c.video_path,
            "duration_seconds": c.duration_seconds,
        }
        for c in video_result.clips
    ]

    voice_segments = [
        {
            "scene_number": vs.scene_number,
            "audio_path": vs.audio_path,
            "duration_seconds": vs.duration_seconds,
            "word_timestamps": vs.word_timestamps,
        }
        for vs in voice_result.segments
    ]

    result = await assemble_video(
        clips=clips,
        voice_segments=voice_segments,
        script=script.raw_json,
        franchise_id=_state.franchise_id,
        franchise_config=franchise_config,
        topic_id=_state.topic_id,
    )

    if not result:
        raise RuntimeError("Assembly failed — no output video")

    emit({"type": "info", "message": f"Assembled video: {result.duration_seconds:.1f}s"})
    return result


async def _step_quality_gate(assembly_result, script_result: dict, voice_result, emit: Callable):
    """Run 9-point quality gate. Failed videos move to quarantine."""
    script: GeneratedScript = script_result["script"]

    # Get similarity score from DB
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT similarity_score FROM scripts WHERE id = ?",
            (script_result["script_id"],),
        )
        row = await cursor.fetchone()
        sim_score = row["similarity_score"] if row and row["similarity_score"] else 0.0
    finally:
        await db.close()

    result = await run_quality_gate(
        video_path=assembly_result.video_path,
        script=script.raw_json,
        voice_duration=voice_result.total_duration_seconds,
        similarity_score=sim_score,
        franchise_id=_state.franchise_id,
    )

    emit({"type": "info", "message": result.summary})

    if not result.passed:
        # Move video to quarantine directory
        await _quarantine_video(
            video_path=assembly_result.video_path,
            topic_id=_state.topic_id,
            franchise_id=_state.franchise_id,
            failed_checks=result.failed_checks,
            emit=emit,
        )
        return False

    return True


async def _step_publish(assembly_result, script_result: dict, emit: Callable):
    """Publish to all platforms."""
    script: GeneratedScript = script_result["script"]

    result = await publish_video(
        video_path=assembly_result.video_path,
        script=script.raw_json,
        franchise_id=_state.franchise_id,
        topic_id=_state.topic_id,
    )

    if result.errors:
        emit({"type": "warning", "message": f"Publish errors: {'; '.join(result.errors)}"})

    # Save video record to DB
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO videos
               (topic_id, script_id, franchise_id, narrator_archetype,
                youtube_video_id, tiktok_video_id, instagram_video_id, facebook_video_id,
                video_path, long_form_outline_path, title, description, tags_json,
                closer_style, published_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                _state.topic_id,
                script_result["script_id"],
                _state.franchise_id,
                "",
                result.youtube_video_id,
                result.tiktok_video_id,
                result.instagram_video_id,
                result.facebook_video_id,
                assembly_result.video_path,
                result.long_form_outline_path,
                script.title,
                script.description,
                json.dumps(script.tags),
                script.closer_style,
            ),
        )

        # Update topic status
        await db.execute(
            "UPDATE topics SET status = 'published', published_at = CURRENT_TIMESTAMP WHERE id = ?",
            (_state.topic_id,),
        )
        await db.commit()
    finally:
        await db.close()

    platforms = ", ".join(result.platforms_published) or "none"
    emit({"type": "info", "message": f"Published to: {platforms}"})
    return result


async def _finalize(status: str, message: str, emit: Callable) -> PipelineState:
    """Finalize the pipeline run."""
    _state.status = status
    _state.completed_at = time.time()
    _state.error = message if status == "failed" else None

    # Update DB
    db = await get_db()
    try:
        steps_json = json.dumps([
            {"step": s.step, "status": s.status, "duration": s.duration_seconds, "error": s.error}
            for s in _state.steps_log
        ])
        await db.execute(
            """UPDATE pipeline_runs
               SET status = ?, current_step = ?, steps_log_json = ?,
                   completed_at = CURRENT_TIMESTAMP, error_message = ?
               WHERE id = ?""",
            (status, _state.current_step, steps_json, _state.error, _state.run_id),
        )

        # If failed, revert topic status
        if status == "failed" and _state.topic_id:
            await db.execute(
                "UPDATE topics SET status = 'queued' WHERE id = ?",
                (_state.topic_id,),
            )

        await db.commit()
    finally:
        await db.close()

    emit({
        "type": "pipeline_complete",
        "status": status,
        "message": message,
        "run_id": _state.run_id,
        "duration": round(_state.completed_at - _state.started_at, 1),
    })

    logger.info("Pipeline %s: %s (%.1fs)", status, message, _state.completed_at - _state.started_at)
    return _state


async def _quarantine_video(
    video_path: str,
    topic_id: str,
    franchise_id: str,
    failed_checks: list[str],
    emit: Callable,
) -> None:
    """Move a failed video to the quarantine directory with metadata."""
    from pathlib import Path
    import shutil

    config = get_config()
    quarantine_dir = Path(
        config.get("pipeline", {}).get("storage", {}).get("quarantine_dir", "data/quarantine")
    )
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    src = Path(video_path)
    if src.exists():
        dest = quarantine_dir / f"{franchise_id}_{topic_id.replace('/', '_')}_{int(time.time())}{src.suffix}"
        shutil.move(str(src), str(dest))

        # Save quarantine metadata
        meta_path = dest.with_suffix(".json")
        meta = {
            "topic_id": topic_id,
            "franchise_id": franchise_id,
            "failed_checks": failed_checks,
            "original_path": str(src),
            "quarantined_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "run_id": _state.run_id,
        }
        meta_path.write_text(json.dumps(meta, indent=2))

        emit({
            "type": "warning",
            "message": f"Video quarantined: {dest.name} — failed: {', '.join(failed_checks)}",
        })
        logger.info("Quarantined video to %s", dest)
    else:
        emit({"type": "warning", "message": f"Video file not found for quarantine: {video_path}"})


async def _update_db_step(step: str, status: str, duration: float, error: str = None) -> None:
    """Update the pipeline run record with step progress."""
    db = await get_db()
    try:
        steps_json = json.dumps([
            {"step": s.step, "status": s.status, "duration": s.duration_seconds, "error": s.error}
            for s in _state.steps_log
        ])
        await db.execute(
            "UPDATE pipeline_runs SET current_step = ?, steps_log_json = ? WHERE id = ?",
            (step, steps_json, _state.run_id),
        )
        await db.commit()
    finally:
        await db.close()
