#!/usr/bin/env bash
# eval/run_generate_all.sh — 6개 구성(2 계열 × 3 단계)에 대해 검증셋 생성을 돌린다.
#
# 계열마다 세 단계를 비교한다.
#   clean  : CC3M 까지만 학습된 기준선
#   marine : 거기에 LLaMarine 텍스트 전용 LoRA 를 얹은 기준선
#   sds9k  : 거기에 20260728 한글 9k 로 SDS 도메인 LoRA 를 얹은 것
#
# GPU 2,3,4,5 에 하나씩 배정해 4개를 동시에 돌리고, 남은 2개를 이어서 돌린다.
#
#   bash eval/run_generate_all.sh

set -uo pipefail

PYTHON="${PYTHON:-/home/yvvyee/miniconda3/envs/eva/bin/python}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

QWEN="/home/yvvyee/data/Models/Qwen3-8B"
LLAMA="/home/yvvyee/data/Models/Llama-3.1-8B-Instruct"
IMAGE_DIR="${IMAGE_DIR:-/home/yvvyee/data/AIVN-SDS/20260728}"
DATA="${DATA:-$ROOT/data/sds_valid_ko_1k.json}"
OUT_DIR="${OUT_DIR:-$ROOT/results/eval_20260728}"
BATCH="${BATCH:-16}"
LIMIT="${LIMIT:-0}"

mkdir -p "$OUT_DIR" "$ROOT/logs"

# 이름|LLM|체크포인트 디렉토리
CONFIGS=(
  "qwen3_clean|$QWEN|clip_qwen3_proj_lora"
  "qwen3_marine|$QWEN|clip_qwen3_proj_lora_marine"
  "qwen3_sds9k|$QWEN|clip_qwen3_proj_lora_marine_sds_ko"
  "llama31_clean|$LLAMA|clip_llama31_lora"
  "llama31_marine|$LLAMA|clip_llama31_lora_marine"
  "llama31_sds9k|$LLAMA|clip_llama31_proj_lora_marine_sds_ko"
)

GPUS=(2 3 4 5)

run_one() {
    local gpu="$1" name="$2" llm="$3" ckpt="$4"
    local dir="$ROOT/checkpoints/$ckpt"
    local log="$ROOT/logs/gen_${name}.log"

    # clip_llama31_lora_marine 에는 vlm_config.json 이 없다. 그 디렉토리만
    # projector_type 을 인수로 준다. 나머지는 체크포인트 기록을 따르게 둔다.
    local extra=()
    if [ ! -f "$dir/vlm_config.json" ]; then
        extra=(--projector_type mlp2x_gelu)
        echo "  [$name] vlm_config.json 없음 -> --projector_type mlp2x_gelu"
    fi

    CUDA_VISIBLE_DEVICES="$gpu" "$PYTHON" "$ROOT/eval/generate.py" \
        --llm_model      "$llm" \
        --projector_path "$dir/projector.bin" \
        --lora_path      "$dir" \
        --data_path      "$DATA" \
        --image_dir      "$IMAGE_DIR" \
        --out            "$OUT_DIR/${name}.jsonl" \
        --batch_size     "$BATCH" \
        --limit          "$LIMIT" \
        "${extra[@]}" > "$log" 2>&1

    echo "  [$name] 종료코드 $?  -> $OUT_DIR/${name}.jsonl"
}

echo "=== 검증셋 생성 ==="
echo "  데이터 : $DATA"
echo "  출력   : $OUT_DIR"
echo "  배치   : $BATCH"
echo ""

i=0
for cfg in "${CONFIGS[@]}"; do
    IFS='|' read -r name llm ckpt <<< "$cfg"
    gpu="${GPUS[$((i % ${#GPUS[@]}))]}"

    run_one "$gpu" "$name" "$llm" "$ckpt" &
    echo "시작: $name  (GPU $gpu)"
    i=$((i + 1))

    # GPU 개수만큼 띄웠으면 그 묶음이 끝날 때까지 기다린다.
    if [ $((i % ${#GPUS[@]})) -eq 0 ]; then
        wait
        echo "-- 묶음 완료 --"
    fi
done
wait

echo ""
echo "=== 전체 완료 ==="
wc -l "$OUT_DIR"/*.jsonl
