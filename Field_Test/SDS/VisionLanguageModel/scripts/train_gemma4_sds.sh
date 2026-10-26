#!/usr/bin/env bash
# scripts/train_gemma4_sds.sh — 네이티브 Gemma 4 로 SDS 20260728 한글 9k 학습
#
# 로컬 RTX 5090 한 장을 쓴다. 원격의 프로젝터 체인 학습과는 별개다.
#
# 단계는 STAGE 로 고른다.
#   connector  커넥터(embed_vision)만 학습
#   lora       커넥터와 언어 모델 LoRA 를 함께 학습  (기본)
#   text_lora  이미지 없이 언어 모델 LoRA 만 학습 (LLaMarine 등)
#
#   bash scripts/train_gemma4_sds.sh
#   STAGE=connector bash scripts/train_gemma4_sds.sh
#   STAGE=text_lora DATA=/path/to/llamarine.parquet bash scripts/train_gemma4_sds.sh
#
# 배치 상한은 실측으로 정했다. 처음에 forward 와 backward 만 재어 배치 2 가
# 23.70 GB 로 들어간다고 보았으나, 실제 학습에서는 OOM 이었다. 그 측정에
# 옵티마이저 상태가 빠져 있었다. AdamW 는 학습 대상 281 M 에 대해 모멘텀 두
# 벌을 따로 들고 있는다. 배치 1 로 내려 전 구간이 통과하는 것을 확인했다.
#
# 단편화도 있었다. OOM 시점에 reserved 중 3.46 GB 가 미사용이었다. 그래서
# PYTORCH_CUDA_ALLOC_CONF 를 함께 설정한다.

set -uo pipefail

PYTHON="${PYTHON:-/home/ywlee/miniforge3/envs/eva/bin/python}"
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MODEL="${MODEL:-/home/ywlee/SSD/checkpoints/gemma-4-E4B-it}"
IMAGE_DIR="${IMAGE_DIR:-/home/ywlee/SSD/dataset/AIVN-SDS/20260728}"
STAGE="${STAGE:-lora}"

DATA="${DATA:-$ROOT/data/sds_train_ko_9k.json}"
VALID="${VALID:-$ROOT/data/sds_valid_ko_1k.json}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT/checkpoints/gemma4_e4b_sds_ko_9k_$STAGE}"

# 유효 배치 32. 원격의 Qwen3/Llama3.1 SDS 단계와 같은 값이라야 비교가 된다.
BATCH_SIZE="${BATCH_SIZE:-1}"
GRAD_ACCUM="${GRAD_ACCUM:-32}"
NUM_EPOCHS="${NUM_EPOCHS:-3}"
MAX_SEQ_LEN="${MAX_SEQ_LEN:-2048}"
SAVE_STEPS="${SAVE_STEPS:-200}"
EVAL_STEPS="${EVAL_STEPS:-100}"
MAX_STEPS="${MAX_STEPS:--1}"

EXTRA=()
if [ "$STAGE" = "text_lora" ]; then
    # 텍스트 전용 단계에는 이미지 인수를 주지 않는다.
    :
else
    EXTRA+=(--image_dir "$IMAGE_DIR" --valid_data_path "$VALID")
fi
[ -n "${RESUME_LORA:-}" ]    && EXTRA+=(--resume_lora_path "$RESUME_LORA")
[ -n "${CONNECTOR:-}" ]      && EXTRA+=(--connector_path "$CONNECTOR")

echo "=== Gemma 4 E4B — SDS 20260728 한글 ==="
echo "  모델      : $MODEL"
echo "  단계      : $STAGE"
echo "  학습      : $DATA"
echo "  산출      : $OUTPUT_DIR"
echo "  유효배치  : $((BATCH_SIZE * GRAD_ACCUM))  (batch $BATCH_SIZE × accum $GRAD_ACCUM)"
echo "  GPU       : ${CUDA_VISIBLE_DEVICES:-0}"
echo ""

"$PYTHON" "$ROOT/train_gemma4.py" \
    --model_path      "$MODEL" \
    --train_type      "$STAGE" \
    --data_path       "$DATA" \
    --output_dir      "$OUTPUT_DIR" \
    --num_epochs      "$NUM_EPOCHS" \
    --batch_size      "$BATCH_SIZE" \
    --grad_accum      "$GRAD_ACCUM" \
    --max_seq_len     "$MAX_SEQ_LEN" \
    --max_steps       "$MAX_STEPS" \
    --lr_scheduler    cosine \
    --warmup_ratio    0.03 \
    --dtype           bfloat16 \
    --gradient_checkpointing \
    --save_steps      "$SAVE_STEPS" \
    --save_total_limit 2 \
    --eval_steps      "$EVAL_STEPS" \
    --logging_steps   10 \
    --dataloader_workers 4 \
    --wandb_project   "${WANDB_PROJECT:-vlm-v2}" \
    --wandb_run_name  "gemma4_e4b_sds_ko_9k_$STAGE" \
    "${EXTRA[@]}"

echo ""
echo "=== 완료: $OUTPUT_DIR ==="
