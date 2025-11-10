#!/bin/bash
# set -e -x
#sudo -v # Get sudo permission

SCRIPT=$( readlink -m $( type -p $0 ))
BASE_DIR=`dirname ${SCRIPT}`

NAMESPACE="jonathan-kafka"
NAME='kafka'
MODE="install" # default
VALUES="values.yaml"

# ================================================
help() {
    echo 
    echo "[kafka DEV RUN SCRIPT]"
    echo "  ./run.sh install :      helm dev 실행"
    echo "  ./run.sh uninstall(un) --name [NAME]:     helm dev 삭제"
    echo "  ./run.sh reinstall(re) --name [NAME]:     helm dev 재설치"
    echo "  ./run.sh upgrade(up)   --name [NAME]:     helm dev 업그레이드"
}

while [[ $# -gt 0 ]]; do
  key="$1"

  case $key in
    install)
      MODE="install"
      ;;
    un|uninstall)
      MODE="uninstall"
      ;;
    up|upgrade)
      MODE="upgrade"
      ;;
    --help|-h|*)
      help
      exit 1
      ;;
  esac
  shift # 처리한 인수를 제거
done

# ================================================
# RUN
# ================================================

cd $BASE_DIR
if [ "$MODE" == "install" ]; then
  echo helm install -n $NAMESPACE $NAME . --values $VALUES --create-namespace
  helm install -n $NAMESPACE $NAME . --values $VALUES --create-namespace
elif [ "$MODE" == "uninstall" ]; then
  helm uninstall -n $NAMESPACE $NAME
elif [ "$MODE" == "upgrade" ]; then
  helm upgrade -n $NAMESPACE $NAME . --values $VALUES
fi

