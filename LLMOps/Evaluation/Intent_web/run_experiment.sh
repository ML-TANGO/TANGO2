#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run_experiment.sh
#   Qwen3-8B 를 MixATIS(UGEN QA)로 학습 -> 평가까지 한 번에 실행.
#
# 사용:
#   bash run_experiment.sh debug   # 빠른 점검(앞 200 학습예제 / 20 평가발화)
#   bash run_experiment.sh full    # 전체 학습(3 epoch) + 전체 평가(828발화)
#
# 환경변수로 덮어쓰기 가능:
#   MODEL_NAME, DATA_DIR, OUTPUT_DIR, EPOCHS, BATCH_SIZE, GRAD_ACCUM, MAX_LEN
#   USE_4BIT=0  -> 4bit 비활성(80GB+ GPU 에서 bf16 LoRA)
# ---------------------------------------------------------------------------
set -euo pipefail

# HF Hub 인증 토큰 (rate limit 상향 + gated 모델 접근).
# docker run -e HF_TOKEN=... 로 덮어쓸 수 있다.
export HF_TOKEN="${HF_TOKEN:-}"
# 일부 라이브러리는 구/신 변수명을 각각 참조하므로 둘 다 맞춰둔다.
export HUGGING_FACE_HUB_TOKEN="${HF_TOKEN}"

MODE="${1:-full}"

MODEL_NAME="${MODEL_NAME:-Qwen/Qwen3-8B}"
DATA_DIR="${DATA_DIR:-/workspace/UGEN/data/MixATIS_clean}"
OUTPUT_DIR="${OUTPUT_DIR:-/workspace/out/qwen3-8b-mixatis-lora}"
EVAL_CSV="${EVAL_CSV:-/workspace/out/mixatis_eval.csv}"
EPOCHS="${EPOCHS:-3}"
BATCH_SIZE="${BATCH_SIZE:-2}"
GRAD_ACCUM="${GRAD_ACCUM:-8}"
MAX_LEN="${MAX_LEN:-768}"

# 4bit(QLoRA) 기본 켜짐. USE_4BIT=0 으로 끌 수 있음.
USE_4BIT="${USE_4BIT:-1}"
QFLAG=""
if [ "${USE_4BIT}" = "1" ]; then
  QFLAG="--use_4bit"
fi

echo "=============================================================="
echo " MODE        : ${MODE}"
echo " MODEL_NAME  : ${MODEL_NAME}"
echo " DATA_DIR    : ${DATA_DIR}"
echo " OUTPUT_DIR  : ${OUTPUT_DIR}"
echo " 4bit(QLoRA) : ${USE_4BIT}"
echo "=============================================================="

# GPU 가시성 간단 확인 (없으면 경고만)
python - <<'PY' || true
import torch
print(f"[gpu] cuda available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"[gpu] device: {torch.cuda.get_device_name(0)}")
PY

if [ "${MODE}" = "debug" ]; then
  echo ">>> [1/2] 학습 (debug: 200 예제)"
  python train_qwen3_mixatis.py \
      --model_name "${MODEL_NAME}" \
      --data_dir "${DATA_DIR}" \
      --output_dir "${OUTPUT_DIR}" \
      --epochs 1 --batch_size "${BATCH_SIZE}" --grad_accum 1 \
      --max_len "${MAX_LEN}" --debug ${QFLAG}

  echo ">>> [2/2] 평가 (debug: 20 발화)"
  python evaluate_qwen3_mixatis.py \
      --model_name "${MODEL_NAME}" \
      --adapter_dir "${OUTPUT_DIR}" \
      --data_dir "${DATA_DIR}" \
      --out_csv "${EVAL_CSV}" \
      --limit 20 ${QFLAG}

elif [ "${MODE}" = "full" ]; then
  echo ">>> [1/2] 학습 (full: ${EPOCHS} epoch)"
  python train_qwen3_mixatis.py \
      --model_name "${MODEL_NAME}" \
      --data_dir "${DATA_DIR}" \
      --output_dir "${OUTPUT_DIR}" \
      --epochs "${EPOCHS}" --batch_size "${BATCH_SIZE}" --grad_accum "${GRAD_ACCUM}" \
      --max_len "${MAX_LEN}" ${QFLAG}

  echo ">>> [2/2] 평가 (full: 828 발화)"
  python evaluate_qwen3_mixatis.py \
      --model_name "${MODEL_NAME}" \
      --adapter_dir "${OUTPUT_DIR}" \
      --data_dir "${DATA_DIR}" \
      --out_csv "${EVAL_CSV}" ${QFLAG}

else
  echo "알 수 없는 MODE: '${MODE}' (debug 또는 full 만 가능)"
  exit 1
fi

echo "=============================================================="
echo " 완료. LoRA 어댑터: ${OUTPUT_DIR}"
echo "       평가 CSV    : ${EVAL_CSV}"
echo "=============================================================="
