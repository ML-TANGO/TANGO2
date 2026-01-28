#!/bin/bash
  
# strictARP
kubectl get configmap kube-proxy -n kube-system -o yaml | sed -e "s/strictARP: false/strictARP: true/" | kubectl apply -f - -n kube-system

# Install MetalLB
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.7/config/manifests/metallb-native.yaml

#kubectl apply -f metallb-native.yaml

# Handling Webhook Error
kubectl delete validatingwebhookconfigurations metallb-webhook-configuration

# MetalLB Config
kubectl create -f metallb-config.yaml
