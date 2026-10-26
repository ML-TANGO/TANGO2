#!/usr/bin/env bash
# Pre-flight: is everything in place to launch the TC1 demo? Changes nothing.
#
#   ./check_ready.sh
#
# Checks the image, GPUs, test data, model weights, labeler files, API key and
# connectivity (one synthetic call to the labeler model — no patient text), and disk space.
# LABELER=gemini ./check_ready.sh checks the gemini-3.5-flash-lite package instead.
# Exit 0 = READY.
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")"

case "${LABELER:-luna}" in
  luna)   IMAGE=chest-ct-foundation:tc1;        ID_FILE=IMAGE_ID;        ENV_FILE=labeler.env
          KEY=OPENAI_API_KEY; MODEL=gpt-6-luna ;;
  gemini) IMAGE=chest-ct-foundation:tc1-gemini; ID_FILE=IMAGE_ID_GEMINI; ENV_FILE=labeler_gemini.env
          KEY=GEMINI_API_KEY; MODEL=gemini-3.5-flash-lite ;;
  *) echo "LABELER must be luna or gemini" >&2; exit 2 ;;
esac
D=data/set_O
fails=0
ok()   { printf '  \033[1;32m✓\033[0m %s\n' "$1"; }
bad()  { printf '  \033[1;31m✗\033[0m %s\n' "$1"; fails=$((fails + 1)); }
check() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
section() { printf '\n\033[1;36m== %s\033[0m\n' "$1"; }

section "Image"
want=$(cat $ID_FILE)
have=$(docker inspect --format '{{.Id}}' "$IMAGE" 2>/dev/null || echo "not found")
echo "  expected $want"
echo "  found    $have"
[ "$have" = "$want" ] && ok "image ID matches $ID_FILE" || bad "image ID matches $ID_FILE"

section "GPU"
nvidia-smi --query-gpu=index,name,driver_version,memory.used,memory.total --format=csv,noheader | sed 's/^/  /'
check "host has 6 GPUs" '[ "$(nvidia-smi -L | wc -l)" -eq 6 ]'
check "driver 570.211.01" 'nvidia-smi --query-gpu=driver_version --format=csv,noheader | grep -qx 570.211.01'
# Inference peaks at ~16 GB; the GUI container may share the card (measured together: 26.5 GB).
free=$(nvidia-smi -i "${GPU:-5}" --query-gpu=memory.free --format=csv,noheader,nounits)
[ "$free" -ge 20000 ] && ok "GPU ${GPU:-5} has room (${free} MiB free, need 20000)" \
  || bad "GPU ${GPU:-5} has room (${free} MiB free, need 20000)"
check "container sees exactly 1 GPU" \
  '[ "$(docker run --rm --gpus "\"device=${GPU:-5}\"" --entrypoint nvidia-smi $IMAGE -L | wc -l)" -eq 1 ]'

section "Test data ($D)"
nv=$(ls $D/volumes/*.npz 2>/dev/null | wc -l)
ng=$(ls $D/gt_reports/*.txt 2>/dev/null | wc -l)
pos=$(tail -n +2 $D/manifest.csv | cut -d, -f2 | grep -cx 1)
neg=$(tail -n +2 $D/manifest.csv | cut -d, -f2 | grep -cx 0)
nn=$(ls $D/nii/*.nii.gz 2>/dev/null | wc -l)
echo "  CT scans    $nn  ($(du -shL $D/nii | cut -f1), original .nii.gz)"
echo "  CT volumes  $nv  ($(du -shL $D/volumes | cut -f1), preprocessed .npz)"
echo "  GT reports  $ng"
echo "  manifest    $(($(wc -l < $D/manifest.csv) - 1)) cases: $pos nodule-positive / $neg nodule-negative"
check "100 original CT scans, same cases as the manifest" \
  '[ "$nn" -eq 100 ] && diff -q <(ls $D/nii | grep nii.gz | sed "s/.nii.gz//") <(tail -n +2 $D/manifest.csv | cut -d, -f1 | sort) >/dev/null'
check "CT scans and masks unchanged (SHA256SUMS)" \
  '(cd $D/nii && sha256sum -c --quiet SHA256SUMS) && (cd $D/totalseg && sha256sum -c --quiet SHA256SUMS)'
check "100 CT volumes" '[ "$nv" -eq 100 ]'
check "100 GT reports" '[ "$ng" -eq 100 ]'
check "50 / 50 split" '[ "$pos" -eq 50 ] && [ "$neg" -eq 50 ]'
check "manifest hash matches MANIFEST.sha256" '(cd $D && sha256sum -c MANIFEST.sha256)'

section "Model weights"
check "MedGemma 1.5 4B in hf_cache" '[ -d hf_cache/hub/models--google--medgemma-1.5-4b-it/snapshots ]'
check "MedGemma weight files readable" \
  'find -L hf_cache/hub/models--google--medgemma-1.5-4b-it/snapshots -name "*.safetensors" | grep -q .'

section "Labeler"
check "system instruction and finding list unchanged (SHA256SUMS)" '(cd labeler && sha256sum -c SHA256SUMS)'
check "image carries the same labeler files" \
  'diff <(docker run --rm --entrypoint sh $IMAGE -c "cd /app/demo/labeler && sha256sum system_instruction.txt findings.json") labeler/SHA256SUMS'
check "$ENV_FILE present, mode 600" '[ "$(stat -c %a $ENV_FILE)" = 600 ] && grep -q "^$KEY=." $ENV_FILE'
if [ "$MODEL" = gpt-6-luna ]; then
  probe='
import openai
r = openai.OpenAI(max_retries=0, timeout=30).responses.create(
    model="gpt-6-luna", input="Reply with the single word OK.", reasoning={"effort": "none"}, store=False)
print(r.model, r.output_text.strip())'
else
  probe='
from google import genai
from google.genai import types
c = genai.Client(http_options=types.HttpOptions(timeout=30000))
r = c.models.generate_content(
    model="gemini-3.5-flash-lite", contents="Reply with the single word OK.",
    config=types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level="minimal")))
print(r.model_version, r.text.strip())'
fi
api=$(docker run --rm --env-file $ENV_FILE --entrypoint python3 $IMAGE -c "$probe" 2>&1 | tail -1)
echo "  API reply: $api"
[[ "$api" == "$MODEL "* ]] && ok "API reachable, key valid, $MODEL answers" \
  || bad "API reachable, key valid, $MODEL answers"

section "Disk"
free=$(df -BG --output=avail . | tail -1 | tr -dc 0-9)
echo "  ${free} GB free"
check "at least 5 GB free for outputs" '[ "$free" -ge 5 ]'

echo
if [ "$fails" -eq 0 ]; then
  launch="./run_demo.sh"; [ "${LABELER:-luna}" = gemini ] && launch="LABELER=gemini ./run_demo.sh"
  printf '\033[1;42;37m  READY  \033[0m  all checks passed — launch with %s\n' "$launch"
else
  printf '\033[1;41;37m  NOT READY  \033[0m  %s check(s) failed\n' "$fails"
fi
exit $(( fails > 0 ))
