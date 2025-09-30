#!/bin/bash
set -e
#sudo -v # Get sudo permission

SCRIPT=$( readlink -m $( type -p $0 ))
BASE_DIR=`dirname ${SCRIPT}`

help() {
    echo 
    echo "[FLIGHTBASE DEV RUN SCRIPT]"
    echo
    echo "- ./run_dev.sh --name [NAME] --basedir [JFB root directory]:    helm dev 실 "
    echo "               (-n, --n, -name --name 모두 지원)"
    echo "- ./run_dev.sh uninstall --name [NAME]:                         helm dev 삭제"
    echo "- ./run_dev.sh reinstall --name [NAME]:                         helm dev 재설치"
    echo "- ./run_dev.sh upgrade --name [NAME]:                           helm dev 수정 "
    echo "- ./run_dev.sh list:                                            helm dev 목록 "
    echo 
    echo "* PV,PVC 삭제 잘 안될때"
    echo "  kubectl patch pv(pvc) [name] -n [ns] -p '{"metadata": {"finalizers": null}}' "
    echo
}

# ================================================
NAME=""
JFB_DIR=""
MODE=true # default

while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    install)
      MODE=true
      ;;
    upgrade)
      MODE="upgrade"
      ;;
    uninstall)
      MODE=false
      ;;
    reinstall)
      MODE="reinstall"
      ;;
    list)
      MODE="list"
      ;;
    --name|-name|-n|--n)
      NAME="$2"
      shift # 인수 하나를 처리했으므로 다음 인수로 이동
      ;;
    --basedir)
      JFB_DIR="$2"
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
if { [ "$MODE" = true ] || [ "$MODE" = false ]; } && [ -z "$NAME" ]; then
  help
  exit 1
fi

# ================================================

install_all(){
  echo "#################################"
  echo "Start installing Flightbase..."
  echo "#################################"
  sleep 2

  echo "Start Init PV Process"
  cd $BASE_DIR/../scripts/aks
  ./init.sh
  sleep 2

  cd $BASE_DIR/jfb_dev
  helm install $NAME --create-namespace -n $NAME --set global.developer=$NAME .
}

delete_all() {
  cd $BASE_DIR/jfb_dev

  echo "#################################"
  echo "Start deleting Flightbase..."
  echo "#################################"
  sleep 2

  helm uninstall $NAME -n $NAME
  kubectl delete all --all -n $NAME
  echo "Deleting postgres PVC..."
  kubectl delete pvc -n $NAME data-$NAME-postgresql-0
  #echo "Deleting postgres data..."
  #rm -r /kong-postgres/$NAME
}

wait_until_resource_down() {
  while :
  do
    if [ "$(kubectl get $1 -n "$NAME" | grep $2 | wc -l)" -eq "0" ]
    then
      echo "[$1] $2 does not exist anymore. Now move on to the next stage..."
      sleep 2
      break
    fi
    sleep 1
  done
}

if [ "$MODE" == "true" ]; then
  install_all
  
elif [ "$MODE" == "false" ]; then
  delete_all
  watch -n 1 kubectl get all -n $NAME 

elif [ "$MODE" == "list" ]; then
  helm list -A

elif [ "$MODE" == "upgrade" ]; then
  cd $BASE_DIR/jfb_dev
  helm upgrade $NAME -n $NAME .

elif [ "$MODE" == "reinstall" ]; then

  if [ "$(kubectl get all -n "$NAME" | wc -l)" -ne "0" ];
  then
    echo "Resource found in namespace [$NAME]."
    sleep 2
    delete_all
  else
    echo "Resource not found in namespace [$NAME]. Skip deleting process..."
    sleep 2
  fi

  wait_until_resource_down pvc data-$NAME-postgres

  install_all

  watch -n 1 kubectl get all -n $NAME

fi
