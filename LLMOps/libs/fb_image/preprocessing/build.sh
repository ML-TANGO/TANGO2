#!/bin/bash
# 빌트인 전처리 공용 실행 이미지(lean 베이스) 빌드 + docker.io/acrylaaai 게시.
#
# 사전: docker.io(acrylaaai push 권한) 로그인 필요. 이 호스트는 docker 소켓이 root 소유라
#       `sudo docker` 로 실행한다(root 에 acrylaaai 로그인 되어 있음).
# 사용: ./build.sh [TAG]        (기본 TAG=tango_v2.4.0)
# context = 이 디렉토리(스크립트만 있으므로 repo 루트 불요; requirements.txt 만 COPY).
#
# 게시 후 정합: apps/fb_utils/settings.py 의 JF_DEFAULT_UBUNTU_22_IMAGE 태그를 맞추고
#   fb_image 앱 재시작 → init.set_default_image 가 DB image.real_name 을 재seed.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

REGISTRY="docker.io/acrylaaai"
IMAGE="genai-platform-builtin-preprocess"
TAG="${1:-tango_v2.4.0}"
FULL="$REGISTRY/$IMAGE:$TAG"

echo "[build] $FULL (-f $SCRIPT_DIR/Dockerfile, context=$SCRIPT_DIR)"
sudo docker build --no-cache -t "$FULL" -f "$SCRIPT_DIR/Dockerfile" "$SCRIPT_DIR"

echo "[push] $FULL"
sudo docker push "$FULL"

echo "[done] $FULL"
