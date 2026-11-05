#!/bin/bash

uvicorn --factory main:main --host 0.0.0.0 --port 8000 \
--reload --reload-dir=/app/src --reload-dir=/utils \
--app-dir /app/src 

# python3 src/main.py