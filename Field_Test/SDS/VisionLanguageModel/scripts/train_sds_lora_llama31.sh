#!/usr/bin/env bash
# Phase 3 (CLIP + Llama-3.1-8B-Instruct): SDS 도메인 LoRA 파인튜닝 — 20260728 한글
#
# scripts/train_sds_lora_qwen3.sh 의 Llama 대응판이다. 하이퍼파라미터와 런처는
# 같고 기본 경로만 다르다. LLaMarine 텍스트 전용 LoRA 단계는 Llama 계열에서
# 이미 끝나 있으므로(clip_llama31_lora_marine) 이 단계만 수행한다.
#
# 사전 준비:
#   python scripts/prepare_sds_dataset.py --dataset_dir <20260728 경로> \
#          --valid_ratio 0.1 --seed 42
#   → data/sds_train_ko_9k.json, data/sds_valid_ko_1k.json
#
# GPU 2,3,4,5 로 실행:
#   CUDA_VISIBLE_DEVICES=2,3,4,5 bash scripts/train_sds_lora_llama31.sh
#
# 짧은 연기 시험 (3 step):
#   CUDA_VISIBLE_DEVICES=2,3,4,5 MAX_STEPS=3 bash scripts/train_sds_lora_llama31.sh

set -euo pipefail

PYTHON="${PYTHON:-/home/yvvyee/miniconda3/envs/eva/bin/python}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── 경로 ──────────────────────────────────────────────────────────────────────
VISION_MODEL="${VISION_MODEL:-openai/clip-vit-large-patch14-336}"
LLM_MODEL="${LLM_MODEL:-/home/yvvyee/data/Models/Llama-3.1-8B-Instruct}"
RESUME_LORA="${RESUME_LORA:-$ROOT/checkpoints/clip_llama31_lora_marine}"
IMAGE_DIR="${IMAGE_DIR:-/home/yvvyee/data/AIVN-SDS/20260728}"
DATA_PATH="${DATA_PATH:-$ROOT/data/sds_train_ko_9k.json}"
VALID_DATA_PATH="${VALID_DATA_PATH:-$ROOT/data/sds_valid_ko_1k.json}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT/checkpoints/clip_llama31_proj_lora_marine_sds_ko}"

# 이 체크포인트에는 vlm_config.json 이 없다. train_text_lora.py 가 그것을
# 복사하려면 원본 LoRA 디렉토리에 있어야 하는데 CC3M 단계 산출물에만 있었다.
# 그래서 projector_type 을 인수로 명시한다. projector.bin 의 텐서는
# proj.0 (4096×1024) 과 proj.2 (4096×4096) 로 mlp2x_gelu 와 일치한다.
PROJECTOR="${PROJECTOR:-$RESUME_LORA/projector.bin}"
PROJECTOR_TYPE="${PROJECTOR_TYPE:-mlp2x_gelu}"

for path in "$LLM_MODEL" "$RESUME_LORA" "$PROJECTOR" "$IMAGE_DIR" \
            "$DATA_PATH" "$VALID_DATA_PATH"; do
    if [ ! -e "$path" ]; then
        echo "ERROR: $path 가 없습니다"
        exit 1
    fi
done

# ── GPU 감지 ──────────────────────────────────────────────────────────────────
NUM_GPUS=$("$PYTHON" -c "import torch; print(torch.cuda.device_count())")

# ── 하이퍼파라미터 ────────────────────────────────────────────────────────────
# Qwen3 실행과 같은 값을 쓴다. 두 조합의 결과를 같은 조건에서 비교하기 위함이다.
BATCH_SIZE="${BATCH_SIZE:-2}"        # per-device
GRAD_ACCUM="${GRAD_ACCUM:-4}"        # effective = BATCH_SIZE × GRAD_ACCUM × NUM_GPUS
LEARNING_RATE="${LEARNING_RATE:-2e-4}"
NUM_EPOCHS="${NUM_EPOCHS:-3}"
MAX_SEQ_LEN="${MAX_SEQ_LEN:-2048}"
SAVE_STEPS="${SAVE_STEPS:-200}"
EVAL_STEPS="${EVAL_STEPS:-100}"
SAVE_TOTAL_LIMIT="${SAVE_TOTAL_LIMIT:-3}"
MAX_STEPS="${MAX_STEPS:--1}"

STEPS_PER_EPOCH=$((9000 / (BATCH_SIZE * GRAD_ACCUM * NUM_GPUS)))

echo "=== SDS 도메인 LoRA 파인튜닝 (Llama-3.1-8B-Instruct, 20260728 ko) ==="
echo "  Vision    : $VISION_MODEL"
echo "  Base LLM  : $LLM_MODEL"
echo "  Resume    : $RESUME_LORA"
echo "  Projector : $PROJECTOR ($PROJECTOR_TYPE)"
echo "  Train     : $DATA_PATH"
echo "  Valid     : $VALID_DATA_PATH"
echo "  Images    : $IMAGE_DIR"
echo "  Output    : $OUTPUT_DIR"
echo "  GPUs      : $NUM_GPUS (CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-all})"
echo "  Eff.batch : $((BATCH_SIZE * GRAD_ACCUM * NUM_GPUS))  (~$STEPS_PER_EPOCH step/epoch)"
echo ""

# ── 런처 ──────────────────────────────────────────────────────────────────────
if [ "$NUM_GPUS" -gt 1 ]; then
    LAUNCHER=("$PYTHON" -m torch.distributed.run "--nproc_per_node=$NUM_GPUS")
    DS_ARG=(--deepspeed "$ROOT/scripts/zero2.json")
else
    LAUNCHER=("$PYTHON")
    DS_ARG=()
fi

"${LAUNCHER[@]}" "$ROOT/train.py" \
    --train_type       lora \
    --vision_model     "$VISION_MODEL" \
    --llm_model        "$LLM_MODEL" \
    --projector_type   "$PROJECTOR_TYPE" \
    --projector_path   "$PROJECTOR" \
    --resume_lora_path "$RESUME_LORA" \
    --data_path        "$DATA_PATH" \
    --image_dir        "$IMAGE_DIR" \
    --valid_data_path  "$VALID_DATA_PATH" \
    --output_dir       "$OUTPUT_DIR" \
    --num_epochs       "$NUM_EPOCHS" \
    --batch_size       "$BATCH_SIZE" \
    --grad_accum       "$GRAD_ACCUM" \
    --learning_rate    "$LEARNING_RATE" \
    --lr_scheduler     cosine \
    --warmup_ratio     0.03 \
    --max_seq_len      "$MAX_SEQ_LEN" \
    --max_steps        "$MAX_STEPS" \
    --dtype            bfloat16 \
    --gradient_checkpointing \
    --save_steps       "$SAVE_STEPS" \
    --save_total_limit "$SAVE_TOTAL_LIMIT" \
    --eval_steps       "$EVAL_STEPS" \
    --logging_steps    10 \
    --dataloader_workers 4 \
    --wandb_project    "${WANDB_PROJECT:-vlm-v2}" \
    --wandb_run_name   "${WANDB_RUN_NAME:-llama31_sds_lora_ko_20260728}" \
    "${DS_ARG[@]}"

echo ""
echo "=== 완료: $OUTPUT_DIR ==="
