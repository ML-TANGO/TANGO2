#!/bin/bash
# 잡 컨테이너의 필수 패키지 확인·설치.
#
# 이 스크립트는 **모든 잡이 기동할 때마다** 실행된다. 여기서 쓰는 시간이 노드 실행
# 하나하나에 그대로 얹히므로, 실제 계산이 초 단위인 노드도 기동 대기가 대부분을 차지한다
# (전처리 잡 실측: 컨테이너 실행 135초 중 계산은 수 초).
#
# 그래서 두 가지를 지킨다.
#   1. 빠진 것이 없으면 apt 를 아예 부르지 않는다 — `apt update` 까지 건너뛴다.
#      (예전에는 무조건 apt update 를 먼저 돌렸다.)
#   2. 설치는 한 번에 몰아서 한다. 패키지마다 apt install 을 부르면 그 횟수만큼
#      dpkg 트리거·의존성 해석이 반복된다(9개면 9번).

packages=(sudo openssh-client openssh-server net-tools iproute2 python3-pip curl git wget)

missing=()
for package in "${packages[@]}"; do
    if ! dpkg -s "$package" > /dev/null 2>&1; then
        missing+=("$package")
    fi
done

if [ ${#missing[@]} -eq 0 ]; then
    echo "필수 패키지가 모두 설치되어 있습니다 — 설치를 건너뜁니다"
    exit 0
fi

echo "빠진 패키지 ${#missing[@]}개 설치: ${missing[*]}"
export DEBIAN_FRONTEND=noninteractive
apt update
apt install -y "${missing[@]}"
