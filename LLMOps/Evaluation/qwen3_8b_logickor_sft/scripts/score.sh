#!/usr/bin/env bash
set -euo pipefail

EVALUATED_GLOB="${1:-evaluated/models/qwen3_8b_sft_high/merged/*.jsonl}"

python logickor_eval/score.py \
  -p "${EVALUATED_GLOB}"
