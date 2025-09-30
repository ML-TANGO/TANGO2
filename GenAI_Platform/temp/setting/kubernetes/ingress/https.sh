#!/bin/bash
DIR="/certs"
HTTPS_KEY="$DIR/https-ssl.key"
HTTPS_CERT="$DIR/https-ssl.crt"

# ===========================================================================
# create key, crt
openssl req \
        -x509 -nodes -newkey rsa:2048 \
        -keyout $HTTPS_KEY -out $HTTPS_CERT \
        -subj "/C=KR/ST=Seoul/L=Seoul/O=Acryl/OU=Flightbase/CN=https-ssl"


echo "---------------------------"
echo "-----Below is your CRT-----"
echo "---------------------------"
echo
cat $HTTPS_CERT
echo
echo "---------------------------"
echo "-----Below is your Key-----"
echo "---------------------------"
echo
cat $HTTPS_KEY

# ===========================================================================
# create kubernetes secret
kubectl create secret tls https-ingress --key $HTTPS_KEY --cert $HTTPS_CERT
