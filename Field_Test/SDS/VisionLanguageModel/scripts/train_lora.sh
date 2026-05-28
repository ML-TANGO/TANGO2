#!/usr/bin/env bash
# Phase 2: LoRA fine-tuning
# Uses pretrained projector from Phase 1
# Trains: projector + LoRA on LLM
# Requires --projector_path from Phase 1
#
# Usage:
#   bash scripts/train_lora.sh /path/to/custom_data.json /path/to/images

set -euo pipefail

PYTHON=/home/ywlee/miniconda3/envs/eva/bin/python
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── Paths ─────────────────────────────────────────────────────────────────────
VISION_MODEL="openai/clip-vit-large-patch14-336"
LLM_MODEL="/home/yvvyee/data/Qwen3-8B"
#LLM_MODEL="/home/yvvyee/data/Llama-3.1-8B-Instruct"
#LLM_MODEL="/home/ywlee/Llama-3.1-8B-Instruct"
PROJECTOR_PATH="$ROOT/checkpoints/clip_qwen3_projector/projector.bin"
DATA_PATH="/home/yvvyee/data/LLaVA-CC3M-Pretrain-595K/chat.json"
IMAGE_DIR="/home/yvvyee/data/LLaVA-CC3M-Pretrain-595K/images"
#DATA_PATH="${1:-/home/ywlee/HDD/Dataset/LLaVA-CC3M-Pretrain-595K/chat.json}"
#IMAGE_DIR="${2:-/home/ywlee/HDD/Dataset/LLaVA-CC3M-Pretrain-595K/images}"
#OUTPUT_DIR="$ROOT/checkpoints/clip_llama31_lora"
OUTPUT_DIR="$ROOT/checkpoints/clip_qwen3_lora"

if [ ! -f "$PROJECTOR_PATH" ]; then
    echo "ERROR: projector not found at $PROJECTOR_PATH"
    echo "Run train_projector.sh first."
    exit 1
fi

# ── Detect GPUs ───────────────────────────────────────────────────────────────
NUM_GPUS=$(python3 -c "import torch; print(torch.cuda.device_count())" 2>/dev/null || echo 1)
echo "Detected $NUM_GPUS GPU(s)"

# ── Hyperparameters ───────────────────────────────────────────────────────────
BATCH_SIZE=4
GRAD_ACCUM=4
LEARNING_RATE=2e-4
NUM_EPOCHS=3
MAX_SEQ_LEN=2048
LORA_R=128
LORA_ALPHA=256

# ── Launch ────────────────────────────────────────────────────────────────────
if [ "$NUM_GPUS" -gt 1 ]; then
    LAUNCHER="torchrun --nproc_per_node=$NUM_GPUS"
    DS_ARG="--deepspeed $ROOT/scripts/zero2.json"
else
    LAUNCHER="$PYTHON"
    DS_ARG=""
fi

$LAUNCHER "$ROOT/train.py" \
    --train_type lora \
    --vision_model "$VISION_MODEL" \
    --llm_model    "$LLM_MODEL" \
    --projector_type mlp2x_gelu \
    --projector_path "$PROJECTOR_PATH" \
    --data_path  "$DATA_PATH" \
    --image_dir  "$IMAGE_DIR" \
    --output_dir "$OUTPUT_DIR" \
    --num_epochs  $NUM_EPOCHS \
    --batch_size  $BATCH_SIZE \
    --grad_accum  $GRAD_ACCUM \
    --learning_rate $LEARNING_RATE \
    --lr_scheduler cosine \
    --warmup_ratio 0.03 \
    --max_seq_len $MAX_SEQ_LEN \
    --lora_r     $LORA_R \
    --lora_alpha $LORA_ALPHA \
    --dtype bfloat16 \
    --gradient_checkpointing \
    --save_steps 5000 \
    --logging_steps 10 \
    --dataloader_workers 4 \
    --wandb_project vlm-v2 \
    $DS_ARG

echo ""
echo "LoRA adapter + projector saved to: $OUTPUT_DIR"
