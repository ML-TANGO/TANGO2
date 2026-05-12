#!/usr/bin/env bash
# Phase 1: Projector pretraining
# Freeze CLIP + Llama 3.1, train only the MLP projector
# Tested on: RTX 5090 (1 GPU), A100-40G (6 GPUs)
#
# Single GPU:
#   bash scripts/train_projector.sh
#
# Multi-GPU (e.g., 6x A100):
#   CUDA_VISIBLE_DEVICES=0,1,2,3,4,5 bash scripts/train_projector.sh

set -euo pipefail

PYTHON=/home/ywlee/miniconda3/envs/eva/bin/python
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── Paths ─────────────────────────────────────────────────────────────────────
VISION_MODEL="openai/clip-vit-large-patch14-336"
LLM_MODEL="/home/yvvyee/data/Llama-3.1-8B-Instruct"
#LLM_MODEL="/home/ywlee/Llama-3.1-8B-Instruct"
#LLM_MODEL="/home/ywlee/Qwen3-8B"
#DATA_PATH="/home/ywlee/HDD/Dataset/LLaVA-CC3M-Pretrain-595K/chat.json"
#IMAGE_DIR="/home/ywlee/HDD/Dataset/LLaVA-CC3M-Pretrain-595K/images"
DATA_PATH="/home/yvvyee/data/LLaVA-CC3M-Pretrain-595K/chat.json"
IMAGE_DIR="/home/yvvyee/data/LLaVA-CC3M-Pretrain-595K/images"
OUTPUT_DIR="$ROOT/checkpoints/clip_llama31_projector"
#OUTPUT_DIR="$ROOT/checkpoints/clip_qwen3_projector"

# ── Detect number of GPUs ─────────────────────────────────────────────────────
NUM_GPUS=$(python3 -c "import torch; print(torch.cuda.device_count())" 2>/dev/null || echo 1)
echo "Detected $NUM_GPUS GPU(s)"

# ── Hyperparameters ───────────────────────────────────────────────────────────
BATCH_SIZE=8          # per-device (adjust to fit VRAM)
GRAD_ACCUM=4
LEARNING_RATE=1e-3
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

$LAUNCHER "$ROOT/train.py" \
    --train_type projector \
    --vision_model "$VISION_MODEL" \
    --llm_model    "$LLM_MODEL" \
    --projector_type mlp2x_gelu \
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
    --dtype bfloat16 \
    --gradient_checkpointing \
    --save_steps 5000 \
    --max_steps 5000 \
    --logging_steps 10 \
    --dataloader_workers 4 \
    --wandb_project vlm-v2 \
    $DS_ARG

echo ""
echo "Projector saved to: $OUTPUT_DIR/projector.bin"
