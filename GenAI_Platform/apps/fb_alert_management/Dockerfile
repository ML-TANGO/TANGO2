FROM python:3.13.2

RUN apt-get update && apt-get install -y --allow-downgrades --allow-change-held-packages --no-install-recommends \
    vim git curl wget net-tools ethtool 

RUN mkdir -p /app/src /utils

COPY fb_alert_management /app
COPY fb_utils /utils
RUN rm /app/src/utils && ln -s /utils /app/src/utils

RUN rm -rf /app/src/__pycache__ && \
    rm -rf /utils/__pycache__ && \
    pip install -r /app/requirements.txt