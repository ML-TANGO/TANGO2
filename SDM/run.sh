#!/bin/bash
# CT-JEPA v2 Training Launch Script
# ===================================
# Supports single-GPU and multi-GPU (DDP) training via torchrun.
#
# Usage:
#   bash run.sh                          # Auto-detect GPUs, use all
#   bash run.sh --gpus 1,2,4,5           # Use specific GPUs
#   bash run.sh --gpus 2                 # Use first 2 GPUs
#   bash run.sh --config large --lr 1e-4 # Pass extra args to train.py

set -euo pipefail

# ---- Ensure SDM is importable as a package ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${SCRIPT_DIR}/..:${PYTHONPATH:-}"

# ---- NCCL settings for multi-GPU on cross-PCIe-bus topologies ----
export NCCL_P2P_DISABLE=1
export NCCL_ALGO=Ring
export NCCL_PROTO=Simple
export NCCL_MAX_NCHANNELS=2
export NCCL_BUFFSIZE=4194304
export NCCL_DEBUG=WARN

# ---- Defaults ----
GPU_ARG=""
DATA_CSV="${SCRIPT_DIR}/final_ct2.csv"
DATA_ROOT="/data/preprocessed"
OUTPUT_DIR="./runs/ctjepa_v3"
CONFIG="base"
RESUME=""
EXTRA_ARGS=""

# ---- Parse script-level args ----
while [[ $# -gt 0 ]]; do
    case "$1" in
        --gpus)
            GPU_ARG="$2"
            shift 2
            ;;
        --data_csv)
            DATA_CSV="$2"
            shift 2
            ;;
        --data_root)
            DATA_ROOT="$2"
            shift 2
            ;;
        --output_dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --config)
            CONFIG="$2"
            shift 2
            ;;
        --resume)
            RESUME="$2"
            shift 2
            ;;
        *)
            EXTRA_ARGS="$EXTRA_ARGS $1"
            shift
            ;;
    esac
done

# ---- Resolve GPU selection ----
if [ -z "$GPU_ARG" ]; then
    # Auto-detect: use all available GPUs
    if command -v nvidia-smi &> /dev/null; then
        NUM_GPUS=$(nvidia-smi -L | wc -l)
    else
        NUM_GPUS=1
    fi
elif [[ "$GPU_ARG" == *","* ]]; then
    # Comma-separated list like "1,2,4,5"
    export CUDA_VISIBLE_DEVICES="$GPU_ARG"
    IFS=',' read -ra GPU_IDS <<< "$GPU_ARG"
    NUM_GPUS=${#GPU_IDS[@]}
else
    # Single number: use first N GPUs
    NUM_GPUS="$GPU_ARG"
fi

echo "============================================"
echo "  CT-JEPA v2 Training"
echo "============================================"
echo "  GPUs:       $NUM_GPUS${CUDA_VISIBLE_DEVICES:+ (CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES)}"
echo "  Config:     $CONFIG"
echo "  Data CSV:   $DATA_CSV"
echo "  Data Root:  $DATA_ROOT"
echo "  Output:     $OUTPUT_DIR"
echo "  Resume:     ${RESUME:-none}"
echo "  Extra args: $EXTRA_ARGS"
echo "============================================"

# ---- Common training args ----
TRAIN_ARGS="
    --config $CONFIG
    --data_csv $DATA_CSV
    --data_root $DATA_ROOT
    --output_dir $OUTPUT_DIR
"
if [ -n "$RESUME" ]; then
    TRAIN_ARGS="$TRAIN_ARGS --resume $RESUME"
fi
TRAIN_ARGS="$TRAIN_ARGS $EXTRA_ARGS"

# ---- Launch ----
if [ "$NUM_GPUS" -gt 1 ]; then
    echo "Launching DDP training with $NUM_GPUS GPUs..."
    torchrun \
        --standalone \
        --nproc_per_node=$NUM_GPUS \
        -m SDM.training.train \
        $TRAIN_ARGS
else
    echo "Launching single-GPU training..."
    python -m SDM.training.train \
        $TRAIN_ARGS
fi
