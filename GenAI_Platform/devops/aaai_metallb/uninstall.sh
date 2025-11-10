#!/bin/bash
kubectl delete -f metallb-config.yaml
kubectl delete -f metallb-native.yaml

kubectl delete pod --all --grace-period=0 --force -n metallb-system
kubectl get namespace "metallb-system" -o json  | tr -d "\n" | sed "s/\"finalizers\": \[[^]]\+\]/\"finalizers\": []/"   | kubectl replace --raw /api/v1/namespaces/"metallb-system"/finalize -f -