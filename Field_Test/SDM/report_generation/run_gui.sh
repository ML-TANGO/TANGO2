#!/usr/bin/env bash
# Interactive demo GUI: chest CT in, report out. Separate from the TC1 test container.
#
#   ./run_gui.sh               serve on http://localhost:7870 (this server only), GPU 5
#   GPU=1 ./run_gui.sh         use a different GPU
#   SHARE=1 GUI_PASSWORD=... ./run_gui.sh
#                              also open a public https://*.gradio.live link, behind a login
#                              (user "demo"); the link is printed in the log
#
# From the Windows client:  ssh -L 7870:localhost:7870 <user>@<server>
# then open http://localhost:7870 in the browser.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

IMAGE=chest-ct-gui:1
GPU=${GPU:-5}
PORT=${PORT:-7870}

# Bound to 127.0.0.1: reachable only from this server or through an SSH tunnel.
exec docker run --rm -it --name chest-ct-gui --gpus "\"device=$GPU\"" --shm-size 8g \
  -p "127.0.0.1:$PORT:7860" \
  -v "$PWD/hf_cache:/hf:ro" \
  -v "$PWD/gui/samples:/samples:ro" \
  --env-file labeler.env \
  -e SHARE="${SHARE:-0}" -e GUI_PASSWORD="${GUI_PASSWORD:-}" \
  "$IMAGE"
