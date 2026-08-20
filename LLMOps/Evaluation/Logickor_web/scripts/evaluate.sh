#!/usr/bin/env bash
set -euo pipefail

MODEL_OUTPUT_DIR="${1:-generated/models/qwen3_8b_sft_high/merged}"
JUDGE_MODEL="${JUDGE_MODEL:-gpt-4.1}"
THREADS="${THREADS:-30}"

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY is required. Example: export OPENAI_API_KEY='...'" >&2
  exit 1
fi

python logickor_eval/evaluator.py \
  -o "${MODEL_OUTPUT_DIR}" \
  -k "${OPENAI_API_KEY}" \
  -j "${JUDGE_MODEL}" \
  -t "${THREADS}"
