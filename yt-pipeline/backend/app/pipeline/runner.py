from __future__ import annotations

import asyncio
import traceback
from collections import defaultdict
from typing import Any, AsyncIterator

from ..models import AppSettings, Job, StageName, StageState, utc_now
from ..paths import job_dir
from ..store import load_job, load_settings, save_job
from . import package, script, thumbnail, tts, video

STAGE_ORDER: list[StageName] = ["script", "tts", "video", "thumbnail", "package"]

_listeners: dict[str, list[asyncio.Queue]] = defaultdict(list)
_running: set[str] = set()
_cancel: set[str] = set()


def subscribe(job_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _listeners[job_id].append(q)
    return q


def unsubscribe(job_id: str, q: asyncio.Queue) -> None:
    if job_id in _listeners and q in _listeners[job_id]:
        _listeners[job_id].remove(q)


async def emit(job_id: str, event: dict[str, Any]) -> None:
    for q in list(_listeners.get(job_id, [])):
        await q.put(event)


def _mark_stale_after(job: Job, stage: StageName) -> None:
    idx = STAGE_ORDER.index(stage)
    for later in STAGE_ORDER[idx + 1 :]:
        st = job.stage_state.get(later) or StageState()
        if st.status == "succeeded":
            st.status = "stale"
            st.updated_at = utc_now()
            job.stage_state[later] = st


async def _run_one(settings: AppSettings, job: Job, stage: StageName) -> Job:
    job.progress_message = f"Running {stage}..."
    await emit(job.id, {"type": "stage_start", "stage": stage, "job": job.model_dump()})

    st = job.stage_state.get(stage) or StageState()
    st.status = "running"
    st.attempts += 1
    st.error = None
    st.updated_at = utc_now()
    job.stage_state[stage] = st
    save_job(settings.workspace_dir, job)

    try:
        if stage == "script":
            job = await script.run_script_stage(settings, job)
        elif stage == "tts":
            job = await tts.run_tts_stage(settings, job)
        elif stage == "video":
            job = video.run_video_stage(settings, job)
        elif stage == "thumbnail":
            job = thumbnail.run_thumbnail_stage(settings, job)
        elif stage == "package":
            job = package.run_package_stage(settings, job)
        else:
            raise RuntimeError(f"Unknown stage {stage}")

        st = job.stage_state[stage]
        st.status = "succeeded"
        st.error = None
        st.updated_at = utc_now()
        _mark_stale_after(job, stage)
        # Actually when we succeed a stage, later should be pending/stale until rerun —
        # _mark_stale_after already marks succeeded later as stale.
        save_job(settings.workspace_dir, job)
        await emit(job.id, {"type": "stage_done", "stage": stage, "job": job.model_dump()})
        return job
    except Exception as e:
        st = job.stage_state[stage]
        st.status = "failed"
        st.error = str(e)
        st.updated_at = utc_now()
        job.last_error = str(e)
        job.status = "failed"
        job.progress_message = f"Failed at {stage}: {e}"
        log_path = job_dir(settings.workspace_dir, job.id) / "logs" / "pipeline.log"
        with log_path.open("a") as f:
            f.write(f"\n[{utc_now()}] STAGE {stage} FAILED\n")
            f.write(traceback.format_exc())
            f.write("\n")
        save_job(settings.workspace_dir, job)
        await emit(job.id, {"type": "stage_error", "stage": stage, "error": str(e), "job": job.model_dump()})
        raise


async def run_job(job_id: str, from_stage: StageName | None = None) -> None:
    if job_id in _running:
        await emit(job_id, {"type": "error", "error": "Job already running"})
        return

    _running.add(job_id)
    _cancel.discard(job_id)
    settings = load_settings()
    if not settings.workspace_dir:
        await emit(job_id, {"type": "error", "error": "Workspace not configured"})
        _running.discard(job_id)
        return

    try:
        job = load_job(settings.workspace_dir, job_id)
        job.status = "running"
        job.last_error = None
        save_job(settings.workspace_dir, job)
        await emit(job_id, {"type": "job_start", "job": job.model_dump()})

        start_idx = STAGE_ORDER.index(from_stage) if from_stage else 0
        for stage in STAGE_ORDER[start_idx:]:
            if job_id in _cancel:
                job = load_job(settings.workspace_dir, job_id)
                job.status = "cancelled"
                job.progress_message = "Cancelled"
                save_job(settings.workspace_dir, job)
                await emit(job_id, {"type": "cancelled", "job": job.model_dump()})
                return
            job = load_job(settings.workspace_dir, job_id)
            job = await _run_one(settings, job, stage)

        job = load_job(settings.workspace_dir, job_id)
        if settings.youtube_defaults.stop_for_review and from_stage is None:
            job.status = "needs_review"
            job.progress_message = "Ready for review"
        else:
            job.status = "succeeded"
            job.progress_message = "Complete"
        save_job(settings.workspace_dir, job)
        await emit(job_id, {"type": "job_done", "job": job.model_dump()})
    except Exception as e:
        await emit(job_id, {"type": "error", "error": str(e)})
    finally:
        _running.discard(job_id)
        _cancel.discard(job_id)


def cancel_job(job_id: str) -> None:
    _cancel.add(job_id)


async def event_stream(job_id: str) -> AsyncIterator[dict[str, Any]]:
    q = subscribe(job_id)
    try:
        yield {"type": "connected", "job_id": job_id}
        while True:
            event = await q.get()
            yield event
            if event.get("type") in {"job_done", "cancelled", "error"}:
                break
    finally:
        unsubscribe(job_id, q)
