from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..models import AppSettings, Job
from ..paths import job_dir


def run_package_stage(settings: AppSettings, job: Job) -> Job:
    jd = job_dir(settings.workspace_dir, job.id)
    export = jd / "export"
    export.mkdir(parents=True, exist_ok=True)

    if not job.outputs.video_path or not Path(job.outputs.video_path).exists():
        raise RuntimeError("Final video missing; run video stage first")
    if not job.outputs.thumbnail_path or not Path(job.outputs.thumbnail_path).exists():
        raise RuntimeError("Thumbnail missing; run thumbnail stage first")

    shutil.copy2(job.outputs.video_path, export / "final.mp4")
    shutil.copy2(job.outputs.thumbnail_path, export / "thumbnail.jpg")

    description = ""
    tags: list[str] = list(settings.youtube_defaults.default_tags)
    script_json = jd / "stages" / "01_script" / "script.json"
    if script_json.exists():
        data = json.loads(script_json.read_text())
        description = data.get("youtube_description") or ""
        tags = data.get("tags") or tags

    footer = settings.youtube_defaults.description_footer.strip()
    if footer:
        description = f"{description.rstrip()}\n\n{footer}"

    (export / "title.txt").write_text(job.inputs.title.strip() + "\n")
    (export / "description.txt").write_text(description.strip() + "\n")
    (export / "tags.txt").write_text(", ".join(tags) + "\n")
    metadata = {
        "job_id": job.id,
        "title": job.inputs.title,
        "series": job.inputs.series,
        "llm_provider": settings.llm.provider,
        "tts_provider": settings.tts.provider,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "visibility_default": settings.youtube_defaults.visibility,
    }
    (export / "metadata.json").write_text(json.dumps(metadata, indent=2))
    job.outputs.package_dir = str(export)
    return job
