# 사용자 정의 이미지 생성
FROM cupy/cupy:v12.0.0

# 필요한 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    vim \
    build-essential \
    dmidecode \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/src /fb_utils

COPY fb_monitoring /app
COPY fb_utils /fb_utils
COPY /usr/bin/nvidia* /usr/bin/

RUN rm /app/src/utils && ln -s /fb_utils /app/src/utils

RUN rm -rf /app/src/__pycache__ 
RUN rm -rf /fb_utils/__pycache__ 
RUN pip3 install -r /app/requirements.txt

