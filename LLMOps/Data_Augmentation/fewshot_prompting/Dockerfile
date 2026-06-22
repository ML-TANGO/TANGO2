# Few-Shot Prompt Optimization service — Tango MSA backend.
# CPU-only is sufficient: this service does NOT host a model. It calls a
# remote OpenAI-compatible LLM endpoint (llm_url) supplied per request.
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=30000

WORKDIR /app

# Dependencies first (build-cache friendly).
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Service code.
COPY . .

# Must match values.yaml backend.port (Tango MSA 탑재 가이드).
EXPOSE 30000

# /health, /info, /run on :30000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "30000"]
