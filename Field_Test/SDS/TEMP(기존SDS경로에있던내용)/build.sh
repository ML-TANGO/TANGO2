#!/usr/bin/env bash
set -euo pipefail
SCRIPTPATH="$( cd "$(dirname "$0")" && pwd )"

docker build -t ctchat "${SCRIPTPATH}"