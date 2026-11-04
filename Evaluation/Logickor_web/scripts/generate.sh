#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH="${1:-models/qwen3_8b_sft_high/merged}"
GPU_DEVICES="${GPU_DEVICES:-0}"
MODEL_LEN="${MODEL_LEN:-4096}"

python logickor_eval/generator.py \
  --model "${MODEL_PATH}" \
  --gpu_devices "${GPU_DEVICES}" \
  --model_len "${MODEL_LEN}"
