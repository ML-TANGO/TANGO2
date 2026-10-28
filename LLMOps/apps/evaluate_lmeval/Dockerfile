# evaluate-lmeval — lm-evaluation-harness 벤치마크 실채점 컨테이너 (GPU, vLLM).
# 같은 이미지를 evaluate-lmeval / evaluate-lmeval-code 두 매니페스트가 쓴다(app.py docstring).
#
# 런타임은 LogicKor 심판 이미지와 같은 ETRI 스냅샷(torch 2.10 / transformers 5.5.4 /
# vllm 0.19.1, --no-deps)이다 — 이 클러스터 A100 에서 검증된 조합이고 lm_eval 0.4.12 의
# [vllm] extra(vllm>=0.18)를 만족한다. 그 위에 lm-eval 층을 정확한 버전으로 얹는다.
FROM python:3.11-slim

# vLLM 이 런타임에 libnuma / libgomp 를 dlopen 하고, Triton 은 CUDA 유틸을 런타임에 C 로
# 컴파일한다(컴파일러가 없으면 EngineCore 초기화에서 'Failed to find C compiler').
RUN apt-get update \
    && apt-get install -y --no-install-recommends libnuma1 libgomp1 gcc g++ python3-dev \
    && apt-get clean \
    && find /var/lib/apt/lists -mindepth 1 -delete

WORKDIR /srv

COPY etri-infer.txt /srv/etri-infer.txt
RUN python3 -m pip install --no-cache-dir --no-deps -r /srv/etri-infer.txt

COPY requirements-lmeval.txt /srv/requirements-lmeval.txt
RUN python3 -m pip install --no-cache-dir --no-deps -r /srv/requirements-lmeval.txt \
    && python3 -m pip check

COPY requirements-wrapper.txt /srv/requirements-wrapper.txt
RUN python3 -m pip install --no-cache-dir -r /srv/requirements-wrapper.txt

# 문항·지표 스크립트를 이미지에 적재한다 — 잡 파드는 egress 가 막혀 있다(network.isolate).
# HF_ALLOW_CODE_EVAL 은 **빌드 단계에만** 켠다: humaneval 태스크 모듈이 임포트 시점에
# code_eval 을 한 번 실행해 본다. 런타임 허용은 evaluate-lmeval-code 매니페스트 env 가 한다.
COPY registry.py prepare_tasks.py /srv/
RUN HF_HOME=/opt/lmeval/hf LMEVAL_TASKS_DIR=/opt/lmeval/tasks HF_ALLOW_CODE_EVAL=1 \
        python3 /srv/prepare_tasks.py fetch \
    && HF_HOME=/opt/lmeval/hf LMEVAL_TASKS_DIR=/opt/lmeval/tasks HF_ALLOW_CODE_EVAL=1 \
       HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_EVALUATE_OFFLINE=1 \
        python3 /srv/prepare_tasks.py verify

# 적재물은 root 로 만들어진다 — evaluate 가 받은 지표 스크립트(evaluate/downloads/*.py)는 600 이라
# 비루트 잡 파드가 복사하지 못해 잡이 시작 직후 Permission denied 로 죽었다(P1 직접 e2e 실측).
# 읽기 권한이 없는 것만 고친다(전부 chmod 하면 레이어가 캐시 크기만큼 복제된다).
RUN find /opt/lmeval -type f ! -perm -o=r -exec chmod o+r {} + \
    && find /opt/lmeval -type d ! -perm -o=rx -exec chmod o+rx {} +

# SP-1 v2 §7.1: 잡 파드는 non-root(runAsUser=1000) + readOnlyRootFilesystem 이다. UID 가
# /etc/passwd 에 없으면 'getpwuid(): uid not found: 1000' 로 죽는다(logickor-judge 실측).
RUN echo 'appuser:x:1000:1000:appuser:/tmp:/sbin/nologin' >> /etc/passwd \
    && echo 'appuser:x:1000:' >> /etc/group

COPY app.py scoring.py checkpoint.py custom_eval.py /srv/

# HF_HOME 은 쓰기 가능한 /tmp — 굽은 캐시(/opt/lmeval/hf)는 잡 시작 시 복사해 쓴다
# (datasets 가 캐시 디렉토리에 락 파일을 만든다). 오프라인 플래그는 매니페스트 env 에도 있다.
ENV HOME=/tmp \
    USER=appuser \
    LOGNAME=appuser \
    XDG_CACHE_HOME=/tmp/.cache \
    TRITON_CACHE_DIR=/tmp/.triton \
    VLLM_CACHE_ROOT=/tmp/.vllm \
    OUTLINES_CACHE_DIR=/tmp/.outlines \
    HF_HOME=/tmp/hf \
    LMEVAL_BAKED_HF_HOME=/opt/lmeval/hf \
    LMEVAL_TASKS_DIR=/opt/lmeval/tasks \
    HF_HUB_OFFLINE=1 \
    HF_DATASETS_OFFLINE=1 \
    HF_EVALUATE_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    TOKENIZERS_PARALLELISM=false \
    JF_PORT=8000 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
ENTRYPOINT []
CMD ["python3", "/srv/app.py"]
