#!/bin/bash

# OS, VER
if [ -f /etc/os-release ];
then
    . /etc/os-release
    OS=$NAME
    VER=$VERSION_ID
elif type lsb_release >/dev/null 2>&1;
then
    OS=$(lsb_release -si)
    VER=$(lsb_release -sr)
else
    OS=$(uname -s)
    VER=$(uname -r)
fi

# Color code
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CLEAR='\033[0m'
LIGHT_GRAY='\033[0;90m'
LIGHT_BLUE='\033[0;94m'
LIGHT_MAGENTA='\033[0;95m'
LIGHT_CYAN='\033[0;96m'

# Linux distribution Code name (ex. focal, jammy)
OS_CODE_NAME=$(lsb_release -cs)