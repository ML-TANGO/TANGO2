FROM ubuntu:20.04 as ubuntu_20_04
RUN apt-get update

FROM docker:24.0.7-dind as dind
# FROM python:3.11.5
COPY --from=ubuntu_20_04 /lib /lib
COPY --from=ubuntu_20_04 /lib64 /lib64
RUN apk update && apk add gcc musl-dev python3-dev build-base linux-headers bash py3-pip curl

RUN mkdir -p /app/src /utils

COPY fb_image /app
COPY fb_utils /utils
RUN rm /app/src/utils && ln -s /utils /app/src/utils

RUN rm -rf /app/src/__pycache__ && \
    rm -rf /utils/__pycache__ && \
    rm /usr/lib/python3.11/EXTERNALLY-MANAGED && \
    pip install -r /app/requirements.txt

# EXTERNALLY-MANAGED
# https://stackoverflow.com/questions/75608323/how-do-i-solve-error-externally-managed-environment-every-time-i-use-pip-3

# pip install
ENV PYTHONUNBUFFERED=1
RUN apk add --update --no-cache python3 && ln -sf python3 /usr/bin/python
RUN python3 -m ensurepip
RUN pip3 install --no-cache --upgrade pip setuptools

# Helm 설치 (3.13.1 버전)
RUN curl -O https://get.helm.sh/helm-v3.13.1-linux-amd64.tar.gz && \
    tar -zxvf helm-v3.13.1-linux-amd64.tar.gz && \
    mv linux-amd64/helm /bin/helm && \
    rm -rf linux-amd64 && \
    rm helm-v3.13.1-linux-amd64.tar.gz

# ngc
RUN wget https://api.ngc.nvidia.com/v2/resources/nvidia/ngc-apps/ngc_cli/versions/3.35.0/files/ngccli_linux.zip -O ngccli_linux.zip && unzip ngccli_linux.zip && \
    find ngc-cli/ -type f -exec md5sum {} + | LC_ALL=C sort | md5sum -c ngc-cli.md5 && \
    sha256sum ngccli_linux.zip && \
    chmod u+x ngc-cli/ngc && \
    echo "export PATH=\"\$PATH:$(pwd)/ngc-cli\"" >> ~/.bash_profile && . ~/.bash_profile && \
    cp -r ngc-cli/* /bin/

# nerdctl
RUN wget --no-check-certificate https://github.com/containerd/nerdctl/releases/download/v1.7.6/nerdctl-1.7.6-linux-amd64.tar.gz && \
    tar -xvf nerdctl-1.7.6-linux-amd64.tar.gz && \
    cp /nerdctl /bin

# buildkit
RUN wget https://github.com/moby/buildkit/releases/download/v0.15.0/buildkit-v0.15.0.linux-amd64.tar.gz && \
    tar -xvf buildkit-v0.15.0.linux-amd64.tar.gz
