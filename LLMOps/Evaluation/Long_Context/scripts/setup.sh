#!/usr/bin/env bash
# Build (or repair) the NIAH + Transformers evaluation environment on this server.
# Safe to re-run. A .venv copied from another server is detected and rebuilt.
#
#   scripts/setup.sh                         # auto-pick the PyTorch CUDA wheel from the driver
#   scripts/setup.sh --torch_index cu126     # or force one: cu126 | cu128 | cu130 | cpu
#   scripts/setup.sh --prefetch google/gemma-4-E4B-it   # also download model weights now
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
OVERLAY_DIR=$(dirname "$SCRIPT_DIR")
NIAH_DIR=${NIAH_DIR:-$OVERLAY_DIR/needle-in-a-haystack}
NIAH_REPO=https://github.com/gkamradt/needle-in-a-haystack.git
NIAH_COMMIT=021385d68d3202e37893e9d3cd29011c569abe30
PYTHON_VERSION=3.12
# Versions this setup was tested with.
TORCH_PKGS=(torch==2.11.0 torchvision==0.26.0)
RUNTIME_PKGS=(transformers==5.15.1 accelerate==1.15.0 peft==0.21.0 tokenizers==0.22.2
              sentencepiece protobuf pillow)

TORCH_INDEX=auto PREFETCH=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --torch_index|--torch-index) TORCH_INDEX=$2; shift 2 ;;
    --prefetch) PREFETCH=$2; shift 2 ;;
    -h|--help) sed -n 2,7p "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

# uv's cache / Python dirs may point at shared, non-writable locations (e.g. /opt/uv).
writable_or() { if mkdir -p "$1" 2>/dev/null && [[ -w $1 ]]; then echo "$1"; else echo "$2"; fi; }
export UV_CACHE_DIR=$(writable_or "${UV_CACHE_DIR:-$HOME/.cache/uv}" "$HOME/.cache/uv")
export UV_PYTHON_INSTALL_DIR=$(writable_or "${UV_PYTHON_INSTALL_DIR:-$HOME/.local/share/uv/python}" "$HOME/.local/share/uv/python")
# Use a uv-downloaded Python so the venv doesn't depend on this server's conda/system Python.
export UV_PYTHON_PREFERENCE=only-managed

if ! command -v uv >/dev/null; then
  echo "uv not found; installing with pip --user"
  python3 -m pip install --user uv
  export PATH=$HOME/.local/bin:$PATH
fi

# 1. NIAH clone at the tested commit.
if [[ ! -d $NIAH_DIR/.git ]]; then
  git clone "$NIAH_REPO" "$NIAH_DIR"
  git -C "$NIAH_DIR" checkout -q "$NIAH_COMMIT"
fi

# 2. Overlay files + patches (patches already applied are skipped).
cp -r "$OVERLAY_DIR/files/." "$NIAH_DIR/"
for p in "$OVERLAY_DIR"/patches/*.patch; do
  if git -C "$NIAH_DIR" apply --reverse --check "$p" 2>/dev/null; then
    echo "already applied: $(basename "$p")"
  else
    git -C "$NIAH_DIR" apply "$p"
    echo "applied: $(basename "$p")"
  fi
done

# 3. venv. Rebuild if it was copied from elsewhere (scripts hard-code the venv path), is broken,
# or uses another Python. Removed here because uv's own removal can fail on NFS.
cd "$NIAH_DIR"
if [[ -d .venv ]] && { ! .venv/bin/python -c "import sys; assert sys.version.startswith('$PYTHON_VERSION.')" 2>/dev/null \
                       || ! grep -qF "$NIAH_DIR/.venv/bin/python" .venv/bin/niah 2>/dev/null; }; then
  echo "rebuilding .venv (copied from another location, broken, or not Python $PYTHON_VERSION)"
  rm -rf .venv
fi
uv sync --extra dev --inexact --python "$PYTHON_VERSION"

# 4. PyTorch wheel matching the NVIDIA driver.
if [[ $TORCH_INDEX == auto ]]; then
  if command -v nvidia-smi >/dev/null; then
    cuda=$(nvidia-smi | grep -oP 'CUDA Version:\s*\K[0-9]+\.[0-9]+')
    if awk "BEGIN{exit !($cuda >= 12.8)}"; then TORCH_INDEX=cu128
    elif awk "BEGIN{exit !($cuda >= 12.6)}"; then TORCH_INDEX=cu126
    else echo "error: driver supports CUDA $cuda; torch 2.11 needs >= 12.6. Update the driver or edit TORCH_PKGS." >&2; exit 1
    fi
    echo "driver CUDA $cuda -> $TORCH_INDEX"
  else
    TORCH_INDEX=cpu
    echo "nvidia-smi not found -> cpu"
  fi
fi
uv pip install --index-url "https://download.pytorch.org/whl/$TORCH_INDEX" "${TORCH_PKGS[@]}"
uv pip install "${RUNTIME_PKGS[@]}"

# 5. Cache the cl100k_base tokenizer inside the clone so offline servers work after copying.
export TIKTOKEN_CACHE_DIR=$NIAH_DIR/.cache/tiktoken
.venv/bin/python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"

if [[ -n $PREFETCH ]]; then
  .venv/bin/hf download "$PREFETCH"
fi

# 6. Smoke check.
.venv/bin/python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.device_count(), 'GPU(s)')"
.venv/bin/niah validate configs/runs/gemma_single_needle.local.yaml
echo "setup done. Next: $SCRIPT_DIR/run_eval.sh --help"
