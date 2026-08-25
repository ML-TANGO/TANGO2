# MixATIS 다중의도·슬롯 평가 컨테이너 (GPU).
# 베이스는 CUDA 휠이 들어오는 slim python — torch cu121 휠이 CUDA 런타임을 함께 싣는다.
FROM python:3.11-slim

# transformers/tokenizers 가 런타임에 libgomp 를 dlopen 한다(slim 에 없음).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && apt-get clean \
    && find /var/lib/apt/lists -mindepth 1 -delete

WORKDIR /srv

COPY requirements.txt /srv/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /srv/requirements.txt

COPY requirements-wrapper.txt /srv/requirements-wrapper.txt
RUN python3 -m pip install --no-cache-dir -r /srv/requirements-wrapper.txt

# SP-1 v2 §7.1: 잡 파드는 non-root(runAsUser=1000) + readOnlyRootFilesystem 이다.
# 그 UID 가 /etc/passwd 에 없으면 홈을 찾는 코드가 'getpwuid(): uid not found: 1000' 로
# 죽는다. 읽기전용 루트라 런타임에 고칠 수 없으므로 항목을 구워 넣고 홈·캐시를
# 차트가 emptyDir 로 주는 /tmp 로 돌린다.
RUN echo 'appuser:x:1000:1000:appuser:/tmp:/sbin/nologin' >> /etc/passwd \
    && echo 'appuser:x:1000:' >> /etc/group

ENV HOME=/tmp \
    USER=appuser \
    LOGNAME=appuser \
    XDG_CACHE_HOME=/tmp/.cache \
    HF_HOME=/tmp/.hf

# ETRI 원본 3종 — build.sh 가 Evaluation/Intent_web 에서 그대로 복사해 스테이징한다.
# 복제본을 레포에 두지 않는 이유는 원본이 바뀌면 다음 빌드에 자동 반영되게 하려는 것이다.
# 셋 다 모듈 최상위 부작용이 없어 import 가 안전하다(지표·프롬프트 정의를 재구현하지 않는다).
COPY ugen_data.py /srv/ugen_data.py
COPY evaluate_qwen3_mixatis.py /srv/evaluate_qwen3_mixatis.py
COPY train_qwen3_mixatis.py /srv/train_qwen3_mixatis.py

# MixATIS 데이터 — build.sh 가 seq.out 을 복원해 스테이징한 사본.
# 벤치마크 정의 자체라 데이터셋 업로드 대상이 아니라 이미지에 baked 한다
# (런마다 같은 문항이어야 점수가 비교된다). 원본은 빌드 시 GitHub 을 쳤는데
# 폐쇄망에서 막히므로 저장소의 사본을 쓴다.
COPY data /srv/data

COPY scoring.py /srv/scoring.py
COPY evaluate.py /srv/evaluate.py
COPY train.py /srv/train.py
COPY app.py /srv/app.py

ENV JF_PORT=8000 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
ENTRYPOINT []
CMD ["python3", "/srv/app.py"]
