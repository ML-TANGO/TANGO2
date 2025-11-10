FROM python:3.11-bullseye
# 3.12는 langhain 오류날 수 있음

RUN apt-get update && apt-get install -y --allow-downgrades --allow-change-held-packages --no-install-recommends \
    vim git curl wget net-tools ethtool nginx rdma-core ibverbs-providers libibverbs-dev

COPY requirements.txt /app/requirements.txt
RUN pip install -U pip
RUN pip install -r /app/requirements.txt
RUN pip3 install -U langchain langchain-huggingface langchain-unstructured langchain-community langchain-milvus || true
RUN pip3 install -U langchain langchain-huggingface langchain-unstructured langchain-community langchain-milvus || true
RUN pip3 install -U vllm==v0.5.4 modelscope ray ray[default]
# RUN pip3 install -U vllm==v0.6.5 modelscope ray ray[default]