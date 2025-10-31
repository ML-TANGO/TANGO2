#!/bin/bash


echo ===================YAML===================
YAML_LIST=$(find ./kube_yaml -type f | grep yaml$)

for YAML in $YAML_LIST
do
    echo kubectl apply -f $YAML
    kubectl apply -f $YAML
done

echo ===================SH===================
SH_LIST=$(find ./kube_yaml -type f | grep sh$)
for SH in $SH_LIST
do
    echo $SH
    $SH
done
