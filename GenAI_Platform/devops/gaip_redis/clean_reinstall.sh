#!/bin/bash
# PVC/PV 완전 삭제 후 재설치 (AOF 오류 등에서 깨끗한 볼륨으로 재시작)
set -e

SCRIPT=$(readlink -m $(type -p $0))
BASE_DIR=$(dirname ${SCRIPT})
NAMESPACE=jonathan-redis
NAME=redis-cluster

# AOF 끄고 설치할지 (yes=끔, no=켜둠)
DISABLE_AOF="${DISABLE_AOF:-no}"

echo "=============================================="
echo " Redis 완전 삭제 후 재설치 (PVC/PV 포함)"
echo "=============================================="
echo " NAMESPACE=$NAMESPACE  RELEASE=$NAME"
echo " AOF 비활성화로 설치: DISABLE_AOF=$DISABLE_AOF (깨끗이 안 되면 DISABLE_AOF=yes 로 실행)"
echo ""

# 1) Helm uninstall
if helm list -n "$NAMESPACE" 2>/dev/null | grep -q "$NAME"; then
  echo "[1/5] Helm uninstall..."
  helm uninstall -n "$NAMESPACE" "$NAME" || true
  sleep 3
else
  echo "[1/5] Helm release 없음, 스킵."
fi

# 2) StatefulSet 직접 삭제 (혹시 남아 있으면)
if kubectl get statefulset -n "$NAMESPACE" "$NAME" 2>/dev/null; then
  echo "[2/5] StatefulSet 삭제..."
  kubectl delete statefulset -n "$NAMESPACE" "$NAME" --cascade=orphan || true
  sleep 2
else
  echo "[2/5] StatefulSet 없음, 스킵."
fi

# 3) Pod 삭제 (이름이 redis-cluster-0 등인 경우)
kubectl delete pod -n "$NAMESPACE" -l "app.kubernetes.io/name=redis-cluster" --force --grace-period=0 2>/dev/null || true
sleep 2

# 4) PVC 삭제 (redis-data-redis-cluster-*)
echo "[3/5] PVC 삭제..."
for pvc in $(kubectl get pvc -n "$NAMESPACE" -o name 2>/dev/null | grep redis-data); do
  echo "  삭제: $pvc"
  kubectl delete -n "$NAMESPACE" "$pvc" --wait=false || true
done
# 이름으로 직접 삭제
kubectl delete pvc -n "$NAMESPACE" -l "app.kubernetes.io/instance=$NAME" --ignore-not-found=true --wait=false 2>/dev/null || true
for i in 0 1 2 3 4 5 6 7 8 9; do
  kubectl delete pvc -n "$NAMESPACE" "redis-data-${NAME}-${i}" --ignore-not-found=true --wait=false 2>/dev/null || true
done

echo "  PVC 삭제 완료 대기 (최대 60초)..."
for _ in $(seq 1 60); do
  cnt=$(kubectl get pvc -n "$NAMESPACE" 2>/dev/null | grep -c "redis-data" || true)
  [ "$cnt" -eq 0 ] && break
  sleep 1
done

# 5) Released PV 정리 (선택)
echo "[4/5] Released 상태 PV 확인..."
released=$(kubectl get pv 2>/dev/null | grep "Released" | grep -c "jonathan-redis" || true)
if [ "${released}" -gt 0 ]; then
  echo "  Released PV가 있습니다. 삭제하려면:"
  kubectl get pv | grep Released
  echo "  예: kubectl delete pv <pv-name>"
fi

echo "[5/5] 재설치..."
cd "$BASE_DIR"
if [ "$DISABLE_AOF" = "yes" ]; then
  echo "  (AOF 비활성화 옵션으로 설치)"
  helm install -n "$NAMESPACE" --create-namespace "$NAME" "$NAME"/ --set redis.useAOFPersistence=no
else
  helm install -n "$NAMESPACE" --create-namespace "$NAME" "$NAME"/
fi

echo ""
echo "설치 완료. Pod 기동 확인: kubectl get pods -n $NAMESPACE -w"
echo "여전히 AOF 오류가 나면 다음으로 다시 시도: DISABLE_AOF=yes $0"
echo ""
