FROM python:3.11.4-buster
# alpine - useradd, userdel 없음 -> buster 사용

RUN apt-get update && apt-get install -y gcc python3-dev musl-dev bash net-tools curl
# buster에서 설치 안됨 build-base, linux-headers

RUN mkdir -p /app/src /utils

COPY fb_user /app
COPY fb_utils /utils
RUN rm /app/src/utils && ln -s /utils /app/src/utils

RUN rm -rf /app/src/__pycache__ && \
    rm -rf /utils/__pycache__ && \
    pip install -r /app/requirements.txt