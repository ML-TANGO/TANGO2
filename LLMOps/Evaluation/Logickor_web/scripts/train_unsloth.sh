#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH="${1:-configs/train_gemma4_e4b_unsloth_sft.yaml}"
OUTPUT_DIR="${2:-runs/gemma4_e4b_unsloth_sft}"
SEED="${SEED:-42}"
SAVE_MERGED="${SAVE_MERGED:-false}"

args=(
  --config "${CONFIG_PATH}"
  --output-dir "${OUTPUT_DIR}"
  --seed "${SEED}"
)

if [[ "${SAVE_MERGED}" == "true" ]]; then
  args+=(--save-merged)
fi

python train/train_unsloth_lora.py "${args[@]}"
