MODEL_PATH=${1:-"/model/ct_siglip/1c_fit3.pth"}
CSV_PATH=${2:-"/data/all_ct_with_labels_val.csv"}
LABELS_JSON=${3:-""}
OUTPUT_DIR=${4:-"results"}
BATCH_SIZE=${5:-16}
DEVICE=${6:-"cuda"}
LOG_LEVEL=${7:-"INFO"}
CMD="CUDA_VISIBLE_DEVICES=5, python3 evaluate_siglip_ct_cal.py --model-path \"$MODEL_PATH\" --csv \"$CSV_PATH\" --batch-size $BATCH_SIZE --device $DEVICE --log-level $LOG_LEVEL --output-dir \"$OUTPUT_DIR\""

if [ -n "$LABELS_JSON" ]; then
  LABELS=$(jq -r '.[]' "$LABELS_JSON" | tr '\n' ' ')
  CMD="$CMD --label-columns $LABELS"
fi

echo "Running evaluation with command:"
echo $CMD

eval $CMD