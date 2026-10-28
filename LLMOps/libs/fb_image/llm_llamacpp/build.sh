#!/bin/bash
# 멀티엔진 서빙 Phase 2 — llama.cpp 서빙 이미지 빌드.
# 결과 태그는 apps/fb_utils/settings.py:DEPLOYMENT_LLM_LLAMACPP_IMAGE 와 정합해야 함.
#   (배포 시 service.py 가 {DOCKER_REGISTRY_URL} 을 앞에 붙여 pod.image 로 전달)
# 참조 recipe: libs/fb_image/llm/build.sh (vLLM 이미지) — 동일한 nerdctl/docker + registry 관례.
SCRIPT=$( readlink -m $( type -p $0 ))
BASE_DIR=`dirname ${SCRIPT}`

IMAGE="acrylaaai/llm_deployment_llamacpp:dev"
CLI="${CLI:-nerdctl}"   # docker 로 쓰려면 CLI=docker ./build.sh

echo "== Building ${IMAGE} with ${CLI} =="
${CLI} build -t "${IMAGE}" "${BASE_DIR}"

echo ""
echo "빌드 완료. 푸시:"
echo "  ${CLI} push ${IMAGE}"
echo "(폐쇄망: 내부 레지스트리로 tag/push. DEPLOYMENT_LLM_LLAMACPP_IMAGE 와 정합 유지)"
