#!/bin/bash

SCRIPT=$( readlink -m $( type -p $0 ))
BASE_DIR=`dirname ${SCRIPT}`

MODE=true # default
NAMESPACE="jonathan-system"

while [[ $# -gt 0 ]]; do
  key="$1"

  case $key in
    install)
      MODE=true
      ;;
    upg|upgrade)
      MODE="upgrade"
      ;;
    upd|upgrade)
      MODE="update"
      ;;
    un|uninstall)
      MODE=false
      ;;
    --values|-f)
      VALUES="$2"
      shift
      ;;
    --name|-name|-n|--n)
      NAME="$2"
      shift # 인수 하나를 처리했으므로 다음 인수로 이동
      ;;
    --help|-h|*)
      echo "error: $1"
      help
      exit 1
      ;;
  esac
  shift # 처리한 인수를 제거
done

# ================================================
if [ -z "$VALUES" ]; then
  echo "스크립트 VALUES를 설정해주세요."
  exit 1
fi

if [ -z "$NAMESPACE" ]; then
  echo "스크립트 NAMESPACE를 설정해주세요."
  exit 1
fi

if [ ! -e "$BASE_DIR/fb_common_app/helm/file/kube/config" ]; then
  echo "COPY kube config file"
  echo "cp ~/.kube/config $BASE_DIR/fb_common_app/helm/file/kube/config"
  exit 1
fi

CHARTS=(
    "common_app" "dashboard" "dataset" "deployment" "front" "image" "monitoring" "notification"
    "option" "resource" "scheduler"
    "user" "workspace" "alert_management" "ingress_management"
)

# ================================================
cd $BASE_DIR
if [ "$MODE" == "true" ]; then
  # kubectl create ns {NAMESPACE}-image
  kubectl create ns jonathan-system-image 2> /dev/null

  for chart in "${CHARTS[@]}"; do
    printf '%*s\n' `tput cols` '' | tr ' ' '-'

    if [ "$chart" == "monitoring" ]; then
      helm dependency update fb_${chart}/helm
      helm install -n $NAMESPACE monitoring-app fb_${chart}/helm --values ${VALUES}
      continue
    fi

    COMMAND="helm dependency update fb_${chart}/helm"
    echo $COMMAND # 출력
    $COMMAND      # 실행

    echo 
    COMMAND="helm install -n $NAMESPACE ${chart//_/-} fb_${chart}/helm --values ${VALUES}"
    echo $COMMAND # 출력
    $COMMAND      # 실행
  done

elif [ "$MODE" == "false" ]; then
  for chart in "${CHARTS[@]}"; do
    printf '%*s\n' `tput cols` '' | tr ' ' '-'

    if [ "$chart" == "monitoring" ]; then
      helm uninstall -n $NAMESPACE monitoring-app 
      continue
    fi

    COMMAND="helm uninstall -n ${NAMESPACE} ${chart//_/-}"
    echo $COMMAND # 출력
    $COMMAND      # 실행
  done

elif [ "$MODE" == "upgrade" ]; then
  for chart in "${CHARTS[@]}"; do
    printf '%*s\n' `tput cols` '' | tr ' ' '-'

    if [ "$chart" == "monitoring" ]; then
      helm dependency update fb_${chart}/helm
      helm upgrade -n $NAMESPACE monitoring-app fb_${chart}/helm --values ${VALUES}
      continue
    fi

    COMMAND="helm dependency update fb_${chart}/helm"
    echo $COMMAND # 출력
    $COMMAND      # 실행

    echo 
    COMMAND="helm upgrade -n $NAMESPACE ${chart//_/-} fb_${chart}/helm --values ${VALUES}"
    echo $COMMAND # 출력
    $COMMAND      # 실행
  done
elif [ "$MODE" == "update" ]; then
  for chart in "${CHARTS[@]}"; do
    printf '%*s\n' `tput cols` '' | tr ' ' '-'
    COMMAND="helm dependency update fb_${chart}/helm"
    echo $COMMAND # 출력
    $COMMAND      # 실행
  done
fi
