#!/bin/bash

# /etc/ufw/user.rules 에서 확인 가능.

#Kong allow
sudo ufw allow 80/tcp #http
sudo ufw allow 443/tcp #https

#Calico and kubernetes allow
sudo ufw allow 179/tcp #Calico networking
sudo ufw allow 2379:2380/tcp #etcd 서버 클라이언트 API
sudo ufw allow 4789/tcp #Calico networking with VXLAN enabled
sudo ufw allow 5473/tcp #Calico networking with Typha enabled
sudo ufw allow 6443/tcp #kubernetes api
sudo ufw allow 51820/tcp #IPv4
sudo ufw allow 51821/tcp #IPv6

sudo ufw allow 10248/tcp #healthz
sudo ufw allow 10250/tcp #kubelet api
sudo ufw allow 10259/tcp #kube-scheduler
sudo ufw allow 10257/tcp #kube-controller 관리자

sudo ufw allow 30000:32767/tcp #Nodeport 서비스
