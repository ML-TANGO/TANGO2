#!/usr/bin/env bash
# 플랫폼(Jonathan)에 노출되는 GPU 집합을 토글한다.
#
# 원리: 이 플랫폼은 k8s device-plugin 의 nvidia.com/gpu 카운트를 쓰지 않고,
#   fb_scheduler 가 자체 인벤토리(dcgm-exporter → Prometheus → fb_monitoring → Redis
#   resource:gpu_info)에서 GPU 를 골라 워크로드 pod 에 NVIDIA_VISIBLE_DEVICES=<UUID> 로 핀한다.
#   따라서 "플랫폼이 보는 GPU" = "dcgm-exporter 가 export 하는 GPU" 이다.
#   dcgm-exporter 는 privileged 라 NVIDIA_VISIBLE_DEVICES 로는 못 줄이지만,
#   앱 레벨 --devices (env DCGM_EXPORTER_DEVICES_STR) 로 export 대상을 제한할 수 있다.
#
# 사용법:
#   ./set-visible-gpus.sh all        # 모든 GPU 노출 (DCGM_EXPORTER_DEVICES_STR=f)
#   ./set-visible-gpus.sh g:4,5      # GPU 인덱스 4,5 만 노출
#   ./set-visible-gpus.sh g:4,5,6,7  # 인덱스 4~7 만 노출
#   (형식은 dcgm-exporter -d 규칙: g=all, g:0,1=GPU 0·1. 인덱스 기준 — nvidia-smi -L 로 확인)
#
# 반영까지: dcgm 재시작(수초) → fb_monitoring 다음 주기(≤수십초)에 Redis 갱신 → 플랫폼 반영.
set -euo pipefail

ARG="${1:-}"
if [ -z "$ARG" ]; then
  echo "Usage: $0 <all | g:IDX[,IDX...]>   (예: g:4,5)"
  echo "현재 dcgm 이 export 하는 GPU 인덱스는 nvidia-smi -L 로 확인"
  exit 1
fi
[ "$ARG" = "all" ] && VAL="f" || VAL="$ARG"

NS=gpu-operator
CP=cluster-policy

# dcgmExporter.env 에 DCGM_EXPORTER_DEVICES_STR 설정 (기존 env 보존, 무효한 NVIDIA_VISIBLE_DEVICES 는 제거)
PATCH=$(kubectl get clusterpolicy "$CP" -o json | VAL="$VAL" python3 -c '
import sys, json, os
d = json.load(sys.stdin)
val = os.environ["VAL"]
env = d["spec"].get("dcgmExporter", {}).get("env", [])
env = [e for e in env if e.get("name") not in ("DCGM_EXPORTER_DEVICES_STR", "NVIDIA_VISIBLE_DEVICES")]
env.append({"name": "DCGM_EXPORTER_DEVICES_STR", "value": val})
print(json.dumps({"spec": {"dcgmExporter": {"env": env}}}))
')
kubectl patch clusterpolicy "$CP" --type=merge -p "$PATCH" >/dev/null
echo "[set-visible-gpus] dcgmExporter DCGM_EXPORTER_DEVICES_STR=${VAL}"

kubectl rollout restart ds/nvidia-dcgm-exporter -n "$NS" >/dev/null 2>&1 || true
kubectl rollout status  ds/nvidia-dcgm-exporter -n "$NS" --timeout=120s >/dev/null 2>&1 || true
echo "[set-visible-gpus] dcgm 재시작 완료. fb_monitoring 다음 주기에 플랫폼 인벤토리가 갱신됩니다."
