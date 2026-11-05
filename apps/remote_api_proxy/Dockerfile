FROM python:3.11.5

RUN mkdir -p /app/src /utils

# llm_playground 와 같은 구조 — 앱 소스 + 공용 fb_utils 를 /utils 심링크로.
COPY remote_api_proxy /app
COPY fb_utils /utils
RUN rm -rf /app/src/utils && ln -s /utils /app/src/utils

RUN rm -rf /app/src/__pycache__ /utils/__pycache__ && \
    pip install --upgrade pip && \
    pip install -r /app/requirements.txt

WORKDIR /app/src
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
