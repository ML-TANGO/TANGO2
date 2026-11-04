#!/bin/bash
# Built-in 전처리 공용 베이스 이미지 빌드 + docker.io/acrylaaai 게시.
#
# 사전: `docker login`(docker.io, acrylaaai push 권한) 필요.
# 사용: ./build_builtin_preprocess.sh [TAG]   (기본 TAG=tango_v2.0.1)
#
# 게시 후 DB/설정 정합(둘 중 하나):
#   - 내구: apps/fb_utils/settings.py 의 JF_DEFAULT_UBUNTU_22_IMAGE 를 이 이미지로
#           (init.py set_default_image 이 DB image real_name 재seed)
#   - 즉시: msa_jfb.image 의 해당 row real_name 을 이 이미지로 UPDATE
set -e
REGISTRY="docker.io/acrylaaai"
IMAGE="genai-platform-builtin-preprocess"
TAG="${1:-tango_v2.0.1}"
cd "$(dirname "$0")"

echo "[build] $REGISTRY/$IMAGE:$TAG (-f Builtin_Preprocess)"
docker build --no-cache -t "$REGISTRY/$IMAGE:$TAG" -f Builtin_Preprocess .

echo "[push] $REGISTRY/$IMAGE:$TAG"
docker push "$REGISTRY/$IMAGE:$TAG"

echo "[done] $REGISTRY/$IMAGE:$TAG"
