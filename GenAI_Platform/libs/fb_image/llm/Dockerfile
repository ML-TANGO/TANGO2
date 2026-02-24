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
RUN pip3 install -U vllm==v0.5.4 modelscope ray ray[default]
# vLLM 0.5.4는 transformers 4.44.x / tokenizers 0.19.x 와 호환됨
# langchain-huggingface 설치 시 최신 버전으로 올라가므로 여기서 다시 고정
RUN pip3 install transformers==4.44.2 tokenizers==0.19.1
# RUN pip3 install -U vllm==v0.6.5 modelscope ray ray[default]