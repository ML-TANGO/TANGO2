#!/bin/bash
set -e

SCRIPT=$(readlink -m $(type -p $0))
BASE_DIR=$(dirname ${SCRIPT})

NAMESPACE="jonathan-mongodb"
NAME="mongodb"
MODE="help"

# ================================================
help() {
    echo 
    echo "[MONGODB DEV RUN SCRIPT]"
    echo "  ./run.sh install :      helm dev 실행"
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
    --help|-h|*)
      MODE="help"
      ;;
  esac
  shift
done

# ================================================
# RUN
# ================================================

cd $BASE_DIR
if [ "$MODE" == "install" ]; then

  echo "#################################"
  echo "Start Installing Mongodb..."
  echo "#################################"
  cd $BASE_DIR
  echo helm install -n $NAMESPACE --create-namespace "$NAME" $NAME/
  helm install -n $NAMESPACE --create-namespace "$NAME" $NAME/

elif [ "$MODE" == "uninstall" ]; then

  echo "#################################"
  echo "Start Uninstalling Mongodb..."
  echo "#################################"
  cd $BASE_DIR
  helm uninstall -n $NAMESPACE "$NAME"

elif [ "$MODE" == "upgrade" ]; then

  echo "#################################"
  echo "Start Upgrading Mongodb..."
  echo "#################################"
  cd $BASE_DIR
  MONGODB_PASSWORD=$(kubectl get secret --namespace $NAMESPACE $NAME -o jsonpath="{.data.mongodb-password}" | base64 -d)
  helm upgrade -n $NAMESPACE "$NAME" $NAME/ --set password=$MONGODB_PASSWORD

elif [ "$MODE" == "help" ]; then
  help
fi



