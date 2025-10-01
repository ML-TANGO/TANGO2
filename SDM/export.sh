#!/usr/bin/env bash
set -euo pipefail

./build.sh
docker save ctchat | gzip -c > CTCHAT.tar.gz
echo "🎉  Created CTgen.tar.gz"
