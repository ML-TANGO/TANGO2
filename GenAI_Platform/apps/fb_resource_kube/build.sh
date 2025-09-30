#!/bin/bash
IMAGE_REGI="192.168.1.14:30500"
IMAGE_REPO="jfb-system"
DOCKERFILE="Dockerfile"

IMAGE_REGISTRY=$IMAGE_REGI/$IMAGE_REPO
SCRIPT=$( readlink -m $( type -p $0 ))
BASE_DIR=`dirname ${SCRIPT}`
APP_NAME=$(basename $(pwd))

# Get First tag ordered by tag name
IMAGE_INFO=$(sudo crictl images | sort -k 2 | grep "$IMAGE_REGISTRY/$APP_NAME" | head -n 1) 

# Docker Image
# DOCKER_IMAGE_INFO=$(sudo docker images --format "{{.Repository}}\t{{.Tag}}" | grep "$IMAGE_REGISTRY/$APP_NAME" | head -n 1)  # Get First tag ordered by tag name

if [[ -z "$IMAGE_INFO" ]]; then
    echo "No image found with this App [$APP_NAME]!"
    echo "Build the first version of image. ($IMAGE_REGISTRY/$APP_NAME:0.1.4)"
    read -p "continue? (y/n)" user_input

    if ! [[ "$user_input" == "y" || "$user_input" == "yes" ]]; then
        exit 2
    fi

    sudo docker build --no-cache --tag $IMAGE_REGISTRY/$APP_NAME:0.1.4 -f $DOCKERFILE ..
    sudo docker push $IMAGE_REGISTRY/$APP_NAME:0.1.4

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


sudo docker build --no-cache --tag $IMAGE_FULL_NAME -f $DOCKERFILE ..
sudo docker push $IMAGE_FULL_NAME
