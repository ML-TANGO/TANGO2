#!/bin/bash

ENV_NAME="eva"
PYTHON_VERSION="3.11"
CUDA_INDEX="https://download.pytorch.org/whl/cu128"

echo ">>> [1/6] 가상환경($ENV_NAME) 생성"
# 기존 환경이 있다면 삭제 (선택 사항, 깨끗한 설치를 원할 때)
# conda remove -n $ENV_NAME --all -y

conda create -n $ENV_NAME python=$PYTHON_VERSION -y

eval "$(conda shell.bash hook)"
conda activate $ENV_NAME

echo ">>> [2/6] PyTorch (CUDA 12.8) 설치"
pip install torch torchvision torchaudio --index-url $CUDA_INDEX

echo ">>> [3/6] 핵심 라이브러리 (Transformers, Accelerate 등) 설치"
pip install -U transformers accelerate peft datasets diffusers

echo ">>> [4/6] 분산 학습 및 병렬 처리 도구 (DeepSpeed, MPI) 설치"
pip install deepspeed mpi4py

echo ">>> [5/6] 유틸리티 패키지 설치"
pip install Pillow requests tqdm sentencepiece bitsandbytes

echo ">>> [6/6] Flash Attention 설치 (빌드 격리 제외)..."
pip install ninja
# RAM 이 충분히 크다면 MAX_JOBS=4 옵션 제외하고 실행
MAX_JOBS=4 pip install flash-attn --no-build-isolation --no-cache-dir

echo "========================================="
echo "설치 완료"
echo "========================================="