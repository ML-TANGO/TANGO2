#!/bin/bash

# DeepSpeed ZeRO-3 사전학습 파이프라인 무결성 테스트 (10 Steps)

DATA_PATH="/home/ywlee/HDD/Dataset/LLaVA-CC3M-Pretrain-595K/chat.json"
IMAGE_FOLDER="/home/ywlee/HDD/Dataset/LLaVA-CC3M-Pretrain-595K/images"
MODEL_PATH="/home/ywlee/Llama-3.1-8B-Instruct"
OUTPUT_DIR="./checkpoints/llava-pretrain-test"

export PYTHONPATH=$PYTHONPATH:$(pwd)
export CUDA_LAUNCH_BLOCKING=1
export TORCH_USE_CUDA_DSA=1

deepspeed llava_custom/train/train.py \
    --deepspeed scripts/zero2.json \
    --model_name_or_path $MODEL_PATH \
    --version v1 \
    --data_path $DATA_PATH \
    --image_folder $IMAGE_FOLDER \
    --is_multimodal True \
    --mm_vision_tower openai/clip-vit-large-patch14-336 \
    --mm_projector_type mlp2x_gelu \
    --tune_mm_mlp_adapter True \
    --freeze_backbone True \
    --mm_vision_select_layer -2 \
    --bf16 True \
    --output_dir $OUTPUT_DIR \
    --num_train_epochs 1 \
    --max_steps 1000 \
    --per_device_train_batch_size 16 \
    --per_device_eval_batch_size 4 \
    --gradient_accumulation_steps 1 \
    --eval_strategy "no" \
    --save_strategy "steps" \
    --save_steps 1000 \
    --save_total_limit 1 \
    --learning_rate 2e-3 \
    --weight_decay 0. \
    --warmup_ratio 0.03 \
    --lr_scheduler_type "cosine" \
    --logging_steps 1 \
    --tf32 True \
    --model_max_length 2048 \
    --gradient_checkpointing True \
    --dataloader_num_workers 4 \
    --lazy_preprocess True \
    --report_to none
