#!/bin/bash
# set -e -x
#sudo -v # Get sudo permission

SCRIPT=$( readlink -m $( type -p $0 ))
BASE_DIR=`dirname ${SCRIPT}`

VALUES=""
MODE="install" # default
NAMESPACE="jonathan-system" # 기본 네임스페이스

# ================================================
help() {
    echo 
    echo "[local-path-provisioner DEV RUN SCRIPT]"
    echo "  ./run.sh install       -f values파일:     helm dev 실행"
    echo "  ./run.sh uninstall(un) -f values파일:     helm dev 삭제"
    echo "  ./run.sh reinstall(re) -f values파일:     helm dev 재설치"
    echo "  ./run.sh upgrade(up)   -f values파일:     helm dev 업그레이드"
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
      help
      exit 1
      ;;
  esac
  shift # 처리한 인수를 제거
done

# ================================================
# RUN
# ================================================
### values 파일을 입력받아, storageClass.name을 사용
if [ -z "$VALUES" ]; then
  echo "./run.sh -f VALUES 파일이름"
  exit 1
fi

# storageClass.name을 읽어오기
SC_NAME=$(grep -A 10 'storageClass:' $VALUES | grep 'name:' | awk '{print $2}')
if [ ! -z "$SC_NAME" ]; then
  NAMESPACE=$SC_NAME
fi

NAME=$NAMESPACE-sc

### helm 명령어
cd $BASE_DIR
if [ "$MODE" == "install" ]; then
  helm install -n $NAMESPACE $NAME . --values $VALUES --create-namespace
elif [ "$MODE" == "uninstall" ]; then
  helm uninstall -n $NAMESPACE $NAME
fi 