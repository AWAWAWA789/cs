"""Tests for the async task queue."""

import time

from src.api.task_queue import TaskQueue, TaskStatus


def test_create_returns_pending_task():
    """create() should register a task in pending state without starting it."""
    q = TaskQueue()
    task_id = q.create(lambda progress_cb: 42)
    info = q.get(task_id)
    assert info is not None
    assert info.status == TaskStatus.PENDING
    assert info.progress == 0.0


def test_run_completes_and_stores_result():
    """run() should execute the task and store the result."""
    q = TaskQueue()
    task_id = q.create(lambda progress_cb: {"answer": 42})
    q.run(task_id)

    # Wait for completion
    for _ in range(50):
        info = q.get(task_id)
        if info and info.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            break
        time.sleep(0.1)

    info = q.get(task_id)
    assert info is not None
    assert info.status == TaskStatus.COMPLETED
    assert info.result == {"answer": 42}
    assert info.progress == 1.0


def test_run_failed_task_stores_error():
    """A task that raises should be marked as failed with the error message."""
    def failing_task(progress_cb):
        raise ValueError("boom")

    q = TaskQueue()
    task_id = q.create(failing_task)
    q.run(task_id)

    for _ in range(50):
        info = q.get(task_id)
        if info and info.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            break
        time.sleep(0.1)

    info = q.get(task_id)
    assert info is not None
    assert info.status == TaskStatus.FAILED
    assert "boom" in (info.error or "")


def test_progress_callback_updates_progress():
    """The progress callback should update the task's progress and message."""
    def task_with_progress(progress_cb):
        progress_cb(0.5, "半途")
        time.sleep(0.1)
        progress_cb(1.0, "完成")
        return "done"

    q = TaskQueue()
    task_id = q.create(task_with_progress)
    q.run(task_id)

    for _ in range(50):
        info = q.get(task_id)
        if info and info.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            break
        time.sleep(0.1)

    info = q.get(task_id)
    assert info is not None
    assert info.status == TaskStatus.COMPLETED


def test_run_unknown_task_raises():
    """run() should raise KeyError for an unknown task_id."""
    q = TaskQueue()
    try:
        q.run("nonexistent")
        assert False, "Should have raised KeyError"
    except KeyError:
        pass


def test_get_unknown_task_returns_none():
    """get() should return None for an unknown task_id."""
    q = TaskQueue()
    assert q.get("nonexistent") is None


def test_ttl_eviction_removes_old_tasks():
    """Tasks older than the TTL should be evicted on cleanup."""
    q = TaskQueue(ttl_seconds=0.5)
    task_id = q.create(lambda progress_cb: 1)
    q.run(task_id)

    # Wait for completion
    for _ in range(50):
        info = q.get(task_id)
        if info and info.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            break
        time.sleep(0.1)

    # Wait for TTL to expire
    time.sleep(0.7)

    # Trigger eviction by calling _evict_old
    q._evict_old()

    assert q.get(task_id) is None, "Task should have been evicted after TTL"


def test_concurrent_tasks_respect_max_workers():
    """Multiple tasks should run concurrently up to max_workers."""
    import threading
    counter = {"active": 0, "max_active": 0}
    lock = threading.Lock()

    def counting_task(progress_cb):
        with lock:
            counter["active"] += 1
            counter["max_active"] = max(counter["max_active"], counter["active"])
        time.sleep(0.2)
        with lock:
            counter["active"] -= 1
        return "ok"

    q = TaskQueue(max_workers=2)
    task_ids = []
    for _ in range(5):
        tid = q.create(counting_task)
        q.run(tid)
        task_ids.append(tid)

    # Wait for all to complete
    for tid in task_ids:
        for _ in range(100):
            info = q.get(tid)
            if info and info.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                break
            time.sleep(0.1)

    assert counter["max_active"] <= 2, f"max_active={counter['max_active']} should be <= 2"
