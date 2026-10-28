# 플랫폼 소유 TensorRT-LLM 서빙 이미지 (멀티엔진 서빙 Phase 3 / Tier B).
# 베이스: 공식 nvcr.io/nvidia/tritonserver *-trtllm-python-py3 — tensorrt_llm(trtllm-serve CLI) +
#   torch/transformers/CUDA 포함. trtllm-serve 는 OpenAI 호환 서버(/v1/chat/completions, /health).
#   그 위에 플랫폼 서빙 레이어(FastAPI shim + nginx/모니터링 도구)만 얹는다.
# 서빙 python(serving_adapter.py)은 이미지에 굽지 않고 helm configMap 으로 /llm 에 마운트
#   (기존 deployment_llm 규약과 동일). 이미지는 "런타임(trtllm-serve) + 도구 + shim 의존성"만 제공.
# PyTorch 백엔드(`trtllm-serve serve <model> --backend pytorch`)로 HF 체크포인트 직접 로드
#   → 별도 AOT `trtllm-build` 엔진 컴파일 불요(vLLM/TGI 와 동형).
# ⚠️ 대용량(~25-30GB). nvcr.io 공개 pull(인증 불요). 태그 25.06 = Triton(vLLM) 이미지와 동일 릴리스 트레인.
FROM nvcr.io/nvidia/tritonserver:25.06-trtllm-python-py3

# command.sh 스캐폴딩 도구.
#  - nginx: 18555(외부) → 8555(app) 프록시
#  - net-tools(netstat): check_api_running 포트 확인
#  - curl: 헬스 체크
# 폐쇄망 대비 런타임 apt-install 을 피하려 미리 굽는다.
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx net-tools curl \
    && rm -rf /var/lib/apt/lists/*

# 플랫폼 서빙 레이어 파이썬 의존성(shim). torch/transformers/tensorrt_llm 은 베이스 제공 — 재핀 금지.
#  --break-system-packages: 최신 base 의 externally-managed 환경 우회(전용 서빙 이미지, 무해 no-op if 아님).
COPY requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir --break-system-packages -r /srv/requirements.txt

# 빌드타임 어서션: trtllm-serve CLI 가 베이스 이미지 PATH 에 실제 존재하는지 확인(없으면 빌드 실패).
#   벤더 이미지 버전별로 CLI 위치/존재가 상이할 수 있어(cf. llm_tgi Dockerfile 의 which 확인 관례),
#   ~25-30GB 이미지를 배포 시점에 처음 깨뜨리지 않도록 fail-fast. (25.06=TRT-LLM 0.20.0 번들 — codex 확인)
RUN which trtllm-serve

# TensorRT-LLM 런처 경로(베이스 규약). serving_adapter 가 subprocess 로 `trtllm-serve serve` 기동.
#  실제 host/port/backend/tp_size 는 serving_adapter 의 _tensorrt_build_args 가 지정.
ENV TRTLLM_SERVE_BIN=trtllm-serve

# 실제 엔트리포인트는 helm command.sh 가 담당(pod command 로 오버라이드).
# 베이스의 nvidia_entrypoint 는 pod command override 로 우회됨 → ENTRYPOINT 비워 command.sh 온전 실행.
ENTRYPOINT []
CMD ["bash"]
