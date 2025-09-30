#! /bin/bash

tar -xvzf chartmuseum-v0.16.0-linux-amd64.tar.gz

cd linux-amd64
chmod +x chartmuseum

mv ./chartmuseum /bin/

nohup chartmuseum  --port=6060 --storage="local" --storage-local-rootdir="/home/jake/jfbcore_msa/ops/setting/helm_chart" > /dev/null 2>&1 & 

helm repo add jfb-repo http://192.168.1.19:6060

cd ..
rm -rf ./linux-amd64




