# 서빙 이미지(tango_v2.0.1)와 같은 베이스 — 고정된 requirements(pydantic 2.4.1 등)는 이 Python 에서 빌드된다
FROM python:3.11.4-alpine3.18

RUN apk update && apk add gcc python3-dev musl-dev build-base linux-headers libffi-dev bash curl

RUN mkdir -p /app/src /utils

COPY fb_dashboard /app
COPY fb_utils /utils
RUN rm /app/src/utils && ln -s /utils /app/src/utils

RUN rm -rf /app/src/__pycache__ && \
    rm -rf /utils/__pycache__ && \
    pip install -r /app/requirements.txt