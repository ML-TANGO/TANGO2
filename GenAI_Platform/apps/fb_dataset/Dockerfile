FROM python:3.11.4-alpine3.18

RUN apk update && apk add gcc python3-dev musl-dev build-base linux-headers bash curl tree git git-lfs

RUN mkdir -p /app/src /utils

COPY fb_dataset /app
COPY fb_utils /utils
RUN rm /app/src/utils && ln -s /utils /app/src/utils

RUN rm -rf /app/src/__pycache__ && \
    rm -rf /utils/__pycache__ && \
    pip install -r /app/requirements.txt

RUN curl -O https://get.helm.sh/helm-v3.13.1-linux-amd64.tar.gz && \
    tar -zxvf helm-v3.13.1-linux-amd64.tar.gz && \
    mv linux-amd64/helm /bin/helm && \
    rm -rf linux-amd64 && \
    rm helm-v3.13.1-linux-amd64.tar.gz