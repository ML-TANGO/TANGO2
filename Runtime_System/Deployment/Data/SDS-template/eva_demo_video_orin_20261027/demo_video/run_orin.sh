#!/usr/bin/env bash
# demo_video/run_orin.sh — Jetson Orin 에서 llama-server 와 데모 웹 서버를 띄운다.
#
#   ./run_orin.sh             # 서버만 (이미 계산된 results.json 사용)
#   ./run_orin.sh precompute  # 사전 추론을 먼저 채운 뒤 서버 실행
#
# 환경 변수로 경로를 바꿀 수 있다.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLAMA_BIN=${LLAMA_BIN:-$HOME/llama.cpp-eva/build-cuda/bin/llama-server}   # CLS 순서 패치 빌드 (README 13-2)
MODEL_DIR=${MODEL_DIR:-$HOME/models/eva_sds_ko_9k}
LLM_PORT=${LLM_PORT:-8080}
WEB_PORT=${WEB_PORT:-8000}
LOG_DIR=${LOG_DIR:-$HERE/logs}
mkdir -p "$LOG_DIR"

if ! curl -sf -m 2 "http://127.0.0.1:${LLM_PORT}/health" >/dev/null; then
  echo "[run] llama-server 시작 (port ${LLM_PORT})"
  nohup "$LLAMA_BIN" -m "$MODEL_DIR/llm-q8_0.gguf" --mmproj "$MODEL_DIR/mmproj.gguf" \
    -c 4096 -ngl 99 -np 1 --host 127.0.0.1 --port "$LLM_PORT" \
    > "$LOG_DIR/llama-server.log" 2>&1 < /dev/null &
  for _ in $(seq 120); do
    curl -sf -m 2 "http://127.0.0.1:${LLM_PORT}/health" >/dev/null && break
    sleep 2
  done
fi
curl -sf -m 2 "http://127.0.0.1:${LLM_PORT}/health" >/dev/null || { echo "[run] llama-server 기동 실패: $LOG_DIR/llama-server.log"; exit 1; }
echo "[run] llama-server 준비됨"

if [[ "${1:-}" == "precompute" ]]; then
  python3 "$HERE/precompute.py" --llm "http://127.0.0.1:${LLM_PORT}"
fi

# 장비에 주소가 여럿(docker, calico 등) 있으므로 모두 보여 준다. 청중은 같은 망의 주소로 접속한다.
for ip in $(hostname -I); do echo "[run] 데모 주소 후보: http://${ip}:${WEB_PORT}"; done
exec python3 "$HERE/server.py" --llm "http://127.0.0.1:${LLM_PORT}" --port "$WEB_PORT"
