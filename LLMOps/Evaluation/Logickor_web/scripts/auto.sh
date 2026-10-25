#!/usr/bin/env bash
# Run the full LogicKor pipeline in one shot:
#   0) clean previous outputs  1) train  2) generate  3) evaluate  4) score
set -euo pipefail

# Always run from the repository root, whatever directory the script is called from.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

CONFIG_PATH="${CONFIG_PATH:-configs/train_gemma4_e4b_sft.yaml}"
RUN_DIR="${RUN_DIR:-runs/gemma4_e4b_sft_high}"
MERGED_DIR="${RUN_DIR}/merged"
SEED="${SEED:-42}"
GPU="${GPU:-0}"
GEN_MODEL_LEN="${GEN_MODEL_LEN:-4096}"
JUDGE_MODEL="${JUDGE_MODEL:-gemma}"
JUDGE_MODEL_LEN="${JUDGE_MODEL_LEN:-8192}"

# MODE=debug 는 짧은 확인용 실행: 학습/평가 데이터의 일부(TRAIN_FRACTION, 기본 10%)만 쓴다.
# MODE=full(기본)은 전체 데이터로 학습한다. TRAIN_FRACTION 을 직접 주면 그 값이 우선한다.
MODE="${MODE:-full}"
if [[ "${MODE}" == "debug" ]]; then
  TRAIN_FRACTION="${TRAIN_FRACTION:-0.1}"
else
  TRAIN_FRACTION="${TRAIN_FRACTION:-1.0}"
fi

# GPU 0 only.
export CUDA_VISIBLE_DEVICES="${GPU}"

step() {
  echo ""
  echo "=============================================================="
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
  echo "=============================================================="
}

step "Step 0/4: cleaning previous outputs"
# The generator and evaluator both skip work when an output file already exists,
# so stale results must be removed before a fresh run.
rm -f evaluated/*.jsonl
rm -rf "generated/runs"
rm -rf "runs"

step "Step 1/4: LoRA SFT training (mode=${MODE}, data=${TRAIN_FRACTION}) -> ${RUN_DIR}"
python train/train_lora.py \
  --config "${CONFIG_PATH}" \
  --output-dir "${RUN_DIR}" \
  --seed "${SEED}" \
  --gpu "${GPU}" \
  --train-fraction "${TRAIN_FRACTION}"

step "Step 2/4: generating LogicKor answers with ${MERGED_DIR}"
python logickor_eval/generator.py \
  --model "${MERGED_DIR}" \
  --gpu_devices "${GPU}" \
  --model_len "${GEN_MODEL_LEN}"

step "Step 3/4: judging with '${JUDGE_MODEL}' -> evaluated/"
python logickor_eval/evaluator.py \
  -o "generated/${MERGED_DIR}" \
  -j "${JUDGE_MODEL}" \
  -g "${GPU}" \
  -ml "${JUDGE_MODEL_LEN}"

step "Step 4/4: scoring evaluated/*.jsonl"
python logickor_eval/score.py -p 'evaluated/*.jsonl'

step "Pipeline finished successfully"
