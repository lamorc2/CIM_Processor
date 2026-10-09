# Automated YouTube Content Pipeline — Spec Sheet

**Document type:** Engineering handoff / product spec  
**Status:** Draft for implementation  
**Audience:** Builder implementing a local app + generation pipeline  
**Primary use case:** Gameplay-bed videos with AI script + TTS narration (not third-party copyrighted show footage)

---

## 1. Goal

Build a **local-first desktop/web UI** that lets an operator:

1. Complete one-time **setup** (API keys, paths, defaults, voice, output settings)
2. Create a **job** by specifying **title**, **prompt(s)**, and **thumbnail** inputs
3. Run an automated pipeline: **script → TTS → video assembly → export package**
4. Review intermediates, regenerate individual stages, and export a ready-to-upload folder

Success looks like: from a filled job form, produce a folder containing final video, thumbnail image(s), title, description, tags, and metadata — with minimal manual editing.

---

## 2. Non-goals (v1)

- Automatic YouTube upload / OAuth publishing (optional later)
- Scraping or remuxing copyrighted TV/film footage as the visual bed
- Multi-user cloud SaaS, accounts, billing
- Fully unattended mass posting farms (thousands of videos/day)
- Guaranteeing monetization or algorithm performance

**v1 visual bed:** operator-provided **gameplay recordings** (or other footage they own / have rights to).

---

## 3. High-level architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Local UI (SPA)                      │
│  Setup · Jobs · Prompt editor · Thumbnail · Review      │
└──────────────────────────┬──────────────────────────────┘
                           │ REST / local IPC
┌──────────────────────────▼──────────────────────────────┐
│                   Local API / orchestrator              │
│  job queue · stage runners · file store · config        │
└───┬──────────┬──────────┬──────────┬────────────────────┘
    │          │          │          │
    ▼          ▼          ▼          ▼
 LLM API    TTS API    FFmpeg     Image gen
 (script)   (voice)   (mux/edit)  (thumbnail)
    │          │          │          │
    └──────────┴──────────┴──────────┘
                     ▼
              Workspace on disk
         projects/<job-id>/...
