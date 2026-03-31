#!/bin/bash

DATA_PATH="/home/ywlee/HDD/Dataset/LLaVA-CC3M-Pretrain-595K/chat.json"
IMAGE_FOLDER="/home/ywlee/HDD/Dataset/LLaVA-CC3M-Pretrain-595K/images"
MODEL_PATH="/home/ywlee/Llama-3.1-8B-Instruct/"
PROJECTOR_PATH="./checkpoints/llama-3.1-8b_pretrain/final_model/mm_projector.bin"
OUTPUT_DIR="./checkpoints/llama-3.1-8b_clip14-336_lora"

# --train_type:   projector, full, lora, qlora
# --deepspeed:    scripts/zero2.json(qlora일 경우), zero3.json(lora 일 경우), zero3_offload.json
# --pretrain_mm_mlp_adapter: projector 학습일 때는 제거할 것

deepspeed eva/train.py \
  --train_type                  lora \
  --deepspeed                   scripts/zero2.json \
  --data_path                   $DATA_PATH \
  --image_folder                $IMAGE_FOLDER \
  --model_path                  $MODEL_PATH \
  --output_dir                  $OUTPUT_DIR \
  --pretrain_mm_mlp_adapter     $PROJECTOR_PATH \
  --per_device_train_batch_size 4 \
  --per_device_eval_batch_size  4 \
  --learning_rate               2e-3 \
  --num_train_epochs            1 \
  --save_strategy               "steps" \
  --save_steps                  5000 \
  --save_total_limit            1 \
  --warmup_steps                0.03 \
  --logging_steps               1 \
  --max_length                  1024 \
  --dataloader_num_workers      4 \
  --bf16 \
  --tf32