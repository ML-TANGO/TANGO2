FROM python:3.11.4-alpine3.18

RUN apk update && apk add gcc python3-dev musl-dev build-base linux-headers bash

RUN mkdir -p /app/src /utils

COPY fb_db /app
COPY fb_utils /utils
RUN rm /app/src/utils && ln -s /utils /app/src/utils

RUN rm -rf /app/src/__pycache__ && \
    rm -rf /utils/__pycache__ && \
    pip install -r /app/requirements.txt