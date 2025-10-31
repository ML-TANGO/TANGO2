#!/bin/bash
SCRIPT=$( readlink -m $( type -p $0 ))
BASE_DIR=`dirname ${SCRIPT}`

IMAGE_NAME="jf_api:dev_0.2"
IMAGE_REGISTRY="registry.jfb.io:30500/jfb-system/"
DOCKERFILE="Dockerfile.dev"

docker build --no-cache --tag $IMAGE_NAME -f $DOCKERFILE $BASE_DIR
docker tag $IMAGE_NAME $IMAGE_REGISTRY$IMAGE_NAME
docker push $IMAGE_REGISTRY$IMAGE_NAME
# docker rmi $IMAGE_REGISTRY$IMAGE_NAME
