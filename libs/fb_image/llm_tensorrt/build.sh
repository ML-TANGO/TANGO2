#!/bin/bash
set -e
# 멀티엔진 서빙 Phase 3 (Tier B) — TensorRT-LLM 서빙 이미지 빌드.
# 결과 태그는 settings.py:DEPLOYMENT_LLM_TENSORRT_IMAGE 와 정합해야 함.
#   (배포 시 service.py 가 {DOCKER_REGISTRY_URL} 을 앞에 붙여 pod.image 로 전달)
# 참조 recipe: libs/fb_image/llm_triton/build.sh — 동일한 nerdctl/docker + registry 관례.
# ⚠️ 베이스 이미지(~25-30GB, nvcr.io tritonserver trtllm) 때문에 빌드/push 시간·용량 매우 큼. 빌드 호스트 인터넷 필요.
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

IMAGE="acrylaaai/llm_deployment_tensorrt:dev"
CLI="${CLI:-nerdctl}"   # docker 로 쓰려면 CLI=docker ./build.sh

echo "== Building ${IMAGE} with ${CLI} =="
${CLI} build -t "${IMAGE}" "${BASE_DIR}"

echo ""
echo "빌드 완료. 푸시:"
echo "  ${CLI} push ${IMAGE}"
echo "(docker.io/acrylaaai 로 push → 클러스터 pull. DEPLOYMENT_LLM_TENSORRT_IMAGE 와 정합 유지)"
