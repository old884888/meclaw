"""In-memory runtime status for brain trace and background jobs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ...storage.common import now_iso

# session_id -> latest trace
_session_traces: dict[str, dict[str, Any]] = {}

# session_id -> latest cache usage { read, create, hit_rate, supported, updated_at }
_session_cache: dict[str, dict[str, Any]] = {}

# bot_id -> background job status
_bot_jobs: dict[str, dict[str, Any]] = {}


def _default_jobs() -> dict[str, Any]:
    return {
        "l1_extraction": {
            "status": "idle",
            "model": "",
            "last_run_at": "",
            "created_count": 0,
            "last_error": "",
            "last_warning": "",
        },
        "tier3_summary": {
            "status": "idle",
            "model": "",
            "last_run_at": "",
            "last_error": "",
        },
        "learner": {
            "status": "disabled",
            "pending_signals": 0,
            "pending_candidates": 0,
            "last_run_at": "",
            "last_error": "",
        },
        "consolidation": {
            "status": "idle",
            "last_run_at": "",
            "last_stats": {},
            "last_error": "",
        },
    }


def save_session_trace(session_id: str, trace: dict[str, Any]) -> None:
    if not session_id:
        return
    _session_traces[session_id] = deepcopy(trace)


def get_session_trace(session_id: str) -> dict[str, Any]:
    return deepcopy(_session_traces.get(session_id) or {})


def save_session_cache_usage(session_id: str, usage: dict[str, Any]) -> None:
    if not session_id:
        return
    _session_cache[session_id] = {**deepcopy(usage), "updated_at": now_iso()}


def get_session_cache_usage(session_id: str) -> dict[str, Any]:
    return deepcopy(_session_cache.get(session_id) or {})


def jobs_for_bot(bot_id: str) -> dict[str, Any]:
    return deepcopy(_bot_jobs.get(bot_id) or _default_jobs())


def _ensure_bot(bot_id: str) -> dict[str, Any]:
    if bot_id not in _bot_jobs:
        _bot_jobs[bot_id] = _default_jobs()
    return _bot_jobs[bot_id]


def mark_job_running(bot_id: str, job: str, *, model: str = "") -> None:
    jobs = _ensure_bot(bot_id)
    if job not in jobs:
        return
    jobs[job]["status"] = "running"
    if model:
        jobs[job]["model"] = model


def mark_job_success(
    bot_id: str,
    job: str,
    *,
    model: str = "",
    created_count: int = 0,
    warning: str = "",
    stats: dict | None = None,
) -> None:
    jobs = _ensure_bot(bot_id)
    if job not in jobs:
        return
    jobs[job]["status"] = "success"
    jobs[job]["last_run_at"] = now_iso()
    if model:
        jobs[job]["model"] = model
    if job == "l1_extraction":
        jobs[job]["created_count"] = int(created_count)
        jobs[job]["last_warning"] = str(warning or "")[:500]
    if job == "consolidation" and stats is not None:
        jobs[job]["last_stats"] = deepcopy(stats)
    jobs[job]["last_error"] = ""


def mark_job_failed(bot_id: str, job: str, error: str, *, model: str = "") -> None:
    jobs = _ensure_bot(bot_id)
    if job not in jobs:
        return
    jobs[job]["status"] = "failed"
    jobs[job]["last_run_at"] = now_iso()
    jobs[job]["last_error"] = str(error or "")[:500]
    if model:
        jobs[job]["model"] = model


def set_learner_status(bot_id: str, enabled: bool) -> None:
    jobs = _ensure_bot(bot_id)
    jobs["learner"]["status"] = "idle" if enabled else "disabled"


def bump_learner_signal(bot_id: str) -> None:
    jobs = _ensure_bot(bot_id)
    if jobs["learner"]["status"] == "disabled":
        return
    jobs["learner"]["pending_signals"] = int(jobs["learner"].get("pending_signals") or 0) + 1
    jobs["learner"]["last_run_at"] = now_iso()
    jobs["learner"]["status"] = "success"


def set_learner_pending_count(bot_id: str, count: int) -> None:
    jobs = _ensure_bot(bot_id)
    jobs["learner"]["pending_candidates"] = int(count or 0)
