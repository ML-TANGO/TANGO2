# 플랫폼 소유 Triton 서빙 이미지 (멀티엔진 서빙 Phase 3 / Tier B).
# 베이스: 공식 nvcr.io/nvidia/tritonserver *-vllm-python-py3 — tritonserver(HTTP/gRPC 추론서버) +
#   vLLM backend(HF/safetensors 직접) + torch/transformers/vllm/CUDA 포함. 그 위에 플랫폼 서빙
#   레이어(FastAPI shim + nginx/모니터링 도구)만 얹는다.
# 서빙 python(serving_adapter.py)은 이미지에 굽지 않고 helm configMap 으로 /llm 에 마운트
#   (기존 deployment_llm 규약과 동일). 이미지는 "런타임(triton+vllm) + 도구 + shim 의존성"만 제공.
# ⚠️ 대용량(~15-20GB). nvcr.io 공개 pull(인증 불요). 태그 25.06 = 최신 안정(2026-07 manifest 확인).
FROM nvcr.io/nvidia/tritonserver:25.06-vllm-python-py3

# command.sh 스캐폴딩 도구.
#  - nginx: 18555(외부) → 8555(app) 프록시
#  - net-tools(netstat): check_api_running 포트 확인
#  - curl: 헬스 체크
# 폐쇄망 대비 런타임 apt-install 을 피하려 미리 굽는다.
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx net-tools curl \
    && rm -rf /var/lib/apt/lists/*

# 플랫폼 서빙 레이어 파이썬 의존성(shim). torch/transformers/vllm/hf 는 베이스 제공 — 재핀 금지.
#  --break-system-packages: 최신 base 의 externally-managed 환경 우회(전용 서빙 이미지, 무해 no-op if 아님).
COPY requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir --break-system-packages -r /srv/requirements.txt

# Triton 런처 경로(베이스 규약). serving_adapter 가 subprocess 로 `tritonserver` 기동.
#  실제 model repository·바인딩은 serving_adapter 의 _triton_build_args/_triton_prepare 가 지정.
ENV TRITON_BIN=tritonserver

# 실제 엔트리포인트는 helm command.sh 가 담당(pod command 로 오버라이드).
# 베이스의 nvidia_entrypoint 는 pod command override 로 우회됨 → ENTRYPOINT 비워 command.sh 온전 실행.
ENTRYPOINT []
CMD ["bash"]
