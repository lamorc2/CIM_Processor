from __future__ import annotations

import os
from pathlib import Path

# App data lives next to the backend by default (overridable via YT_PIPELINE_DATA)
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = Path(os.environ.get("YT_PIPELINE_DATA", str(_BACKEND_ROOT / "data")))


def data_dir() -> Path:
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_DATA_DIR


def settings_path() -> Path:
    p = data_dir() / "config"
    p.mkdir(parents=True, exist_ok=True)
    return p / "settings.json"


def presets_dir() -> Path:
    p = data_dir() / "config" / "prompt_presets"
    p.mkdir(parents=True, exist_ok=True)
    return p


def workspace_root(workspace_dir: str) -> Path:
    root = Path(workspace_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / "projects").mkdir(exist_ok=True)
    (root / "gameplay").mkdir(exist_ok=True)
    return root


def job_dir(workspace_dir: str, job_id: str) -> Path:
    d = workspace_root(workspace_dir) / "projects" / job_id
    for sub in (
        "inputs/gameplay",
        "inputs/thumbnail_src",
        "stages/01_script",
        "stages/02_tts",
        "stages/03_video",
        "stages/04_thumbnail",
        "export",
        "logs",
    ):
        (d / sub).mkdir(parents=True, exist_ok=True)
    return d
