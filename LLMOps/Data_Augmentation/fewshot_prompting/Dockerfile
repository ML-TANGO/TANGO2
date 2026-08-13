# Few-Shot Prompt Optimization service — Tango MSA backend.
# CPU-only is sufficient: this service does NOT host a model. It calls a
# remote OpenAI-compatible LLM endpoint (llm_url) supplied per request.
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=30000

WORKDIR /app

# Dependencies first (build-cache friendly).
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Service code.
COPY . .

# Must match values.yaml backend.port (Tango MSA 탑재 가이드).
EXPOSE 30000

# textgrad 는 import 시점에 CWD 기준 './logs/' 를 생성한다(textgrad/__init__.py).
# 플랫폼 external container 는 readOnlyRootFilesystem=true + runAsNonRoot 로 pod 을
# 띄우므로 /app 에 쓸 수 없어 import 자체가 OSError(Errno 30) 로 죽는다.
# → CWD 만 쓰기 가능한 /tmp(scratch emptyDir)로 옮기고, 모듈은 --app-dir 로 /app 에서
#   로드한다. 코드는 그대로 두고 실행 위치만 바꾸는 최소 우회.
WORKDIR /tmp

# HOME 을 쓰기 가능한 곳으로 고정 — CWD 우회만으로는 부족하다.
#   pod 은 runAsUser=1000 으로 돌고 이미지 /etc/passwd 에 그 uid 가 없어 HOME 이
#   설정되지 않는다 → os.path.expanduser("~") 가 "/" 로 해석되고, HOME 기준 캐시가
#   전부 루트에 잡혀 read-only rootfs 에서 죽는다:
#     textgrad → "/.cache/textgrad/cache_*.db"  (치명적 — OSError 로 job 실패)
#     dspy     → "/.dspy_cache/"                (graceful — memory-only 폴백)
#   XDG_CACHE_HOME 도 함께 지정해 XDG 규약을 따르는 라이브러리까지 덮는다.
ENV HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache

# /health, /info, /run, /status on :30000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "30000", "--app-dir", "/app"]
