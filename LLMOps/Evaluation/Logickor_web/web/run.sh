#!/usr/bin/env bash
# Logickor 평가 웹 서비스 실행
#   bash web/run.sh                 # http://0.0.0.0:8000
#   PORT=8080 bash web/run.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(dirname "${SCRIPT_DIR}")"      # 프로젝트 루트에서 실행
exec python web/app.py
