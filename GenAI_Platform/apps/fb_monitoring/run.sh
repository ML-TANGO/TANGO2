#!/bin/bash

#uvicorn --factory main:main --host 0.0.0.0 --port 8000 \
#--reload --reload-dir=/app/src --reload-dir=/utils \
#--app-dir /app/src 
# --workers 1
#--log-config uvicorn.ini 
python3 src/main.py
