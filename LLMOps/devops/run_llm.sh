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

# ================================================
cd $BASE_DIR
if [ "$MODE" == "true" ]; then
    helm dependency update llm_model/helm
    helm dependency update llm_playground/helm
    kubectl create ns jonathan-system-image 2> /dev/null

    helm install -n $NAMESPACE model llm_model/helm      --values $VALUES
    helm install -n $NAMESPACE playground llm_playground/helm       --values $VALUES

elif [ "$MODE" == "false" ]; then
    helm uninstall -n $NAMESPACE model
    helm uninstall -n $NAMESPACE playground

elif [ "$MODE" == "upgrade" ]; then
    helm dependency update llm_model/helm
    helm dependency update llm_playground/helm

    helm upgrade -n $NAMESPACE model llm_model/helm        --values $VALUES
    helm upgrade -n $NAMESPACE playground llm_playground/helm --values $VALUES

elif [ "$MODE" == "update" ]; then
    helm dependency update llm_model/helm   
    helm dependency update llm_playground/helm
fi
