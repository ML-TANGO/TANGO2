#!/usr/bin/env bash
# scripts/train_projector_chain_qwen3.sh
#
# CLIP + Qwen3-8B 조합에서 프로젝터 구조 하나를 네 단계 전부 학습한다.
#
#   Phase 1  CC3M 프로젝터 사전학습 (LLM 동결)
#   Phase 2  CC3M 프로젝터 + LoRA
#   Phase 2b LLaMarine 텍스트 전용 LoRA 계속학습
#   Phase 3  SDS 20260728 한글 9k 도메인 LoRA
#
# 단계 수와 유효 배치는 기존 mlp2x_gelu 체인의 실측값에 맞춘다. 그래야 프로젝터
# 구조만 다른 비교가 된다.
#
#   Phase 1  5,000 step   (유효 배치 32)
#   Phase 2 18,606 step   (유효 배치 32, CC3M 595,375건 1 epoch)
#   Phase 2b   855 step   (유효 배치 64, LLaMarine 54,657건 1 epoch)
#   Phase 3    846 step   (유효 배치 32, SDS 9,000건 3 epoch)
#
# 사용:
#   CUDA_VISIBLE_DEVICES=2,3,4,5 PROJECTOR_TYPE=linear \
#       bash scripts/train_projector_chain_qwen3.sh
#
# 산출 디렉토리는 프로젝터 종류를 이름에 담는다.
#   checkpoints/clip_qwen3_projector_<type>
#   checkpoints/clip_qwen3_proj_lora_<type>
#   checkpoints/clip_qwen3_proj_lora_marine_<type>
#   checkpoints/clip_qwen3_proj_lora_marine_sds_ko_9k_<type>
#
#   PHASES="1" 로 특정 단계만 돌릴 수 있다. 기본은 "1 2 2b 3".
#   MAX_STEPS_OVERRIDE 를 주면 모든 단계를 그 step 수로 잘라 실측용으로 쓴다.

set -uo pipefail

PYTHON="${PYTHON:-/home/yvvyee/miniconda3/envs/eva/bin/python}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PROJECTOR_TYPE="${PROJECTOR_TYPE:?PROJECTOR_TYPE 를 지정하십시오}"
# 체크포인트 이름에 프로젝터 종류를 그대로 박는다. 디렉토리 이름만 보고 어떤
# 구조로 학습된 것인지 알 수 있어야 하기 때문이다. 리샘플러의 쿼리 토큰 수 같은
# 세부 설정은 각 디렉토리의 vlm_config.json 에 기록되며, train.py 가 이어서
# 학습할 때 그 값과 요청값이 다르면 중단한다.
TAG="${TAG:-$PROJECTOR_TYPE}"
PHASES="${PHASES:-1 2 2b 3}"
MAX_STEPS_OVERRIDE="${MAX_STEPS_OVERRIDE:-}"

# ── 경로 ──────────────────────────────────────────────────────────────────────
VISION_MODEL="openai/clip-vit-large-patch14-336"
LLM_MODEL="${LLM_MODEL:-/home/yvvyee/data/Models/Qwen3-8B}"
CC3M_DATA="/home/yvvyee/data/LLaVA-CC3M-Pretrain-595K/chat.json"
CC3M_IMG="/home/yvvyee/data/LLaVA-CC3M-Pretrain-595K/images"
MARINE_DATA="/home/yvvyee/data/Models/llamarine-sft/train-00000-of-00001.parquet"
SDS_TRAIN="$ROOT/data/sds_train_ko_9k.json"
SDS_VALID="$ROOT/data/sds_valid_ko_1k.json"
SDS_IMG="/home/yvvyee/data/AIVN-SDS/20260728"

P1_OUT="$ROOT/checkpoints/clip_qwen3_projector_$TAG"
P2_OUT="$ROOT/checkpoints/clip_qwen3_proj_lora_$TAG"
P2B_OUT="$ROOT/checkpoints/clip_qwen3_proj_lora_marine_$TAG"
P3_OUT="$ROOT/checkpoints/clip_qwen3_proj_lora_marine_sds_ko_9k_$TAG"

# ── 리샘플러 설정 (cross_attn / qformer 만 사용) ──────────────────────────────
NUM_QUERY_TOKENS="${NUM_QUERY_TOKENS:-32}"
NUM_HEADS="${NUM_HEADS:-8}"
NUM_LAYERS="${NUM_LAYERS:-2}"
RESAMPLER_ARGS=(
    --projector_num_query_tokens "$NUM_QUERY_TOKENS"
    --projector_num_heads        "$NUM_HEADS"
    --projector_num_layers       "$NUM_LAYERS"
)

