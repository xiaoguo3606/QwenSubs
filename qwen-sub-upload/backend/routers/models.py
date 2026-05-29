"""Model management endpoints — list, download."""

from __future__ import annotations

import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_task_manager
from backend.schemas import ModelInfo, ModelListResponse, ModelDownloadResponse, ModelDownloadRequest
from backend.task_manager import TaskManager
from utils.model_manager import is_model_downloaded, download_model, MODELS
from config import settings as cfg

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@router.get("/models", response_model=ModelListResponse)
async def list_models():
    model_dir = cfg.get("model_dir", "models")
    base = PROJECT_ROOT / model_dir
    models = []
    for m in MODELS:
        downloaded = is_model_downloaded(str(base / m["id"].replace("--", "/")))
        models.append(ModelInfo(
            id=m["id"],
            name=m["name"],
            size_gb=m.get("size_gb", 0),
            type=m.get("type", "asr"),
            downloaded=downloaded,
        ))
    return ModelListResponse(models=models)


@router.post("/models/download", status_code=201)
async def download_model_endpoint(
    body: ModelDownloadRequest,
    task_manager: TaskManager = Depends(get_task_manager),
):
    model_dir = cfg.get("model_dir", "models")
    base = PROJECT_ROOT / model_dir
    model = next((m for m in MODELS if m["id"] == body.model_id), None)
    if not model:
        raise HTTPException(404, f"Unknown model: {body.model_id}")

    task = task_manager.create()

    def _run():
        try:
            download_model(
                model_id=body.model_id,
                local_dir=str(base / body.model_id.replace("--", "/")),
                source=body.source or "modelscope",
            )
            task_manager.complete(task.task_id, {"status": "downloaded"})
        except Exception as e:
            task_manager.fail(task.task_id, str(e))

    threading.Thread(target=_run, daemon=True).start()
    return ModelDownloadResponse(task_id=task.task_id)
