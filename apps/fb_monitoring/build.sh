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

IMAGE=$REGISTRY/jfb-system/REPLACE_app:$VERSION
BUILD_COMMAND="$CLI build --no-cache --tag $IMAGE -f Dockerfile .."
PUSH_COMMAND="$CLI push $INSECURE_REGISTRY $IMAGE"
SAVE_COMMAND="$CLI save -o REPLACE.tar $IMAGE"


read -p "APP NAME? (ex. dashboard) " APP

echo cd $BASE_DIR
cd $BASE_DIR

command="${BUILD_COMMAND/REPLACE/"$APP"}"
echo $command
$command

command="${PUSH_COMMAND/REPLACE/"$APP"}"
echo $command
$command

if [ "$SAVE" == "y" ]; then
    command="${SAVE_COMMAND/REPLACE/"$APP"}"
    echo $command
    $command
fi


