"""Thread-safe in-memory task manager for background pipeline tasks."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

TaskStatus = Literal["pending", "running", "completed", "failed", "cancelled"]


@dataclass
class TaskRecord:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = "pending"
    progress: float = 0.0
    status_text: str = ""
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    result: Any = None
    cancel_event: threading.Event = field(default_factory=threading.Event)


_TASK_TTL = 1800  # 30 minutes


class TaskManager:
    """Thread-safe manager for tracking background task progress."""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = threading.Lock()

    def create(self) -> TaskRecord:
        rec = TaskRecord()
        with self._lock:
            self._tasks[rec.task_id] = rec
        return rec

    def get(self, task_id: str) -> TaskRecord | None:
        self._expire_old()
        with self._lock:
            return self._tasks.get(task_id)

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            rec = self._tasks.get(task_id)
            if rec is None:
                return False
            rec.cancel_event.set()
            rec.status = "cancelled"
            rec.updated_at = time.time()
            return True

    def update(self, task_id: str, progress: float, status_text: str) -> None:
        with self._lock:
            rec = self._tasks.get(task_id)
            if rec is None:
                return
            if rec.status == "cancelled":
                return
            if rec.status == "pending":
                rec.status = "running"
            rec.progress = progress
            rec.status_text = status_text
            rec.updated_at = time.time()

    def complete(self, task_id: str, result: Any) -> None:
        with self._lock:
            rec = self._tasks.get(task_id)
            if rec is None:
                return
            if rec.cancel_event.is_set() or rec.status == "cancelled":
                return
            rec.status = "completed"
            rec.progress = 1.0
            rec.result = result
            rec.updated_at = time.time()

    def fail(self, task_id: str, error: str) -> None:
        with self._lock:
            rec = self._tasks.get(task_id)
            if rec is None:
                return
            if rec.cancel_event.is_set() or rec.status == "cancelled":
                return
            rec.status = "failed"
            rec.error = error
            rec.updated_at = time.time()

    def _expire_old(self) -> None:
        now = time.time()
        with self._lock:
            expired = [
                tid
                for tid, rec in self._tasks.items()
                if rec.status in ("completed", "failed", "cancelled")
                and (now - rec.updated_at) > _TASK_TTL
            ]
            for tid in expired:
                del self._tasks[tid]
