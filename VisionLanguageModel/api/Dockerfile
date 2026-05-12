# ── 에바(Eva) VLM MSA 백엔드 ─────────────────────────────────────────────────
#
# 베이스: CUDA 12.4.1 (조나단 파인튜닝 이미지와 동일 CUDA 버전)
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

FROM nvidia/cuda:12.4.1-devel-ubuntu22.04

# ── 시스템 패키지 ─────────────────────────────────────────────────────────────
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 \
        python3.11-dev \
        python3-pip \
        python3.11-venv \
        git \
        curl \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# python3 → python3.11 심볼릭 링크
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python  python  /usr/bin/python3.11 1

# ── PyTorch (CUDA 12.4) ───────────────────────────────────────────────────────
RUN pip3 install --no-cache-dir \
    torch==2.5.1 \
    torchvision==0.20.1 \
    --index-url https://download.pytorch.org/whl/cu124

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

# HuggingFace 캐시 → NFS 마운트된 경로를 사용하도록 설정 가능
# (미설정 시 컨테이너 내 /root/.cache/huggingface/ 사용)
# ENV HF_HOME=/models/hf_cache

# ── 포트 ─────────────────────────────────────────────────────────────────────
EXPOSE 8000

# ── 실행 ─────────────────────────────────────────────────────────────────────
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", \
     "--timeout-keep-alive", "300"]