```

**Principles**

- Local UI + local orchestrator (runs on operator machine)
- All artifacts stored as plain files on disk (easy to inspect/debug)
- Stages are independently re-runnable
- Secrets stay in local config / env, never in job JSON committed to git

---

## 4. Recommended stack (implementation guidance)

| Layer | Suggestion | Notes |
|-------|------------|-------|
| UI | React + Vite (or Next.js static export) | Simple local SPA |
| API | Node (Fastify/Express) or Python (FastAPI) | Pick one; Python is nicer if FFmpeg/ML glue is heavy |
| Queue | In-process job runner + SQLite | Enough for single-user local |
| Video | FFmpeg CLI | Required |
| LLM | OpenAI-compatible API (configurable base URL) | Supports OpenAI, local LM Studio, etc. |
| TTS | Pluggable provider (ElevenLabs / OpenAI TTS / local) | Provider interface |
| Thumbnails | LLM image API **or** local canvas template compositor | Template path recommended for v1 reliability |
| Packaging | Electron optional | Browser UI + `localhost` server is fine for v1 |

**Default recommendation:** FastAPI + React/Vite + SQLite + FFmpeg.

---

## 5. Core objects

### 5.1 App settings (global)

```json
{
  "workspace_dir": "/path/to/yt-workspace",
  "llm": {
    "provider": "openai_compatible",
    "base_url": "https://api.openai.com/v1",
    "api_key_env": "LLM_API_KEY",
    "model": "gpt-4.1-mini",
    "temperature": 0.7
  },
  "tts": {
    "provider": "elevenlabs",
    "api_key_env": "TTS_API_KEY",
    "voice_id": "...",
    "stability": 0.4,
    "speaking_rate": 1.0
  },
  "video": {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "video_bitrate": "6M",
    "audio_bitrate": "192k",
    "gameplay_library_dir": "/path/to/gameplay-clips",
    "default_bed_mode": "shuffle_clips"
  },
  "thumbnail": {
    "mode": "template",
    "template_id": "bold_title_face",
    "image_provider": "optional_openai_images",
    "font_path": "/path/to/font.ttf"
  },
  "youtube_defaults": {
    "description_footer": "Like & subscribe...",
    "default_tags": ["gaming", "analysis"],
    "visibility": "private"
  }
}
```

### 5.2 Job

A job is one intended video.

```json
{
  "id": "20261009-deadbeef",
  "status": "draft | queued | running | needs_review | succeeded | failed | cancelled",
  "created_at": "...",
  "updated_at": "...",
  "inputs": {
    "title": "Why This Boss Fight Still Breaks Players in 2026",
    "series": "Elden Ring Thoughts",
    "prompt_system": "You write punchy YouTube narration...",
    "prompt_user": "Topic: ... Audience: ... Tone: ... Length target: 12 minutes...",
    "script_constraints": {
      "target_duration_sec": 720,
      "word_count_min": 1400,
      "word_count_max": 2000,
      "include_hook": true,
      "include_cta": true,
      "banned_phrases": ["in conclusion", "as an AI"]
    },
    "thumbnail": {
      "mode": "template | generate | upload",
      "headline": "THIS BOSS IS BROKEN",
      "subheadline": "and players still fall for it",
      "source_image_path": "optional/path.png",
      "template_id": "bold_title_face",
      "style_prompt": "optional image-gen prompt",
      "text_color": "#FFFFFF",
      "accent_color": "#FF3B30"
    },
    "video_bed": {
      "mode": "single_file | shuffle_clips | timeline",
      "paths": ["clip1.mp4", "clip2.mp4"],
      "mute_source_audio": true,
      "loop_if_short": true
    },
    "tts": {
      "voice_id_override": null,
      "speaking_rate_override": null
    }
  },
  "outputs": {
    "script_path": "stages/01_script/script.md",
    "script_json_path": "stages/01_script/script.json",
    "audio_path": "stages/02_tts/narration.wav",
    "aligned_transcript_path": "stages/02_tts/words.json",
    "timeline_path": "stages/03_video/timeline.json",
    "video_path": "stages/03_video/final.mp4",
    "thumbnail_path": "stages/04_thumbnail/thumb.jpg",
    "package_dir": "export/"
  },
  "stage_state": {
    "script": { "status": "succeeded", "attempts": 1, "error": null },
    "tts": { "status": "pending", "attempts": 0, "error": null },
    "video": { "status": "pending", "attempts": 0, "error": null },
    "thumbnail": { "status": "pending", "attempts": 0, "error": null },
    "package": { "status": "pending", "attempts": 0, "error": null }
  }
}
```

### 5.3 On-disk layout

```
<workspace>/
  config/
    settings.json
    prompt_presets/
      gaming_analysis.json
      lore_explainer.json
  voices/
    preview-samples/
  templates/
    thumbnails/
      bold_title_face/
        template.json
        overlay.png
  gameplay/
    (optional library shortcuts / indexes)
  projects/
    <job-id>/
      job.json
      inputs/
        gameplay/          # copied or linked clips for reproducibility
        thumbnail_src/
      stages/
        01_script/
        02_tts/
        03_video/
        04_thumbnail/
      export/
        final.mp4
        thumbnail.jpg
        title.txt
        description.txt
        tags.txt
        metadata.json
      logs/
        pipeline.log
