#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# auto2.sh
#   웹페이지(web_app.py)에서 넘겨준 설정으로 Qwen3-MixATIS 실험 컨테이너 실행.
#   run_experiment.sh 가 MODEL_NAME/DATA_DIR/OUTPUT_DIR/USE_4BIT 를 env 로 읽으므로
#   -e 로 그대로 전달하고, MODE 는 실행 인자로 넘긴다.
#
# 사용:
#   MODE=debug MODEL_NAME=Qwen/Qwen3-8B ... bash auto2.sh
#   (아무 것도 안 주면 아래 기본값 사용 = 웹페이지에 보이는 기본값)
# ---------------------------------------------------------------------------
set -euo pipefail

# 스크립트가 있는 위치로 이동 -> out 볼륨 마운트 경로가 항상 맞게 잡힘.
cd "$(dirname "$0")"

# ------------------------- 웹에서 수정 가능한 값 ----------------------------
MODE="${MODE:-debug}"
MODEL_NAME="${MODEL_NAME:-Qwen/Qwen3-8B}"
DATA_DIR="${DATA_DIR:-/workspace/UGEN/data/MixATIS_clean}"
OUTPUT_DIR="${OUTPUT_DIR:-/workspace/out/qwen3-8b-mixatis-lora}"
USE_4BIT="${USE_4BIT:-1}"
# --------------------------------------------------------------------------

HF_TOKEN="${HF_TOKEN:-}"
IMAGE="${IMAGE:-qwen3-mixatis:latest}"
GPU_DEVICE="${GPU_DEVICE:-0}"
CONTAINER_NAME="${CONTAINER_NAME:-qwen3_web_run}"

# 이전 실행이 남아 있으면 정리 (있을 때만).
docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true

# 로그가 실시간으로 흘러나오도록 -u(파이썬 unbuffered)는 이미지 내부에서 처리됨.
exec docker run --rm \
  --name "${CONTAINER_NAME}" \
  --gpus "\"device=${GPU_DEVICE}\"" \
  -e HF_TOKEN="${HF_TOKEN}" \
  -e MODEL_NAME="${MODEL_NAME}" \
  -e DATA_DIR="${DATA_DIR}" \
  -e OUTPUT_DIR="${OUTPUT_DIR}" \
  -e USE_4BIT="${USE_4BIT}" \
  -v "$(pwd)/out:/workspace/out" \
  -v hf_cache:/workspace/.hf_cache \
  "${IMAGE}" bash run_experiment.sh "${MODE}"
