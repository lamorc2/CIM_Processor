from __future__ import annotations

import math
import struct
import subprocess
import wave
from pathlib import Path

import httpx

from ..models import AppSettings, Job
from ..paths import job_dir
from ..store import get_api_key
from .script import estimate_duration_sec, load_script_text


def _write_tone_wav(path: Path, duration_sec: float, sample_rate: int = 24000) -> None:
    """Generate a quiet tone bed as a stand-in narration for mock TTS."""
    n_samples = int(duration_sec * sample_rate)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            # Very quiet soft tone + silence-ish envelope so file isn't pure digital silence
            t = i / sample_rate
            amp = 800 if int(t * 2) % 2 == 0 else 200
            sample = int(amp * math.sin(2 * math.pi * 220 * t))
            frames += struct.pack("<h", sample)
        wf.writeframes(frames)


def _chunk_text(text: str, max_chars: int = 3500) -> list[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    parts = text.split("\n\n")
    buf = ""
    for part in parts:
        if len(buf) + len(part) + 2 <= max_chars:
            buf = f"{buf}\n\n{part}".strip()
        else:
            if buf:
                chunks.append(buf)
            if len(part) > max_chars:
                # hard split
                for i in range(0, len(part), max_chars):
                    chunks.append(part[i : i + max_chars])
                buf = ""
            else:
                buf = part
    if buf:
        chunks.append(buf)
    return chunks


async def _openai_tts(settings: AppSettings, job: Job, text: str, out_path: Path) -> None:
    key = get_api_key(settings.tts.api_key_env, settings.tts.api_key_env, settings.tts.api_key)
    if not key:
        raise RuntimeError("TTS API key missing. Set it in Setup or TTS_API_KEY env.")

    voice = job.inputs.tts.voice_override or settings.tts.voice
    rate = job.inputs.tts.speaking_rate_override or settings.tts.speaking_rate
    chunks = _chunk_text(text)
    tmp_files: list[Path] = []
    async with httpx.AsyncClient(timeout=180) as client:
        for i, chunk in enumerate(chunks):
            payload = {
                "model": settings.tts.model,
                "voice": voice,
                "input": chunk,
                "format": "wav",
                "speed": rate,
            }
            resp = await client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
            )
            resp.raise_for_status()
            part = out_path.parent / f"part_{i:03d}.wav"
            part.write_bytes(resp.content)
            tmp_files.append(part)

    if len(tmp_files) == 1:
        tmp_files[0].replace(out_path)
        return

    # Concat with ffmpeg
    list_file = out_path.parent / "concat.txt"
    list_file.write_text("\n".join(f"file '{p.name}'" for p in tmp_files) + "\n")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )
    for p in tmp_files:
        p.unlink(missing_ok=True)


async def run_tts_stage(settings: AppSettings, job: Job) -> Job:
    text = load_script_text(settings.workspace_dir, job).strip()
    if not text:
        raise RuntimeError("Script is empty")

    out = job_dir(settings.workspace_dir, job.id) / "stages" / "02_tts" / "narration.wav"

    if settings.tts.provider == "mock":
        wpm = settings.tts.words_per_minute
        duration = estimate_duration_sec(text, wpm)
        # Keep mock videos short enough for CI/smoke unless target is already short
        duration = min(duration, max(8, min(job.inputs.script_constraints.target_duration_sec, 30)))
        _write_tone_wav(out, float(duration))
    else:
        await _openai_tts(settings, job, text, out)

    # Loudness normalize lightly via ffmpeg if available
    norm = out.with_name("narration_norm.wav")
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(out),
                "-af",
                "loudnorm=I=-16:TP=-1.5:LRA=11",
                str(norm),
            ],
            check=True,
            capture_output=True,
        )
        norm.replace(out)
    except subprocess.CalledProcessError:
        pass

    job.outputs.audio_path = str(out)
    return job
