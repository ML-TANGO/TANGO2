#!/bin/bash
set -e

SCRIPT=$(readlink -m $(type -p $0))
BASE_DIR=$(dirname ${SCRIPT})

# source /etc/jfb/func.sh $BASE_DIR
NAMESPACE=jonathan-redis
# source /etc/jfb/$NAMESPACE/parser.sh

KUBER_IS_MUITI_NODE=${KUBER_IS_MUITI_NODE:-false}

# if [ "$KUBER_IS_MUITI_NODE" == "true" ]; then
#     NAME="redis-cluster"
# else
#     NAME="redis"
# fi
NAME="redis-cluster"
help() {
    echo 
    echo "[REDIS DEV RUN SCRIPT]"
    echo "  ./run.sh install :      helm dev 실행"
    echo "  ./run.sh uninstall(un) --name [NAME]:     helm dev 삭제"
    echo "  ./run.sh reinstall(re) --name [NAME]:     helm dev 재설치"
    echo "  ./run.sh upgrade(up) --name [NAME]:     helm dev 업그레이드"
}

MODE="help"

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

install(){
    echo "#################################"
    echo "Start Installing Redis..."
    echo "#################################"
    cd $BASE_DIR
    helm install -n $NAMESPACE --create-namespace "$NAME" $NAME/
}

uninstall(){
    echo "#################################"
    echo "Start Uninstalling Redis..."
    echo "#################################"
    cd $BASE_DIR
    helm uninstall -n $NAMESPACE "$NAME"
}

case $MODE in
  install)
    install
    ;;
  uninstall)
    uninstall
    ;;
  reinstall)
    if helm list -n $NAMESPACE | grep -q "$NAME"; then
        echo "Resource found in namespace [$NAMESPACE]."
        sleep 2
        uninstall
    else
        echo "Resource not found in namespace [$NAMESPACE]. Skip deleting process..."
        sleep 2
    fi
    install
    ;;
  upgrade)
    echo "#################################"
    echo "Start Upgrading Redis..."
    echo "#################################"
    cd $BASE_DIR
    REDIS_PASSWORD=$(kubectl get secret --namespace $NAMESPACE $NAME -o jsonpath="{.data.redis-password}" | base64 -d)
    helm upgrade -n $NAMESPACE "$NAME" $NAME/ --set password=$REDIS_PASSWORD
    ;;
  help)
    help
    ;;
  *)
    help
    ;;
esac
