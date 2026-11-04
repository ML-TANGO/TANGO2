# 플랫폼 소유 Ollama 서빙 이미지 (멀티엔진 서빙 Phase 3 / Tier B).
# 베이스: 공식 ollama/ollama — `ollama` 바이너리(HTTP 서버 + 모델 스토어) 포함.
#   TGI 와 달리 (1) `ollama serve` 가 모델을 로드하지 않아 serving_adapter 가 ready 후
#   `ollama create` 로 스토어에 등록, (2) 베이스에 python3 가 없어 apt 로 설치(TGI 는 uv venv 규약).
# 서빙 python(serving_adapter.py)은 이미지에 굽지 않고 helm configMap 으로 /llm 에 마운트
#   (기존 deployment_llm 규약과 동일). 이미지는 "런타임(ollama) + 도구 + shim 의존성"만 제공.
# 태그 0.32.0 = Docker Hub 최신 안정 semver(2026-07 조회). Qwen3 등 safetensors 임포트(`ollama create`)
#    지원 버전. 대상 아키텍처 지원은 빌드 스모크에서 재확인.
FROM ollama/ollama:0.32.0

# command.sh 스캐폴딩 도구 + serving_adapter 실행용 python(베이스에 없음).
#  - python3/python3-pip: serving_adapter.py 실행 + shim 의존성 설치
#  - nginx: 18555(외부) → 8555(app) 프록시
#  - net-tools(netstat): check_api_running 포트 확인
#  - curl: 헬스 체크
# 폐쇄망 대비 런타임 apt-install 을 피하려 미리 굽는다.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip nginx net-tools curl \
    && rm -rf /var/lib/apt/lists/*

# 플랫폼 서빙 레이어 파이썬 의존성. 추론 스택(torch)은 ollama 바이너리 내부라 shim 만 설치.
#  --break-system-packages: 최신 우분투 base 의 externally-managed 환경 우회(전용 서빙 이미지).
COPY requirements.txt /srv/requirements.txt
RUN python3 -m pip install --no-cache-dir --break-system-packages -r /srv/requirements.txt

# Ollama 런처 경로(베이스 규약). serving_adapter 가 subprocess 로 `ollama serve`/`ollama create` 호출.
#  실제 바인딩/스토어는 serving_adapter 의 extra_env(OLLAMA_HOST/OLLAMA_MODELS)가 지정.
ENV OLLAMA_BIN=ollama

# 실제 엔트리포인트는 helm command.sh 가 담당(pod command 로 오버라이드).
# 베이스 ollama 의 ENTRYPOINT(=/bin/ollama)를 비워 command.sh 가 온전히 실행되게 함.
ENTRYPOINT []
CMD ["bash"]
