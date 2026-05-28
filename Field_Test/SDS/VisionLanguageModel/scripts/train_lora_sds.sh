#!/usr/bin/env bash
# Phase 3: SDS 도메인 LoRA 파인튜닝
#
# 사전 준비:
#   python scripts/prepare_sds_dataset.py
#
# 3가지 학습 시나리오 중 SCENARIO 변수로 선택:
#   en         — 영문 해상상황묘사 + 영문 항해조력메시지
#   ko         — 한글 해상상황묘사 + 한글 항해조력메시지
#   ko_compact — 한글 간결 항해조력메시지
#
# 사용 예:
#   SCENARIO=en         bash scripts/train_lora_sds.sh
#   SCENARIO=ko         bash scripts/train_lora_sds.sh
#   SCENARIO=ko_compact bash scripts/train_lora_sds.sh
#
# 기본값: en

set -euo pipefail

PYTHON=/home/ywlee/miniconda3/envs/eva/bin/python
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── 시나리오 선택 ──────────────────────────────────────────────────────────────
SCENARIO="${SCENARIO:-en}"

case "$SCENARIO" in
  en)
    DATA_PATH="$ROOT/data/sds_train_en.json"
    OUTPUT_DIR="$ROOT/checkpoints/sds_lora_en"
    ;;
  ko)
    DATA_PATH="$ROOT/data/sds_train_ko.json"
    OUTPUT_DIR="$ROOT/checkpoints/sds_lora_ko"
    ;;
  ko_compact)
    DATA_PATH="$ROOT/data/sds_train_ko_compact.json"
    OUTPUT_DIR="$ROOT/checkpoints/sds_lora_ko_compact"
    ;;
  *)
    echo "ERROR: SCENARIO must be one of: en | ko | ko_compact"
    exit 1
    ;;
esac

echo "=== SDS LoRA Fine-tuning ==="
echo "  Scenario  : $SCENARIO"
echo "  Data      : $DATA_PATH"
echo "  Output    : $OUTPUT_DIR"

if [ ! -f "$DATA_PATH" ]; then
    echo "ERROR: $DATA_PATH not found. Run prepare_sds_dataset.py first."
    exit 1
fi

# ── 경로 ──────────────────────────────────────────────────────────────────────
LLM_MODEL="/home/ywlee/Llama-3.1-8B-Instruct"
#LLM_MODEL="/home/yvvyee/data/Llama-3.1-8B-Instruct"

IMAGE_DIR="/home/ywlee/dev/TANGO2_main/SDS/dataset/20260227"
#IMAGE_DIR="/home/yvvyee/data/SDS/dataset/20260227"

# 기존 LoRA 이어받기 (maritime 지식 보존)
# ① clip_llama31_lora_marine 이 있으면 우선 사용 (CC3M + LLaMarine 학습됨)
# ② 없으면 clip_llama31_lora 로 폴백 (CC3M 학습됨)
if [ -f "$ROOT/checkpoints/clip_llama31_lora_marine/adapter_config.json" ]; then
    RESUME_LORA="$ROOT/checkpoints/clip_llama31_lora_marine"
    PROJECTOR="$ROOT/checkpoints/clip_llama31_lora_marine/projector.bin"
    echo "  Base LoRA : clip_llama31_lora_marine (CC3M + LLaMarine)"
else
    RESUME_LORA="$ROOT/checkpoints/clip_llama31_lora"
    PROJECTOR="$ROOT/checkpoints/clip_llama31_lora/projector.bin"
    echo "  Base LoRA : clip_llama31_lora (CC3M only)"
fi

# ── GPU 감지 ──────────────────────────────────────────────────────────────────
NUM_GPUS=$(python3 -c "import torch; print(torch.cuda.device_count())" 2>/dev/null || echo 1)
echo "  GPUs      : $NUM_GPUS"

# ── 하이퍼파라미터 ─────────────────────────────────────────────────────────────
# 100개 소규모 데이터셋 전용 설정
# effective batch = BATCH_SIZE × GRAD_ACCUM × NUM_GPUS
BATCH_SIZE=1
GRAD_ACCUM=2
LEARNING_RATE=2e-4
NUM_EPOCHS=10          # 소규모 데이터셋: 충분한 반복 학습
MAX_SEQ_LEN=2048

# steps/epoch ≈ 100 / (1 × 2 × NUM_GPUS)
# 6 GPU → ~8 steps/epoch → 10 epoch → ~80 steps 총합
echo ""

# ── 런처 ──────────────────────────────────────────────────────────────────────
if [ "$NUM_GPUS" -gt 1 ]; then
    LAUNCHER="torchrun --nproc_per_node=$NUM_GPUS"
    DS_ARG="--deepspeed $ROOT/scripts/zero2.json"
else
    LAUNCHER="$PYTHON"
    DS_ARG=""
fi

$LAUNCHER "$ROOT/train.py" \
    --train_type      lora \
    --vision_model    "openai/clip-vit-large-patch14-336" \
    --llm_model       "$LLM_MODEL" \
    --projector_type  mlp2x_gelu \
    --projector_path  "$PROJECTOR" \
    --resume_lora_path "$RESUME_LORA" \
    --data_path       "$DATA_PATH" \
    --image_dir       "$IMAGE_DIR" \
    --output_dir      "$OUTPUT_DIR" \
    --num_epochs      $NUM_EPOCHS \
    --batch_size      $BATCH_SIZE \
    --grad_accum      $GRAD_ACCUM \
    --learning_rate   $LEARNING_RATE \
    --lr_scheduler    cosine \
    --warmup_ratio    0.03 \
    --max_seq_len     $MAX_SEQ_LEN \
    --dtype           bfloat16 \
    --gradient_checkpointing \
    --save_steps      100 \
    --logging_steps   5 \
    --dataloader_workers 4 \
    --wandb_project   vlm-v2 \
    --wandb_run_name  "sds_lora_${SCENARIO}" \
    $DS_ARG

# ── 완료 후 projector.bin 복사 ────────────────────────────────────────────────
PROJ_DST="$OUTPUT_DIR/projector.bin"
if [ ! -f "$PROJ_DST" ]; then
    cp "$PROJECTOR" "$PROJ_DST"
    echo "projector.bin → $PROJ_DST"
fi

echo ""
echo "=== 완료: $OUTPUT_DIR ==="
