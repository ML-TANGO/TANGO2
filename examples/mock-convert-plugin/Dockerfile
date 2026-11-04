# mock-convert-plugin Dockerfile — Tango 외부 컨테이너 보안 표준(spec §7.1) 준수.
# mock-generate/hello-plugin 과 동일 구조 (non-root UID 1000, write 는 mount 된 /output·/tmp 만).
FROM python:3.11-slim

RUN groupadd -g 1000 tango && useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash tango

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY --chown=1000:1000 app.py /app/app.py

USER 1000
WORKDIR /tmp
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

ENTRYPOINT ["sh", "-c", "exec uvicorn --app-dir /app app:app --host 0.0.0.0 --port ${JF_PORT:-8000}"]
