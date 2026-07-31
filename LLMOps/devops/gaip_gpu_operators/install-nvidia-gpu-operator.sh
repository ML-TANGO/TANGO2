# Add helm repo
#helm repo add nvidia-ngc https://helm.ngc.nvidia.com/nvidia --force-update
#helm repo update

# 커스텀 dcgm metrics (DCP 프로파일링 제외) ConfigMap 을 helm install 전에 apply.
# values.yaml 의 dcgmExporter.config.name=dcgm-custom-metrics 가 이걸 참조한다.
kubectl create namespace gpu-operator 2>/dev/null || true
kubectl apply -f ./dcgm-custom-metrics.yaml

cd gpu-operator
# Install GPU Operator
helm install \
       -n gpu-operator gpu-operator --create-namespace \
       . --values values.yaml \
       --set driver.enabled=false \
       --set driver.rdma.enabled=false \
       --set driver.rdma.useHostMofed=false \
       --set mig.strategy=mixed \
       --set dcgmExporter.serviceMonitor.interval=1s 
       
# driver.enabled: false when using pre-installed driver (false일 경우 gpudirect rdma를 위해 직접 nvidia_peermem 모듈을 호스트에서 실행해야 함)
# driver.rdma.enabled: nvidia-peermem kernel module
# mig.strategy: [single|mixed] mixed when MIG mode is not enabled on all GPUs on a node
