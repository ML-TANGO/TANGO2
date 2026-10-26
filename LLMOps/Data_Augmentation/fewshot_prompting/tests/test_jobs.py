"""jobs.py: single-worker queue, progress reporting, retention."""

from __future__ import annotations

import threading
import time

from src import jobs
from src.jobs import JobStore


def _wait_done(store: JobStore, job_id: str, timeout: float = 5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = store.get(job_id)
        if job is not None and job.status in ("completed", "failed"):
            return job
        time.sleep(0.01)
    raise AssertionError(f"{job_id} did not finish")


def test_progress_is_capped_below_100_until_completion():
    store = JobStore()
    started, release = threading.Event(), threading.Event()

    def fn(set_progress):
        set_progress(150)
        started.set()
        release.wait(5)
        return {"ok": True}

    job = store.submit(fn)
    assert started.wait(5)
    assert store.get(job.job_id).status == "running"
    assert store.get(job.job_id).progress == 99
    release.set()
    done = _wait_done(store, job.job_id)
    assert (done.status, done.progress, done.result) == ("completed", 100, {"ok": True})


def test_jobs_run_one_at_a_time():
    store = JobStore()
    release = threading.Event()
    first = store.submit(lambda set_progress: release.wait(5))
    second = store.submit(lambda set_progress: "second")
    time.sleep(0.1)
    assert store.get(second.job_id).status == "pending"
    release.set()
    assert _wait_done(store, second.job_id).result == "second"
    assert _wait_done(store, first.job_id).status == "completed"


def test_finished_jobs_expire_after_ttl(monkeypatch):
    monkeypatch.setattr(jobs, "JOB_TTL_SECONDS", 0)
    store = JobStore()
    job = store.submit(lambda set_progress: "x")
    deadline = time.time() + 5
    while store._jobs[job.job_id]._finished_ts is None and time.time() < deadline:
        time.sleep(0.01)
    time.sleep(0.01)
    assert store.get(job.job_id) is None


def test_only_the_newest_finished_jobs_are_kept(monkeypatch):
    monkeypatch.setattr(jobs, "MAX_FINISHED_JOBS", 2)
    store = JobStore()
    ids = []
    for i in range(3):
        ids.append(store.submit(lambda set_progress, i=i: i).job_id)
        _wait_done(store, ids[-1])
        time.sleep(0.01)
    assert store.get(ids[0]) is None
    assert store.get(ids[1]) is not None and store.get(ids[2]) is not None
