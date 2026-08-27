#!/usr/bin/env bash
# evaluate-intent 이미지 빌드.
#
# 레포 루트를 빌드 컨텍스트로 쓰지 않고 필요한 파일만 고정 스테이징 경로에 모은다.
# ETRI 원본(ugen_data.py / evaluate_qwen3_mixatis.py / train_qwen3_mixatis.py)과 MixATIS 데이터는 복제본을
# 레포에 두지 않는다 — 원본이 바뀌면 다음 빌드에 자동 반영되게 하려는 것이다.
# seq.out 은 저장소에 없으므로(.gitignore `*.out`) 스테이징 사본에 대고 복원한다.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLMOPS_ROOT="$(cd "${APP_DIR}/../.." && pwd)"
TAG="${TAG:-docker.io/acrylaaai/evaluate-intent:0.2.4}"
STAGE="${STAGE:-${TMPDIR:-/tmp}/intent-build}"
OUT="${OUT:-${TMPDIR:-/tmp}/evaluate-intent.tar}"

rm -rf "${STAGE}"
mkdir -p "${STAGE}"
cp "${APP_DIR}"/{Dockerfile,app.py,evaluate.py,train.py,scoring.py,remote.py,requirements.txt,requirements-wrapper.txt} "${STAGE}/"
cp "${LLMOPS_ROOT}/Evaluation/Intent_web/ugen_data.py"              "${STAGE}/"
cp "${LLMOPS_ROOT}/Evaluation/Intent_web/evaluate_qwen3_mixatis.py" "${STAGE}/"
cp "${LLMOPS_ROOT}/Evaluation/Intent_web/train_qwen3_mixatis.py"    "${STAGE}/"

# MixATIS 사본 + seq.out 복원(원본 저장소는 건드리지 않는다).
mkdir -p "${STAGE}/data"
cp -r "${LLMOPS_ROOT}/Evaluation/Intent_Detection/data/MixATIS_clean" "${STAGE}/data/"
python3 "${APP_DIR}/rebuild_seq_out.py" "${STAGE}/data/MixATIS_clean"

echo "빌드 컨텍스트: ${STAGE} ($(du -sh "${STAGE}" | cut -f1))"

# buildkitd 가 없으면 임시로 띄운다(이 호스트에는 root 용 소켓이 상시 없다).
STARTED_BUILDKITD=0
if ! sudo buildctl debug workers >/dev/null 2>&1; then
  sudo sh -c 'nohup buildkitd --root /var/lib/buildkit-julian > /tmp/buildkitd-build.log 2>&1 &'
  for _ in $(seq 1 60); do sudo buildctl debug workers >/dev/null 2>&1 && break; sleep 1; done
  STARTED_BUILDKITD=1
fi

sudo buildctl build --frontend dockerfile.v0 \
  --local context="${STAGE}" --local dockerfile="${STAGE}" \
  --output "type=oci,dest=${OUT},name=${TAG}"

[ "${STARTED_BUILDKITD}" = 1 ] && sudo pkill -f 'buildkitd --root /var/lib/buildkit-julian' || true

# OCI tar → containerd k8s.io. import 는 CRI 라벨을 붙이지 않으므로
# io.cri-containerd.image=managed 를 별도로 박아야 kubelet 이 로컬 이미지로 인식한다
# (없으면 IfNotPresent 인데도 pull 을 시도해 ErrImagePull 이 난다).
sudo ctr -n k8s.io images import --base-name "${TAG%:*}" "${OUT}"
sudo ctr -n k8s.io images label "${TAG}" io.cri-containerd.image=managed
sudo crictl images | grep evaluate-intent
