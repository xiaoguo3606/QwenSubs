"""Alignment task endpoints — start forced alignment."""

from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, Depends, HTTPException

from core.model_registry import ModelRegistry
from backend.dependencies import get_registry, get_task_manager
from backend.path_utils import resolve_upload_wav
from backend.schemas import AlignStartRequest
from backend.task_manager import TaskManager
from backend.pipelines.align_pipeline import run_align_pipeline, CancelError

logger = logging.getLogger(__name__)

router = APIRouter()


def _align_language(language: str) -> str:
    if not language or language == "auto":
        return "Chinese"
    return language


@router.post("/align/start", status_code=201)
async def start_align(
    body: AlignStartRequest,
    registry: ModelRegistry = Depends(get_registry),
    task_manager: TaskManager = Depends(get_task_manager),
):
    wav_path = resolve_upload_wav(body.file_id)
    if not body.text.strip():
        raise HTTPException(400, "Text content is required for alignment")

    task = task_manager.create()

    def _run():
        try:
            task_manager.update(task.task_id, 0, "Starting alignment...")

            def _report(p: float, msg: str):
                task_manager.update(task.task_id, p, msg)

            result = run_align_pipeline(
                registry=registry,
                wav_path=str(wav_path),
                text_content=body.text,
                split_point=body.split_point,
                language=_align_language(body.language),
                strip_punct=body.strip_punct,
                strip_mid_punct=body.strip_mid_punct,
                mid_punct_choices=body.mid_punct_choices,
                space_replacement=body.space_replacement,
                capitalize=body.capitalize,
                cancel_event=task.cancel_event,
                progress_cb=_report,
            )
            task_manager.complete(task.task_id, result=result)
        except CancelError:
            logger.info("Alignment task %s cancelled", task.task_id)
        except Exception as e:
            logger.exception("Alignment task %s failed", task.task_id)
            task_manager.fail(task.task_id, str(e))

    threading.Thread(target=_run, daemon=True, name=f"align-{task.task_id[:8]}").start()
    return {"task_id": task.task_id}
