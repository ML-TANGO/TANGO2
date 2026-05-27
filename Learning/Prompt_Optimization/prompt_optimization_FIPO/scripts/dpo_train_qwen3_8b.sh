#!/bin/bash
set -e
export WANDB_MODE=disabled

ISLORA=$1
ROOTPATH=$2

if [ -z "$ISLORA" ] || [ -z "$ROOTPATH" ]; then
  echo "Usage: bash sft_train_qwen3_8b.sh <ISLORA:0|1> <ROOTPATH>"
  exit 1
fi

MODEL_NAME="Qwen/Qwen3-8B"
OUTPUT_DIR="${ROOTPATH}/model/qwen3_8b_sft"
PEFT_DIR="${OUTPUT_DIR}_peft"
MERGED_DIR="${OUTPUT_DIR}_merged"

python ${ROOTPATH}/train_sft_qwen3_8b.py \
  --model_name_or_path ${MODEL_NAME} \
  --dataset_name Junrulu/Prompt_Preference_Dataset \
  --dataset_split train \
  --raw_prompt_column raw_prompt \
  --target_column gpt4_optimized_prompt \
  --model_max_length 2048 \
  --if_lora ${ISLORA} \
  --output_dir $( [ "${ISLORA}" = "1" ] && echo ${PEFT_DIR} || echo ${OUTPUT_DIR} ) \
  --num_train_epochs 3 \
  --per_device_train_batch_size 1 \
  --gradient_accumulation_steps 16 \
  --learning_rate 2e-5 \
  --weight_decay 0.0 \
  --warmup_ratio 0.04 \
  --lr_scheduler_type cosine \
  --logging_steps 10 \
  --save_steps 500 \
  --save_total_limit 2 \
  --bf16 True \
  --tf32 True \
  --gradient_checkpointing True \
  --report_to none

if [ "${ISLORA}" = "1" ]; then
  python ${ROOTPATH}/merge_peft_adapter_qwen3_8b.py \
    --base_model ${MODEL_NAME} \
    --adapter_model ${PEFT_DIR} \
    --output_dir ${MERGED_DIR}
fi