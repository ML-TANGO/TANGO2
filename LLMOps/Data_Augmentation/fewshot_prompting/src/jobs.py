"""In-memory job store for the async ``/run`` -> ``/status`` pattern.

``POST /run`` submits the optimization as a job and returns a ``job_id``
immediately; the platform polls ``GET /status?job_id=...`` until the job
reaches ``completed`` / ``failed`` (see ``README.md``).

Jobs run on a single-worker executor: optimizations share one LLM endpoint, so
running them concurrently would only contend for the same GPU. Queued jobs
report ``pending``. Finished jobs are kept for ``JOB_TTL_SECONDS`` (or until
``MAX_FINISHED_JOBS`` is exceeded, oldest first) and then purged — single
uvicorn process only; a restart loses all jobs.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

JOB_TTL_SECONDS = int(os.environ.get("JOB_TTL_SECONDS", "3600"))
MAX_FINISHED_JOBS = int(os.environ.get("MAX_FINISHED_JOBS", "100"))

# fn(set_progress) -> result; set_progress accepts 0..100
JobFn = Callable[[Callable[[int], None]], Any]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Job:
    job_id: str
    status: str = "pending"  # pending | running | completed | failed
    progress: int = 0
    created_at: str = field(default_factory=_now_iso)
    started_at: str | None = None
    finished_at: str | None = None
    result: Any = None
    error_code: str | None = None
    error_message: str | None = None
    _finished_ts: float | None = None


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="job")

    def submit(self, fn: JobFn) -> Job:
        job = Job(job_id=f"job-{uuid.uuid4().hex[:12]}")
        with self._lock:
            self._purge_locked()
            self._jobs[job.job_id] = job
        self._executor.submit(self._run, job, fn)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            self._purge_locked()
            return self._jobs.get(job_id)

    def _run(self, job: Job, fn: JobFn) -> None:
        def set_progress(pct: int) -> None:
            job.progress = max(0, min(99, int(pct)))

        job.status = "running"
        job.started_at = _now_iso()
        set_progress(1)
        try:
            result = fn(set_progress)
            job.result = result.model_dump() if hasattr(result, "model_dump") else result
            job.status = "completed"
            job.progress = 100
        except ValueError as e:
            job.status = "failed"
            job.error_code = "INVALID_PARAMS"
            job.error_message = str(e)
        except Exception as e:  # noqa: BLE001 — job failure must be observable via /status
            job.status = "failed"
            job.error_code = "INTERNAL_ERROR"
            job.error_message = f"{type(e).__name__}: {e}"
        finally:
            job.finished_at = _now_iso()
            job._finished_ts = time.time()

    def _purge_locked(self) -> None:
        now = time.time()
        finished = [
            j for j in self._jobs.values()
            if j._finished_ts is not None
        ]
        for j in finished:
            if now - j._finished_ts > JOB_TTL_SECONDS:
                self._jobs.pop(j.job_id, None)
        finished = [j for j in finished if j.job_id in self._jobs]
        if len(finished) > MAX_FINISHED_JOBS:
            finished.sort(key=lambda j: j._finished_ts or 0.0)
            for j in finished[: len(finished) - MAX_FINISHED_JOBS]:
                self._jobs.pop(j.job_id, None)
