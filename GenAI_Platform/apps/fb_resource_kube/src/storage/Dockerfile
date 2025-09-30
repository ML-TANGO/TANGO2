FROM python:3.11.5

RUN apt-get update && apt-get install -y --allow-downgrades --allow-change-held-packages --no-install-recommends \
    vim git curl wget net-tools ethtool 

COPY storage /storage
# COPY utils ./../utils

RUN rm -rf /storage/src/__pycache__ && \
    pip install -r /storage/requirements.txt

