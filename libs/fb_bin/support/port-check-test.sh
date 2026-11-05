#!/bin/bash
SCRIPT=$( readlink -m $( type -p $0 ))
BASE_DIR=`dirname ${SCRIPT}`

echo netstat
$BASE_DIR/netstat -nltp
