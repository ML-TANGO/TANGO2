#!/usr/bin/env bash
# ETRI 평가 웹데모 서빙 환경 구축 (멱등).
#   1) 런타임 루트/로그/캐시 디렉터리
#   2) docker shim (실행 계정이 docker 그룹이 아니고 sudo 로만 docker 를 쓸 수 있을 때)
#   3) Logickor venv  : python3.11 + ETRI 핀 스냅샷(vllm/torch)
#   4) Intent  venv   : python3.11 stdlib 전용 (web_app.py)
#   5) Intent  이미지 : qwen3-mixatis:latest
#   6) Logickor 학습데이터 부트스트랩 + GPU 기본값
set -euo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/env.sh"

echo "== 1. 디렉터리 =="
mkdir -p "${SERVE_ROOT}"/{bin,venvs,hf_cache,logs,run,uv_cache}

echo "== 2. docker shim =="
cat > "${SHIM_BIN}/docker" <<'SHIM'
#!/usr/bin/env bash
# 실행 계정이 docker 그룹이 아니어도 sudo 로 docker 를 쓸 수 있으면 된다. ETRI 원본 스크립트를
# 고치지 않고 PATH 앞단에서 docker 호출을 sudo 로 넘긴다.
exec sudo -n /usr/bin/docker "$@"
SHIM
chmod +x "${SHIM_BIN}/docker"
PATH="${SHIM_BIN}:${PATH}" docker version --format '{{.Server.Version}}' >/dev/null \
  && echo "   docker OK" || { echo "   docker 접근 실패" >&2; exit 1; }

command -v uv >/dev/null || { echo "uv 가 필요합니다" >&2; exit 1; }
export UV_CACHE_DIR="${SERVE_ROOT}/uv_cache"

echo "== 3. Logickor venv (python 3.11 + vllm/torch) =="
if [[ ! -x "${LOGICKOR_VENV}/bin/python" ]]; then
  uv venv --python 3.11 "${LOGICKOR_VENV}"
fi
# ETRI README 는 `pip install --no-deps` 로 검증된 스냅샷을 그대로 넣으라고 한다.
# uv 는 --extra-index-url 에 대해 pip 과 달리 첫 인덱스만 보므로
# --index-strategy unsafe-best-match 가 있어야 pytorch cu128 인덱스와 PyPI 를 함께 본다.
uv pip install --python "${LOGICKOR_VENV}/bin/python" \
   --index-strategy unsafe-best-match --no-deps \
   -r "${LOGICKOR_DIR}/requirements.txt"

echo "== 4. Intent venv (stdlib 전용) =="
[[ -x "${INTENT_VENV}/bin/python" ]] || uv venv --python 3.11 "${INTENT_VENV}"

echo "== 5. Intent 이미지 =="
if PATH="${SHIM_BIN}:${PATH}" docker image inspect qwen3-mixatis:latest >/dev/null 2>&1; then
  echo "   qwen3-mixatis:latest 존재 — 건너뜀"
else
  ( cd "${INTENT_DIR}" && PATH="${SHIM_BIN}:${PATH}" docker build -t qwen3-mixatis:latest . )
fi

echo "== 6. Logickor 학습데이터 + 기본 GPU =="
python3 "${SERVE_DIR}/bootstrap_logickor_data.py"
# settings.json 의 gpu 기본값을 유휴 GPU 로 맞춘다(웹에서 변경 가능한 런타임 설정).
python3 - "$LOGICKOR_DIR/web/settings.json" "${LOGICKOR_GPU}" <<'PY'
import json, sys
p, gpu = sys.argv[1], sys.argv[2]
with open(p, encoding="utf-8") as f:
    s = json.load(f)
if s.get("gpu") != gpu:
    s["gpu"] = gpu
    with open(p, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
    print(f"   settings.json gpu -> {gpu}")
else:
    print(f"   settings.json gpu 이미 {gpu}")
PY

echo
echo "완료. 기동:  ${SERVE_DIR}/serve.sh start all"
