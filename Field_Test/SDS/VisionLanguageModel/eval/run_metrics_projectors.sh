#!/usr/bin/env bash
# eval/run_metrics_projectors.sh — 프로젝터 구조별 생성 결과를 채점하고 집계한다.
#
#   bash eval/run_metrics_projectors.sh
#
# BERTScore 만 GPU 를 쓴다. 생성이 모두 끝난 뒤에 돌리는 것을 전제한다.
# mlp2x_gelu 에 해당하는 qwen3_sds9k 는 이미 채점되어 있으므로 다시 돌리지 않는다.

set -uo pipefail

PYTHON="${PYTHON:-/home/yvvyee/miniconda3/envs/eva/bin/python}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

OUT_DIR="${OUT_DIR:-$ROOT/results/eval_20260728}"
IMAGE_DIR="${IMAGE_DIR:-/home/yvvyee/data/AIVN-SDS/20260728}"
BS_MODEL="${BS_MODEL:-klue/roberta-large}"
GPU="${GPU:-2}"

NAMES=(proj_linear proj_cross_attn proj_mlp3x_gelu proj_qformer)

for name in "${NAMES[@]}"; do
    pred="$OUT_DIR/${name}.jsonl"
    if [ ! -s "$pred" ]; then
        echo "건너뜀 (없음): $pred"
        continue
    fi
    echo "=== 채점: $name ($(wc -l < "$pred") 건) ==="
    CUDA_VISIBLE_DEVICES="$GPU" "$PYTHON" "$ROOT/eval/metrics.py" \
        --pred "$pred" \
        --image_dir "$IMAGE_DIR" \
        --out "$OUT_DIR/${name}.metrics.json" \
        --bertscore_model "$BS_MODEL" \
        > "$ROOT/logs/metrics_${name}.log" 2>&1
    echo "  종료코드 $?"
done

echo ""
echo "=== 집계 ==="
"$PYTHON" "$ROOT/eval/aggregate.py" --dir "$OUT_DIR" \
    --group projector --out "$OUT_DIR/summary_projector"
exit 0
