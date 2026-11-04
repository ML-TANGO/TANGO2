#!/bin/bash

# Docker 이미지 이름과 태그 지정
IMAGE_NAME="registry.jonathan.acryl.ai/jfb-system/cuda-12.2.0:0.1.7"
DOCKERFILE="Dockerfile"
# Docker 이미지 빌드
#docker build -t "$IMAGE_NAME" .

sudo nerdctl build --no-cache --tag $IMAGE_NAME -f $DOCKERFILE ./../../..
sudo nerdctl push $IMAGE_NAME


# 빌드 결과 확인
if [ $? -eq 0 ]; then
    echo "Docker image '$IMAGE_NAME' was built successfully."
else
    echo "Error occurred during Docker image build."
    exit 1
fi
