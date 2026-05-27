#!/usr/bin/env bash
set -euo pipefail

export WANDB_MODE=disabled
export TOKENIZERS_PARALLELISM=false

ISLORA=${1:-1}   # 1 for LoRA, 0 for full fine-tuning
ROOTPATH=${2:-$(pwd)}
MODEL_NAME=${3:-Qwen/Qwen3.5-0.8B}
MAXLEN=${4:-2048}
EPOCH=${5:-3}

DATASET_NAME="Junrulu/Prompt_Preference_Dataset"
DATASET_SPLIT="train"

RAW_MODEL_PATH=${MODEL_NAME}
DEEPSPEED_CONFIG_PATH="${ROOTPATH}/data/ds_config.json"

if [[ ${ISLORA} -ne 0 ]]; then
  MODEL_OUTPUT_PATH="${ROOTPATH}/output/qwen35-0.8b-sft-peft"
  FINAL_MODEL_OUTPUT_PATH="${ROOTPATH}/output/qwen35-0.8b-sft-merged"
  PER_GPU_BATCH=8
  GRA_ACC=2
else
  MODEL_OUTPUT_PATH="${ROOTPATH}/output/qwen35-0.8b-sft-full"
  PER_GPU_BATCH=2
  GRA_ACC=4
fi

NPROC_PER_NODE=${GPU_NUM_PER_NODE:-1}
NNODES=${NODE_NUM:-1}
NODE_RANK=${INDEX:-0}
MASTER_ADDR=${MASTER_ADDR:-127.0.0.1}
MASTER_PORT=${MASTER_PORT:-29500}

torchrun --nnodes=${NNODES} \
  --node_rank=${NODE_RANK} \
  --nproc_per_node=${NPROC_PER_NODE} \
  --master_addr=${MASTER_ADDR} \
  --master_port=${MASTER_PORT} \
  ${ROOTPATH}/codes/train_sft_qwen35.py \
  --model_name_or_path ${RAW_MODEL_PATH} \
  --trust_remote_code True \
  --bf16 True \
  --output_dir ${MODEL_OUTPUT_PATH} \
  --num_train_epochs ${EPOCH} \
  --per_device_train_batch_size ${PER_GPU_BATCH} \
  --gradient_accumulation_steps ${GRA_ACC} \
  --save_strategy steps \
  --save_steps 1000 \
  --save_total_limit 1 \
  --learning_rate 2e-5 \
  --log_level info \
  --logging_strategy steps \
  --logging_steps 10 \
  --weight_decay 0.0 \
  --warmup_ratio 0.03 \
  --lr_scheduler_type cosine \
  --deepspeed ${DEEPSPEED_CONFIG_PATH} \
  --tf32 True \
  --model_max_length ${MAXLEN} \
  --dataset_name ${DATASET_NAME} \
  --dataset_split ${DATASET_SPLIT} \
  --raw_prompt_column raw_prompt \
  --target_column gpt4_optimized_prompt \
  --preprocessing_num_workers 4 \
  --gradient_checkpointing True \
  --report_to none \
  --if_lora ${ISLORA}

if [[ ${ISLORA} -ne 0 ]]; then
  python3 ${ROOTPATH}/codes/merge_peft_adapter_qwen35.py \
    --adapter_model_name ${MODEL_OUTPUT_PATH} \
    --base_model_name ${RAW_MODEL_PATH} \
    --output_name ${FINAL_MODEL_OUTPUT_PATH} \
    --trust_remote_code True
fi
