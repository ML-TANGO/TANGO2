#!/bin/bash
SCRIPT=$( readlink -m $( type -p $0 ))
BASE_DIR=`dirname ${SCRIPT}`

# ============================================================
# CLI INFO
# ============================================================
CLI='nerdctl'
read -p "Image Build CLI? $CLI? (y/n) " RESPONSE
if [ "$RESPONSE" == "n" ]; then
    # CLI: docker
    CLI='docker'
    read -p "Image Build CLI? $CLI (y/n) " RESPONSE
    if [ "$RESPONSE" == "n" ]; then
        exit 0
    fi 
else
    # CLI: nerdctl
    ### protocol
    PROTOCOL='http'
    read -p "Image registry protocol? $PROTOCOL (y/n) " RESPONSE
    if [ "$RESPONSE" == "n" ]; then
        PROTOCOL='https'
        echo "using protocol $PROTOCOL"
    fi

    ### insecure
    if [ "$PROTOCOL" == "http" ]; then
        INSECURE_REGISTRY='--insecure-registry'
    else
        INSECURE_REGISTRY=''
    fi
fi

# ============================================================
# IMAGE INFO
# ============================================================
REGISTRY="registry.jonathan.acryl.ai"
read -p "Image registry url? $REGISTRY (y/n) " RESPONSE
if [ "$RESPONSE" == "n" ]; then
    read -p "Enter Image registry url: " REGISTRY
fi

TAG="jfb/llm_deployment"
read -p "Image registry tag? $TAG (y/n) " RESPONSE
if [ "$RESPONSE" == "n" ]; then
    read -p "Enter Image registry tag: " TAG
fi

VERSION="0.0.3"
read -p "Image registry version? $VERSION (y/n) " RESPONSE
if [ "$RESPONSE" == "n" ]; then
    read -p "Enter Image version: " VERSION
fi

read -p "Image save (y/n)? " RESPONSE
if [ "$RESPONSE" == "y" ]; then
    SAVE="y"
    read -p "save tar name (xxx.tar): " APP
fi

IMAGE=$REGISTRY/$TAG:$VERSION
echo $IMAGE

# ============================================================
# IMAGE BUILD
# ============================================================

cd $BASE_DIR
echo $CLI build --no-cache --tag $IMAGE -f Dockerfile .
$CLI build --no-cache --tag $IMAGE -f Dockerfile .

echo $CLI push $INSECURE_REGISTRY $IMAGE
$CLI push $INSECURE_REGISTRY $IMAGE

if [ "$SAVE" == "y" ]; then
    cd $BASE_DIR
    echo $CLI save -o $APP $IMAGE
    $CLI save -o $APP $IMAGE
fi
