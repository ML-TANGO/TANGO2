# ============================================================================
# 배포 파이프라인 실행 이미지 (multi-stage)
#   - builder : llama.cpp 를 clone → CMake 컴파일 → 같은 폴더로 설치(bin/lib/include)
#   - runtime : 파이썬 변환 환경 + 컴파일된 llama.cpp 를 코드 옆(/app/llama.cpp)에 배치
#
# 이미지에 들어가는 것: pipeline.py 와 그 모듈 전부
#   pipeline.py                           파이프라인 드라이버 (기본 ENTRYPOINT)
#   yaml_parser.py                        deploy.yaml 파싱·검증·실행계획
#   model_optimizer/optimizer.py          양자화 (rtn/gptq/awq/fp8/nvfp4)
#   model_optimizer/pruner.py             프루닝 (unstructural/structural/wanda)
#   model_converter/model_converter.py    포맷 변환 (pytorch/safetensors/gguf/onnx)
#   code_generator/codegen.py             서비스 코드 생성
#   image_builder/imagebuild.py           배포 아티팩트 생성
#
# llama.cpp 는 model_converter.py 와 같은 위치(/app)에 'llama.cpp' 폴더로 둔다.
#   → model_converter.py 가 이 폴더를 기본값으로 자동 탐색하므로, gguf 변환 시
#     --llama-cpp-dir 를 줄 필요가 없다.
# 변환·검증은 CPU 기준(ONNX 검증도 CPUExecutionProvider). GPU 는 하단 주석 참고.
# builder/runtime 모두 Debian bookworm 기반으로 맞춰 런타임 라이브러리 호환성을 확보한다.
# ============================================================================

# ---------- 1) builder: llama.cpp 컴파일 ----------
FROM debian:bookworm-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates build-essential cmake libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# llama.cpp 다운로드 → /opt/llama.cpp 에 받아 컴파일하고, 같은 폴더에 설치(bin/lib/include)
#   - BUILD_SHARED_LIBS=OFF : 정적 링크 → 런타임에 .so 복사 불필요(바이너리만 옮기면 됨)
#   - GGML_NATIVE=OFF       : -march=native 비활성 → 빌드 머신 CPU 에 종속되지 않게(이식성)
#   - LLAMA_CURL=OFF        : libcurl 의존 제거(변환 이미지엔 불필요)
WORKDIR /opt
RUN git clone --depth 1 https://github.com/ggml-org/llama.cpp.git
RUN cmake -S /opt/llama.cpp -B /tmp/build \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_SHARED_LIBS=OFF \
        -DGGML_NATIVE=OFF \
        -DLLAMA_CURL=OFF \
    && cmake --build /tmp/build --config Release -j"$(nproc)" \
    && cmake --install /tmp/build --prefix /opt/llama.cpp \
    && rm -rf /opt/llama.cpp/.git

# ---------- 2) runtime: 파이썬 변환 환경 ----------
FROM python:3.11-slim

WORKDIR /app

# GPTQ/AWQ 의존성을 함께 넣을지 여부 (GPU 이미지에서만 의미가 있다)
#   docker compose build --build-arg INSTALL_QUANT=true
ARG INSTALL_QUANT=false

# llama.cpp 바이너리 실행에 필요한 런타임 라이브러리(OpenMP / C++ 런타임)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# PyTorch(CPU) — 전용 인덱스로 CUDA 의존 회피
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 변환·검증 의존성 (코드보다 먼저 복사해 레이어 캐시 활용)
COPY requirements.txt requirements-quant.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 양자화(GPTQ/AWQ) 의존성은 선택 설치.
#   RTN 은 이것 없이도 동작하므로 기본 이미지는 가볍게 유지한다.
RUN if [ "$INSTALL_QUANT" = "true" ]; then \
        pip install --no-cache-dir -r requirements-quant.txt; \
    else \
        echo "[build] INSTALL_QUANT=false — GPTQ/AWQ 의존성을 건너뜁니다 (RTN 은 사용 가능)"; \
    fi

# 컴파일·설치된 llama.cpp 를 '코드 옆'(/app/llama.cpp)에 배치
#   소스 트리(convert_hf_to_gguf.py, gguf-py 등) + 설치된 bin/lib/include 가 한 폴더에 들어간다.
COPY --from=builder /opt/llama.cpp/ /app/llama.cpp/

# 컴파일된 바이너리(llama-quantize, llama-cli 등)를 PATH 에 노출
ENV PATH="/app/llama.cpp/bin:${PATH}"

# convert_hf_to_gguf.py 가 쓰는 gguf 파이썬 모듈을 '클론한 버전과 동일하게' 설치
RUN pip install --no-cache-dir /app/llama.cpp/gguf-py

# 파이프라인 코드 일체 (llama.cpp 와 같은 위치 /app 에 둔다)
#   기능별 서브폴더 구조를 그대로 유지한다. pipeline.py 가 기동 시 각 서브폴더를
#   모듈 검색 경로에 넣으므로 별도 패키지화나 PYTHONPATH 설정이 필요 없다.
COPY pipeline.py yaml_parser.py deploy.yaml ./
COPY model_optimizer/ ./model_optimizer/
COPY model_converter/ ./model_converter/
COPY code_generator/ ./code_generator/
COPY image_builder/ ./image_builder/

ENV HF_HOME=/cache/huggingface
ENV PYTHONUNBUFFERED=1
# LLAMA_CPP_DIR 는 설정하지 않는다.
#   model_converter.py 가 '코드 옆 llama.cpp 폴더'(/app/llama.cpp)를 기본값으로 자동 탐색하므로
#   gguf 변환에 --llama-cpp-dir 가 필요 없다.

# CLI 진입점 — 실제 인자는 `docker compose run` 으로 전달
#   개별 도구를 직접 쓰려면 compose 의 converter / optimizer 서비스를 사용한다.
ENTRYPOINT ["python", "pipeline.py"]
CMD ["--help"]

# ── GPU 빌드로 바꾸려면 ──────────────────────────────────────────────
# 1) builder 를 nvidia/cuda:*-devel 이미지로, cmake 에 -DGGML_CUDA=ON 추가
# 2) runtime 을 nvidia/cuda:*-runtime 기반(혹은 CUDA 런타임 설치)으로
# 3) torch 를 CUDA 빌드, requirements 의 onnxruntime 를 onnxruntime-gpu 로
# 4) --build-arg INSTALL_QUANT=true 로 GPTQ/AWQ 의존성 포함
# 5) compose 의 deploy.devices(nvidia) 블록 활성화 + nvidia-container-toolkit
