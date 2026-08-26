#!/usr/bin/env bash
# eval/run_metrics_all.sh — 생성 결과 전부를 채점하고 하나의 표로 모은다.
#
#   bash eval/run_metrics_all.sh
#
# BERTScore 만 GPU 를 쓴다. 생성이 모두 끝난 뒤에 돌리는 것을 전제한다.

set -uo pipefail

PYTHON="${PYTHON:-/home/yvvyee/miniconda3/envs/eva/bin/python}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

OUT_DIR="${OUT_DIR:-$ROOT/results/eval_20260728}"
IMAGE_DIR="${IMAGE_DIR:-/home/yvvyee/data/AIVN-SDS/20260728}"
BS_MODEL="${BS_MODEL:-klue/roberta-large}"
GPU="${GPU:-2}"

NAMES=(qwen3_clean qwen3_marine qwen3_sds9k
       llama31_clean llama31_marine llama31_sds9k)

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
"$PYTHON" "$ROOT/eval/aggregate.py" --dir "$OUT_DIR" --out "$OUT_DIR/summary"
