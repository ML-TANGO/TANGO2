# ── 에바(Eva) VLM MSA 백엔드 ─────────────────────────────────────────────────
#
# 베이스: CUDA 12.8.0 / Ubuntu 24.04 / Python 3.12
# 포트: 8000 (FastAPI/uvicorn)
#
# 필수 볼륨 마운트 (Helm Chart values.yaml 참고):
#   /models/llm/         ← LLM 모델 가중치 (Llama-3.1-8B-Instruct 등)
#   /models/checkpoints/ ← projector.bin + LoRA 어댑터
#
# 필수 환경 변수:
#   EVA_LLM_MODEL_PATH      /models/llm/<모델명>
#   EVA_CHECKPOINT_PATH     /models/checkpoints/<체크포인트명>
#   EVA_VISION_MODEL_NAME   openai/clip-vit-large-patch14-336  (기본값)
#   EVA_DEVICE              cuda:0  (기본값)
# ─────────────────────────────────────────────────────────────────────────────

FROM nvidia/cuda:12.8.0-devel-ubuntu24.04

# ── 시스템 패키지 ─────────────────────────────────────────────────────────────
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.12 \
        python3.12-dev \
        python3.12-venv \
        python3-pip \
        build-essential \
        git \
        curl \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# python3 / python 심볼릭 링크
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 \
    && update-alternatives --install /usr/bin/python  python  /usr/bin/python3.12 1

# Ubuntu 24.04 PEP 668 — externally-managed-environment 우회
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# ── PyTorch (CUDA 12.8) ───────────────────────────────────────────────────────
RUN pip3 install --no-cache-dir \
    torch==2.11.0 \
    torchvision==0.26.0 \
    torchaudio==2.11.0 \
    --index-url https://download.pytorch.org/whl/cu128

# ── flash-attn (소스 빌드, nvcc 12.8 사용) ────────────────────────────────────
RUN pip3 install --no-cache-dir 'ninja>=1.11' 'packaging>=23.0' \
    && MAX_JOBS=4 pip3 install --no-cache-dir flash-attn==2.8.3 --no-build-isolation

# ── Python 패키지 ─────────────────────────────────────────────────────────────
WORKDIR /app

# requirements만 먼저 복사하여 레이어 캐시 최적화
COPY api/requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# ── 에바 소스코드 복사 ────────────────────────────────────────────────────────
# VisionLanguageModel/ 디렉토리 전체를 /app/vlm/ 에 배치
COPY . /app/vlm/

# API 서버 파일은 /app/ 루트에도 배치 (uvicorn 진입점)
COPY api/app.py            /app/app.py
COPY api/model_manager.py  /app/model_manager.py
COPY api/train_manager.py  /app/train_manager.py
COPY api/schemas.py        /app/schemas.py

# ── 환경 변수 기본값 ──────────────────────────────────────────────────────────
ENV EVA_VLM_ROOT=/app/vlm
ENV EVA_VISION_MODEL_NAME=openai/clip-vit-large-patch14-336
ENV EVA_DEVICE=cuda:0
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TORCH_EXTENSIONS_DIR=/tmp/torch_extensions

# HuggingFace 캐시 → NFS 마운트된 경로를 사용하도록 설정 가능
# (미설정 시 컨테이너 내 /root/.cache/huggingface/ 사용)
# ENV HF_HOME=/models/hf_cache

# ── 포트 ─────────────────────────────────────────────────────────────────────
EXPOSE 8000

# ── 실행 ─────────────────────────────────────────────────────────────────────
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", \
     "--timeout-keep-alive", "300"]
