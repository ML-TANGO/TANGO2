#!/bin/bash

uvicorn --factory main:main --host 0.0.0.0 --port 8000 \
--app-dir /app/src 
# --reload --reload-dir=/app/src --reload-dir=/utils \

# python3 src/main.py