#!/usr/bin/env bash
# Phase 2b: Text-only maritime domain LoRA fine-tuning
#
# Loads an existing VLM LoRA checkpoint and continues training on the
# LLaMarine-SFT dataset (54,657 maritime instruction-output pairs, no images).
#
# This improves maritime domain knowledge in the LLM without re-training
# the vision encoder or projector.
#
# Single GPU:
#   bash scripts/train_lora_marine.sh
#
# Multi-GPU (e.g., 6x A100):
#   CUDA_VISIBLE_DEVICES=0,1,2,3,4,5 bash scripts/train_lora_marine.sh

set -euo pipefail

PYTHON=/home/ywlee/miniconda3/envs/eva/bin/python
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── Paths ─────────────────────────────────────────────────────────────────────
#LLM_MODEL="/home/ywlee/Llama-3.1-8B-Instruct"
LLM_MODEL="/home/yvvyee/data/Llama-3.1-8B-Instruct"
#LLM_MODEL="/home/ywlee/Qwen3-8B"

LORA_PATH="$ROOT/checkpoints/clip_llama31_lora"
#LORA_PATH="$ROOT/checkpoints/clip_qwen3_lora"

#DATA_PATH="/home/ywlee/HDD/Dataset/llamarine-sft/data/train-00000-of-00001.parquet"
DATA_PATH="/home/yvvyee/data/llamarine-sft/train-00000-of-00001.parquet"

OUTPUT_DIR="$ROOT/checkpoints/clip_llama31_proj_lora_marine"
#OUTPUT_DIR="$ROOT/checkpoints/clip_qwen3_proj_lora_marine"

# ── Detect GPUs ───────────────────────────────────────────────────────────────
NUM_GPUS=$(python3 -c "import torch; print(torch.cuda.device_count())" 2>/dev/null || echo 1)
echo "Detected $NUM_GPUS GPU(s)"

# ── Hyperparameters ───────────────────────────────────────────────────────────
BATCH_SIZE=2          # per-device
GRAD_ACCUM=8          # effective batch = BATCH_SIZE * GRAD_ACCUM * NUM_GPUS
LEARNING_RATE=5e-5    # lower than initial LoRA LR to avoid catastrophic forgetting
NUM_EPOCHS=1
MAX_SEQ_LEN=2048

# ── Launch ─────────────────────────────────────────────────────────────────────
if [ "$NUM_GPUS" -gt 1 ]; then
    LAUNCHER="torchrun --nproc_per_node=$NUM_GPUS"
    DS_ARG="--deepspeed $ROOT/scripts/zero2.json"
else
    LAUNCHER="$PYTHON"
    DS_ARG=""
fi

$LAUNCHER "$ROOT/train_text_lora.py" \
    --llm_model      "$LLM_MODEL" \
    --lora_path      "$LORA_PATH" \
    --data_path      "$DATA_PATH" \
    --output_dir     "$OUTPUT_DIR" \
    --max_seq_len    $MAX_SEQ_LEN \
    --batch_size     $BATCH_SIZE \
    --grad_accum     $GRAD_ACCUM \
    --learning_rate  $LEARNING_RATE \
    --num_epochs     $NUM_EPOCHS \
    --dtype          bfloat16 \
    --gradient_checkpointing \
    --save_steps     500 \
    --logging_steps  10 \
    --dataloader_workers 4 \
    --wandb_project  vlm-v2 \
    $DS_ARG

echo ""
echo "LoRA adapter saved to: $OUTPUT_DIR"
echo "projector.bin copied from: $LORA_PATH"
