#!/usr/bin/env bash
# Edge remoteManager 에이전트 실행 (디바이스 호스트에서).
#   호스트의 docker 를 관리하므로 docker 접근 권한 있는 사용자로 실행.
#   설정은 env 로: AGENT_PORT MODEL_DIR CONTAINER_NAME GPU(auto|on|off)
#                  PLATFORM_HEARTBEAT_URL DEVICE_ID DEVICE_TOKEN
set -euo pipefail
cd "$(dirname "$0")"

python3 -m pip install --quiet -r requirements.txt
exec python3 -m uvicorn remote_manager_agent:app --host 0.0.0.0 --port "${AGENT_PORT:-8600}"
