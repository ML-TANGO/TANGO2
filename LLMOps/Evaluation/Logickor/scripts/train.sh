#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH="${1:-configs/train_qwen3_8b_sft.yaml}"
OUTPUT_DIR="${2:-runs/qwen3_8b_sft_high}"
SEED="${SEED:-42}"

python train/train_lora.py \
  --config "${CONFIG_PATH}" \
  --output-dir "${OUTPUT_DIR}" \
  --seed "${SEED}"
