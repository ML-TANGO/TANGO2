#!/bin/bash

SCRIPT=$( readlink -m $( type -p $0 ))
BASE_DIR=`dirname ${SCRIPT}`

# apt install -y apache2-utils
htpasswd -Bbn tango tango > $BASE_DIR/file/htpasswd

# dockercconfigjson
# cat ~/.docker/config.json | base64 -w 0