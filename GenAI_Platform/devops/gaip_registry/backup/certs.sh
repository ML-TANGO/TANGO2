#!/bin/bash

SCRIPT=$( readlink -m $( type -p $0 ))
BASE_DIR=`dirname ${SCRIPT}`

#. /etc/jfb/func.sh $BASE_DIR
#NAMESPACE=$(namespace)
#. /etc/jfb/$NAMESPACE/parser.sh

DOCKER_SSL_KEY="$BASE_DIR/registry.key"
DOCKER_SSL_CRT="$BASE_DIR/registry.crt"

DOCKER_REGISTRY_IP="192.168.1.14"

openssl req  \
    -newkey rsa:4096 -nodes -sha256 -keyout $DOCKER_SSL_KEY \
    -addext "subjectAltName=IP:$DOCKER_REGISTRY_IP" \
    -x509 -days 36500 -out $DOCKER_SSL_CRT \
    -subj "/C=KR/ST=Seoul/L=Seoul/O=Acryl/OU=Flightbase"

echo "---------------------------"
echo "-----Below is your CRT-----"
echo "---------------------------"
echo
cat $DOCKER_SSL_CRT
echo
echo "---------------------------"
echo "-----Below is your Key-----"
echo "---------------------------"
echo
cat $DOCKER_SSL_KEY

