#!/bin/bash

# 설정할 로컬 레지스트리 주소
REGISTRY_HOST="" # vip 적용
REGISTRY_PORT="30500"
CONFIG_FILE="/etc/containerd/config.toml"

# 백업 파일 생성
cp $CONFIG_FILE ${CONFIG_FILE}.backup

echo "Updating containerd config to add local registry: $REGISTRY_HOST:$REGISTRY_PORT"

# config.toml 수정하여 로컬 레지스트리 추가
sed -i "/\[plugins.\"io.containerd.grpc.v1.cri\".registry.mirrors\]/a \\
        [plugins.\"io.containerd.grpc.v1.cri\".registry.mirrors.\"$REGISTRY_HOST:$REGISTRY_PORT\"]\n          endpoint = [\"http://$REGISTRY_HOST:$REGISTRY_PORT\"]" $CONFIG_FILE

# containerd 재시작
systemctl daemon-reload
systemctl restart containerd

echo "containerd restarted successfully with the new registry settings."