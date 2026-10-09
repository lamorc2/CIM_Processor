from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

from ..models import AppSettings, Job
from ..paths import job_dir
from ..store import get_api_key

SCRIPT_SCHEMA_HINT = """
Return ONLY valid JSON with these keys:
{
  "narration_script": "full spoken script as plain text",
  "sections": [{"heading": "...", "narration": "..."}],
  "youtube_description": "...",
  "tags": ["tag1", "tag2"],
  "thumbnail_headline_ideas": ["...", "...", "..."]
}
"""


def estimate_duration_sec(text: str, wpm: int = 150) -> int:
    words = len(re.findall(r"\b\w+\b", text))
    return max(1, int(words / max(wpm, 1) * 60))


def _mock_script(job: Job) -> dict:
    title = job.inputs.title or "Untitled"
    topic = job.inputs.prompt_user or title
    target = job.inputs.script_constraints.target_duration_sec
    # Aim ~150 wpm → words ≈ duration/60 * 150
    target_words = max(200, int(target / 60 * 150))
    paragraphs = []
    paragraphs.append(
        f"Today we're breaking down {title}. If you've been around this game, "
        f"you already know why this moment keeps coming up — and if you haven't, "
        f"you're about to see why people won't shut up about it."
    )
    # Expand with filler that still reads like narration
    seed_points = [
        f"Let's set the stage. {topic[:280]}",
        "The first thing that stands out is how the design teaches you one lesson, then punishes you for trusting it.",
        "Most players blame their mechanics. The real issue is information — what the game shows you versus what it actually expects.",
        "Watch the pacing. The quiet stretch isn't filler; it's loading the trap.",
        "Community takes usually overfit one clip. Zoom out and the pattern is clearer.",
        "There's a clean counterplay line once you stop reacting and start reading the tell.",
        "If you're stuck, change the question you're asking. Not 'how do I dodge' — 'when am I allowed to act'.",
        "That's the difference between a clip that goes viral and a run that actually clears.",
    ]
    body = []
    while len(" ".join(paragraphs + body).split()) < target_words:
        body.append(seed_points[len(body) % len(seed_points)])
        body.append(
            "Stay with me for this next beat, because this is where most guides hand-wave the hard part."
        )
    if job.inputs.script_constraints.include_cta:
        body.append(
            "If this helped, subscribe — I'm covering more of these breakdowns every week."
        )
    sections = [
        {"heading": "Hook", "narration": paragraphs[0]},
        {"heading": "Breakdown", "narration": " ".join(body[:-1] if len(body) > 1 else body)},
    ]
    if job.inputs.script_constraints.include_cta and body:
        sections.append({"heading": "CTA", "narration": body[-1]})
    narration = "\n\n".join(s["narration"] for s in sections)
    return {
        "narration_script": narration,
        "sections": sections,
        "youtube_description": f"{title}\n\n{topic[:400]}\n\n#gaming #analysis",
        "tags": ["gaming", "analysis", "breakdown", "guide"],
        "thumbnail_headline_ideas": [
            title[:42].upper(),
            "THIS CHANGES EVERYTHING",
            "PLAYERS STILL MISS THIS",
        ],
    }


async def _llm_script(settings: AppSettings, job: Job) -> dict:
    key = get_api_key(settings.llm.api_key_env, settings.llm.api_key_env, settings.llm.api_key)
    if not key:
        raise RuntimeError("LLM API key missing. Set it in Setup or LLM_API_KEY env.")

    user = (
        f"Title: {job.inputs.title}\n"
        f"Series: {job.inputs.series}\n"
        f"Constraints: {job.inputs.script_constraints.model_dump_json()}\n\n"
        f"{job.inputs.prompt_user}\n\n{SCRIPT_SCHEMA_HINT}"
    )
    payload = {
        "model": settings.llm.model,
        "temperature": settings.llm.temperature,
        "messages": [
            {"role": "system", "content": job.inputs.prompt_system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    url = settings.llm.base_url.rstrip("/") + "/chat/completions"
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {key}"},
            json=payload,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
    data = json.loads(content)
    if "narration_script" not in data:
        raise RuntimeError("LLM response missing narration_script")
    return data


def _write_script_files(workspace_dir: str, job: Job, data: dict) -> None:
    jd = job_dir(workspace_dir, job.id)
    script_dir = jd / "stages" / "01_script"
    md_path = script_dir / "script.md"
    json_path = script_dir / "script.json"
    md_path.write_text(data["narration_script"].strip() + "\n")
    json_path.write_text(json.dumps(data, indent=2))
    job.outputs.script_path = str(md_path)
    job.outputs.script_json_path = str(json_path)


async def run_script_stage(settings: AppSettings, job: Job) -> Job:
    if settings.llm.provider == "mock":
        data = _mock_script(job)
    else:
        data = await _llm_script(settings, job)

    # Strip banned phrases lightly
    text = data["narration_script"]
    for phrase in job.inputs.script_constraints.banned_phrases:
        text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)
    data["narration_script"] = re.sub(r"\s+", " ", text).strip()
    if data.get("sections"):
        for sec in data["sections"]:
            for phrase in job.inputs.script_constraints.banned_phrases:
                sec["narration"] = re.sub(
                    re.escape(phrase), "", sec.get("narration", ""), flags=re.IGNORECASE
                )

    _write_script_files(settings.workspace_dir, job, data)
    return job


def load_script_text(workspace_dir: str, job: Job) -> str:
    if job.outputs.script_path and Path(job.outputs.script_path).exists():
        return Path(job.outputs.script_path).read_text()
    jd = job_dir(workspace_dir, job.id) / "stages" / "01_script" / "script.md"
    if jd.exists():
        return jd.read_text()
    raise FileNotFoundError("Script not generated yet")
