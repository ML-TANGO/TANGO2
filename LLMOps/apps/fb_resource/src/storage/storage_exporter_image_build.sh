#!/bin/bash
# SP-Ext.4: 인프라 app 차트와 동일하게 오픈 docker hub (acrylaaai) 로 push.
# helm chart (apps/fb_resource/src/storage/helm_chart/storage-exporter,
# devops/gaip_prometheus/storage-exporter) 가 docker.io/acrylaaai/storage-exporter
# 를 참조한다. 이전엔 build.sh 만 사내 registry (registry.jonathan.acryl.ai)
# 타겟이라 chart 와 불일치했음.
IMAGE_REGI="docker.io"
IMAGE_REPO="acrylaaai"
DOCKERFILE="Dockerfile"
TAG=0.3.2
IMAGE_REGISTRY=$IMAGE_REGI/$IMAGE_REPO
APP_NAME="storage-exporter"

# Get First tag ordered by tag name
IMAGE_INFO=$(sudo crictl images | sort -k 2 | grep "$IMAGE_REGISTRY/$APP_NAME" | head -n 1) 

# Docker Image
# DOCKER_IMAGE_INFO=$(sudo docker images --format "{{.Repository}}\t{{.Tag}}" | grep "$IMAGE_REGISTRY/$APP_NAME" | head -n 1)  # Get First tag ordered by tag name

if [[ -z "$IMAGE_INFO" ]]; then
    echo "No image found with this App [$APP_NAME]!"
    echo "Build the first version of image. ($IMAGE_REGISTRY/$APP_NAME:$TAG)"
    read -p "continue? (y/n)" user_input

    if ! [[ "$user_input" == "y" || "$user_input" == "yes" ]]; then
        exit 2
    fi

    sudo nerdctl build --no-cache --tag $IMAGE_REGISTRY/$APP_NAME:$TAG -f $DOCKERFILE ../../..
    sudo nerdctl push $IMAGE_REGISTRY/$APP_NAME:$TAG

    echo "Image build & push completed"
    exit 0
fi

IMAGE_NAME=$(echo $IMAGE_INFO | cut -d' ' -f1)
IMAGE_TAG=$(echo $IMAGE_INFO | cut -d' ' -f2)

echo "################################"
echo "Latest Crictl Image Info"
echo "Name: $IMAGE_NAME"
echo "Tag: $IMAGE_TAG"
echo "################################"


echo "Enter new tag in x.y.z format (ex. 2.13.5)"
read -p ": " TAG

pattern="^[0-9]+\.[0-9]+\.[0-9]+$"

if ! [[ $TAG =~ $pattern ]]; then
    echo "Please enter tag in correct format!"
    exit 1
fi


echo "Build & Push an image [$IMAGE_NAME:$TAG] to registry."
read -p "continue? (y/n)" user_input

if ! [[ "$user_input" == "y" || "$user_input" == "yes" ]]; then
    exit 2
fi

IMAGE_FULL_NAME="$IMAGE_NAME:$TAG"


sudo nerdctl build --no-cache --tag $IMAGE_FULL_NAME -f $DOCKERFILE ../../..
sudo nerdctl push $IMAGE_FULL_NAME

