#!/bin/bash

. /etc/jfb/parser.sh
if [ $? -gt 0 ]
then
    echo "Please Check /etc/jfb/parser.sh"
    exit 1
fi
#HTTPS_KEY=/jfbcore/jf-bin/https-ssl.key
#HTTPS_CERT=/jfbcore/jf-bin/https-ssl.crt


kubectl create secret tls https-ingress --key $HTTPS_KEY --cert $HTTPS_CERT