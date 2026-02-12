#!/bin/bash
# Helm chart 빌드 전, common app을 준비하는 코드
# commonlib를 불러오기 위한 dependency build 및 kube 코드 복제를 수행

cd ./helm
mkdir -p "${HELM_CHART_DIR}/file"
echo "Copy ${CONFIGURATION_DIR}/${DEPLOY_TARGET}/kube to ${HELM_CHART_DIR}/file/"
cp -r "${CONFIGURATION_DIR}/${DEPLOY_TARGET}/kube" "${HELM_CHART_DIR}/file/"
helm dependency build
cd ..