```

---

## 6. Pipeline stages

### Stage 0 — Validate job

- Required: title, user prompt, at least one gameplay source, thumbnail mode chosen
- Check API keys present for selected providers
- Check FFmpeg available
- Estimate disk space; fail early if clips missing

### Stage 1 — Script generation

**Input:** system prompt + user prompt + constraints + title  
**Output:**

- `script.md` — narration text only (what gets spoken)
- `script.json` — structured:
  - `title`
  - `hook`
  - `sections[]` `{ heading, narration }`
  - `description` (YouTube description draft)
  - `tags[]`
  - `chapters[]` optional `{ title, approx_time_sec }`
  - `thumbnail_headline_suggestions[]`

**UI affordances after stage:**

- Edit script in place
- “Regenerate full script”
- “Regenerate section N”
- Show estimated duration from word count (~150 wpm default, configurable)

### Stage 2 — TTS narration

**Input:** final narration text (concatenated sections)  
**Output:** `narration.wav` + optional word/sentence timestamps  

**Requirements:**

- Chunk long scripts if provider has char limits; stitch with short silences
- Normalize loudness (e.g. loudnorm / target LUFS)
- Allow voice override per job
- Preview audio in UI before video build

### Stage 3 — Video assembly

**Input:** narration audio duration + gameplay bed settings  
**Process:**

1. Probe audio duration `D`
2. Build visual timeline of length `D` from gameplay clips
   - `single_file`: trim/loop one recording
   - `shuffle_clips`: random/sequential clip concat until `D`
   - `timeline`: operator-specified ordered list (v1.1 ok)
3. Mute or duck source gameplay audio (default mute)
4. Mux narration as primary audio
5. Optional burn-in: subtle progress bar / chapter titles (off by default)
6. Export H.264 + AAC MP4

**Quality rules:**

- Constant output resolution/fps from settings
- Avoid black frames at joins
- Soft cut or 2–6 frame crossfade between clips (configurable)
- If clips shorter than audio and `loop_if_short=false`, fail with clear error

### Stage 4 — Thumbnail

Support three modes:

| Mode | Behavior |
|------|----------|
| `upload` | Operator provides image; optional text overlay |
| `template` | Local compositor: background image/frame + big headline + accent |
| `generate` | Image model from `style_prompt` + optional face/game still, then overlay text |

**Always produce:** 1280×720 JPEG/PNG  
**UI:** live preview of headline/subheadline/colors before commit

### Stage 5 — Package for upload

Write `export/`:

- `final.mp4`
- `thumbnail.jpg`
- `title.txt`
- `description.txt`
- `tags.txt`
- `metadata.json` (job id, model used, voice, duration, created_at)

Optional later: “Copy title”, “Open folder”, YouTube draft upload.

---

## 7. Local UI specification

### 7.1 Global chrome

- Left nav: **Setup**, **Jobs**, **Presets**, **Library**, **Logs**
- Top status: API connectivity dots (LLM / TTS / FFmpeg)
- Dark or light theme acceptable; prioritize clarity over ornament

### 7.2 Setup page (first-run wizard + editable later)

Steps:

1. **Workspace** — choose/create workspace directory
2. **Dependencies** — detect FFmpeg; show install hint if missing
3. **LLM** — base URL, model, API key, test button (“Generate 1 sentence”)
4. **TTS** — provider, API key, voice picker + 5s preview
5. **Defaults** — target duration, output resolution, description footer, default tags
6. **Gameplay library** — folder picker + scan clip count
7. **Thumbnail defaults** — default mode/template/font
8. **Finish** — write settings, mark setup complete

Block job creation until setup checklist passes.

### 7.3 Jobs list

- Table/cards: title, status, duration estimate, updated_at
- Filters: draft / running / needs_review / succeeded / failed
- Actions: New job, Duplicate, Delete, Open folder

### 7.4 Job editor (core screen)

Tabs or single scrolling form with sticky run controls:

#### A. Basics
- Title (required)
- Series / playlist label (optional)
- Target duration
- Prompt preset selector

#### B. Prompts
- System prompt textarea (with preset load/save)
- User prompt textarea (topic, angle, tone, must-include bullets)
- Constraints panel: word count, hook/CTA toggles, banned phrases
- “Estimate length” helper

#### C. Media bed
- Dropzone / file picker for gameplay clips
- Mode: single / shuffle
- Mute source audio toggle
- Clip list with duration badges

#### D. Thumbnail
- Mode selector: upload / template / generate
- Headline + subheadline fields (independent from video title)
- Color pickers
- Background image upload or “grab frame from clip”
- Live 16:9 preview
- Save thumbnail draft without running full pipeline

#### E. Voice
- Use default voice / override
- Rate slider
- Preview selected sample line

#### F. Run & review
- Buttons:
  - **Run full pipeline**
  - **Run from stage…** (script / tts / video / thumbnail / package)
  - **Regenerate script only**
- Stage timeline with status chips + logs
- Inline players for audio + video
- Script editor (markdown) with Save
- “Mark needs review” / “Approve & package”

### 7.5 Presets page

CRUD for reusable:

- Prompt presets (system + user template with `{{topic}}` slots)
- Thumbnail templates
- Voice profiles

### 7.6 Library page

- Index gameplay folder
- Show duration, resolution, last used
- Mark clips as favorites / exclude broken files

### 7.7 Logs page

- Per-job and global logs
- Copy error + provider response snippets (redact API keys)

---

## 8. API surface (local)

Base: `http://127.0.0.1:<port>/api`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | App + dependency status |
| GET/PUT | `/settings` | Read/update settings |
| POST | `/settings/test-llm` | Connectivity test |
| POST | `/settings/test-tts` | Voice preview generation |
| GET | `/presets` | List presets |
| POST | `/presets` | Create preset |
| GET | `/jobs` | List jobs |
| POST | `/jobs` | Create job |
| GET | `/jobs/:id` | Get job |
| PATCH | `/jobs/:id` | Update inputs / edited script |
| POST | `/jobs/:id/run` | `{ from_stage?: "script"\|"tts"\|... }` |
| POST | `/jobs/:id/cancel` | Cancel running job |
| GET | `/jobs/:id/events` | SSE progress stream |
| GET | `/library/clips` | Scan gameplay library |
| POST | `/thumbnails/preview` | Render thumbnail preview bytes |

