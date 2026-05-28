# ────────────────────────────────────────────────────────────────
# Grand‑Challenge CT‑CHAT submission image
#   • CUDA 12.2 development stack (nvcc available)
#   • Python 3.10 (Ubuntu 22.04 default)
# ────────────────────────────────────────────────────────────────
FROM nvidia/cuda:12.2.0-devel-ubuntu22.04

ARG PYTHON_VERSION=3.10
ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_NO_INPUT=1 PIP_DEFAULT_TIMEOUT=120   \
    TORCH_CUDA_ARCH_LIST=8.0,8.6             \
    DS_BUILD_OPS=1 FLASH_ATTENTION_FORCE_CUDA=1

# ---- System packages ---------------------------------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python${PYTHON_VERSION} python${PYTHON_VERSION}-dev \
        python3-pip python3-venv \
        build-essential git curl ca-certificates \
        ffmpeg libsm6 libxext6 \
        ninja-build cmake \
        && \
    rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python${PYTHON_VERSION} /usr/local/bin/python3 && \
    python3 -m pip install --upgrade pip setuptools wheel

# ---- Non‑root user & mandatory directories -----------------------------------
RUN groupadd -r user && useradd -m --no-log-init -r -g user user && \
    mkdir -p /opt/app /input /output && \
    chown -R user:user /opt/app /input /output

USER user
WORKDIR /opt/app
ENV PATH="/home/user/.local/bin:${PATH}"

# ---- Copy code & models ------------------------------------------------------
COPY --chown=user:user training  /opt/app/training
COPY --chown=user:user merlin    /opt/app/merlin
COPY --chown=user:user models    /opt/app/models
COPY --chown=user:user llm2vec4cxr /opt/app/llm2vec4cxr

# ---- Python dependencies -----------------------------------------------------
COPY --chown=user:user requirements.txt /opt/app/
RUN python3 -m pip install --user pip-tools && \
    python3 -m piptools sync requirements.txt

# Editable installs (if needed)
RUN pip install --user -e ./llm2vec4cxr

# ---- Inference entrypoint ----------------------------------------------------

COPY --chown=user:user process.py /opt/app/
RUN chmod +x /opt/app/process.py

# Grand Challenge entrypoint - generates reports from /input/ to /output/results.json
ENTRYPOINT ["python3", "/opt/app/process.py", "--checkpoint", "/opt/app/models/pytorch_model.bin", "--input_dir", "/input/", "--impressions_path", "/opt/app/models/impression.json", "--findings_path", "/opt/app/models/findings.json", "--impressions_emb", "/opt/app/models/impression_embeddings.pth", "--findings_emb", "/opt/app/models/findings_embeddings.pth", "--two_stage_retrieval", "--output_path", "/output/results.json", "--device", "cuda"]
