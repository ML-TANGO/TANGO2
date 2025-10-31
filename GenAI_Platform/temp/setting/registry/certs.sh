#!/bin/bash

DIR="/registry/certs"
DOCKER_SSL_KEY="$DIR/registry.key"
DOCKER_SSL_CRT="$DIR/registry.crt"
DOCKER_REPOSITORY_DNS="registry.jfb.io"


openssl req  \
        -newkey rsa:4096 -nodes -sha256 -keyout $DOCKER_SSL_KEY \
        -addext "subjectAltName = DNS:$DOCKER_REPOSITORY_DNS" \
        -x509 -days 36500 -out $DOCKER_SSL_CRT \
        -subj "/C=KR/ST=Seoul/L=Seoul/O=Acryl/OU=Flightbase"

echo "---------------------------"
echo "-----Below is your CRT-----"
echo "---------------------------"
echo
cat $DOCKER_SSL_CERT
echo
echo "---------------------------"
echo "-----Below is your Key-----"
echo "---------------------------"
echo
cat $DOCKER_SSL_KEY

