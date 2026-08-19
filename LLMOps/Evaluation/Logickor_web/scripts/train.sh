#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH="${1:-configs/train_qwen3_8b_sft.yaml}"
OUTPUT_DIR="${2:-runs/qwen3_8b_sft_high}"
SEED="${SEED:-42}"
GPU="${GPU:-0}"
# 짧은 확인용 실행: TRAIN_FRACTION=0.1 처럼 데이터 일부만 사용.
TRAIN_FRACTION="${TRAIN_FRACTION:-1.0}"

python train/train_lora.py \
  --config "${CONFIG_PATH}" \
  --output-dir "${OUTPUT_DIR}" \
  --seed "${SEED}" \
  --gpu "${GPU}" \
  --train-fraction "${TRAIN_FRACTION}"
