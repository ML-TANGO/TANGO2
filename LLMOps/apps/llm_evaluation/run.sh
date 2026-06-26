#!/bin/bash
uvicorn --factory main:main --host 0.0.0.0 --port 8000 \
--app-dir /app/src
