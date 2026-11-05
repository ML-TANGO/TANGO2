#!/bin/bash
set -e
# 멀티엔진 서빙 Phase 3 (Tier B) — TGI 서빙 이미지 빌드.
# 결과 태그는 settings.py:DEPLOYMENT_LLM_TGI_IMAGE 와 정합해야 함.
#   (배포 시 service.py 가 {DOCKER_REGISTRY_URL} 을 앞에 붙여 pod.image 로 전달)
# 참조 recipe: libs/fb_image/llm_llamacpp/build.sh — 동일한 nerdctl/docker + registry 관례.
# ⚠️ 베이스 이미지(~10GB+)라 빌드/푸시 시간·용량 큼. 빌드 호스트는 인터넷(ghcr pull) 필요.
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

IMAGE="acrylaaai/llm_deployment_tgi:dev"
CLI="${CLI:-nerdctl}"   # docker 로 쓰려면 CLI=docker ./build.sh

echo "== Building ${IMAGE} with ${CLI} =="
${CLI} build -t "${IMAGE}" "${BASE_DIR}"

echo ""
echo "빌드 완료. 푸시:"
echo "  ${CLI} push ${IMAGE}"
echo "(docker.io/acrylaaai 로 push → 클러스터 pull. DEPLOYMENT_LLM_TGI_IMAGE 와 정합 유지)"