NUM_GPUS=$("$PYTHON" -c "import torch; print(torch.cuda.device_count())")
if [ "$NUM_GPUS" -gt 1 ]; then
    LAUNCHER=("$PYTHON" -m torch.distributed.run "--nproc_per_node=$NUM_GPUS")
    DS_ARG=(--deepspeed "$ROOT/scripts/zero2.json")
else
    LAUNCHER=("$PYTHON")
    DS_ARG=()
fi

# 유효 배치를 GPU 수와 무관하게 고정한다. 기존 체인과 같은 값이라야 비교가 된다.
#   유효 배치 = BATCH × ACCUM × NUM_GPUS
eff32_batch=2;  eff32_accum=$(( 32 / (2 * NUM_GPUS) ))
eff64_batch=2;  eff64_accum=$(( 64 / (2 * NUM_GPUS) ))
if [ "$eff32_accum" -lt 1 ] || [ "$eff64_accum" -lt 1 ]; then
    echo "ERROR: GPU $NUM_GPUS 장에서는 유효 배치 32/64 를 맞출 수 없습니다"
    exit 1
fi

echo "=== 프로젝터 체인: $PROJECTOR_TYPE (tag=$TAG) ==="
echo "  GPUs        : $NUM_GPUS (CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-all})"
echo "  단계        : $PHASES"
echo "  유효배치 32 : batch $eff32_batch × accum $eff32_accum × $NUM_GPUS"
echo "  유효배치 64 : batch $eff64_batch × accum $eff64_accum × $NUM_GPUS"
[ -n "$MAX_STEPS_OVERRIDE" ] && echo "  ** 실측 모드: 모든 단계 $MAX_STEPS_OVERRIDE step 로 자름 **"
echo ""

steps_for() {  # 단계별 목표 step. 실측 모드면 덮어쓴다.
    if [ -n "$MAX_STEPS_OVERRIDE" ]; then echo "$MAX_STEPS_OVERRIDE"; else echo "$1"; fi
}

has_phase() { [[ " $PHASES " == *" $1 "* ]]; }

# ── Phase 1: CC3M 프로젝터 ────────────────────────────────────────────────────
if has_phase 1; then
    echo "--- Phase 1: CC3M 프로젝터 ---"
    "${LAUNCHER[@]}" "$ROOT/train.py" \
        --train_type      projector \
        --vision_model    "$VISION_MODEL" \
        --llm_model       "$LLM_MODEL" \
        --projector_type  "$PROJECTOR_TYPE" \
        "${RESAMPLER_ARGS[@]}" \
        --data_path       "$CC3M_DATA" \
        --image_dir       "$CC3M_IMG" \
        --output_dir      "$P1_OUT" \
        --num_epochs      1 \
        --batch_size      "$eff32_batch" \
        --grad_accum      "$eff32_accum" \
        --learning_rate   1e-3 \
        --lr_scheduler    cosine \
        --warmup_ratio    0.03 \
        --max_seq_len     2048 \
        --max_steps       "$(steps_for 5000)" \
        --dtype           bfloat16 \
        --gradient_checkpointing \
        --save_steps      2500 \
        --save_total_limit 1 \
        --logging_steps   50 \
        --dataloader_workers 8 \
        --wandb_project   "${WANDB_PROJECT:-vlm-v2}" \
        --wandb_run_name  "proj_${TAG}_p1" \
        "${DS_ARG[@]}" || { echo "Phase 1 실패"; exit 1; }
fi

