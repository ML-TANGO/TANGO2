#!/usr/bin/env bash
# NIAH single-needle long-context evaluation for a Hugging Face model (+ optional LoRA adapter).
#
# Edit the settings block below and run `scripts/run_eval.sh`. Command-line
# options (see --help) override the block for a single run:
#   scripts/run_eval.sh --model google/gemma-4-E4B-it --context_length 4 8 16
#
# Run scripts/setup.sh once per server before using this.
set -euo pipefail

# ========================= settings =========================
MODEL="google/gemma-4-E4B-it"   # HF model id or local path. "" with ADAPTER: read from adapter_config.json
ADAPTER=""                      # LoRA/PEFT adapter directory (absolute path). "" = evaluate the base model as-is
CONTEXT=(all)                   # k tokens, e.g. (4 8 16) or (all) = 4 8 16 32 64 128
TOKENIZER="gpt"                 # length measured in: gpt (NIAH default) | model (the model's own tokenizer)
DEPTHS=(50)                     # needle depth percents, e.g. (0 25 50 75 100)
GPUS=""                         # e.g. "0" or "0,1". "" = all visible GPUs
MAX_NEW_TOKENS=128              # answer length limit
DTYPE=bfloat16                  # bfloat16 | float16 | float32
OUTPUT_DIR=""                   # "" = needle-in-a-haystack/results
# ============================================================

usage() {
  cat <<'EOF'
Usage: run_eval.sh [options]   (unset options use the settings block at the top of this file)

  --model NAME            HF model id or local path (optional with --adapter:
                          read from adapter_config.json base_model_name_or_path)
  --adapter PATH          LoRA/PEFT adapter directory. Omit to evaluate the base model.
  --context_length K...   Context lengths in k tokens (4 8 16 32 64 128) or "all". Default: all
  --tokenizer NAME        Tokenizer used to measure context length:
                            gpt   (default) NIAH's cl100k_base; lengths that overflow the model are skipped
                            model the evaluated model's own tokenizer; 128k is trimmed to fit
                            <id>  any other HF tokenizer id or path
  --depths D...           Needle depth percents. Default: 50
  --max_new_tokens N      Answer length limit. Default: 128
  --dtype TYPE            bfloat16 | float16 | float32. Default: bfloat16
  --gpus IDS              GPUs to use, e.g. 0 or 0,1 (sets CUDA_VISIBLE_DEVICES). Default: all visible
  --output_dir DIR        Default: <niah>/results
  --dry_run               Write configs and validate only; don't load the model.
EOF
}

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
NIAH_DIR=${NIAH_DIR:-$(dirname "$SCRIPT_DIR")/needle-in-a-haystack}

DRY_RUN=0

# Collect values until the next --flag, so `--context_length 4 8 16` works.
take_list() { local -n _arr=$1; _arr=(); shift; while [[ $# -gt 0 && $1 != --* ]]; do _arr+=("$1"); shift; done; }
while [[ $# -gt 0 ]]; do
  case $1 in
    --model) MODEL=$2; shift 2 ;;
    --adapter) ADAPTER=$2; shift 2 ;;
    --tokenizer) TOKENIZER=$2; shift 2 ;;
    --context_length|--context-length) shift; take_list CONTEXT "$@"; shift ${#CONTEXT[@]} ;;
    --depths) shift; take_list DEPTHS "$@"; shift ${#DEPTHS[@]} ;;
    --max_new_tokens|--max-new-tokens) MAX_NEW_TOKENS=$2; shift 2 ;;
    --dtype) DTYPE=$2; shift 2 ;;
    --gpus) GPUS=$2; shift 2 ;;
    --output_dir|--output-dir) OUTPUT_DIR=$2; shift 2 ;;
    --dry_run|--dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done
# Absolute paths, since the run happens from inside the NIAH clone.
[[ -n $ADAPTER ]] && ADAPTER=$(realpath "$ADAPTER")
OUTPUT_DIR=$(realpath -m "${OUTPUT_DIR:-$NIAH_DIR/results}")

# 1. Activate the NIAH venv built by setup.sh.
if [[ ! -x $NIAH_DIR/.venv/bin/python ]] || ! "$NIAH_DIR/.venv/bin/python" -c "import needlehaystack" 2>/dev/null; then
  echo "error: no working venv at $NIAH_DIR/.venv; run scripts/setup.sh first" >&2
  exit 1
fi
# shellcheck disable=SC1091
source "$NIAH_DIR/.venv/bin/activate"
export TIKTOKEN_CACHE_DIR=$NIAH_DIR/.cache/tiktoken
[[ -n $GPUS ]] && export CUDA_VISIBLE_DEVICES=$GPUS

# 2. Resolve model / adapter / tokenizer.
if [[ -n $ADAPTER ]]; then
  [[ -f $ADAPTER/adapter_config.json ]] || { echo "error: $ADAPTER has no adapter_config.json" >&2; exit 1; }
  if [[ -z $MODEL ]]; then
    MODEL=$(python -c "import json,sys; print(json.load(open(sys.argv[1]))['base_model_name_or_path'])" "$ADAPTER/adapter_config.json")
    echo "base model from adapter_config.json: $MODEL"
  fi
fi
[[ -n $MODEL ]] || { echo "error: --model is required" >&2; usage >&2; exit 2; }

# An adapter saved with its own tokenizer (e.g. added chat tokens) overrides the base one.
TOKENIZER_PATH=""
[[ -n $ADAPTER && -f $ADAPTER/tokenizer_config.json ]] && TOKENIZER_PATH=$ADAPTER

case $TOKENIZER in
  gpt) unset NIAH_TOKENIZER; LENGTH_UNIT=gpt ;;
  model) export NIAH_TOKENIZER=${TOKENIZER_PATH:-$MODEL}; LENGTH_UNIT=model ;;
  *) export NIAH_TOKENIZER=$TOKENIZER; LENGTH_UNIT=gpt ;;
esac

RUN_NAME="$(basename "$MODEL")${ADAPTER:+__$(basename "$ADAPTER")}__tok-$(basename "$TOKENIZER")"
OUT="$OUTPUT_DIR/$RUN_NAME"

# 3. Write configs, then run from the NIAH clone (the haystack path is relative to it).
cd "$NIAH_DIR"
python "$SCRIPT_DIR/niah_helper.py" plan \
  --model "$MODEL" ${ADAPTER:+--adapter "$ADAPTER"} ${TOKENIZER_PATH:+--tokenizer-path "$TOKENIZER_PATH"} \
  --length-unit "$LENGTH_UNIT" --context-length "${CONTEXT[@]}" --depths "${DEPTHS[@]}" \
  --max-new-tokens "$MAX_NEW_TOKENS" --dtype "$DTYPE" --run-name "$RUN_NAME" --out-dir "$OUT"

niah validate "$OUT/run.yaml"
if [[ $DRY_RUN == 1 ]]; then
  niah run "$OUT/run.yaml" --dry-run
  exit 0
fi

niah run "$OUT/run.yaml"
python "$SCRIPT_DIR/niah_helper.py" summary --out-dir "$OUT"
