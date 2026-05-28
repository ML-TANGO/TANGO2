#!/bin/bash
# GAA LoRA Fine-tuning Script (multi-GPU with DeepSpeed ZeRO-2)
#
# Prerequisites:
#   1. Phase 1 projector pre-training completed:
#      scripts/train_projector.sh  →  checkpoints/projector/projector.bin
#   2. Training data prepared with bboxes field (see gaa/sds_reformat.py in
#      llava-icml2026-failed for the CSV-to-JSON conversion reference)
#
# Usage:
#   bash scripts/train_lora_gaa.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

DATA_PATH="/path/to/sds_gaa_train.json"   # JSON with "bboxes" field
IMAGE_DIR="/path/to/images"
PROJECTOR="/path/to/projector.bin"        # from Phase 1 pre-training
OUTPUT_DIR="checkpoints/gaa_lora"

torchrun \
    --nproc_per_node=2 \
    "$ROOT_DIR/gaa/train_gaa.py" \
    --vision_model "openai/clip-vit-large-patch14-336" \
    --llm_model    "/home/ywlee/Llama-3.1-8B-Instruct" \
    --projector_type mlp2x_gelu \
    --train_type lora \
    --projector_path "$PROJECTOR" \
    --data_path  "$DATA_PATH" \
    --image_dir  "$IMAGE_DIR" \
    --output_dir "$OUTPUT_DIR" \
    --num_epochs 3 \
    --batch_size 4 \
    --grad_accum 4 \
    --learning_rate 2e-4 \
    --warmup_ratio 0.03 \
    --lr_scheduler cosine \
    --geo_loss_weight 0.5 \
    --geo_tau 0.5 \
    --feature_size -1 \
    --lora_r 128 \
    --lora_alpha 256 \
    --lora_dropout 0.05 \
    --dtype bfloat16 \
    --save_steps 500 \
    --logging_steps 10 \
    --deepspeed "$SCRIPT_DIR/zero2.json" \
    --wandb_project vlm-gaa
