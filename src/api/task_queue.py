"""Thread-safe in-memory task queue with ThreadPoolExecutor and TTL eviction."""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskInfo:
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    message: str = ""
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict for API responses."""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "result": self.result,
            "error": self.error,
        }


ProgressCallback = Callable[[float, str], None]


class TaskQueue:
    """Thread-safe in-memory task queue with TTL eviction and concurrency limit."""

    def __init__(
        self,
        ttl_seconds: float = 3600.0,
        max_workers: int = 4,
    ) -> None:
        self._tasks: dict[str, TaskInfo] = {}
        self._fns: dict[str, Callable[[ProgressCallback], Any]] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="task-queue")

    def create(self, fn: Callable[[ProgressCallback], Any]) -> str:
        """Register a task and return its ID. Does not start execution."""
        task_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._tasks[task_id] = TaskInfo(task_id=task_id)
            self._fns[task_id] = fn
        return task_id

    def run(self, task_id: str) -> None:
        """Start a registered task via the thread pool."""
        with self._lock:
            info = self._tasks.get(task_id)
            fn = self._fns.get(task_id)
            if info is None or fn is None:
                raise KeyError(f"Task not found: {task_id}")
            if info.status != TaskStatus.PENDING:
                raise ValueError(f"Task already started or finished: {task_id}")
            info.status = TaskStatus.RUNNING

        self._executor.submit(self._execute, task_id, fn)

    def get(self, task_id: str) -> Optional[TaskInfo]:
        """Return task info, or None if not found."""
        with self._lock:
            return self._tasks.get(task_id)

    def _execute(self, task_id: str, fn: Callable[[ProgressCallback], Any]) -> None:
        """Internal: execute task and update state. Runs in worker thread."""
        try:
            def progress_cb(value: float, message: str = "") -> None:
                with self._lock:
                    ti = self._tasks.get(task_id)
                    if ti:
                        ti.progress = value
                        ti.message = message

            result = fn(progress_cb)
            with self._lock:
                ti = self._tasks.get(task_id)
                if ti:
                    ti.status = TaskStatus.COMPLETED
                    ti.progress = 1.0
                    ti.result = result
                    ti.completed_at = time.time()
        except Exception as exc:
            with self._lock:
                ti = self._tasks.get(task_id)
                if ti:
                    ti.status = TaskStatus.FAILED
                    ti.error = str(exc)
                    ti.completed_at = time.time()

    def _evict_old(self) -> None:
        """Remove completed/failed tasks older than TTL. Call periodically."""
        now = time.time()
        with self._lock:
            to_remove = [
                tid
                for tid, info in self._tasks.items()
                if info.completed_at is not None
                and (now - info.completed_at) > self._ttl
            ]
            for tid in to_remove:
                del self._tasks[tid]
                self._fns.pop(tid, None)

    def shutdown(self) -> None:
        """Shut down the thread pool."""
        self._executor.shutdown(wait=False)


# 全局单例
TASK_QUEUE = TaskQueue(ttl_seconds=3600.0, max_workers=4)
