"""Alignment task endpoints — start, poll, cancel, get result."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from core.model_registry import ModelRegistry
from backend.dependencies import get_registry, get_task_manager
from backend.schemas import AlignStartRequest, TaskStatusResponse, TaskResultResponse, TimestampEntry, SubtitleEntry
from backend.task_manager import TaskManager
from backend.pipelines.align_pipeline import run_align_pipeline

logger = logging.getLogger(__name__)

router = APIRouter()
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"


@router.post("/align/start", status_code=201)
async def start_align(
    body: AlignStartRequest,
    registry: ModelRegistry = Depends(get_registry),
    task_manager: TaskManager = Depends(get_task_manager),
):
    file_dir = UPLOAD_DIR / body.file_id
    wav_path = file_dir / "converted.wav"
    if not wav_path.exists():
        raise HTTPException(404, "Uploaded file not found")
    if not body.text.strip():
        raise HTTPException(400, "Text content is required for alignment")

    task = task_manager.create()

    def _run():
        try:
            task_manager.update(task.task_id, progress=0, status_text="Starting alignment...")

            def _report(p: float, msg: str):
                task_manager.update(task.task_id, progress=p, status_text=msg)

            result = run_align_pipeline(
                registry=registry,
                wav_path=str(wav_path),
                text_content=body.text,
                split_point=body.split_point,
                language=body.language,
                strip_punct=body.strip_punct,
                strip_mid_punct=body.strip_mid_punct,
                mid_punct_choices=body.mid_punct_choices,
                space_replacement=body.space_replacement,
                capitalize=body.capitalize,
                cancel_event=task.cancel_event,
                progress_cb=_report,
            )
            task_manager.complete(task.task_id, result=result)
        except Exception as e:
            logger.exception("Alignment task %s failed", task.task_id)
            task_manager.fail(task.task_id, str(e))

    t = threading.Thread(target=_run, daemon=True, name=f"align-{task.task_id[:8]}")
    t.start()

    return {"task_id": task.task_id}


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_status(
    task_id: str,
    task_manager: TaskManager = Depends(get_task_manager),
):
    record = task_manager.get(task_id)
    if record is None:
        raise HTTPException(404, "Task not found")
    return TaskStatusResponse(
        task_id=record.task_id,
        status=record.status,
        progress=record.progress,
        status_text=record.status_text,
    )


@router.get("/tasks/{task_id}/result", response_model=TaskResultResponse)
async def get_result(
    task_id: str,
    task_manager: TaskManager = Depends(get_task_manager),
):
    record = task_manager.get(task_id)
    if record is None:
        raise HTTPException(404, "Task not found")
    if record.status != "completed":
        raise HTTPException(400, "Task not completed")
    if record.result is None:
        raise HTTPException(500, "No result data")

    text = record.result.get("text", "")
    timestamps = [
        TimestampEntry(
            text=t.get("text", ""),
            start_time=t.get("start_time", 0.0),
            end_time=t.get("end_time", 0.0),
        )
        for t in record.result.get("timestamps", [])
    ]
    subtitle_entries = [
        SubtitleEntry(
            text=e.get("text", ""),
            start=e.get("start", 0.0),
            end=e.get("end", 0.0),
        )
        for e in record.result.get("subtitle_entries", [])
    ]

    return TaskResultResponse(
        text=text,
        timestamps=timestamps,
        subtitle_entries=subtitle_entries,
    )


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    task_manager: TaskManager = Depends(get_task_manager),
):
    task_manager.cancel(task_id)
    return {"status": "cancelled"}
