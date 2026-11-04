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
    INSECURE_REGISTRY=''
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

VERSION="dev"
read -p "Image registry version? $VERSION (y/n) " RESPONSE
if [ "$RESPONSE" == "n" ]; then
    read -p "Enter Image version: " VERSION
fi

read -p "Image save tar? (y/n) " SAVE

echo REGISTRY: $REGISTRY
echo VERSION: $VERSION
echo SAVE: $SAVE

# ============================================================
# IMAGE BUILD
# ============================================================
# front 는 backend (fb_*, llm_*) 와 달리 자기 디렉터리만 컨텍스트로 사용 (-f Dockerfile .)
# backend 는 fb_utils 공통 lib 때문에 부모 컨텍스트 (-f Dockerfile ..) 를 씀.

APP="front"
IMAGE=$REGISTRY/jfb-system/${APP}_app:$VERSION
BUILD_COMMAND="$CLI build --no-cache --tag $IMAGE -f Dockerfile ."
PUSH_COMMAND="$CLI push $INSECURE_REGISTRY $IMAGE"
SAVE_COMMAND="$CLI save -o ${APP}.tar $IMAGE"

echo cd $BASE_DIR
cd $BASE_DIR

echo $BUILD_COMMAND
$BUILD_COMMAND

echo $PUSH_COMMAND
$PUSH_COMMAND

if [ "$SAVE" == "y" ]; then
    echo $SAVE_COMMAND
    $SAVE_COMMAND
fi
