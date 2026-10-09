#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cleanup() {
  kill $(jobs -p) 2>/dev/null || true
}
trap cleanup EXIT

cd "$ROOT/backend"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8787 --reload &

cd "$ROOT/frontend"
npm run dev -- --host 127.0.0.1 --port 5173 &

wait
