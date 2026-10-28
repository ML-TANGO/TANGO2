FROM python:3.11.15-slim-bookworm
# python:3.11.4-buster (Debian 10) is EOL — its apt mirrors return 404.
# bookworm (Debian 12) is the current stable base image and matches what
# upstream python images recommend as of late 2025.

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc python3-dev curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/src /utils

# fb_external_container's own code lives in /app, shared fb_utils symlinked
# from /app/src/utils to /utils (same convention as apps/fb_user/Dockerfile).
COPY fb_external_container /app
COPY fb_utils /utils
RUN rm -f /app/src/utils && ln -s /utils /app/src/utils

RUN rm -rf /app/src/__pycache__ \
    && rm -rf /utils/__pycache__ \
    && pip install --no-cache-dir -r /app/requirements.txt -c /app/constraints.txt

WORKDIR /app
EXPOSE 8000

CMD ["./run.sh"]
