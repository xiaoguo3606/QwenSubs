"""ASR task endpoints — start, poll, cancel, get result."""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from core.audio_processor import convert_to_16k_mono
from core.model_registry import ModelRegistry
from backend.dependencies import get_registry, get_task_manager
from backend.schemas import AsrStartRequest, TaskStatusResponse, TaskResultResponse, TimestampEntry, SubtitleEntry
from backend.task_manager import TaskManager
from backend.pipelines.asr_pipeline import run_asr_pipeline, CancelError

logger = logging.getLogger(__name__)

router = APIRouter()
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"


@router.post("/asr/start", status_code=201)
async def start_asr(
    body: AsrStartRequest,
    registry: ModelRegistry = Depends(get_registry),
    task_manager: TaskManager = Depends(get_task_manager),
):
    file_dir = UPLOAD_DIR / body.file_id
    wav_path = file_dir / "converted.wav"
    if not wav_path.exists():
        raise HTTPException(404, "Uploaded file not found")

    task = task_manager.create()

    def _progress(p: float, text: str):
        task_manager.update(task.task_id, p, text)

    def _run():
        try:
            result = run_asr_pipeline(
                registry=registry,
                wav_path=str(wav_path),
                split_point=body.split_point,
                language=body.language,
                hint_text=body.hint_text,
                asr_model=body.asr_model,
                strip_punct=body.strip_punct,
                strip_mid_punct=body.strip_mid_punct,
                mid_punct_choices=body.mid_punct_choices,
                space_replacement=body.space_replacement,
                capitalize=body.capitalize,
                cancel_event=task.cancel_event,
                progress_cb=_progress,
            )
            task_manager.complete(task.task_id, result)
        except CancelError:
            task_manager.fail(task.task_id, "cancelled")
        except Exception as e:
            logger.exception("ASR task failed")
            task_manager.fail(task.task_id, str(e))

    threading.Thread(target=_run, daemon=True).start()
    return {"task_id": task.task_id}


@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    task_manager: TaskManager = Depends(get_task_manager),
):
    rec = task_manager.get(task_id)
    if rec is None:
        raise HTTPException(404, "Task not found")
    return TaskStatusResponse(
        task_id=rec.task_id,
        status=rec.status,
        progress=rec.progress,
        status_text=rec.status_text,
        error=rec.error,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    task_manager: TaskManager = Depends(get_task_manager),
):
    ok = task_manager.cancel(task_id)
    if not ok:
        raise HTTPException(404, "Task not found")
    return {"status": "cancelled"}


@router.get("/tasks/{task_id}/result")
async def get_task_result(
    task_id: str,
    task_manager: TaskManager = Depends(get_task_manager),
):
    rec = task_manager.get(task_id)
    if rec is None:
        raise HTTPException(404, "Task not found")
    if rec.status != "completed":
        raise HTTPException(400, f"Task is {rec.status}, not completed")
    result = rec.result
    ts_list = result.get("timestamps", [])
    lines = [l for l in result["text"].split("\n") if l.strip()]
    # Build per-line timing from per-character timestamps
    subtitle_entries = []
    char_idx = 0
    for line in lines:
        line_len = len(line)
        start_time = ts_list[char_idx]["start_time"] if char_idx < len(ts_list) else 0.0
        end_idx = min(char_idx + line_len - 1, len(ts_list) - 1)
        end_time = ts_list[end_idx]["end_time"] if end_idx >= 0 else 0.0
        subtitle_entries.append(SubtitleEntry(text=line, start_time=start_time, end_time=end_time))
        char_idx += line_len
    return TaskResultResponse(
        text=result["text"],
        timestamps=[TimestampEntry(**t) for t in ts_list],
        subtitle_entries=subtitle_entries,
    )
