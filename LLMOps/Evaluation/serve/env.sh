#!/usr/bin/env bash
# ETRI 평가 웹데모(Intent_web / Logickor_web) 서빙 공통 설정.
# ETRI 원본 소스는 건드리지 않고, 이 계층에서 포트/GPU/캐시/권한만 주입한다.

# 이 파일 위치 기준으로 경로를 잡는다(worktree/체크아웃 위치 무관).
SERVE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EVAL_DIR="$(dirname "${SERVE_DIR}")"
INTENT_DIR="${EVAL_DIR}/Intent_web"
LOGICKOR_DIR="${EVAL_DIR}/Logickor_web"

# 런타임 산출물(venv/캐시/로그/pid)은 저장소 밖에 둔다.
SERVE_ROOT="${SERVE_ROOT:-$HOME/etri-eval-serve}"
LOG_DIR="${SERVE_ROOT}/logs"
RUN_DIR_PID="${SERVE_ROOT}/run"
SHIM_BIN="${SERVE_ROOT}/bin"

# --- 포트 -------------------------------------------------------------------
# 이 호스트는 8080/8081 이 이미 점유되어 있어 Intent 는 8090 으로 옮겼다.
INTENT_PORT="${INTENT_PORT:-8090}"
LOGICKOR_PORT="${LOGICKOR_PORT:-8000}"

# --- GPU --------------------------------------------------------------------
# 기본값 6,7 번. 서빙 스택이 쓰는 GPU 와 겹치지 않게 호스트에 맞춰 바꾼다.
INTENT_GPU="${INTENT_GPU:-7}"     # auto2.sh 의 GPU_DEVICE (docker --gpus device=N)
LOGICKOR_GPU="${LOGICKOR_GPU:-6}" # auto.sh 의 GPU (CUDA_VISIBLE_DEVICES)

# --- 파이썬 -----------------------------------------------------------------
LOGICKOR_VENV="${SERVE_ROOT}/venvs/logickor"   # py3.11 + vllm/torch (무거움)
INTENT_VENV="${SERVE_ROOT}/venvs/intent"       # py3.11 stdlib 전용 (web_app.py)

# --- HF 캐시 ----------------------------------------------------------------
export HF_HOME="${HF_HOME:-${SERVE_ROOT}/hf_cache}"

# --- 토큰 (선택) -------------------------------------------------------------
# Qwen3-8B / gemma-4-E4B-it 는 비게이트라 토큰 없이도 받아진다.
# rate limit 회피용으로만 쓰며, 넣고 싶으면 아래 파일에 HF_TOKEN=... 한 줄.
SECRETS_FILE="${SERVE_ROOT}/secrets.env"
if [[ -f "${SECRETS_FILE}" ]]; then
  set -a; . "${SECRETS_FILE}"; set +a
fi
export HF_TOKEN="${HF_TOKEN:-}"
