from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


StageName = Literal["script", "tts", "video", "thumbnail", "package"]
JobStatus = Literal[
    "draft", "queued", "running", "needs_review", "succeeded", "failed", "cancelled"
]
StageStatus = Literal["pending", "running", "succeeded", "failed", "stale"]


class LLMSettings(BaseModel):
    provider: Literal["openai_compatible", "mock"] = "mock"
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "LLM_API_KEY"
    api_key: str = ""
    model: str = "gpt-4.1-mini"
    temperature: float = 0.7


class TTSSettings(BaseModel):
    provider: Literal["openai", "mock"] = "mock"
    api_key_env: str = "TTS_API_KEY"
    api_key: str = ""
    voice: str = "alloy"
    model: str = "gpt-4o-mini-tts"
    speaking_rate: float = 1.0
    words_per_minute: int = 150


class VideoSettings(BaseModel):
    width: int = 1920
    height: int = 1080
    fps: int = 30
    video_bitrate: str = "6M"
    audio_bitrate: str = "192k"
    gameplay_library_dir: str = ""
    default_bed_mode: Literal["single_file", "shuffle_clips"] = "shuffle_clips"
    crossfade_frames: int = 0


class ThumbnailSettings(BaseModel):
    mode: Literal["template", "upload", "generate"] = "template"
    template_id: str = "bold_title"
    font_path: str = ""
    default_text_color: str = "#FFFFFF"
    default_accent_color: str = "#FF3B30"


class YouTubeDefaults(BaseModel):
    description_footer: str = ""
    default_tags: list[str] = Field(default_factory=lambda: ["gaming", "analysis"])
    visibility: str = "private"
    stop_for_review: bool = True


class AppSettings(BaseModel):
    setup_complete: bool = False
    workspace_dir: str = ""
    llm: LLMSettings = Field(default_factory=LLMSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    video: VideoSettings = Field(default_factory=VideoSettings)
    thumbnail: ThumbnailSettings = Field(default_factory=ThumbnailSettings)
    youtube_defaults: YouTubeDefaults = Field(default_factory=YouTubeDefaults)


class ScriptConstraints(BaseModel):
    target_duration_sec: int = 720
    word_count_min: int = 1400
    word_count_max: int = 2000
    include_hook: bool = True
    include_cta: bool = True
    banned_phrases: list[str] = Field(
        default_factory=lambda: ["in conclusion", "as an AI"]
    )


class ThumbnailInput(BaseModel):
    mode: Literal["template", "upload", "generate"] = "template"
    headline: str = ""
    subheadline: str = ""
    source_image_path: str = ""
    template_id: str = "bold_title"
    style_prompt: str = ""
    text_color: str = "#FFFFFF"
    accent_color: str = "#FF3B30"


class VideoBedInput(BaseModel):
    mode: Literal["single_file", "shuffle_clips"] = "shuffle_clips"
    paths: list[str] = Field(default_factory=list)
    mute_source_audio: bool = True
    loop_if_short: bool = True


class TTSJobOverride(BaseModel):
    voice_override: str | None = None
    speaking_rate_override: float | None = None


class JobInputs(BaseModel):
    title: str = ""
    series: str = ""
    prompt_system: str = (
        "You write punchy YouTube narration for gaming analysis videos. "
        "Return strict JSON only."
    )
    prompt_user: str = ""
    script_constraints: ScriptConstraints = Field(default_factory=ScriptConstraints)
    thumbnail: ThumbnailInput = Field(default_factory=ThumbnailInput)
    video_bed: VideoBedInput = Field(default_factory=VideoBedInput)
    tts: TTSJobOverride = Field(default_factory=TTSJobOverride)


class StageState(BaseModel):
    status: StageStatus = "pending"
    attempts: int = 0
    error: str | None = None
    updated_at: str | None = None


class JobOutputs(BaseModel):
    script_path: str | None = None
    script_json_path: str | None = None
    audio_path: str | None = None
    video_path: str | None = None
    thumbnail_path: str | None = None
    package_dir: str | None = None


class Job(BaseModel):
    id: str
    status: JobStatus = "draft"
    created_at: str
    updated_at: str
    inputs: JobInputs = Field(default_factory=JobInputs)
    outputs: JobOutputs = Field(default_factory=JobOutputs)
    stage_state: dict[str, StageState] = Field(
        default_factory=lambda: {
            "script": StageState(),
            "tts": StageState(),
            "video": StageState(),
            "thumbnail": StageState(),
            "package": StageState(),
        }
    )
    last_error: str | None = None
    progress_message: str = ""


class JobCreate(BaseModel):
    title: str
    series: str = ""
    prompt_system: str | None = None
    prompt_user: str = ""
    script_constraints: ScriptConstraints | None = None
    thumbnail: ThumbnailInput | None = None
    video_bed: VideoBedInput | None = None


class JobUpdate(BaseModel):
    inputs: JobInputs | None = None
    script_markdown: str | None = None
    status: JobStatus | None = None


class RunRequest(BaseModel):
    from_stage: StageName | None = None


class HealthResponse(BaseModel):
    ok: bool
    ffmpeg: bool
    ffprobe: bool
    workspace_configured: bool
    setup_complete: bool
    llm_provider: str
    tts_provider: str
    detail: dict[str, Any] = Field(default_factory=dict)


class PromptPreset(BaseModel):
    id: str
    name: str
    prompt_system: str
    prompt_user_template: str
    created_at: str


class ThumbnailPreviewRequest(BaseModel):
    headline: str
    subheadline: str = ""
    text_color: str = "#FFFFFF"
    accent_color: str = "#FF3B30"
    source_image_path: str = ""
    template_id: str = "bold_title"
