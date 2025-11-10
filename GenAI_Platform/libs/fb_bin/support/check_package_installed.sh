#!/bin/bash

apt update
echo "패키지 버전 확인 및 설치"

# 설치할 패키지 목록
packages=("sudo" "openssh-client" "openssh-server" "net-tools" "iproute2" "python3-pip" "curl" "git" "wget")

# 각 패키지에 대해 설치 여부 확인 및 설치
for package in "${packages[@]}"; do
    if ! dpkg -s "$package" > /dev/null 2>&1; then
        echo "$package 설치"
        apt install -y "$package"
    fi
done