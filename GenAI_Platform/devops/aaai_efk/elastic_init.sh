#!/bin/bash

# 네임스페이스 설정
NAMESPACE="jonathan-efk"

# ConfigMap 생성
echo "Creating ConfigMap..."
kubectl delete configmap elasticsearch-config-script -n $NAMESPACE
kubectl create configmap elasticsearch-config-script --from-file=elasticsearch_config.sh=./elastic_init/setup_elastic.sh -n $NAMESPACE

# ConfigMap 생성 확인
if [ $? -ne 0 ]; then
    echo "Failed to create ConfigMap. Exiting."
    exit 1
fi

echo "ConfigMap created successfully."

# Job 적용
echo "Applying Elasticsearch config job..."
kubectl delete -f ./elastic_init/setup-job.yaml -n $NAMESPACE
kubectl apply -f ./elastic_init/setup-job.yaml -n $NAMESPACE

# Job 적용 확인
if [ $? -ne 0 ]; then
    echo "Failed to apply Job. Exiting."
    exit 1
fi

echo "Job applied successfully."

# Job 완료 대기
echo "Waiting for job to complete..."
kubectl wait --for=condition=complete job/elasticsearch-config-job -n $NAMESPACE --timeout=300s

if [ $? -ne 0 ]; then
    echo "Job did not complete successfully. Check the logs for more information."
    kubectl logs job/elasticsearch-config-job -n $NAMESPACE
    exit 1
fi

echo "Elasticsearch configuration job completed successfully."

# Job 로그 출력 (선택적)
echo "Job logs:"
kubectl logs job/elasticsearch-config-job -n $NAMESPACE

echo "Elasticsearch configuration process completed."