FROM python:3.13.4-slim

RUN apt-get update && apt-get install -y --allow-downgrades --allow-change-held-packages --no-install-recommends \
    vim git curl wget net-tools ethtool 


COPY fb_resource/src/storage /storage
COPY fb_utils /utils

RUN rm -rf /storage/src/__pycache__ && \
    rm -rf /utils/__pycache__ && \
    pip install -r /storage/requirements.txt

