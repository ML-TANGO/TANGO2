#!/bin/bash
set -euo pipefail

export CUDA_VISIBLE_DEVICES=5  # Use GPU 5 (free — training runs on 0-4)

# ---- Paths ----
CHECKPOINT="./runs/ctjepa_v3/checkpoints/checkpoint_latest.pt"
CSV_PATH="./final_ct2.csv"
NPZ_ROOT="/data/preprocessed"
EMB_DIR="./ct/cepa_embs"
OUT_DIR="./linear_probe_output"

# ---- Ensure SDM is importable ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${SCRIPT_DIR}/..:${PYTHONPATH:-}"

echo "=========================================="
echo "Step 1: Extract embeddings (train + val)"
echo "=========================================="

python3 -m SDM.evaluation.extract_embeddings \
    --checkpoint "$CHECKPOINT" \
    --csv_path "$CSV_PATH" \
    --npz_root "$NPZ_ROOT" \
    --splits train val \
    --config base \
    --embed_type concat \
    --window_id 1 \
    --batch_size 16 \
    --num_workers 4 \
    --amp \
    --output_dir "$EMB_DIR"

echo ""
echo "=========================================="
echo "Step 2: Linear probing"
echo "=========================================="

python3 -m SDM.evaluation.linear_probe \
    --emb_dir "$EMB_DIR" \
    --csv "$CSV_PATH" \
    --out_dir "$OUT_DIR" \
    --epochs 100 \
    --batch_size 512 \
    --loss asl \
    --lr 1e-3 \
    --weight_decay 1e-4 \
    --dropout 0.0 \
    --gamma_pos 0.0 --gamma_neg 4.0 --clip 0.05

echo ""
echo "=========================================="
echo "Linear Probe Complete!"
echo "=========================================="
echo "Embeddings:   $EMB_DIR"
echo "Results:      $OUT_DIR"
