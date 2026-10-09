#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API="http://127.0.0.1:8787"
DATA="$ROOT/backend/data-smoke"
WS="$ROOT/workspace-data-smoke"
export YT_PIPELINE_DATA="$DATA"
rm -rf "$DATA" "$WS"
mkdir -p "$WS/gameplay"

# Fixtures
bash "$ROOT/scripts/make_fixtures.sh"
cp "$ROOT/fixtures/sample_gameplay.mp4" "$WS/gameplay/"
cp "$ROOT/fixtures/sample_gameplay_b.mp4" "$WS/gameplay/"

# Start API
cd "$ROOT/backend"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8787 &
PID=$!
cleanup() { kill $PID 2>/dev/null || true; }
trap cleanup EXIT

for i in $(seq 1 30); do
  if curl -sf "$API/api/health" >/dev/null; then break; fi
  sleep 0.3
done
curl -sf "$API/api/health" | grep -q '"ok":true'

# Setup
curl -sf -X PUT "$API/api/settings" \
  -H 'Content-Type: application/json' \
  -d "{
    \"setup_complete\": true,
    \"workspace_dir\": \"$WS\",
    \"llm\": {\"provider\": \"mock\", \"base_url\": \"https://api.openai.com/v1\", \"api_key_env\": \"LLM_API_KEY\", \"api_key\": \"\", \"model\": \"gpt-4.1-mini\", \"temperature\": 0.7},
    \"tts\": {\"provider\": \"mock\", \"api_key_env\": \"TTS_API_KEY\", \"api_key\": \"\", \"voice\": \"alloy\", \"model\": \"gpt-4o-mini-tts\", \"speaking_rate\": 1.0, \"words_per_minute\": 150},
    \"video\": {\"width\": 1280, \"height\": 720, \"fps\": 30, \"video_bitrate\": \"2M\", \"audio_bitrate\": \"128k\", \"gameplay_library_dir\": \"$WS/gameplay\", \"default_bed_mode\": \"shuffle_clips\", \"crossfade_frames\": 0},
    \"thumbnail\": {\"mode\": \"template\", \"template_id\": \"bold_title\", \"font_path\": \"\", \"default_text_color\": \"#FFFFFF\", \"default_accent_color\": \"#FF3B30\"},
    \"youtube_defaults\": {\"description_footer\": \"Smoke test\", \"default_tags\": [\"gaming\"], \"visibility\": \"private\", \"stop_for_review\": false}
  }" >/dev/null

# Create job with short target for speed
JOB=$(curl -sf -X POST "$API/api/jobs" -H 'Content-Type: application/json' -d "{
  \"title\": \"Smoke Test Boss Fight\",
  \"prompt_user\": \"Explain why the second phase feels unfair and how to read the tell.\",
  \"script_constraints\": {\"target_duration_sec\": 12, \"word_count_min\": 40, \"word_count_max\": 120, \"include_hook\": true, \"include_cta\": true, \"banned_phrases\": [\"as an AI\"]},
  \"thumbnail\": {\"mode\": \"template\", \"headline\": \"BOSS IS BROKEN\", \"subheadline\": \"smoke test\", \"source_image_path\": \"\", \"template_id\": \"bold_title\", \"style_prompt\": \"\", \"text_color\": \"#FFFFFF\", \"accent_color\": \"#FF3B30\"},
  \"video_bed\": {\"mode\": \"shuffle_clips\", \"paths\": [\"$WS/gameplay/sample_gameplay.mp4\", \"$WS/gameplay/sample_gameplay_b.mp4\"], \"mute_source_audio\": true, \"loop_if_short\": true}
}")
JOB_ID=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$JOB")
echo "Job: $JOB_ID"

curl -sf -X POST "$API/api/jobs/$JOB_ID/run" -H 'Content-Type: application/json' -d '{}' >/dev/null

for i in $(seq 1 120); do
  STATUS=$(curl -sf "$API/api/jobs/$JOB_ID" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')
  echo "status=$STATUS"
  if [[ "$STATUS" == "succeeded" || "$STATUS" == "needs_review" ]]; then
    break
  fi
  if [[ "$STATUS" == "failed" || "$STATUS" == "cancelled" ]]; then
    curl -sf "$API/api/jobs/$JOB_ID" | python3 -m json.tool
    exit 1
  fi
  sleep 1
done

EXPORT=$(curl -sf "$API/api/jobs/$JOB_ID" | python3 -c 'import json,sys; print(json.load(sys.stdin)["outputs"]["package_dir"])')
test -f "$EXPORT/final.mp4"
test -f "$EXPORT/thumbnail.jpg"
test -f "$EXPORT/title.txt"
test -f "$EXPORT/description.txt"
test -f "$EXPORT/tags.txt"
test -f "$EXPORT/metadata.json"
echo "SMOKE OK — export at $EXPORT"
