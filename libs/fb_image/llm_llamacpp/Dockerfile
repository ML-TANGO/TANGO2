# 플랫폼 소유 llama.cpp 서빙 이미지 (멀티엔진 서빙 Phase 2).
# 베이스: 공식 llama.cpp full 이미지 — llama-server(HTTP 서버 바이너리) + convert_hf_to_gguf.py
#   + torch(cpu)/transformers/gguf 포함. 그 위에 플랫폼 서빙 레이어(FastAPI wrapper 의존성 +
#   nginx/모니터링 도구)만 얹는다.
# 서빙 python(playground_llamacpp.py 등)은 이미지에 굽지 않고 helm configMap 으로 /llm 에 마운트됨
#   (기존 deployment_llm 규약과 동일). 따라서 이미지는 "런타임 + 도구"만 제공.
FROM ghcr.io/ggml-org/llama.cpp:full

# _command.tpl 스캐폴딩이 기대하는 시스템 도구.
#  - nginx: 18555(외부) → 8555(app) 프록시
#  - net-tools(netstat): check_api_running 포트 확인
#  - curl: 헬스 체크
# 폐쇄망 대비 런타임 apt-install(install_package)을 피하려 미리 굽는다.
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx net-tools curl \
    && rm -rf /var/lib/apt/lists/*

# 플랫폼 서빙 레이어 파이썬 의존성 (torch/transformers/gguf 는 베이스 제공).
# PEP 668(externally-managed) 대비 --break-system-packages (apps/convert 와 동일 패턴).
COPY requirements.txt /srv/requirements.txt
RUN python3 -m pip install --no-cache-dir --break-system-packages -r /srv/requirements.txt

# llama.cpp 도구 경로 (베이스 llama.cpp:full 규약, apps/convert/Dockerfile 와 동일).
#  - llama-server: GGUF 를 OpenAI 호환 HTTP 로 서빙(+ --embeddings 로 임베딩 능력 내포)
#  - convert_hf_to_gguf.py: HF/commit 모델을 기동 시 GGUF 로 온더플라이 변환
ENV LLAMA_SERVER_BIN=/app/llama-server \
    CONVERT_HF_TO_GGUF=/app/convert_hf_to_gguf.py \
    LD_LIBRARY_PATH=/app

# 실제 엔트리포인트는 helm _command.tpl → /addlib/command.sh 가 담당(pod command 로 오버라이드).
# 이미지 CMD 는 미사용이나 로컬 스모크용 기본값.
ENTRYPOINT []
CMD ["bash"]
