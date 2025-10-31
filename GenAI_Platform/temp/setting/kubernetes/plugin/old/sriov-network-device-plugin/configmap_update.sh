#!/bin/bash


kubectl apply -f sriovdp-configMap.yaml && kubectl delete pods -n kube-system -l name=sriov-device-plugin