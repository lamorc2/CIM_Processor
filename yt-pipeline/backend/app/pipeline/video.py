from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..models import AppSettings, Job
from ..paths import job_dir


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def _resolve_clips(job: Job) -> list[Path]:
    clips: list[Path] = []
    for p in job.inputs.video_bed.paths:
        path = Path(p)
        if path.exists() and path.is_file():
            clips.append(path)
    if not clips:
        raise RuntimeError(
            "No valid gameplay clips found. Add at least one video file in the job media bed."
        )
    if job.inputs.video_bed.mode == "single_file":
        return [clips[0]]
    return clips


def _build_filter_timeline(
    clips: list[Path],
    audio_duration: float,
    width: int,
    height: int,
    fps: int,
    loop_if_short: bool,
    mute: bool,
) -> tuple[list[str], str]:
    """Return ffmpeg args input list extras aren't needed — we use concat demuxer approach."""
    # Simpler approach: create a concat list looping clips until duration covered, then trim.
    return [], ""


def run_video_stage(settings: AppSettings, job: Job) -> Job:
    if not job.outputs.audio_path or not Path(job.outputs.audio_path).exists():
        raise RuntimeError("Narration audio missing; run TTS stage first")

    audio = Path(job.outputs.audio_path)
    audio_dur = probe_duration(audio)
    clips = _resolve_clips(job)

    out_dir = job_dir(settings.workspace_dir, job.id) / "stages" / "03_video"
    out_path = out_dir / "final.mp4"
    concat_list = out_dir / "concat.txt"
    bed_path = out_dir / "bed.mp4"

    # Build concat list long enough to cover audio
    needed = audio_dur
    entries: list[str] = []
    total = 0.0
    idx = 0
    safety = 0
    while total < needed + 0.25:
        clip = clips[idx % len(clips)]
        try:
            d = probe_duration(clip)
        except Exception:
            d = 5.0
        entries.append(f"file '{clip.resolve()}'")
        total += d
        idx += 1
        safety += 1
        if safety > 500:
            break
        if not job.inputs.video_bed.loop_if_short and idx >= len(clips) and total < needed:
            raise RuntimeError(
                f"Gameplay clips total {total:.1f}s but narration is {needed:.1f}s. "
                "Add more clips or enable loop_if_short."
            )
        if not job.inputs.video_bed.loop_if_short and idx >= len(clips):
            break

    concat_list.write_text("\n".join(entries) + "\n")

    w = settings.video.width
    h = settings.video.height
    fps = settings.video.fps

    # Create scaled/trimmed video bed (no audio)
    bed_cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
        "-t",
        f"{audio_dur:.3f}",
        "-vf",
        f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps}",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-b:v",
        settings.video.video_bitrate,
        "-pix_fmt",
        "yuv420p",
        str(bed_path),
    ]
    result = subprocess.run(bed_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg bed failed: {result.stderr[-2000:]}")

    # Mux narration
    mux_cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(bed_path),
        "-i",
        str(audio),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        settings.video.audio_bitrate,
        "-shortest",
        str(out_path),
    ]
    result = subprocess.run(mux_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg mux failed: {result.stderr[-2000:]}")

    timeline = {
        "audio_duration_sec": audio_dur,
        "clips": [str(c) for c in clips],
        "mode": job.inputs.video_bed.mode,
        "mute_source_audio": job.inputs.video_bed.mute_source_audio,
    }
    (out_dir / "timeline.json").write_text(json.dumps(timeline, indent=2))
    job.outputs.video_path = str(out_path)
    return job
