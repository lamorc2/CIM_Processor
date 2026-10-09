# Pipecast — local YouTube automation pipeline

Local-first app that turns **title + prompts + gameplay clips + thumbnail settings** into a YouTube-ready export package:

`script → TTS → FFmpeg mux → thumbnail → export/`

See [`../docs/automated-youtube-pipeline-spec.md`](../docs/automated-youtube-pipeline-spec.md) for the full product spec.

## Stack

- **API:** FastAPI (`backend/`) on `127.0.0.1:8787`
- **UI:** React + Vite (`frontend/`) on `127.0.0.1:5173`
- **Video:** FFmpeg / FFprobe
- **Providers:** `mock` (offline) or OpenAI-compatible LLM / OpenAI TTS

## Quick start

```bash
cd yt-pipeline
make install
make fixtures
make backend    # terminal 1
make frontend   # terminal 2
```

Open http://127.0.0.1:5173 → **Setup** → set workspace dir → save & finish → create a job.

For a one-shot smoke run (mock providers, no API keys):

```bash
make smoke
```

## Setup checklist

1. Workspace directory (projects + exports live here)
2. FFmpeg installed (`ffmpeg`, `ffprobe` on PATH)
3. LLM provider (`mock` or `openai_compatible` + key)
4. TTS provider (`mock` or `openai` + key)
5. Gameplay library folder (optional; you can also upload per job)

Copy `.env.example` to `.env` if you want keys in the environment (`LLM_API_KEY`, `TTS_API_KEY`).

## Job flow

1. Create job with title + prompt notes
2. Add gameplay clips (upload or library)
3. Set thumbnail headline / colors / optional background
4. **Run full pipeline** (or regenerate from a stage)
5. Review script / audio / video; edit script and re-run from TTS if needed
6. Grab `export/` (`final.mp4`, `thumbnail.jpg`, title/description/tags)

v1 does **not** auto-upload to YouTube.

## Project layout

```
yt-pipeline/
  backend/app/           # FastAPI + pipeline stages
  frontend/src/          # Local UI
  fixtures/              # Generated sample clips
  scripts/               # dev + smoke helpers
```

## Notes

- Use gameplay (or other footage you have rights to). The app is not built around ripping TV/film.
- Mock TTS writes a short tone bed sized from the script so you can validate muxing without paid voices.
- Bound to localhost by default.
