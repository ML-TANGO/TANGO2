# 플랫폼 소유 llama.cpp 양자화·포팅 컨테이너 (SP-4 / v0.4 3.9).
# 베이스: 공식 llama.cpp full 이미지 — convert_hf_to_gguf.py + llama-quantize +
# torch(cpu)/transformers/gguf 포함. 그 위에 SP-1 계약 FastAPI 래퍼만 얹는다.
# b9628 고정 — SDS(eva-vlm) mmproj 키/텐서 규약(clip 'mlp', mm.0/mm.2)을 이 빌드로 검증했다.
# 태그 없는 :full 은 빌드 시점마다 바뀌어 mtmd 규약이 달라질 수 있다.
FROM ghcr.io/ggml-org/llama.cpp:full-b9628

# FastAPI 래퍼 (torch/transformers/gguf 는 베이스 제공). PEP 668(externally-managed)
# 환경 대비 --break-system-packages.
WORKDIR /srv
COPY requirements.txt /srv/requirements.txt
RUN python3 -m pip install --no-cache-dir --break-system-packages -r /srv/requirements.txt
COPY app.py eva_vlm.py /srv/

ENV LLAMA_QUANTIZE_BIN=/app/llama-quantize \
    CONVERT_HF_TO_GGUF=/app/convert_hf_to_gguf.py \
    LD_LIBRARY_PATH=/app \
    JF_PORT=8000

EXPOSE 8000
ENTRYPOINT []
CMD ["python3", "/srv/app.py"]
