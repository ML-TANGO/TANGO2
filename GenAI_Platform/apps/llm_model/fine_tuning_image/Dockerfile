# Base image with CUDA support
FROM nvidia/cuda:12.1.0-devel-ubuntu22.04

# Install basic utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    git \
    vim \
    ca-certificates \
    sudo \
    build-essential \
    software-properties-common \
    net-tools \
    python3-pip \
    ethtool \
    librdkafka-dev \
    openssh-client \
    openssh-server \
    iproute2 \
    numactl \
    && rm -rf /var/lib/apt/lists/*


COPY fine_tuning_image/requirements.txt /requirements.txt

# Install Hugging Face Transformers and other essential Python libraries for deep learning
RUN pip install -r /requirements.txt