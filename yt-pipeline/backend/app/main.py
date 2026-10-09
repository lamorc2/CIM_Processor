from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .models import (
    AppSettings,
    HealthResponse,
    JobCreate,
    JobUpdate,
    PromptPreset,
    RunRequest,
    ThumbnailPreviewRequest,
    utc_now,
)
from .paths import data_dir, job_dir
from .pipeline import runner
from .pipeline.thumbnail import preview_thumbnail
from .store import (
    create_job,
    delete_job,
    list_jobs,
    list_presets,
    load_job,
    load_settings,
    save_job,
    save_preset,
    save_settings,
    scan_library,
)

app = FastAPI(title="YT Pipeline", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_workspace() -> AppSettings:
    settings = load_settings()
    if not settings.workspace_dir:
        raise HTTPException(400, "Workspace not configured. Complete Setup first.")
    return settings


def _which(cmd: str) -> bool:
    return shutil.which(cmd) is not None


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = load_settings()
    return HealthResponse(
        ok=True,
        ffmpeg=_which("ffmpeg"),
        ffprobe=_which("ffprobe"),
        workspace_configured=bool(settings.workspace_dir),
        setup_complete=settings.setup_complete,
        llm_provider=settings.llm.provider,
        tts_provider=settings.tts.provider,
        detail={"data_dir": str(data_dir())},
    )


@app.get("/api/settings")
def get_settings() -> dict:
    settings = load_settings()
    data = settings.model_dump()
    # Never echo full keys to casual logs in UI — mask if long
    if data["llm"].get("api_key"):
        data["llm"]["api_key_set"] = True
        data["llm"]["api_key"] = "••••" if settings.llm.api_key else ""
    else:
        data["llm"]["api_key_set"] = False
    if data["tts"].get("api_key"):
        data["tts"]["api_key_set"] = True
        data["tts"]["api_key"] = "••••" if settings.tts.api_key else ""
    else:
        data["tts"]["api_key_set"] = False
    # Return actual keys only via a flag — UI sends new keys on save; keep raw for local use
    # For local single-user, return raw keys so setup form can round-trip. Mask above breaks that.
    raw = settings.model_dump()
    raw["llm"]["api_key_set"] = bool(settings.llm.api_key)
    raw["tts"]["api_key_set"] = bool(settings.tts.api_key)
    return raw


@app.put("/api/settings")
def put_settings(payload: AppSettings) -> AppSettings:
    # Preserve keys if masked placeholder sent
    existing = load_settings()
    if payload.llm.api_key in {"", "••••"} and existing.llm.api_key:
        payload.llm.api_key = existing.llm.api_key
    if payload.tts.api_key in {"", "••••"} and existing.tts.api_key:
        payload.tts.api_key = existing.tts.api_key
    if payload.workspace_dir:
        Path(payload.workspace_dir).expanduser().mkdir(parents=True, exist_ok=True)
    return save_settings(payload)


@app.post("/api/settings/test-llm")
async def test_llm() -> dict:
    settings = load_settings()
    if settings.llm.provider == "mock":
        return {"ok": True, "message": "Mock LLM ready (no network call)."}
    from .store import get_api_key
    import httpx

    key = get_api_key(settings.llm.api_key_env, settings.llm.api_key_env, settings.llm.api_key)
    if not key:
        raise HTTPException(400, "LLM API key missing")
    url = settings.llm.base_url.rstrip("/") + "/chat/completions"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": settings.llm.model,
                "messages": [{"role": "user", "content": "Reply with exactly: ok"}],
                "max_tokens": 8,
            },
        )
        if resp.status_code >= 400:
            raise HTTPException(400, f"LLM test failed: {resp.text[:500]}")
    return {"ok": True, "message": "LLM reachable"}


@app.post("/api/settings/test-tts")
async def test_tts() -> dict:
    settings = load_settings()
    if settings.tts.provider == "mock":
        return {"ok": True, "message": "Mock TTS ready (generates tone wav)."}
    from .store import get_api_key
    import httpx

    key = get_api_key(settings.tts.api_key_env, settings.tts.api_key_env, settings.tts.api_key)
    if not key:
        raise HTTPException(400, "TTS API key missing")
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": settings.tts.model,
                "voice": settings.tts.voice,
                "input": "Pipeline voice check.",
                "format": "wav",
            },
        )
        if resp.status_code >= 400:
            raise HTTPException(400, f"TTS test failed: {resp.text[:500]}")
    return {"ok": True, "message": "TTS reachable", "bytes": len(resp.content)}


@app.get("/api/presets")
def get_presets() -> list[PromptPreset]:
    return list_presets()


@app.post("/api/presets")
def post_preset(preset: PromptPreset) -> PromptPreset:
    if not preset.created_at:
        preset.created_at = utc_now()
    return save_preset(preset)


@app.get("/api/jobs")
def get_jobs() -> list:
    settings = _require_workspace()
    return [j.model_dump() for j in list_jobs(settings.workspace_dir)]


