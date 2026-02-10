#!/bin/bash
set -e

SCRIPT=$( readlink -m $( type -p $0 ))
BASE_DIR=`dirname ${SCRIPT}`

NAMESPACE=jonathan-system

NAME="monitoring"
MODE=true # default
DCGM="./dcgm"
PROMETHEUS_STACK="./kube-prometheus-stack/"
VALUE_PATH="./value.yaml"
ORIGIN_VALUE_PATH="./value.yaml"

## LOCAL STORAGE USE
LOCAL_STORAGE="false" # true or false
LOCAL_STORAGECLASSNAME="local-storage"
LOCAL_PATH="/jf-storage/system/prometheus_data"
LOCAL_NODEAFFINITY_KEY="node-role"
LOCAL_NODEAFFINITY_VALUE="prometheus"

# ================================================
help() {
    echo 
    echo "[MONITORING OPS RUN SCRIPT]"
    echo "  ./run.sh :      helm dev 실행"
    echo 
    echo "  ./run.sh uninstall(un) --name [NAME]:     helm dev 삭제"
    echo "  ./run.sh reinstall(re) --name [NAME]:     helm dev 재설치"

}
# ================================================

while [[ $# -gt 0 ]]; do
  key="$1"

  case $key in
    install)
      MODE=true
      ;;
    un|uninstall)
      MODE=false
      ;;
    re|reinstall)
      MODE="reinstall"
      ;;
    up|upgrade)
      MODE="upgrade"
      ;;

    --help|-h|*)
      echo "error: $1"
      help
      exit 1
      ;;
  esac
  shift # 처리한 인수를 제거
done

install_all(){
  echo "#################################"
  echo "Start installing Monitoring..."
  echo "#################################"
  #helm install dcgm $DCGM  -n $NAMESPACE

  # DCGM_METRIC_PORT=$(kubectl get ServiceMonitor -A -l app.kubernetes.io/component=dcgm-exporter -o jsonpath='{.items[*].spec.endpoints[*].port}')

  # PORTS=$(kubectl get ServiceMonitor -A -l team=rook -o jsonpath='{range .items[*]}{.spec.endpoints[0].port}{"\n"}{end}')
  # for PORT in $PORTS; do
  #     if [[ "$PORT" == "csi-http-metrics" ]]; then
  #         CSI_METRIC_PORT="$PORT"
  #     elif [[ "$PORT" == "http-metrics" ]]; then
  #         ROOK_CEPH_METRIC_PORT="$PORT"
  #     fi
  # done

  # cp $ORIGIN_VALUE_PATH $VALUE_PATH
  # sed -i "s/<storageclass-name>/$WORKSPACE_STORAGE_CLASS_NAME/g" $VALUE_PATH
  # sed -i "s/<dcgm-metric-port>/$DCGM_METRIC_PORT/g" $VALUE_PATH
  # sed -i "s/<cis-metric-port>/$CSI_METRIC_PORT/g" $VALUE_PATH
  # sed -i "s/<rook-ceph-metric-port>/$ROOK_CEPH_METRIC_PORT/g" $VALUE_PATH

  cd $BASE_DIR
  helm dependency build kube-prometheus-stack
  if [ "$LOCAL_STORAGE" == "true" ]; then
    helm install local-storage ./local_storage/local-storage -n $NAMESPACE \
	    --set StorageClassName=$LOCAL_STORAGECLASSNAME \
      --set path=$LOCAL_PATH \
      --set nodeAffinity.key=$LOCAL_NODEAFFINITY_KEY \
      --set nodeAffinity.values=$LOCAL_NODEAFFINITY_VALUE
#    kubectl apply -f ./local_storage/local_storage_class.yaml -n $NAMESPACE
#    kubectl apply -f ./local_storage/local_storage_volume.yaml -n $NAMESPACE
  fi
  
  helm install $NAME $PROMETHEUS_STACK -n $NAMESPACE --values $VALUE_PATH --create-namespace
  #helm install dcgm $DCGM  -n $NAMESPACE
  kubectl apply -f ./ingress.yaml -n $NAMESPACE

}

uninstall_all(){
  echo "#################################"
  echo "Start uninstalling Monitoring..."
  echo "#################################"
  
  #helm uninstall dcgm -n $NAMESPACE
  helm uninstall $NAME -n $NAMESPACE
  if [ "$LOCAL_STORAGE" == "true" ]; then
    # kubectl delete -f ./local_storage/local_storage_class.yaml -n $NAMESPACE
    # kubectl delete -f ./local_storage/local_storage_volume.yaml -n $NAMESPACE
    helm uninstall local-storage -n $NAMESPACE
  fi

  kubectl delete -f ./ingress.yaml -n $NAMESPACE
}

if [ -z "$VALUE_PATH" ]; then
  echo "VALUES 파일이름을 스크립트에 입력하세요."
  exit 1
fi

if [ "$MODE" == "true" ]; then
  install_all
  
elif [ "$MODE" == "false" ]; then
  uninstall_all
  #watch -n 1 kubectl get all -n $NAME 

elif [ "$MODE" == "reinstall" ]; then

  if [ "$(kubectl get all -n "$NAME" | wc -l)" -ne "0" ];
  then
    echo "Resource found in namespace [$NAME]."
    sleep 2
    uninstall_all
  else
    echo "Resource not found in namespace [$NAME]. Skip deleting process..."
    sleep 2
  fi
  install_all

  watch -n 1 kubectl get all -n $NAME
elif [ "$MODE" == "upgrade" ]; then
  helm upgrade $NAME $PROMETHEUS_STACK -n $NAMESPACE --values $VALUE_PATH

fi