# ── Phase 2: CC3M 프로젝터 + LoRA ─────────────────────────────────────────────
if has_phase 2; then
    echo "--- Phase 2: CC3M 프로젝터 + LoRA ---"
    "${LAUNCHER[@]}" "$ROOT/train.py" \
        --train_type      lora \
        --vision_model    "$VISION_MODEL" \
        --llm_model       "$LLM_MODEL" \
        --projector_type  "$PROJECTOR_TYPE" \
        "${RESAMPLER_ARGS[@]}" \
        --projector_path  "$P1_OUT/projector.bin" \
        --data_path       "$CC3M_DATA" \
        --image_dir       "$CC3M_IMG" \
        --output_dir      "$P2_OUT" \
        --num_epochs      1 \
        --batch_size      "$eff32_batch" \
        --grad_accum      "$eff32_accum" \
        --learning_rate   2e-4 \
        --lr_scheduler    cosine \
        --warmup_ratio    0.03 \
        --max_seq_len     2048 \
        --max_steps       "$(steps_for -1)" \
        --lora_r          128 \
        --lora_alpha      256 \
        --dtype           bfloat16 \
        --gradient_checkpointing \
        --save_steps      5000 \
        --save_total_limit 2 \
        --logging_steps   50 \
        --dataloader_workers 8 \
        --wandb_project   "${WANDB_PROJECT:-vlm-v2}" \
        --wandb_run_name  "proj_${TAG}_p2" \
        "${DS_ARG[@]}" || { echo "Phase 2 실패"; exit 1; }
fi

# ── Phase 2b: LLaMarine 텍스트 전용 LoRA ──────────────────────────────────────
# 이 단계는 프로젝터를 적재하지 않는다. 프로젝터에 대한 의존은 출발점 LoRA 가
# Phase 2 에서 프로젝터와 함께 학습되었다는 간접 경로뿐이다. 그래서 프로젝터마다
# 다시 돌린다.
if has_phase 2b; then
    echo "--- Phase 2b: LLaMarine 텍스트 LoRA ---"
    "${LAUNCHER[@]}" "$ROOT/train_text_lora.py" \
        --llm_model      "$LLM_MODEL" \
        --lora_path      "$P2_OUT" \
        --data_path      "$MARINE_DATA" \
        --output_dir     "$P2B_OUT" \
        --max_seq_len    2048 \
        --batch_size     "$eff64_batch" \
        --grad_accum     "$eff64_accum" \
        --learning_rate  5e-5 \
        --num_epochs     1 \
        --max_steps      "$(steps_for -1)" \
        --dtype          bfloat16 \
        --gradient_checkpointing \
        --save_steps     400 \
        --logging_steps  50 \
        --dataloader_workers 4 \
        --wandb_project  "${WANDB_PROJECT:-vlm-v2}" \
        "${DS_ARG[@]}" || { echo "Phase 2b 실패"; exit 1; }
fi

# ── Phase 3: SDS 도메인 LoRA ──────────────────────────────────────────────────
if has_phase 3; then
    echo "--- Phase 3: SDS 9k 도메인 LoRA ---"
    "${LAUNCHER[@]}" "$ROOT/train.py" \
        --train_type       lora \
        --vision_model     "$VISION_MODEL" \
        --llm_model        "$LLM_MODEL" \
        --projector_type   "$PROJECTOR_TYPE" \
        "${RESAMPLER_ARGS[@]}" \
        --projector_path   "$P2B_OUT/projector.bin" \
        --resume_lora_path "$P2B_OUT" \
        --data_path        "$SDS_TRAIN" \
        --image_dir        "$SDS_IMG" \
        --valid_data_path  "$SDS_VALID" \
        --output_dir       "$P3_OUT" \
        --num_epochs       3 \
        --batch_size       "$eff32_batch" \
        --grad_accum       "$eff32_accum" \
        --learning_rate    2e-4 \
        --lr_scheduler     cosine \
        --warmup_ratio     0.03 \
        --max_seq_len      2048 \
        --max_steps        "$(steps_for -1)" \
        --dtype            bfloat16 \
        --gradient_checkpointing \
        --save_steps       200 \
        --save_total_limit 2 \
        --eval_steps       100 \
        --logging_steps    10 \
        --dataloader_workers 4 \
        --wandb_project    "${WANDB_PROJECT:-vlm-v2}" \
        --wandb_run_name   "proj_${TAG}_p3" \
        "${DS_ARG[@]}" || { echo "Phase 3 실패"; exit 1; }
fi

echo ""
echo "=== 체인 완료: $PROJECTOR_TYPE ==="
for d in "$P1_OUT" "$P2_OUT" "$P2B_OUT" "$P3_OUT"; do
    if [ -d "$d" ]; then echo "  $d"; fi
done

# 마지막 명령이 요약 출력이므로 그 결과가 스크립트 종료 코드가 되지 않도록 한다.
# 돌리지 않은 단계의 디렉토리는 없는 것이 정상인데, 그 검사 실패가 체인 실패로
# 보이면 상위 오케스트레이터가 다음 프로젝터로 넘어가지 않는다.
exit 0
