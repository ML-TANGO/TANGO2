#!/bin/bash


kubectl apply -f k8s-rdma-shared-dev-plugin-config-map.yaml && kubectl delete pods -n kube-system -l name=rdma-shared-dp-ds