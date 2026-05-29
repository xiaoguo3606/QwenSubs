"""FastAPI dependency injection for global singletons."""

from __future__ import annotations

from fastapi import Request

from core.model_registry import ModelRegistry
from backend.task_manager import TaskManager


def get_registry(request: Request) -> ModelRegistry:
    return request.app.state.registry


def get_task_manager(request: Request) -> TaskManager:
    return request.app.state.task_manager
