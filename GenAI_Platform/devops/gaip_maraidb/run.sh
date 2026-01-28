#!/bin/bash
set -e

SCRIPT=$(readlink -m $(type -p $0))
BASE_DIR=$(dirname ${SCRIPT})

MODE="help"
NAMESPACE=jonathan-mariadb

NAME="mariadb-galera"
DIRECTORY="mariadb-galera"

INIT_NAME="mariadb-init"
INIT_DIRECTORY="mariadb-init"

VALUES=""

# ================================================
help() {
    echo 
    echo "[MARIADB DEV RUN SCRIPT]"
    echo "  ./run.sh install :      helm dev 실행"
    echo "  ./run.sh init -f 파일명:      DB 초기화"
    echo "  ./run.sh initun :      DB 초기화 삭제"
    echo "  ./run.sh uninstall(un) --name [NAME]:     helm dev 삭제"
    echo "  ./run.sh reinstall(re) --name [NAME]:     helm dev 재설치"
    echo "  ./run.sh upgrade(up) --name [NAME]:     helm dev 업그레이드"
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
    re|reinstall)
      MODE="reinstall"
      ;;
    up|upgrade)
      MODE="upgrade"
      ;;
    init)
      MODE="init"
      ;;
    initun)
      MODE="initun"
      ;;
    backup)
      MODE="backup"  # TODO
      ;;  
    --values|-f)
      VALUES="$2"
      shift
      ;;
    --help|-h|*)
      MODE="help"
      exit 1
      ;;
  esac
  shift
done

# ================================================
# RUN
# ================================================

cd $BASE_DIR
if [ "$MODE" == "install" ]; then
  echo helm install -n $NAMESPACE $NAME $DIRECTORY --create-namespace
  helm install -n $NAMESPACE $NAME $DIRECTORY --create-namespace
elif [ "$MODE" == "uninstall" ]; then
  helm uninstall -n $NAMESPACE $NAME
elif [ "$MODE" == "init" ]; then
  if [ -z "$VALUES" ]; then
    echo "./run.sh -f VALUES 파일이름"
    exit 1
  fi
  helm uninstall -n $NAMESPACE $INIT_NAME 2>/dev/null || true
  helm install -n $NAMESPACE $INIT_NAME $INIT_DIRECTORY -f $VALUES
elif [ "$MODE" == "initun" ]; then
  helm uninstall -n $NAMESPACE $INIT_NAME
elif [ "$MODE" == "upgrade" ]; then
  helm upgrade -n $NAMESPACE $NAME $DIRECTORY
elif [ "$MODE" == "help" ]; then
  help
fi
