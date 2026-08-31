#!/usr/bin/env bash
# eval/run_generate_projectors.sh — 비전 프로젝터 구조별 SDS-9k 체크포인트에 대해
# 검증셋 생성을 돌린다.
#
# LLM 은 Qwen3-8B 로 고정하고 SDS-9k 까지 학습한 최종 단계만 본다.
# 기존 mlp2x_gelu 는 results/eval_20260728/qwen3_sds9k.jsonl 로 이미 있으므로
# 여기서는 이번 일괄 실행으로 만든 네 구조만 돌린다.
#
#   bash eval/run_generate_projectors.sh

set -uo pipefail

PYTHON="${PYTHON:-/home/yvvyee/miniconda3/envs/eva/bin/python}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

QWEN="/home/yvvyee/data/Models/Qwen3-8B"
IMAGE_DIR="${IMAGE_DIR:-/home/yvvyee/data/AIVN-SDS/20260728}"
DATA="${DATA:-$ROOT/data/sds_valid_ko_1k.json}"
OUT_DIR="${OUT_DIR:-$ROOT/results/eval_20260728}"
BATCH="${BATCH:-16}"
LIMIT="${LIMIT:-0}"

mkdir -p "$OUT_DIR" "$ROOT/logs"

# 이름|프로젝터 구조
CONFIGS=(
  "proj_linear|linear"
  "proj_cross_attn|cross_attn"
  "proj_mlp3x_gelu|mlp3x_gelu"
  "proj_qformer|qformer"
)

GPUS=(2 3 4 5)

run_one() {
    local gpu="$1" name="$2" ptype="$3"
    local dir="$ROOT/checkpoints/clip_qwen3_proj_lora_marine_sds_ko_9k_${ptype}"
    local log="$ROOT/logs/gen_${name}.log"

    if [ ! -f "$dir/projector.bin" ]; then
        echo "  [$name] 체크포인트 없음: $dir"
        return 1
    fi

    CUDA_VISIBLE_DEVICES="$gpu" "$PYTHON" "$ROOT/eval/generate.py" \
        --llm_model      "$QWEN" \
        --projector_path "$dir/projector.bin" \
        --lora_path      "$dir" \
        --data_path      "$DATA" \
        --image_dir      "$IMAGE_DIR" \
        --out            "$OUT_DIR/${name}.jsonl" \
        --batch_size     "$BATCH" \
        --limit          "$LIMIT" > "$log" 2>&1

    echo "  [$name] 종료코드 $?  -> $OUT_DIR/${name}.jsonl"
}

echo "=== 프로젝터 구조별 검증셋 생성 ==="
echo "  데이터 : $DATA"
echo "  출력   : $OUT_DIR"
echo "  배치   : $BATCH"
echo ""

i=0
for cfg in "${CONFIGS[@]}"; do
    IFS='|' read -r name ptype <<< "$cfg"
    gpu="${GPUS[$((i % ${#GPUS[@]}))]}"

    run_one "$gpu" "$name" "$ptype" &
    echo "시작: $name  (GPU $gpu, $ptype)"
    i=$((i + 1))

    if [ $((i % ${#GPUS[@]})) -eq 0 ]; then
        wait
        echo "-- 묶음 완료 --"
    fi
done
wait

echo ""
echo "=== 전체 완료 ==="
for cfg in "${CONFIGS[@]}"; do
    IFS='|' read -r name ptype <<< "$cfg"
    f="$OUT_DIR/${name}.jsonl"
    [ -s "$f" ] && echo "  $(wc -l < "$f") 건  $f"
done
exit 0
