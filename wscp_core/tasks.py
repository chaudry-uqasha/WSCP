import threading
import time
import uuid

TASK_TTL_SECONDS = 3600
TASKS = {}
TASKS_LOCK = threading.Lock()


def _cleanup_tasks():
    cutoff = time.time() - TASK_TTL_SECONDS
    with TASKS_LOCK:
        old_ids = [tid for tid, t in TASKS.items() if t.get("updated_at", 0) < cutoff]
        for tid in old_ids:
            TASKS.pop(tid, None)


def create_task(kind, message="Queued"):
    _cleanup_tasks()
    task_id = uuid.uuid4().hex
    now = time.time()
    with TASKS_LOCK:
        TASKS[task_id] = {
            "task_id": task_id,
            "kind": kind,
            "status": "queued",
            "phase": "queued",
            "message": message,
            "bytes_done": 0,
            "total_bytes": 0,
            "percent": 0,
            "speed_bps": 0,
            "hash_sha256": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
            "started_at": now,
        }
    return task_id


def update_task(task_id, **updates):
    if not task_id:
        return
    with TASKS_LOCK:
        task = TASKS.get(task_id)
        if not task:
            return
        task.update(updates)
        task["updated_at"] = time.time()


def update_task_progress(task_id, bytes_done=None, total_bytes=None, phase=None, message=None):
    if not task_id:
        return
    with TASKS_LOCK:
        task = TASKS.get(task_id)
        if not task:
            return
        if bytes_done is not None:
            task["bytes_done"] = max(0, int(bytes_done))
        if total_bytes is not None:
            task["total_bytes"] = max(0, int(total_bytes))
        if phase is not None:
            task["phase"] = phase
        if message is not None:
            task["message"] = message
        task["status"] = "running"
        elapsed = max(time.time() - task.get("started_at", time.time()), 0.001)
        task["speed_bps"] = int(task.get("bytes_done", 0) / elapsed)
        total = task.get("total_bytes", 0)
        if total > 0:
            task["percent"] = min(100, int((task.get("bytes_done", 0) * 100) / total))
        task["updated_at"] = time.time()


def finish_task(task_id, message="Completed", hash_sha256=None):
    if not task_id:
        return
    with TASKS_LOCK:
        task = TASKS.get(task_id)
        if not task:
            return
        if hash_sha256:
            task["hash_sha256"] = hash_sha256
        total = task.get("total_bytes", 0)
        if total > 0:
            task["bytes_done"] = total
        task["percent"] = 100
        task["status"] = "done"
        task["phase"] = "done"
        task["message"] = message
        task["updated_at"] = time.time()


def fail_task(task_id, error_message):
    if not task_id:
        return
    with TASKS_LOCK:
        task = TASKS.get(task_id)
        if not task:
            return
        task["status"] = "error"
        task["phase"] = "error"
        task["message"] = "Failed"
        task["error"] = str(error_message)
        task["updated_at"] = time.time()


def get_task(task_id):
    with TASKS_LOCK:
        task = TASKS.get(task_id)
        if not task:
            return None
        return dict(task)
