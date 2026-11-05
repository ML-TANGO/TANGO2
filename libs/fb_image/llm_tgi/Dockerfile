# 플랫폼 소유 TGI 서빙 이미지 (멀티엔진 서빙 Phase 3 / Tier B).
# 베이스: 공식 HF text-generation-inference — text-generation-launcher(HTTP 서버 바이너리) +
#   torch/transformers/CUDA 커널 포함(플랫폼 핀과 격리). 그 위에 플랫폼 서빙 레이어(FastAPI
#   shim 의존성 + nginx/모니터링 도구)만 얹는다.
# 서빙 python(serving_adapter.py 등)은 이미지에 굽지 않고 helm configMap 으로 /llm 에 마운트됨
#   (기존 deployment_llm 규약과 동일). 따라서 이미지는 "런타임 + 도구"만 제공.
# 태그 v3.3.7 = 2025-12-19 최신 안정 릴리스. A100(compute 8.0) 호환. 클러스터 CUDA 드라이버와
#   정합하는지 빌드 스모크에서 확인 후 필요시 조정.
FROM ghcr.io/huggingface/text-generation-inference:3.3.7

# _command.tpl/command.sh 스캐폴딩이 기대하는 시스템 도구.
#  - nginx: 18555(외부) → 8555(app) 프록시
#  - net-tools(netstat): check_api_running 포트 확인
#  - curl: 헬스 체크
# 폐쇄망 대비 런타임 apt-install 을 피하려 미리 굽는다.
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx net-tools curl \
    && rm -rf /var/lib/apt/lists/*

# 플랫폼 서빙 레이어 파이썬 의존성 (torch/transformers 는 베이스 제공 — 여기서 재핀 금지).
# TGI 베이스는 uv 로 만든 venv(/usr/src/.venv, pip 미포함)를 쓴다 → uv 로 그 venv 에 설치.
#   (llm_llamacpp 는 pip 가 있어 python3 -m pip 였으나 TGI 는 uv 규약이라 다름.)
COPY requirements.txt /srv/requirements.txt
RUN uv pip install --no-cache --python /usr/src/.venv/bin/python3 -r /srv/requirements.txt

# TGI 런처 경로 (베이스 규약). serving_adapter 가 subprocess 로 기동.
#  - text-generation-launcher: 로컬 model 경로를 OpenAI 호환 HTTP 로 서빙(오프라인)
# 실제 PATH 위치는 벤더 이미지 버전별 상이 → 빌드 후 `which text-generation-launcher` 로 확인.
ENV TGI_LAUNCHER_BIN=text-generation-launcher

# 실제 엔트리포인트는 helm command.sh 가 담당(pod command 로 오버라이드).
# 이미지 CMD 는 미사용이나 로컬 스모크용 기본값.
ENTRYPOINT []
CMD ["bash"]
