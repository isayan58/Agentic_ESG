"""Background job runner for long-running pipeline work.

Streamlit's UI thread blocks on ``agent.run()`` — a 30-second pipeline
freezes every reload during that window. ThreadPoolExecutor offloads the
work; the UI just polls ``get_job_status(job_id)`` and renders progress.

Constraints worth knowing about:

- **No Streamlit access from workers.** ``st.session_state`` lives on the
  request thread, not the worker pool, so callers must capture
  ``user_id`` at submit time and pass it as an argument. Reading
  session state from inside ``fn`` will raise.
- **Lock everything.** ``_jobs`` is mutated by the submitting Streamlit
  rerun and read by every polling rerun — both can be concurrent across
  tabs. A single ``threading.Lock`` is plenty here; this is not a hot
  path.
- **Bounded retention.** Long-running sessions accumulate completed
  futures otherwise. We keep the most recent ``_JOBS_PER_USER_CAP``
  finished jobs per user; running jobs are never evicted.

When this becomes a bottleneck (cross-process orchestration, durable
queues, retries), swap the public API to RQ/Celery — call sites that
use ``submit_job`` / ``get_job_status`` / ``list_jobs`` won't change.
"""
from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4


# 4 concurrent workers is plenty for an internal multi-user tool. Each
# pipeline run is mostly I/O-bound (HF API, file loads, BigQuery), so the
# GIL doesn't dominate. Bump if a single workspace fans out parallel runs.
_MAX_WORKERS = 4
_JOBS_PER_USER_CAP = 100

_executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="esg-job")
_lock = threading.Lock()
# job_id → {"future", "user_id", "label", "submitted_at"}
_jobs: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def submit_job(
    fn: Callable[..., Any],
    *args: Any,
    user_id: str,
    label: str = "",
    **kwargs: Any,
) -> str:
    """Run ``fn(*args, **kwargs)`` on a background worker; return a job_id.

    ``user_id`` is captured here because the worker can't reach
    ``st.session_state`` to resolve it later. ``label`` is a free-form
    description shown in ``list_jobs`` (e.g. "Full pipeline run").
    """
    if not user_id:
        raise ValueError("submit_job requires user_id — workers can't read it from session_state.")
    job_id = str(uuid4())
    future = _executor.submit(fn, *args, **kwargs)
    with _lock:
        _jobs[job_id] = {
            "future": future,
            "user_id": user_id,
            "label": label,
            "submitted_at": _now_iso(),
        }
        _evict_old_for_user_locked(user_id)
    return job_id


def _evict_old_for_user_locked(user_id: str) -> None:
    """Drop oldest *finished* jobs for ``user_id`` past the cap.

    Caller holds ``_lock``. Running/queued jobs are never evicted —
    losing a future you can still poll is much worse than holding a
    handful of done ones.
    """
    user_jobs = [(jid, meta) for jid, meta in _jobs.items()
                 if meta["user_id"] == user_id]
    if len(user_jobs) <= _JOBS_PER_USER_CAP:
        return
    user_jobs.sort(key=lambda kv: kv[1]["submitted_at"])  # oldest first
    overflow = len(user_jobs) - _JOBS_PER_USER_CAP
    for jid, meta in user_jobs:
        if overflow <= 0:
            break
        if meta["future"].done():
            _jobs.pop(jid, None)
            overflow -= 1


def get_job_status(job_id: str) -> tuple[str, Any]:
    """Return ``(status, payload)`` for one job.

    Status is one of:

    - ``"not_found"``  — unknown ``job_id`` (or evicted).
    - ``"queued"``     — submitted but a worker hasn't picked it up.
    - ``"running"``    — currently executing.
    - ``"completed"``  — finished cleanly; payload is the return value.
    - ``"failed"``     — raised; payload is the exception message.
    """
    with _lock:
        meta = _jobs.get(job_id)
    if meta is None:
        return "not_found", None

    future: Future = meta["future"]
    if future.done():
        exc = future.exception()
        if exc is not None:
            return "failed", str(exc)
        return "completed", future.result()
    if future.running():
        return "running", None
    return "queued", None


def list_jobs(user_id: str) -> list[dict[str, Any]]:
    """Return job metadata for ``user_id``, newest first, without futures.

    Safe to render in Streamlit — no live ``Future`` objects leak out, so
    callers can serialize this freely.
    """
    with _lock:
        rows = [
            {
                "job_id": jid,
                "user_id": meta["user_id"],
                "label": meta["label"],
                "submitted_at": meta["submitted_at"],
                "status": _status_of_locked(meta["future"]),
            }
            for jid, meta in _jobs.items()
            if meta["user_id"] == user_id
        ]
    rows.sort(key=lambda m: m["submitted_at"], reverse=True)
    return rows


def _status_of_locked(future: Future) -> str:
    if future.done():
        return "failed" if future.exception() is not None else "completed"
    if future.running():
        return "running"
    return "queued"


def cancel_job(job_id: str) -> bool:
    """Best-effort cancel. Returns ``True`` only if the job was still queued.

    A running job can't be interrupted from Python — submit cancellable
    work yourself if you need that, or use a flag the worker checks.
    """
    with _lock:
        meta = _jobs.get(job_id)
    if meta is None:
        return False
    return meta["future"].cancel()


def reset() -> None:
    """Clear the entire job table. Tests/admin only — never call in app code."""
    with _lock:
        _jobs.clear()
