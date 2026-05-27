#!/bin/bash
set -euo pipefail

export HF_HOME=/model/huggingface
export HF_TOKEN="${HF_TOKEN:?Set HF_TOKEN env var}"
export CUDA_VISIBLE_DEVICES=0

# ---- Ensure SDM is importable ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${SCRIPT_DIR}/..:${PYTHONPATH:-}"

# ---- Paths ----
CHECKPOINT="/model/airdrop/final_model/baseline/last.pt"
CSV_PATH="./ct_rate_labels.csv"
CSV_PATH2="./final_ct.csv"
NPZ_ROOT="/data/preprocessed"
EMB_DIR="./ct/encoder_embs"
OUT_DIR="./linear_probe_output"

# echo "=========================================="
# echo "Step 1: Extract embeddings (train + val)"
# echo "=========================================="

python3 -m SDM.evaluation.extract_embeddings \
    --checkpoint "$CHECKPOINT" \
    --csv_path "$CSV_PATH" \
    --npz_root "$NPZ_ROOT" \
    --splits train val \
    --mask_type repeat \
    --chest2vec_path lukeingawesome/chest2vec_0.6b_chest \
    --embed_dim 1024 \
    --batch_size 16 \
    --amp \
    --output_dir "$EMB_DIR"

echo ""
echo "=========================================="
echo "Step 2: Linear probing"
echo "=========================================="

# python3 -m SDM.evaluation.linear_probe \
#     --emb_dir "$EMB_DIR" \
#     --csv "$CSV_PATH" \
#     --out_dir "$OUT_DIR" \
#     --epochs 100 \
#     --batch_size 512 \
#     --lr 3e-3 \
#     --weight_decay 1e-4 \
#     --dropout 0.0 \
#     --gamma 2.0 \
#     --alpha 0.25 \
#     --threshold 0.5


python3 -m SDM.evaluation.linear_probe \
    --emb_dir "$EMB_DIR" \
    --csv "$CSV_PATH2" \
    --out_dir "$OUT_DIR" \
    --epochs 100 \
    --batch_size 512 \
    --loss asl \
    --lr 1e-4 \
    --weight_decay 1e-4 \
    --dropout 0.0 \
    --gamma_pos 0.0 --gamma_neg 4.0 --clip 0.05


echo ""
echo "=========================================="
echo "Linear Probe Complete!"
echo "=========================================="
echo "Embeddings:   $EMB_DIR"
echo "Results:      $OUT_DIR"
