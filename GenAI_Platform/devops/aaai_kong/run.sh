#!/bin/bash
# set -e -x
# sudo -v # Get sudo permission

SCRIPT=$( readlink -m $( type -p $0 ))
BASE_DIR=`dirname ${SCRIPT}`

VALUES=""
MODE="install" # default
NAME='kong'

# ================================================
help() {
  printf \
"[FLIGHTBASE KONG RUN SCRIPT]

Usage: ./run.sh COMMAND

Options:
  -h, --help        help

Commands:
  NO COMMAND        Install app
  un, uninstall     Uninstall app
"
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
    --values|-f)
      VALUES="$2"
      shift
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
# RUN
# ================================================
### values 파일을 입력받아, 'developer:' 을 namespace로 사용
if [ -z "$VALUES" ]; then
  echo "./run.sh -f VALUES 파일이름"
  exit 1
fi
NAMESPACE=$(grep 'developer:' $VALUES  | awk '{print $2}')

### helm 명령어
cd $BASE_DIR
if [ "$MODE" == "install" ]; then
  echo helm install -n $NAMESPACE $NAME . --values $VALUES --create-namespace
  helm install -n $NAMESPACE $NAME . --values $VALUES --create-namespace
elif [ "$MODE" == "uninstall" ]; then
  helm uninstall -n $NAMESPACE $NAME
  echo "CHECK DELETE volume - pvc, pv, directory"
fi
