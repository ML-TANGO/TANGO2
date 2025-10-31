#!/bin/bash

REGISTRY=""

nerdctl build  --no-cache --tag $REGISTRY/jfb/jbi_ubuntu-20.04.6:latest -f  JBI_Ubuntu-20.04.6-linux_5.4.0-182-generic .
nerdctl build  --no-cache --tag $REGISTRY/jfb/jbi_ubuntu-22.04.6:latest -f  JBI_Ubuntu-22.04.6-linux_5.4.0-187-generic . 

#docker build  --no-cache --tag $REGISTRY/jfb/jbi_ubuntu-22.04.6_linux_5.4.0-187-generic:latest -f  JBI_Ubuntu-22.04.6-linux_5.4.0-187-generic .
#docker build  --no-cache --tag $REGISTRY/jfb/jbi_ubuntu-22.04.6_linux_5.4.0-187-generic:latest -f  JBI_Ubuntu-22.04.6-linux_5.4.0-187-generic .

# nerdctl push --insecure-registry $REGISTRY/jfb/jbi_ubuntu-20.04.6:latest
# nerdctl push --insecure-registry $REGISTRY/jfb/jbi_ubuntu-22.04.6:latest