@app.post("/api/jobs")
def post_job(payload: JobCreate) -> dict:
    settings = _require_workspace()
    if not payload.title.strip():
        raise HTTPException(400, "Title is required")
    job = create_job(settings.workspace_dir, payload)
    return job.model_dump()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    settings = _require_workspace()
    try:
        return load_job(settings.workspace_dir, job_id).model_dump()
    except FileNotFoundError:
        raise HTTPException(404, "Job not found")


@app.patch("/api/jobs/{job_id}")
def patch_job(job_id: str, payload: JobUpdate) -> dict:
    settings = _require_workspace()
    try:
        job = load_job(settings.workspace_dir, job_id)
    except FileNotFoundError:
        raise HTTPException(404, "Job not found")

    if payload.inputs is not None:
        job.inputs = payload.inputs
    if payload.status is not None:
        job.status = payload.status
    if payload.script_markdown is not None:
        jd = job_dir(settings.workspace_dir, job_id)
        script_path = jd / "stages" / "01_script" / "script.md"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(payload.script_markdown)
        job.outputs.script_path = str(script_path)
        # Invalidate downstream
        for stage in ("tts", "video", "package"):
            st = job.stage_state[stage]
            if st.status == "succeeded":
                st.status = "stale"
                st.updated_at = utc_now()
    save_job(settings.workspace_dir, job)
    return job.model_dump()


@app.delete("/api/jobs/{job_id}")
def remove_job(job_id: str) -> dict:
    settings = _require_workspace()
    delete_job(settings.workspace_dir, job_id)
    return {"ok": True}


@app.post("/api/jobs/{job_id}/run")
async def run_job(job_id: str, payload: RunRequest | None = None) -> dict:
    settings = _require_workspace()
    try:
        load_job(settings.workspace_dir, job_id)
    except FileNotFoundError:
        raise HTTPException(404, "Job not found")
    from_stage = payload.from_stage if payload else None
    asyncio.create_task(runner.run_job(job_id, from_stage))
    return {"ok": True, "started": True, "from_stage": from_stage}


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    runner.cancel_job(job_id)
    return {"ok": True}


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str) -> StreamingResponse:
    async def gen():
        async for event in runner.event_stream(job_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/jobs/{job_id}/files/{kind}")
def get_job_file(job_id: str, kind: str):
    settings = _require_workspace()
    try:
        job = load_job(settings.workspace_dir, job_id)
    except FileNotFoundError:
        raise HTTPException(404, "Job not found")

    mapping = {
        "script": job.outputs.script_path,
        "audio": job.outputs.audio_path,
        "video": job.outputs.video_path,
        "thumbnail": job.outputs.thumbnail_path,
    }
    path = mapping.get(kind)
    if not path or not Path(path).exists():
        raise HTTPException(404, f"{kind} not available")
    return FileResponse(path)


@app.get("/api/jobs/{job_id}/script")
def get_script(job_id: str) -> dict:
    settings = _require_workspace()
    jd = job_dir(settings.workspace_dir, job_id)
    path = jd / "stages" / "01_script" / "script.md"
    if not path.exists():
        return {"text": ""}
    return {"text": path.read_text()}


@app.post("/api/jobs/{job_id}/upload-clip")
async def upload_clip(job_id: str, file: UploadFile = File(...)) -> dict:
    settings = _require_workspace()
    try:
        job = load_job(settings.workspace_dir, job_id)
    except FileNotFoundError:
        raise HTTPException(404, "Job not found")
    dest_dir = job_dir(settings.workspace_dir, job_id) / "inputs" / "gameplay"
    dest = dest_dir / (file.filename or "clip.mp4")
    content = await file.read()
    dest.write_bytes(content)
    paths = list(job.inputs.video_bed.paths)
    if str(dest) not in paths:
        paths.append(str(dest))
    job.inputs.video_bed.paths = paths
    save_job(settings.workspace_dir, job)
    return {"path": str(dest), "job": job.model_dump()}


@app.post("/api/jobs/{job_id}/upload-thumb-source")
async def upload_thumb_source(job_id: str, file: UploadFile = File(...)) -> dict:
    settings = _require_workspace()
    try:
        job = load_job(settings.workspace_dir, job_id)
    except FileNotFoundError:
        raise HTTPException(404, "Job not found")
    dest_dir = job_dir(settings.workspace_dir, job_id) / "inputs" / "thumbnail_src"
    dest = dest_dir / (file.filename or "thumb_src.jpg")
    dest.write_bytes(await file.read())
    job.inputs.thumbnail.source_image_path = str(dest)
    save_job(settings.workspace_dir, job)
    return {"path": str(dest), "job": job.model_dump()}


@app.get("/api/library/clips")
def library_clips() -> list:
    settings = load_settings()
    lib = settings.video.gameplay_library_dir
    if not lib and settings.workspace_dir:
        lib = str(Path(settings.workspace_dir) / "gameplay")
    return scan_library(lib)


@app.post("/api/thumbnails/preview")
def thumb_preview(req: ThumbnailPreviewRequest) -> Response:
    settings = load_settings()
    data = preview_thumbnail(settings, req)
    return Response(content=data, media_type="image/jpeg")


# Optional: serve built frontend if present
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="ui")


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8787, reload=True)


if __name__ == "__main__":
    run()
