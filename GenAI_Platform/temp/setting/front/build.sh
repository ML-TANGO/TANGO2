#!/bin/bash
SCRIPT=$( readlink -m $( type -p $0 ))
BASE_DIR=`dirname ${SCRIPT}`


IMAGE_NAME="front:0.1.0"
IMAGE_REGISTRY="registry.jfb.io:30500/jfb-system/"
DOCKERFILE="Dockerfile"


if [ ! -d "jonathan-platform-front" ]; then
    echo "mv ..?/jonathan-platform-fornt $BASE_DIR/"
    exit 0
fi

cd $BASE_DIR
docker build --no-cache --tag $IMAGE_NAME -f $DOCKERFILE ..
docker tag $IMAGE_NAME $IMAGE_REGISTRY$IMAGE_NAME
docker push $IMAGE_REGISTRY$IMAGE_NAME