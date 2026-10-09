from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

from .models import (
    AppSettings,
    Job,
    JobCreate,
    JobInputs,
    PromptPreset,
    ThumbnailInput,
    VideoBedInput,
    utc_now,
)
from .paths import job_dir, presets_dir, settings_path, workspace_root


def load_settings() -> AppSettings:
    path = settings_path()
    if not path.exists():
        return AppSettings()
    return AppSettings.model_validate_json(path.read_text())


def save_settings(settings: AppSettings) -> AppSettings:
    path = settings_path()
    path.write_text(settings.model_dump_json(indent=2))
    if settings.workspace_dir:
        workspace_root(settings.workspace_dir)
    return settings


def get_api_key(settings_key: str, env_name: str, inline: str = "") -> str:
    if inline.strip():
        return inline.strip()
    return os.environ.get(env_name, "").strip()


def _jobs_index(workspace_dir: str) -> Path:
    return workspace_root(workspace_dir) / "projects" / "index.json"


def list_job_ids(workspace_dir: str) -> list[str]:
    idx = _jobs_index(workspace_dir)
    if not idx.exists():
        # Fall back to directory scan
        projects = workspace_root(workspace_dir) / "projects"
        return sorted(
            p.name for p in projects.iterdir() if p.is_dir() and (p / "job.json").exists()
        )
    return json.loads(idx.read_text())


def _write_index(workspace_dir: str, ids: list[str]) -> None:
    _jobs_index(workspace_dir).write_text(json.dumps(ids, indent=2))


def load_job(workspace_dir: str, job_id: str) -> Job:
    path = job_dir(workspace_dir, job_id) / "job.json"
    if not path.exists():
        raise FileNotFoundError(job_id)
    return Job.model_validate_json(path.read_text())


def save_job(workspace_dir: str, job: Job) -> Job:
    job.updated_at = utc_now()
    path = job_dir(workspace_dir, job.id) / "job.json"
    path.write_text(job.model_dump_json(indent=2))
    ids = list_job_ids(workspace_dir)
    if job.id not in ids:
        ids.insert(0, job.id)
        _write_index(workspace_dir, ids)
    return job


def list_jobs(workspace_dir: str) -> list[Job]:
    jobs: list[Job] = []
    for jid in list_job_ids(workspace_dir):
        try:
            jobs.append(load_job(workspace_dir, jid))
        except FileNotFoundError:
            continue
    jobs.sort(key=lambda j: j.updated_at, reverse=True)
    return jobs


def create_job(workspace_dir: str, payload: JobCreate) -> Job:
    job_id = utc_now()[:10].replace("-", "") + "-" + uuid.uuid4().hex[:8]
    now = utc_now()
    inputs = JobInputs(
        title=payload.title,
        series=payload.series,
        prompt_user=payload.prompt_user,
    )
    if payload.prompt_system:
        inputs.prompt_system = payload.prompt_system
    if payload.script_constraints:
        inputs.script_constraints = payload.script_constraints
    if payload.thumbnail:
        inputs.thumbnail = payload.thumbnail
    else:
        inputs.thumbnail = ThumbnailInput(headline=payload.title[:48].upper())
    if payload.video_bed:
        inputs.video_bed = payload.video_bed
    else:
        inputs.video_bed = VideoBedInput()

    job = Job(id=job_id, status="draft", created_at=now, updated_at=now, inputs=inputs)
    # Copy referenced clips into job folder for reproducibility when they exist
    jd = job_dir(workspace_dir, job_id)
    copied: list[str] = []
    for src in job.inputs.video_bed.paths:
        sp = Path(src)
        if sp.exists() and sp.is_file():
            dest = jd / "inputs" / "gameplay" / sp.name
            if not dest.exists():
                shutil.copy2(sp, dest)
            copied.append(str(dest))
        else:
            copied.append(src)
    job.inputs.video_bed.paths = copied
    return save_job(workspace_dir, job)


def delete_job(workspace_dir: str, job_id: str) -> None:
    jd = job_dir(workspace_dir, job_id)
    if jd.exists():
        shutil.rmtree(jd)
    ids = [i for i in list_job_ids(workspace_dir) if i != job_id]
    _write_index(workspace_dir, ids)


def list_presets() -> list[PromptPreset]:
    out: list[PromptPreset] = []
    for p in presets_dir().glob("*.json"):
        out.append(PromptPreset.model_validate_json(p.read_text()))
    if not out:
        # Seed defaults
        defaults = [
            PromptPreset(
                id="gaming_analysis",
                name="Gaming analysis",
                prompt_system=(
                    "You write punchy YouTube narration for gaming analysis. "
                    "Be concrete, opinionated, and retention-aware. Return strict JSON only."
                ),
                prompt_user_template=(
                    "Topic: {{topic}}\nAudience: players who know the game\n"
                    "Tone: sharp, conversational\nLength: about {{minutes}} minutes\n"
                    "Must cover: {{bullets}}"
                ),
                created_at=utc_now(),
            ),
            PromptPreset(
                id="lore_explainer",
                name="Lore explainer",
                prompt_system=(
                    "You write clear lore explainer narration for YouTube. "
                    "Avoid spoilers unless asked. Return strict JSON only."
                ),
                prompt_user_template=(
                    "Lore topic: {{topic}}\nTone: curious documentary\n"
                    "Length: about {{minutes}} minutes\nInclude: {{bullets}}"
                ),
                created_at=utc_now(),
            ),
        ]
        for d in defaults:
            save_preset(d)
            out.append(d)
    return out


def save_preset(preset: PromptPreset) -> PromptPreset:
    path = presets_dir() / f"{preset.id}.json"
    path.write_text(preset.model_dump_json(indent=2))
    return preset


def scan_library(library_dir: str) -> list[dict]:
    root = Path(library_dir).expanduser() if library_dir else None
    if not root or not root.exists():
        return []
    exts = {".mp4", ".mov", ".mkv", ".webm"}
    clips = []
    for p in sorted(root.rglob("*")):
        if p.suffix.lower() in exts and p.is_file():
            clips.append(
                {
                    "path": str(p.resolve()),
                    "name": p.name,
                    "size_bytes": p.stat().st_size,
                }
            )
    return clips
