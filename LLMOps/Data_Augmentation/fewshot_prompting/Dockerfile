# NVIDIA CUDA 기반 이미지를 사용 (GPU 추론 지원)
# vLLM이 원활하게 동작하기 위해 CUDA 12.1.1 런타임 사용
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

# 환경변수 설정 (파이썬이 버퍼링 없이 출력하도록 설정, 시간대 설정)
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 시스템 의존성 및 Python 설치
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# 파이썬 기본 명령어를 python3로 연결
RUN ln -s /usr/bin/python3 /usr/bin/python

# 의존성 파일 복사 및 설치
COPY requirements.txt .

# pip 업그레이드 및 필수 패키지 설치
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# 애플리케이션 실행
CMD ["python", "main.py"]
