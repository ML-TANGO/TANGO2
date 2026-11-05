# Qwen3-8B × MixATIS (UGEN QA) 실험용 이미지
# 베이스: 공식 PyTorch 이미지 (Python 3.11 / torch 2.5.1 / CUDA 12.1 / cuDNN9)
#  - GPU 학습/추론 + bitsandbytes 4bit 를 위해 CUDA 런타임 포함 이미지를 사용한다.
#  - torch 2.5+ 필수: transformers>=4.51 의 bitsandbytes 4bit 로더가
#    nn.Module.set_submodule() 를 사용하는데 이 API 는 torch 2.5 부터 추가됨.
#    (torch 2.4.1 에서는 'Qwen3ForCausalLM' object has no attribute 'set_submodule' 오류)
FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/workspace/.hf_cache

# UGEN 데이터셋 클론용 git
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# 파이썬 의존성 (torch 는 베이스 이미지에 이미 존재 -> requirements-docker.txt 에서 제외)
COPY requirements-docker.txt .
RUN pip install -r requirements-docker.txt

# UGEN 데이터셋(seq.in/seq.out/label + intent.json/slot.json) 클론 — 텍스트라 가볍다
RUN git clone --depth 1 https://github.com/Young1993/UGEN.git /workspace/UGEN

# 실험 코드 복사
COPY ugen_data.py train_qwen3_mixatis.py evaluate_qwen3_mixatis.py run_experiment.sh ./
RUN chmod +x run_experiment.sh

# 결과/캐시 디렉터리 (볼륨 마운트 권장)
RUN mkdir -p /workspace/out /workspace/.hf_cache

# 기본은 셸. 실험은 run_experiment.sh 로 실행.
CMD ["bash"]
