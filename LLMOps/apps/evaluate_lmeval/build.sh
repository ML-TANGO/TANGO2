#!/usr/bin/env bash
# evaluate-lmeval 이미지 빌드 (evaluate-lmeval / evaluate-lmeval-code 공용 이미지).
#
# 레포 루트를 빌드 컨텍스트로 쓰지 않고 필요한 파일만 스테이징한다. etri-infer.txt 는 ETRI
# 원본(LogicKor 스냅샷)이며 복제본을 레포에 두지 않는다 — logickor-judge 와 같은 런타임이다.
# 빌드 중 17종 데이터셋·지표 스크립트를 받으므로 빌드 호스트에 외부망이 필요하다(약 1GB).
#
#   ./build.sh                 # 빌드 → 이 노드 containerd(k8s.io) 적재
#   PUSH=1 ./build.sh          # + docker.io push (신규 서버는 로컬 적재본이 없어 ErrImagePull)
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLMOPS_ROOT="$(cd "${APP_DIR}/../.." && pwd)"
TAG="${TAG:-docker.io/acrylaaai/evaluate-lmeval:0.1.2}"
STAGE="${STAGE:-${TMPDIR:-/tmp}/lmeval-build}"
OUT="${OUT:-${TMPDIR:-/tmp}/evaluate-lmeval.tar}"

rm -rf "${STAGE}" && mkdir -p "${STAGE}"
cp "${APP_DIR}"/{Dockerfile,app.py,registry.py,scoring.py,checkpoint.py,custom_eval.py,prepare_tasks.py,requirements-lmeval.txt,requirements-wrapper.txt} "${STAGE}/"
cp "${LLMOPS_ROOT}/Evaluation/Logickor/requirements/etri-infer.txt" "${STAGE}/"
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

if [ "${PUSH:-0}" = 1 ]; then
  sudo buildctl build --frontend dockerfile.v0 \
    --local context="${STAGE}" --local dockerfile="${STAGE}" \
    --output "type=image,name=${TAG},push=true"
fi

[ "${STARTED_BUILDKITD}" = 1 ] && sudo pkill -f 'buildkitd --root /var/lib/buildkit-julian' || true

# OCI tar → containerd k8s.io. import 는 CRI 라벨을 붙이지 않으므로
# io.cri-containerd.image=managed 를 별도로 박아야 kubelet 이 로컬 이미지로 인식한다
# (없으면 IfNotPresent 인데도 pull 을 시도해 ErrImagePull 이 난다).
sudo ctr -n k8s.io images import --base-name "${TAG%:*}" "${OUT}"
sudo ctr -n k8s.io images label "${TAG}" io.cri-containerd.image=managed
sudo rm -f "${OUT}"
sudo crictl images | grep evaluate-lmeval
