#!/bin/bash

# 새로운 비밀번호를 입력으로 받습니다.
if [ -z "$1" ]; then
  echo "Usage: $0 <new_root_password>"
  exit 1
fi

NEW_PASSWORD=$1

NODES="$JF_HOME/.config/nodes-$JF_POD_NAME"

mkdir -p "$JF_HOME/.config"

if [ -z "$JF_RDMA_ENABLED" ] || [ "$JF_RDMA_ENABLED" = "false" ]; then
  IFACE="eth0"
else
  IFACE="net1" 
fi

POD_IP=$(ip -o -4 addr list "$IFACE" | awk '{print $4}' | cut -d/ -f1)

if [ -z "$JF_NUM_GPUS" ]; then
  if command -v nvidia-smi &> /dev/null; then
    JF_NUM_GPUS=$(nvidia-smi --list-gpus | wc -l)
  else
    JF_NUM_GPUS=0
  fi
fi

# Check if the NODES file exists
if [ ! -f "$NODES" ]; then
  # Write nodes file (for ssh)
  (
    flock -x 201  # lock file
    echo "$POD_IP $NEW_PASSWORD $JF_POD_INDEX" >> "$NODES"
  ) 201>>"$NODES"
fi

# root 계정의 비밀번호를 변경합니다.
echo "root:${NEW_PASSWORD}" | chpasswd
if [ $? -ne 0 ]; then
  echo "Failed to change root password."
  exit 1
fi
echo "Root password changed successfully."

# SSH 설정 파일을 백업합니다.
SSH_CONFIG="/etc/ssh/sshd_config"
BACKUP_SSH_CONFIG="/etc/ssh/sshd_config.bak"
if [ ! -f "${BACKUP_SSH_CONFIG}" ]; then
  cp "${SSH_CONFIG}" "${BACKUP_SSH_CONFIG}"
  echo "Backup of SSH config file created at ${BACKUP_SSH_CONFIG}."
fi

# SSH 설정 파일에서 PermitRootLogin 값을 yes로 변경합니다.
sed -i "s/#PermitRootLogin prohibit-password/PermitRootLogin yes/" "${SSH_CONFIG}"

# SSH 서비스를 다시 시작합니다.
service ssh restart
if [ $? -ne 0 ]; then
  echo "Failed to restart SSH service."
  exit 1
fi

echo "SSH service restarted successfully."

echo "Script completed. Root login is now enabled via SSH."
