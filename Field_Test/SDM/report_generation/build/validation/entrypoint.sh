#!/usr/bin/env bash
# Stage dispatcher for the external-validation image.
#
#   docker run ... ctreportgen-val check      [flags]   pre-flight the cohort dir
#   docker run ... ctreportgen-val preprocess [flags]   nii.gz + totalseg -> npz
#   docker run ... ctreportgen-val infer      [flags]   npz -> reports.json
#   docker run ... ctreportgen-val score      [flags]   reports.json -> nodule_f1.json
#   docker run ... ctreportgen-val review     [flags]   readable per-case export
#   docker run ... ctreportgen-val all                  all three, in order
#   docker run -it ... chest-ct-foundation [demo]       TC1 end to end (the default)
#   docker run -it ... chest-ct-foundation shell        interactive shell, steps by hand
#   docker run ... ctreportgen-val --npz_dir /data ...  falls through to run_inference.py
#
# The fall-through keeps the bundle's own documented invocation working unchanged, so
# `--npz_dir ... --out ...` behaves exactly as `inference_bundle/README.md` describes.
set -euo pipefail

DATA_ROOT=${DATA_ROOT:-/data}
OUT_DIR=${OUT_DIR:-/out}
NPZ_DIR=${NPZ_DIR:-$OUT_DIR/npz}
BATCH_SIZE=${BATCH_SIZE:-4}
NPROC=${NPROC:-$(( $(nproc) - 2 ))}
[ "$NPROC" -lt 1 ] && NPROC=1

# The bundle's input contract. Spelled out here rather than left to the script's
# defaults (1.0 mm / 384^3, the high-res config) because getting it wrong does not
# fail — it produces a fluent report from the wrong geometry.
SPACING=${SPACING:-1.5 1.5 1.5}
SHAPE=${SHAPE:-256 256 256}

preprocess() {
  # Stamp the npz directory with where it came from. The stage is resumable and npz
  # files are named by case id alone, so without this a directory built from one
  # cohort and topped up from another is indistinguishable from a clean one — and
  # the mix would be scored as a single run. SOURCE_LABEL is the host path; inside
  # the container every cohort is /data.
  local stamp="$NPZ_DIR/SOURCE.json"
  mkdir -p "$NPZ_DIR"
  if [ -f "$stamp" ]; then
    local was
    was=$(sed -n 's/.*"source_label": *"\([^"]*\)".*/\1/p' "$stamp")
    if [ -n "$was" ] && [ "$was" != "${SOURCE_LABEL:-unset}" ]; then
      echo "ERROR: $NPZ_DIR already holds npz built from '$was', but this run's" >&2
      echo "       cohort is '${SOURCE_LABEL:-unset}'. Mixing two cohorts into one" >&2
      echo "       npz directory would be scored as a single run." >&2
      echo "       Delete $NPZ_DIR (or point NPZ_DIR elsewhere) and re-run." >&2
      exit 3
    fi
  fi
  python3 /app/validation/preprocess_npz.py \
    --data_root "$DATA_ROOT" \
    --original_dirname "${CT_DIRNAME:-nii}" \
    --totalseg_dirname "${TOTALSEG_DIRNAME:-totalseg}" \
    --dst "$NPZ_DIR" \
    --target_spacing $SPACING \
    --target_shape $SHAPE \
    --compress --nproc "$NPROC" "$@"
  printf '{\n  "source_label": "%s",\n  "spacing": "%s",\n  "shape": "%s",\n  "n_npz": %s,\n  "built": "%s"\n}\n' \
    "${SOURCE_LABEL:-unset}" "$SPACING" "$SHAPE" \
    "$(ls "$NPZ_DIR"/*.npz 2>/dev/null | wc -l)" "$(date -Iseconds)" > "$stamp"
  echo "[stamp] $stamp  source=${SOURCE_LABEL:-unset}"
}

infer() {
  python3 /app/run_inference.py \
    --npz_dir "$NPZ_DIR" --out "$OUT_DIR/reports.json" \
    --batch_size "$BATCH_SIZE" "$@"
}

check() {
  python3 /app/validation/check_cohort.py --data_root "$DATA_ROOT" \
    --ct_dirname "${CT_DIRNAME:-nii}" --totalseg_dirname "${TOTALSEG_DIRNAME:-totalseg}" "$@"
}

review() {
  python3 /app/validation/export_review.py --reports "$OUT_DIR/reports.json" \
    --audit "$OUT_DIR/nodule_f1_cases.csv" --data_root "$DATA_ROOT" \
    --out "$OUT_DIR/manual_review.csv" "$@"
}

score() {
  python3 /app/validation/eval_nodule_f1.py \
    --reports "$OUT_DIR/reports.json" --data_root "$DATA_ROOT" \
    --out "$OUT_DIR/nodule_f1.json" "$@"
}

stage=${1:-demo}
[[ "$stage" == -* ]] && exec python3 /app/run_inference.py "$@"
shift || true

case "$stage" in
  check)      check "$@" ;;
  preprocess) preprocess "$@" ;;
  infer)      infer "$@" ;;
  score)      score "$@" ;;
  review)     review "$@" ;;
  all)
    # Flags are stage-specific, so `all` takes none: run the stages separately to
    # pass any. Order matters — each reads what the previous one wrote.
    if [[ $# -gt 0 ]]; then
      echo "'all' takes no flags; run the stages separately to pass any" >&2
      exit 2
    fi
    check || [ $? -eq 1 ]      # exit 1 is "incomplete but usable"; 2 is fatal
    preprocess
    infer
    score
    ;;
  test)
    exec python3 /app/validation/test_nodule_readout.py
    ;;
  demo)
    # TC1 end to end: environment, dataset, generation, check, 3-round labeling, F1, CSV.
    exec python3 /app/demo/run_all.py "$@"
    ;;
  shell)
    # Interactive shell for the live demo: the reviewers run each step by hand.
    exec bash "$@"
    ;;
  help|-h|--help)
    sed -n '2,15p' "$0"
    echo
    echo "Per-stage flags: run '<stage> --help'.  'test' runs the read-out checks."
    ;;
  *)
    echo "unknown stage '$stage'; expected check | preprocess | infer | score | review | all | test | demo | shell" >&2
    exit 2
    ;;
esac