All file paths returned as workspace-relative where possible; include absolute `open_path` for OS reveal.

---

## 9. Prompt contract (important)

The LLM must return **strict JSON** matching a schema (use provider JSON mode / schema validation). If parse fails, retry once with repair prompt, then fail stage with error visible in UI.

Minimum schema fields:

- `narration_script` (string, full spoken script)
- `sections` (array)
- `youtube_description` (string)
- `tags` (string array, ≤ 20)
- `thumbnail_headline_ideas` (string array, 3–5)

UI title is authoritative for packaging unless operator enables “allow model to rewrite title.”

---

## 10. UX / product rules

1. **Never auto-upload in v1.** Export package only.
2. **Human review gate:** after first successful full run on a machine, default new jobs to stop at `needs_review` before package; setting can disable.
3. **Stage isolation:** editing script invalidates TTS/video stages (mark stale, don’t delete until regenerate).
4. **Cost visibility:** show rough token/char estimates before run when possible.
5. **Idempotent reruns:** regenerating TTS replaces audio and marks video stale.
6. **No silent failures:** every stage writes structured error with next action (“check TTS key”, “add longer clips”, etc.).
7. **Rights posture:** UI copy should state operator must own/have rights to gameplay footage used.

---

## 11. MVP scope (ship first)

**Must have**

- Setup wizard (workspace, LLM, TTS, FFmpeg check, gameplay dir)
- Create job with title + prompts + clip select + thumbnail headline/template
- Pipeline: script → TTS → FFmpeg mux → thumbnail template → export folder
- Job list + stage status + script edit + regenerate-from-stage
- Local SSE/progress + logs

**Nice-to-have (v1.1)**

- Image-gen thumbnails
- Word-level highlight / karaoke captions
- Chapter markers from script sections
- Job duplication + batch queue
- YouTube upload draft via API

**Later**

- Local LLM/TTS fully offline mode
- Timeline editor for clip order
- A/B thumbnail variants
- Analytics hooks

---

## 12. Acceptance criteria

1. Fresh machine: complete Setup and save valid settings in <10 minutes (assuming keys/FFmpeg present).
2. Operator can create a job specifying **title**, **system/user prompts**, and **thumbnail headline/background**, then run pipeline end-to-end.
3. Output folder contains playable `final.mp4`, `thumbnail.jpg`, and text metadata files.
4. Operator can edit script and regenerate **only** TTS+video without regenerating script.
5. Operator can regenerate thumbnail without re-running script/TTS/video.
6. Failure in TTS shows actionable error and leaves prior successful stages intact.
7. App runs locally without requiring a public server.

---

## 13. Security & secrets

- Store API keys in OS env or local secrets file with `600` permissions; do not put raw keys in `job.json`
- Bind API to `127.0.0.1` only by default
- CORS locked to local UI origin
- Redact Authorization headers in logs
- No telemetry unless explicitly opted in

---

## 14. Testing plan (minimum)

- Unit: script JSON schema validation; duration estimator; timeline builder length math
- Integration: mock LLM/TTS; real FFmpeg with short sample wav + sample mp4
- UI e2e: setup → create job → run mocked pipeline → export exists
- Manual: one real provider smoke test checklist in README

---

## 15. README deliverables for implementer

Repo should include:

- `README.md` — run instructions
- `.env.example` — `LLM_API_KEY`, `TTS_API_KEY`
- `docs/automated-youtube-pipeline-spec.md` — this file
- Sample gameplay clip + sample voice preview fixtures under `fixtures/`
- `make dev` / `npm run dev` starting API + UI together

---

## 16. Open decisions (resolve during implementation)

| Decision | Options | Default if unspecified |
|----------|---------|------------------------|
| App language | Node vs Python backend | **Python/FastAPI** |
| TTS provider first | ElevenLabs vs OpenAI TTS | **OpenAI TTS** (fewer moving parts) |
| Thumbnail v1 | Template only vs image-gen | **Template + upload** |
| Caption burn-in | On/off | **Off** |
| Clip selection | Random shuffle vs sequential | **Sequential then loop** (more reproducible) |

---

## 17. One-paragraph summary for handoff

Build a local single-user app (React UI + FastAPI) where Setup stores provider keys and paths, and Jobs capture title, prompts, gameplay clips, and thumbnail settings. Running a job generates a validated script via LLM, narrates it via TTS, muxes narration over operator gameplay with FFmpeg, renders a 1280×720 thumbnail from template/upload, and exports a YouTube-ready folder. Stages must be re-runnable, artifacts must live on disk, and v1 must not auto-upload or rely on copyrighted third-party show footage.
