# 플랫폼 소유 llama.cpp 양자화·포팅 컨테이너 (SP-4 / v0.4 3.9).
# 베이스: 공식 llama.cpp full 이미지 — convert_hf_to_gguf.py + llama-quantize +
# torch(cpu)/transformers/gguf 포함. 그 위에 SP-1 계약 FastAPI 래퍼만 얹는다.
FROM ghcr.io/ggml-org/llama.cpp:full

# FastAPI 래퍼 (torch/transformers/gguf 는 베이스 제공). PEP 668(externally-managed)
# 환경 대비 --break-system-packages.
WORKDIR /srv
COPY requirements.txt /srv/requirements.txt
RUN python3 -m pip install --no-cache-dir --break-system-packages -r /srv/requirements.txt
COPY app.py /srv/app.py

ENV LLAMA_QUANTIZE_BIN=/app/llama-quantize \
    CONVERT_HF_TO_GGUF=/app/convert_hf_to_gguf.py \
    LD_LIBRARY_PATH=/app \
    JF_PORT=8000

EXPOSE 8000
ENTRYPOINT []
CMD ["python3", "/srv/app.py"]
