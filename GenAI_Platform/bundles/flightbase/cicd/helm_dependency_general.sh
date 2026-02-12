#!/bin/bash
# Helm chart 빌드 전, common app에 대한 dependency load를 수행하는 코드
# commonapps에서 commonlib를 불러오기 위한 dependency build 및 kube 코드 복제를 수행
# 이후 commonapps를 불러오도록 dependency build 수행

# Save the current directory
CURRENT_DIR=$(pwd)

# Copy kube configuration file
mkdir -p "${COMMONAPP_CHART_DIR}/file"
echo "Copy ${CONFIGURATION_DIR}/${DEPLOY_TARGET}/kube to ${COMMONAPP_CHART_DIR}/file/"
cp -r "${CONFIGURATION_DIR}/${DEPLOY_TARGET}/kube" "${COMMONAPP_CHART_DIR}/file/"

# Run helm dependency build for common app
echo "Building commonapp dependency from $CURRENT_DIR..."
cd "${COMMONAPP_CHART_DIR}"
helm dependency build

# Return to the saved current directory
cd "$CURRENT_DIR"

# Go to ./helm and run helm dependency build
echo "Building dependency for $CURRENT_DIR..."
cd ./helm
helm dependency build

# Go back to original directory after operations
cd "$CURRENT_DIR"
