# LogicKor 심판 채점 + 집계 컨테이너 (GPU).
# CUDA 는 pip 휠로 들어온다(ETRI 스냅샷에 nvidia-*-cu12 19개 + --extra-index-url cu128)
# → CUDA 베이스 이미지가 필요 없다. 파이썬은 ETRI 검증 환경과 같은 3.11.
#
# 의존성은 ETRI 가 실제로 돌린 스냅샷(requirements/etri-infer.txt, 185줄)을 --no-deps 로
# 그대로 설치한다. 그들의 README 지시이며, torch 2.10 / transformers 5.5.4 / vllm 0.19.1
# 조합은 이 스냅샷 안에서만 검증돼 있다. resolver 에 맡기면 조합이 바뀐다.
FROM python:3.11-slim

# vLLM 이 런타임에 libnuma / libgomp 를 dlopen 한다(slim 에 없음).
# gcc/g++/python3-dev 는 Triton 때문에 필요하다 — Triton 은 CUDA 유틸 모듈을 **런타임에**
# C 로 컴파일한다(triton/backends/nvidia/driver.py: CudaUtils → compile_module_from_src).
# 컴파일러가 없으면 vLLM 엔진 코어 초기화 단계에서
#   RuntimeError: Failed to find C compiler
# 로 죽는다(2026-08-21 실측). ETRI 는 빌드도구가 있는 conda 환경이라 겪지 않은 문제다.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libnuma1 libgomp1 gcc g++ python3-dev \
    && apt-get clean \
    && find /var/lib/apt/lists -mindepth 1 -delete

WORKDIR /srv

# 빌드 컨텍스트는 build.sh 가 스테이징한 디렉토리다(레포 루트를 컨텍스트로 넣지 않기
# 위함 — Evaluation/ 산출물만 20MB 다).
COPY etri-infer.txt /srv/etri-infer.txt
RUN python3 -m pip install --no-cache-dir --no-deps -r /srv/etri-infer.txt

# SP-1 래퍼용 deps(스냅샷에 fastapi 가 있더라도 버전 보장을 위해 명시)
COPY requirements-wrapper.txt /srv/requirements-wrapper.txt
RUN python3 -m pip install --no-cache-dir -r /srv/requirements-wrapper.txt

# SP-1 v2 §7.1: 잡 파드는 non-root(runAsUser=1000) + readOnlyRootFilesystem 이다.
# 그 UID 가 /etc/passwd 에 없으면 홈 디렉토리를 찾는 코드가 죽는다
#   → 'getpwuid(): uid not found: 1000' (2026-08-21 실측 실패).
# 런타임에 /etc/passwd 를 고칠 수 없으므로(읽기전용 루트) 항목을 구워 넣고, 홈·캐시는
# 차트가 emptyDir 로 마운트해 주는 /tmp 로 돌린다. HOME/USER/LOGNAME 을 함께 박는 이유:
# expanduser 는 HOME 을, getpass.getuser() 는 LOGNAME/USER 를 먼저 보므로 UID 가 바뀌어도
# getpwuid 까지 내려가지 않는다.
RUN echo 'appuser:x:1000:1000:appuser:/tmp:/sbin/nologin' >> /etc/passwd \
    && echo 'appuser:x:1000:' >> /etc/group

ENV HOME=/tmp \
    USER=appuser \
    LOGNAME=appuser \
    XDG_CACHE_HOME=/tmp/.cache \
    TRITON_CACHE_DIR=/tmp/.triton \
    VLLM_CACHE_ROOT=/tmp/.vllm \
    OUTLINES_CACHE_DIR=/tmp/.outlines

# templates.py = ETRI 원본 심판 프롬프트(복제본을 레포에 두지 않는다)
# scoring.py   = evaluate-logickor 와 공유하는 집계 로직(점수 정의 단일화)
COPY templates.py /srv/templates.py
COPY scoring.py /srv/scoring.py
COPY judge.py /srv/judge.py
COPY app.py /srv/app.py

# HF_HOME 은 /hf-cache(읽기전용 공유 NFS) — operator 가 미리 받아둔 가중치를 cache hit
# 으로 읽는다. 여기에 쓰려 하면 실패하므로 다운로드가 필요한 모델은 사전 캐시가 전제다.
ENV JF_PORT=8000 \
    HF_HOME=/hf-cache \
    PYTHONUNBUFFERED=1

EXPOSE 8000
ENTRYPOINT []
CMD ["python3", "/srv/app.py"]
