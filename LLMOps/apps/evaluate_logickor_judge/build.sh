#!/usr/bin/env bash
# evaluate-logickor-judge 이미지 빌드.
#
# 레포 루트를 빌드 컨텍스트로 쓰지 않고 필요한 파일만 고정 스테이징 경로에 모은다
# (Evaluation/ 의 평가 산출물만 20MB, front/node_modules 는 수백MB). 매 실행 시 덮어쓰며
# 남겨 두어도 무해하다(빌드 입력 추적에 오히려 유용).
# templates.py 와 etri-infer.txt 는 ETRI 원본이며 복제본을 레포에 두지 않는다 —
# 원본이 바뀌면 다음 빌드에 자동 반영되게 하려는 것이다.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLMOPS_ROOT="$(cd "${APP_DIR}/../.." && pwd)"
TAG="${TAG:-docker.io/acrylaaai/evaluate-logickor-judge:0.2.5}"
STAGE="${STAGE:-${TMPDIR:-/tmp}/logickor-judge-build}"
OUT="${OUT:-${TMPDIR:-/tmp}/evaluate-logickor-judge.tar}"

mkdir -p "${STAGE}"
cp "${APP_DIR}"/{Dockerfile,app.py,generate.py,judge.py,requirements-wrapper.txt} "${STAGE}/"
cp "${LLMOPS_ROOT}/apps/evaluate_logickor/scoring.py"                     "${STAGE}/"
cp "${LLMOPS_ROOT}/Evaluation/Logickor_web/logickor_eval/templates.py"    "${STAGE}/"
cp "${LLMOPS_ROOT}/Evaluation/Logickor/logickor_eval/questions.jsonl"     "${STAGE}/"
cp "${LLMOPS_ROOT}/Evaluation/Logickor/requirements/etri-infer.txt"       "${STAGE}/"
echo "빌드 컨텍스트: ${STAGE} ($(du -sh "${STAGE}" | cut -f1))"

# buildkitd 가 없으면 임시로 띄운다(이 호스트에는 root 용 소켓이 상시 없다).
BUILDKIT_ROOT="${BUILDKIT_ROOT:-/var/lib/buildkit-$(id -un)}"
STARTED_BUILDKITD=0
if ! sudo buildctl debug workers >/dev/null 2>&1; then
  BUILDKITD_PID=$(sudo sh -c 'nohup buildkitd --root "$1" > /tmp/buildkitd-build.log 2>&1 & echo $!' sh "${BUILDKIT_ROOT}")
  for _ in $(seq 1 60); do sudo buildctl debug workers >/dev/null 2>&1 && break; sleep 1; done
  STARTED_BUILDKITD=1
fi

sudo buildctl build --frontend dockerfile.v0 \
  --local context="${STAGE}" --local dockerfile="${STAGE}" \
  --output "type=oci,dest=${OUT},name=${TAG}"

[ "${STARTED_BUILDKITD}" = 1 ] && sudo kill "${BUILDKITD_PID}" || true

# OCI tar → containerd k8s.io. nerdctl 의 load 경로로 넣은 이미지는 파드 종료 후 사라져
# ErrImagePull 이 났다(2026-08-21 실측). 또한 import 는 CRI 라벨을 붙이지 않으므로
# io.cri-containerd.image=managed 를 별도로 박아야 kubelet 이 로컬 이미지로 인식한다.
sudo ctr -n k8s.io images import --base-name "${TAG%:*}" "${OUT}"
sudo ctr -n k8s.io images label "${TAG}" io.cri-containerd.image=managed
sudo crictl images | grep evaluate-logickor-judge
