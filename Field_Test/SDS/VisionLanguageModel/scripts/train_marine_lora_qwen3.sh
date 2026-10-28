#!/usr/bin/env bash
# Phase 2b (CLIP + Qwen3-8B): LLaMarine 텍스트 전용 LoRA 계속학습
#
# clip_qwen3_proj_lora (CC3M projector + LoRA 완료) 에서 이어받아 LLaMarine-SFT
# 명령-응답 데이터로 LLM 의 해양 도메인 지식만 보강한다. 비전 인코더와 프로젝터는
# 이 단계에서 적재하지 않으며, projector.bin 과 vlm_config.json 은 출력 디렉토리로
# 복사되어 다음 단계와 추론 경로가 그대로 이어 쓸 수 있게 한다.
#
# GPU 2,3,4,5 로 실행:
#   CUDA_VISIBLE_DEVICES=2,3,4,5 bash scripts/train_marine_lora_qwen3.sh
#
# 짧은 연기 시험 (2 step):
#   CUDA_VISIBLE_DEVICES=2,3,4,5 MAX_STEPS=2 bash scripts/train_marine_lora_qwen3.sh

set -euo pipefail

PYTHON="${PYTHON:-/home/yvvyee/miniconda3/envs/eva/bin/python}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── 경로 ──────────────────────────────────────────────────────────────────────
LLM_MODEL="${LLM_MODEL:-/home/yvvyee/data/Models/Qwen3-8B}"
LORA_PATH="${LORA_PATH:-$ROOT/checkpoints/clip_qwen3_proj_lora}"
DATA_PATH="${DATA_PATH:-/home/yvvyee/data/Models/llamarine-sft/train-00000-of-00001.parquet}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT/checkpoints/clip_qwen3_proj_lora_marine}"

for path in "$LLM_MODEL" "$LORA_PATH" "$DATA_PATH"; do
    if [ ! -e "$path" ]; then
        echo "ERROR: $path 가 없습니다"
        exit 1
    fi
done

# ── GPU 감지 ──────────────────────────────────────────────────────────────────
# CUDA_VISIBLE_DEVICES 를 존중해야 하므로 학습에 쓰는 것과 같은 인터프리터로 센다.
NUM_GPUS=$("$PYTHON" -c "import torch; print(torch.cuda.device_count())")

# ── 하이퍼파라미터 ────────────────────────────────────────────────────────────
BATCH_SIZE="${BATCH_SIZE:-2}"        # per-device
GRAD_ACCUM="${GRAD_ACCUM:-8}"        # effective = BATCH_SIZE × GRAD_ACCUM × NUM_GPUS
LEARNING_RATE="${LEARNING_RATE:-5e-5}"   # 초기 LoRA LR 보다 낮게: 파국적 망각 억제
NUM_EPOCHS="${NUM_EPOCHS:-1}"
MAX_SEQ_LEN="${MAX_SEQ_LEN:-2048}"
SAVE_STEPS="${SAVE_STEPS:-200}"
MAX_STEPS="${MAX_STEPS:--1}"

echo "=== LLaMarine 텍스트 전용 LoRA 계속학습 (Qwen3-8B) ==="
echo "  Base LLM  : $LLM_MODEL"
echo "  Resume    : $LORA_PATH"
echo "  Data      : $DATA_PATH"
echo "  Output    : $OUTPUT_DIR"
echo "  GPUs      : $NUM_GPUS (CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-all})"
echo "  Eff.batch : $((BATCH_SIZE * GRAD_ACCUM * NUM_GPUS))"
echo ""

# ── 런처 ──────────────────────────────────────────────────────────────────────
if [ "$NUM_GPUS" -gt 1 ]; then
    LAUNCHER=("$PYTHON" -m torch.distributed.run "--nproc_per_node=$NUM_GPUS")
    DS_ARG=(--deepspeed "$ROOT/scripts/zero2.json")
else
    LAUNCHER=("$PYTHON")
    DS_ARG=()
fi

"${LAUNCHER[@]}" "$ROOT/train_text_lora.py" \
    --llm_model      "$LLM_MODEL" \
    --lora_path      "$LORA_PATH" \
    --data_path      "$DATA_PATH" \
    --output_dir     "$OUTPUT_DIR" \
    --max_seq_len    "$MAX_SEQ_LEN" \
    --batch_size     "$BATCH_SIZE" \
    --grad_accum     "$GRAD_ACCUM" \
    --learning_rate  "$LEARNING_RATE" \
    --num_epochs     "$NUM_EPOCHS" \
    --max_steps      "$MAX_STEPS" \
    --dtype          bfloat16 \
    --gradient_checkpointing \
    --save_steps     "$SAVE_STEPS" \
    --logging_steps  10 \
    --dataloader_workers 4 \
    --wandb_project  "${WANDB_PROJECT:-vlm-v2}" \
    "${DS_ARG[@]}"

echo ""
echo "=== 완료: $OUTPUT_DIR ==="
echo "projector.bin 과 vlm_config.json 은 $LORA_PATH 에서 복사되었습니다."
