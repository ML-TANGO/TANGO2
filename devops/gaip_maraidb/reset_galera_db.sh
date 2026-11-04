#!/bin/bash

# 네임스페이스 고정 설정
NAMESPACE="jonathan-mariadb"

# PVC 목록 조회 ('data-mariadb-galera-'로 시작하는 것만 필터링)
PVC_LIST=$(kubectl get pvc -n $NAMESPACE -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep '^data-mariadb-galera-')

# PVC가 없을 경우 스크립트 종료
if [ -z "$PVC_LIST" ]; then
    echo "PVC를 찾을 수 없습니다. 클러스터가 생성되지 않은 것으로 보입니다. 스크립트를 종료합니다."
    exit 1
fi

# safe_to_bootstrap 값이 1인 노드를 추적할 변수 초기화
SAFE_NODE=""
MAX_SEQNO=-1
MAX_SEQNO_NODE=""

echo "PVC 목록 확인 중..."

for PVC_NAME in $PVC_LIST; do
    # 현재 PVC의 Galera 인덱스 추출
    INDEX=$(echo $PVC_NAME | awk -F'-' '{print $NF}')
    
    echo "Checking PVC: $PVC_NAME (Galera Index: $INDEX)"

    # 임시 Pod를 생성하여 grastate.dat 파일 내용 가져오기
    OUTPUT=$(kubectl run -i --rm --tty volpod --overrides="$(cat <<EOF
{
    "apiVersion": "v1",
    "kind": "Pod",
    "metadata": {
        "name": "volpod-$PVC_NAME"
    },
    "spec": {
        "containers": [{
            "command": [
                "cat",
                "/mnt/data/grastate.dat"
            ],
            "image": "bitnami/minideb",
            "name": "mycontainer",
            "volumeMounts": [{
                "mountPath": "/mnt",
                "name": "galeradata"
            }]
        }],
        "restartPolicy": "Never",
        "volumes": [{
            "name": "galeradata",
            "persistentVolumeClaim": {
                "claimName": "$PVC_NAME"
            }
        }]
    }
}
EOF
)" --image="bitnami/minideb" -n $NAMESPACE --quiet)

    # safe_to_bootstrap 값과 seqno 값 추출
    SAFE_TO_BOOTSTRAP=$(echo "$OUTPUT" | grep "safe_to_bootstrap" | awk -F': ' '{print $2}' | tr -d '[:space:]')
    SEQNO=$(echo "$OUTPUT" | grep "seqno" | awk -F': ' '{print $2}' | tr -d '[:space:]')

    # safe_to_bootstrap 값이 1이면 해당 인덱스를 SAFE_NODE로 저장하고 루프 종료
    if [ -n "$SAFE_TO_BOOTSTRAP" ] && [ "$SAFE_TO_BOOTSTRAP" == "1" ]; then
        SAFE_NODE=$INDEX
        break
    fi

    # 모든 safe_to_bootstrap 값이 0일 경우 seqno 값이 가장 높은 인덱스를 찾음
    if [ "$SEQNO" -gt "$MAX_SEQNO" ]; then
        MAX_SEQNO=$SEQNO
        MAX_SEQNO_NODE=$INDEX
    fi

    echo "$OUTPUT" 
    echo "----------------------------------------"
done

# safe_to_bootstrap이 1인 노드가 있으면 helm 명령을 실행하고, 없으면 seqno가 가장 높은 노드로 helm 명령을 실행
if [ -n "$SAFE_NODE" ]; then
    echo "safe_to_bootstrap 값이 1인 Galera 인덱스: $SAFE_NODE"
    helm install -n $NAMESPACE mariadb-galera mariadb-galera --create-namespace \
        --set galera.bootstrap.forceBootstrap=true \
        --set galera.bootstrap.bootstrapFromNode=$SAFE_NODE \
        --set podManagementPolicy=Parallel
else
    echo "모든 safe_to_bootstrap 값이 0입니다. seqno가 가장 높은 Galera 인덱스: $MAX_SEQNO_NODE (seqno: $MAX_SEQNO)"
    helm install -n $NAMESPACE mariadb-galera mariadb-galera --create-namespace \
        --set galera.bootstrap.forceBootstrap=true \
        --set galera.bootstrap.bootstrapFromNode=$MAX_SEQNO_NODE \
        --set galera.bootstrap.forceSafeToBootstrap=true \
        --set podManagementPolicy=Parallel
fi


echo "클러스터가 생성된 후 모든 노드 준비 상태 확인 중..."
kubectl wait --namespace $NAMESPACE \
  --for=condition=Ready pod \
  -l app.kubernetes.io/instance=mariadb-galera --timeout=300s

#echo "인스턴스 간 충분한 연결 시간 확보"
#sleep 60

#echo "모든 노드가 준비되었습니다. 업그레이드를 수행합니다..."
#helm upgrade -n $NAMESPACE mariadb-galera mariadb-galera \
#    --set podManagementPolicy=Parallel
