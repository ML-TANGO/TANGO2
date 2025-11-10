#!/bin/bash

SCRIPT=$( readlink -m $( type -p $0 ))
BASE_DIR=`dirname ${SCRIPT}`

cd $BASE_DIR

. /etc/jfb/func.sh $BASE_DIR
NAMESPACE=$(namespace_sub)
. /etc/jfb/$NAMESPACE/parser.sh

helm uninstall ${NAMESPACE}-kong -n $NAMESPACE

# kong uninstall
# kong 고도화 - 재사용...
seq -s= 40 | tr -d '[:digit:]'
echo [DELETE kong]

echo "Deleting postgres PVC..."
kubectl delete pvc -n $NAMESPACE data-$NAMESPACE-kong-postgresql-0 --timeout 10s
kubectl get pvc -n $NAMESPACE data-$NAMESPACE-kong-postgresql-0 | awk '{print $1}' | xargs kubectl -n $NAMESPACE patch pvc -p '{"metadata":{"finalizers":null}}'
echo

echo "kubectl delete pv..."
kubectl get pv | grep data-$NAMESPACE-kong-postgresql | awk '{print $1}' | xargs kubectl delete pv --timeout 10s
kubectl get pv | grep data-$NAMESPACE-kong-postgresql | awk '{print $1}' | xargs kubectl patch pv -p '{"metadata":{"finalizers":null}}'

kubectl get pv | grep $NAMESPACE-kong-pv | awk '{print $1}' | xargs kubectl delete pv --timeout 10s
kubectl get pv | grep $NAMESPACE-kong-pv | awk '{print $1}' | xargs kubectl patch pv -p '{"metadata":{"finalizers":null}}'
echo


KONG_PATH=$(cat ../values.yaml | yq r - "global.jfb.volume.path")
echo "rm -r $KONG_PATH"
rm -r $KONG_PATH