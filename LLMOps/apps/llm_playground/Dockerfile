FROM python:3.11.5

# Build argument for conditional logic
ARG BUILD_TYPE=src

# Install essential tools and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    vim git curl wget net-tools ethtool librdkafka-dev sshpass && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Create necessary directories
RUN mkdir -p /app/src /utils

# Copy source files and create symbolic links
COPY llm_playground /app
COPY fb_utils /utils
RUN rm /app/src/utils && ln -s /utils /app/src/utils

# Install Python dependencies
RUN rm -rf /app/src/__pycache__ && \
    rm -rf /utils/__pycache__ && \
    pip install --upgrade pip && \
    pip install -r /app/requirements.txt && \
    pip install huggingface-hub

# Install Helm (3.13.1)
RUN curl -fsSL https://get.helm.sh/helm-v3.13.1-linux-amd64.tar.gz -o helm.tar.gz && \
    tar -zxvf helm.tar.gz && \
    mv linux-amd64/helm /usr/local/bin/helm && \
    rm -rf linux-amd64 helm.tar.gz

# Conditional PyInstaller binary build
RUN if [ "$BUILD_TYPE" = "binary" ]; then \
    cd /app && \
    mkdir /app/bin && \
    pyinstaller -y --hidden-import uvicorn --onefile ./src/main.py -n APP-BINARY --distpath /app/bin && \
    rm -rf /app/src; \
    fi

# Set working directory
WORKDIR /app
