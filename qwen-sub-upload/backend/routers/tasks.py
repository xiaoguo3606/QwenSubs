"""Shared task status / cancel / result endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_task_manager
from backend.result_builder import task_result_from_dict
from backend.schemas import TaskStatusResponse
from backend.task_manager import TaskManager

router = APIRouter()


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
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
    if rec.result is None:
        raise HTTPException(500, "No result data")
    return task_result_from_dict(rec.result)
