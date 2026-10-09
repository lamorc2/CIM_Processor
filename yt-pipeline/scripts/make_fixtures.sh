#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/fixtures"
mkdir -p "$OUT"

# 8s color bars style gameplay stand-in
ffmpeg -y -f lavfi -i "testsrc=size=1280x720:rate=30" -f lavfi -i "sine=frequency=440:sample_rate=44100" \
  -t 8 -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest "$OUT/sample_gameplay.mp4" </dev/null

# Second shorter clip for concat testing
ffmpeg -y -f lavfi -i "testsrc2=size=1280x720:rate=30" -t 5 -c:v libx264 -pix_fmt yuv420p -an \
  "$OUT/sample_gameplay_b.mp4" </dev/null

echo "Fixtures written to $OUT"
