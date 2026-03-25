"""Pipeline API routes — run, stop, WebSocket status, quarantine management."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.config.config_loader import get_config

from backend.db.database import get_db
from backend.services.pipeline.orchestrator import (
    run_pipeline,
    get_state,
    is_running,
    request_abort,
    STEPS,
    STEP_LABELS,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

# Active WebSocket connections
_ws_connections: set[WebSocket] = set()


async def _broadcast(data: dict) -> None:
    """Broadcast a message to all connected WebSocket clients."""
    dead: set[WebSocket] = set()
    for ws in _ws_connections:
        try:
            await ws.send_json(data)
        except Exception:
            dead.add(ws)
    _ws_connections -= dead


def _progress_callback(data: dict) -> None:
    """Called by the orchestrator for each progress event.

    Schedules a broadcast to all WebSocket clients.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_broadcast(data))
    except Exception:
        pass


@router.post("/run")
async def run_pipeline_endpoint():
    """Start the pipeline (pulls next queued topic)."""
    if is_running():
        return {"status": "error", "message": "Pipeline is already running"}

    # Run pipeline in background task
    asyncio.create_task(_run_pipeline_task())

    return {"status": "started", "message": "Pipeline started"}


async def _run_pipeline_task():
    """Background task that runs the pipeline."""
    try:
        await run_pipeline(on_progress=_progress_callback)
    except Exception as e:
        logger.exception("Pipeline task failed")
        await _broadcast({"type": "pipeline_error", "error": str(e)})


@router.post("/stop")
async def stop_pipeline():
    """Abort the current pipeline run."""
    if not is_running():
        return {"status": "error", "message": "Pipeline is not running"}

    request_abort()
    await _broadcast({"type": "pipeline_aborting", "message": "Abort requested"})
    return {"status": "aborting", "message": "Pipeline abort requested"}


@router.get("/status")
async def pipeline_status():
    """Get current pipeline status and recent runs."""
    state = get_state()

    # Get recent runs from DB
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 10"
        )
        rows = await cursor.fetchall()
        runs = [dict(row) for row in rows]
    finally:
        await db.close()

    return {
        "is_running": is_running(),
        "current": {
            "run_id": state.run_id,
            "topic_id": state.topic_id,
            "franchise_id": state.franchise_id,
            "status": state.status,
            "current_step": state.current_step,
            "steps_log": [
                {
                    "step": s.step,
                    "status": s.status,
                    "duration": s.duration_seconds,
                    "message": s.message,
                    "error": s.error,
                }
                for s in state.steps_log
            ],
        },
        "steps": [{"id": s, "label": STEP_LABELS[s]} for s in STEPS],
        "runs": runs,
    }


@router.get("/quarantine")
async def list_quarantined():
    """List all quarantined videos with metadata."""
    config = get_config()
    quarantine_dir = Path(
        config.get("pipeline", {}).get("storage", {}).get("quarantine_dir", "data/quarantine")
    )

    if not quarantine_dir.exists():
        return {"quarantined": [], "total": 0}

    items = []
    for meta_file in sorted(quarantine_dir.glob("*.json"), reverse=True):
        try:
            meta = json.loads(meta_file.read_text())
            video_file = meta_file.with_suffix(".mp4")
            meta["video_exists"] = video_file.exists()
            meta["video_filename"] = video_file.name
            meta["meta_filename"] = meta_file.name
            items.append(meta)
        except Exception:
            pass

    return {"quarantined": items, "total": len(items)}


@router.post("/quarantine/{filename}/retry")
async def retry_quarantined(filename: str):
    """Re-queue a quarantined video's topic for another pipeline run."""
    config = get_config()
    quarantine_dir = Path(
        config.get("pipeline", {}).get("storage", {}).get("quarantine_dir", "data/quarantine")
    )

    meta_file = quarantine_dir / f"{filename}.json"
    if not meta_file.exists():
        meta_file = quarantine_dir / filename
    if not meta_file.exists():
        return {"status": "error", "message": "Quarantine metadata not found"}

    try:
        meta = json.loads(meta_file.read_text())
        topic_id = meta.get("topic_id")
        if not topic_id:
            return {"status": "error", "message": "No topic_id in metadata"}

        # Re-queue the topic
        db = await get_db()
        try:
            await db.execute(
                "UPDATE topics SET status = 'queued' WHERE id = ?",
                (topic_id,),
            )
            await db.commit()
        finally:
            await db.close()

        # Remove quarantine files
        meta_file.unlink(missing_ok=True)
        video_file = meta_file.with_suffix(".mp4")
        video_file.unlink(missing_ok=True)

        return {"status": "ok", "message": f"Topic {topic_id} re-queued", "topic_id": topic_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/quarantine/{filename}/discard")
async def discard_quarantined(filename: str):
    """Permanently delete a quarantined video."""
    config = get_config()
    quarantine_dir = Path(
        config.get("pipeline", {}).get("storage", {}).get("quarantine_dir", "data/quarantine")
    )

    meta_file = quarantine_dir / f"{filename}.json"
    if not meta_file.exists():
        meta_file = quarantine_dir / filename

    deleted = []
    for ext in [".json", ".mp4", ".webm"]:
        f = meta_file.with_suffix(ext)
        if f.exists():
            f.unlink()
            deleted.append(f.name)

    if deleted:
        return {"status": "ok", "deleted": deleted}
    return {"status": "error", "message": "No files found to delete"}


@router.websocket("/ws")
async def pipeline_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time pipeline progress."""
    await websocket.accept()
    _ws_connections.add(websocket)

    try:
        # Send current state
        state = get_state()
        await websocket.send_json({
            "type": "connected",
            "is_running": is_running(),
            "current_step": state.current_step,
            "status": state.status,
            "steps_log": [
                {"step": s.step, "status": s.status, "duration": s.duration_seconds}
                for s in state.steps_log
            ],
        })

        # Keep alive — listen for messages
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
            elif data == "status":
                state = get_state()
                await websocket.send_json({
                    "type": "status",
                    "is_running": is_running(),
                    "current_step": state.current_step,
                    "status": state.status,
                })

    except WebSocketDisconnect:
        pass
    finally:
        _ws_connections.discard(websocket)
