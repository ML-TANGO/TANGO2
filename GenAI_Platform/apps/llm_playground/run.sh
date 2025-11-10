#!/bin/bash
# cd /app/src
# hypercorn -c hypercorn.toml main:app

# hypercorn main:app --bind 0.0.0.0:8000 --reload --workers 1 --access-logfile - --error-logfile - --worker-class trio    


uvicorn --factory main:main --host 0.0.0.0 --port 8000 \
--app-dir /app/src 
# --reload --reload-dir=/app/src --reload-dir=/utils \
# --workers 1
#--log-config uvicorn.ini