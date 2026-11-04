# 벤치마크 평가 mock 컨테이너 (llm_evaluation P1a).
# 모델 로드/데이터셋 파싱 없음(mock) → torch 불필요 → slim 베이스(빠른 빌드/pull).
# SP-1 계약 FastAPI 래퍼만.
FROM python:3.11-slim

WORKDIR /srv
COPY requirements.txt /srv/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /srv/requirements.txt
COPY app.py /srv/app.py

ENV JF_PORT=8000

EXPOSE 8000
ENTRYPOINT []
CMD ["python3", "/srv/app.py"]
