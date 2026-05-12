#!/usr/bin/env bash
# demo/run.sh — VLM SDS 데모 실행 스크립트
set -euo pipefail

PYTHON=/home/ywlee/miniconda3/envs/eva/bin/python
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PORT=${1:-7860}
HOST=${2:-0.0.0.0}

echo "======================================"
echo "  VisionLanguageModel SDS Demo"
echo "  http://${HOST}:${PORT}"
echo "======================================"

exec "$PYTHON" "$ROOT/demo/app.py" --port "$PORT" --host "$HOST"
