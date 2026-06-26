# 플랫폼 소유 자동평가 컨테이너 (SP-5 / v0.4 3.8).
# 베이스: 공식 llama.cpp full 이미지 — torch/transformers 포함(convert 와 동일 베이스
# 재사용 → 추가 멀티GB pull 회피). 그 위에 SP-1 계약 FastAPI 래퍼만 얹는다.
# 메트릭(BLEU/ROUGE/perplexity)은 순수 파이썬 + torch 로 계산(외부 의존 없음).
FROM ghcr.io/ggml-org/llama.cpp:full

# SP-1 FastAPI 래퍼 deps(torch/transformers 는 베이스 제공). PEP 668 대비
# --break-system-packages.
WORKDIR /srv
COPY requirements.txt /srv/requirements.txt
RUN python3 -m pip install --no-cache-dir --break-system-packages -r /srv/requirements.txt
COPY app.py /srv/app.py

ENV LD_LIBRARY_PATH=/app \
    JF_PORT=8000

EXPOSE 8000
ENTRYPOINT []
CMD ["python3", "/srv/app.py"]
