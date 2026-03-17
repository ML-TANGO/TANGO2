FROM python:3.11-bullseye
# 3.12는 langhain 오류날 수 있음

RUN apt-get update && apt-get install -y --allow-downgrades --allow-change-held-packages --no-install-recommends \
    vim git curl wget net-tools ethtool nginx rdma-core ibverbs-providers libibverbs-dev

COPY requirements.txt /app/requirements.txt
RUN pip install -U pip
RUN pip install -r /app/requirements.txt
RUN pip3 install -U "setuptools<81"
# Work around broken pyairports 0.0.1 distribution pulled by outlines on Python 3.11
RUN pip3 install -U "git+https://github.com/NICTA/pyairports.git"
RUN pip3 install -U langchain langchain-huggingface langchain-unstructured langchain-community langchain-milvus || true
RUN pip3 install -U langchain langchain-huggingface langchain-unstructured langchain-community langchain-milvus || true
RUN pip3 install -U "vllm>=0.8.0" modelscope "ray[default]"
# vLLM 0.8.x+: Qwen 3, LLaMA 4 등 최신 아키텍처 지원 (transformers>=4.51.0 필요)
# langchain-huggingface 설치 시 버전이 내려갈 수 있으므로 다시 고정
RUN pip3 install "transformers>=4.52.4,<5.0.0" "tokenizers>=0.21.0"