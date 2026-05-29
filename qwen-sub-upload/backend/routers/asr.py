"""ASR task endpoints — start recognition."""

from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, Depends, HTTPException

from core.model_registry import ModelRegistry
from backend.dependencies import get_registry, get_task_manager
from backend.path_utils import resolve_upload_wav
from backend.schemas import AsrStartRequest
from backend.task_manager import TaskManager
from backend.pipelines.asr_pipeline import run_asr_pipeline, CancelError

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/asr/start", status_code=201)
async def start_asr(
    body: AsrStartRequest,
    registry: ModelRegistry = Depends(get_registry),
    task_manager: TaskManager = Depends(get_task_manager),
):
    wav_path = resolve_upload_wav(body.file_id)
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
            logger.info("ASR task %s cancelled", task.task_id)
        except Exception as e:
            logger.exception("ASR task failed")
            task_manager.fail(task.task_id, str(e))

    threading.Thread(target=_run, daemon=True).start()
    return {"task_id": task.task_id}
