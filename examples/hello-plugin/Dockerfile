# hello-plugin Dockerfile — Tango 외부 컨테이너 보안 표준(spec §7.1) 준수
#
# 핵심 제약 (플랫폼이 securityContext 로 자동 강제):
#   - non-root (UID 1000)
#   - readOnlyRootFilesystem → 컨테이너 자체 디스크에 쓰지 않음. write 는
#     mount 된 /output, /tmp 만.
#   - drop ALL capabilities (ping/raw socket/iptables 등 사용 금지)
#
# GPU 컨테이너라면 base 를 nvidia/cuda:<ver>-runtime-ubuntu22.04 로 바꾸고,
# CUDA/torch 버전은 배포 클러스터 GPU driver 와 호환되는 것으로 (운영 측 조정).
FROM python:3.11-slim

# UID 1000 사용자 (securityContext.runAsUser 와 일치). root 권한 필요한 작업은
# 이 USER 전환 전에 모두 끝낸다.
RUN groupadd -g 1000 tango && useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash tango

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 컨테이너 코드 (RO 로 마운트돼도 무방 — 코드는 읽기만)
COPY --chown=1000:1000 app.py /app/app.py

USER 1000
# WORKDIR 은 writable 영역만. 코드는 --app-dir 로 /app 에서 import.
WORKDIR /tmp
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# 플랫폼이 JF_PORT 를 주입(manifest.spec.port). uvicorn 이 /app/app.py 의 app 을 서빙.
# shell-form 으로 ${JF_PORT} 를 읽는다 — exec-form 에 "8000" 하드코딩하면 port override 가
# 무시되어 probe/service 와 listen port 가 어긋난다.
ENTRYPOINT ["sh", "-c", "exec uvicorn --app-dir /app app:app --host 0.0.0.0 --port ${JF_PORT:-8000}"]
