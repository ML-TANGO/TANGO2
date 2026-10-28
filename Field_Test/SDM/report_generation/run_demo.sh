#!/usr/bin/env bash
# TC1 live demo — chest CT report generation, nodule accuracy.
#
#   ./run_demo.sh                 Steps 2-7 end to end, results in out/<date_time>/
#   ./run_demo.sh shell           interactive shell in the same container, steps by hand
#   RUN=out/<date_time> ./run_demo.sh
#                                 rerun into an existing run folder: inference repeats
#                                 (identical output), labeling sends only missing calls
#   GPU=1 ./run_demo.sh           expose a different GPU (default 5)
#   LABELER=gemini ./run_demo.sh  label with gemini-3.5-flash-lite instead of gpt-6-luna
#                                 (image chest-ct-foundation:tc1-gemini, IMAGE_ID_GEMINI,
#                                 key in labeler_gemini.env)
#
# Exit code: 0 PASS, 1 FAIL, 2 stopped on an error, 3 image ID mismatch.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

GPU=${GPU:-5}
case "${LABELER:-luna}" in
  luna)   IMAGE=chest-ct-foundation:tc1;        ID_FILE=IMAGE_ID;        ENV_FILE=labeler.env ;;
  gemini) IMAGE=chest-ct-foundation:tc1-gemini; ID_FILE=IMAGE_ID_GEMINI; ENV_FILE=labeler_gemini.env ;;
  *) echo "LABELER must be luna or gemini" >&2; exit 2 ;;
esac

# Refuse to run anything but the image recorded in the procedure document.
want=$(cat $ID_FILE)
have=$(docker inspect --format '{{.Id}}' "$IMAGE" 2>/dev/null || echo "not found")
echo "image     $IMAGE"
echo "expected  $want"
echo "found     $have"
if [ "$have" != "$want" ]; then
  echo "IMAGE ID MISMATCH — not running. See README.md, 'Rebuilding the image'." >&2
  exit 3
fi

[ -f $ENV_FILE ] || { echo "$ENV_FILE missing (API key for the $LABELER labeler)" >&2; exit 2; }

RUN=${RUN:-out/$(date +%Y%m%d_%H%M%S)}
mkdir -p "$RUN"
echo "output    $PWD/$RUN"
echo

# A terminal gets the live progress bars; without one (cron, a pipe) output is plain text.
TTY=-i
[ -t 1 ] && TTY=-it

exec docker run $TTY --rm --gpus "\"device=$GPU\"" --shm-size 8g \
  -v "$PWD/data/set_O:/data:ro" \
  -v "$PWD/hf_cache:/hf:ro" \
  -v "$PWD/$RUN:/out" \
  --env-file $ENV_FILE \
  "$IMAGE" "$@"
