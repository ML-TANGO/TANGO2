#!/usr/bin/env bash
# Steps 4-5 — generate one report per CT volume, then check the output.
#
#   bash /app/demo/inference.sh                 # /data -> /out/generated_reports.json
#
# Runs once. Greedy decoding (do_sample=False in src/pipeline.py), batch size and case
# order fixed, seeds fixed. The bundle left-pads each batch to its longest prompt, so
# batch size and order change the generated text — keep both as they are here.
#
# Writes /out/generated_reports.json, /out/inference_log.txt, /out/timing.json.
set -euo pipefail

DATA=${DATA:-/data}
OUT=${OUT:-/out}

python3 /app/demo/generate.py --data "$DATA" --out "$OUT" \
  --batch_size "${BATCH_SIZE:-4}" --seed "${SEED:-42}"
python3 /app/demo/check_reports.py --data "$DATA" --pred "$OUT/generated_reports.json"
