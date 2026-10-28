# Kubernetes 클러스터 구축 가이드

이 문서는 **플랫폼 설치 이전 단계**인 Kubernetes 클러스터 구축을 다룹니다.
설치 매뉴얼([INSTALL.md](./INSTALL.md), `Tango GenAI Platform 설치 간소화 매뉴얼.md`)은
"클러스터가 이미 준비되어 있음"을 전제하므로, 클러스터부터 만들어야 한다면 이 문서를 먼저 수행합니다.

완료 시점의 상태가 곧 설치 매뉴얼의 시작 조건입니다.

```bash
kubectl cluster-info        # 오류 없이 출력
kubectl get nodes -o wide   # 노드가 Ready
helm version                # 정상 출력
kubectl top nodes           # 수치 출력 (metrics-server)
```

---

## 1. 검증된 스택 버전

아래는 실제 운영 환경에서 검증된 조합입니다. 특별한 이유가 없으면 이 버전을 사용하십시오.

| 구성요소 | 버전 | 비고 |
|---|---|---|
| OS | Ubuntu 22.04.5 LTS 이상 | |
| Kubernetes | **v1.34.x** (검증 v1.34.0) | kubeadm / kubelet / kubectl |
| containerd | **1.7.29** | CRI 런타임 |
| runc | 1.3.x | containerd 의존 |
| CNI | **Calico v3.32.1** | tigera-operator 방식 |
| pause 이미지 | `registry.k8s.io/pause:3.10.1` | k8s 1.34 계열 |
| cgroup 드라이버 | `systemd` | containerd·kubelet 양쪽 일치 필수 |
| helm | 3.x | |
| metrics-server | 최신 릴리스 | 대시보드·HPA·`kubectl top` 에 필요 |

> ⚠️ **버전을 올릴 때의 제약**: GPU 노드를 쓰는 경우 `gaip_gpu_operators` 의 GPU Operator 차트
> 버전이 실질 상한을 결정합니다. Kubernetes 마이너 버전을 올리려면 GPU Operator 도 함께
> 올려야 하며, `gpu-operator/values.yaml` 의 커스텀 설정(dcgm-exporter 이미지,
> `dcgm-custom-metrics` ConfigMap, nodeSelector)을 이식해야 합니다.

---

## 2. 사전 확정 값

설치 전에 아래 값을 정합니다. 이후 단계에서 그대로 사용합니다.

| 값 | 설명 | 예시 |
|---|---|---|
| `<NODE_NAME>` | 노드로 등록할 이름 (보통 호스트명) | `k8s-node-01` |
| `<NODE_IP>` | API 서버가 광고할 주소 | `10.0.0.10` |
| `<POD_CIDR>` | 파드 네트워크 대역 | `20.0.1.0/24` |
| `<SERVICE_CIDR>` | 서비스 대역 | `10.96.0.0/12` |
| `<REGISTRY_HOST>:<PORT>` | 사용자 이미지 레지스트리 (HTTP 사용 시) | `10.0.0.10:30500` |

**`<NODE_IP>` 선택 주의** — 네트워크 인터페이스가 둘 이상인 서버(예: 서비스망 + 고속/스토리지망)에서는
kubeadm 이 의도하지 않은 인터페이스를 고를 수 있습니다. 이후 kubeconfig·NFS·Ingress 경로가 모두
이 주소 기준이 되므로 **반드시 명시**합니다.

**`<POD_CIDR>` 선택 주의** — 아래와 겹치면 안 됩니다.
- 노드의 물리 네트워크 대역 (`ip -4 addr`, `ip route` 로 확인)
- `<SERVICE_CIDR>`
- **VPN 클라이언트의 로컬 네트워크** — 원격 접속자가 있으면 `192.168.0.0/16` 같은 가정용
  공유기 대역은 피합니다. 접속자 로컬망과 겹치면 그 사용자만 파드에 라우팅이 깨져 재현이 어렵습니다.

`/24` 는 파드 IP 254 개입니다. 노드당 파드가 많거나 노드를 늘릴 계획이면 `/16` 을 권장합니다.

---

## 3. OS 준비

```bash
# 3-1. swap 비활성화 (kubelet 요구사항)
sudo swapoff -a
sudo sed -i.bak '/\sswap\s/s/^/#/' /etc/fstab
free -h | grep -i swap        # [검증] 모두 0B

# 3-2. 커널 모듈
sudo tee /etc/modules-load.d/k8s.conf >/dev/null <<'EOF'
overlay
br_netfilter
EOF
sudo modprobe overlay && sudo modprobe br_netfilter

# 3-3. sysctl
sudo tee /etc/sysctl.d/k8s.conf >/dev/null <<'EOF'
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF
sudo sysctl --system >/dev/null

# 3-4. NFS 클라이언트 — 모든 노드(워커 추가 시 각 노드에서도)
#      플랫폼 values 의 볼륨이 모두 type: nfs 라 kubelet 이 마운트할 때 필요
sudo apt-get install -y nfs-common
```

**[검증]**
```bash
lsmod | grep -E "^overlay|^br_netfilter"
sysctl net.ipv4.ip_forward net.bridge.bridge-nf-call-iptables   # 둘 다 = 1
dpkg -s nfs-common | grep Status                                 # install ok installed
```

> `sysctl --system` 실행 시 `net.ipv4.conf.all.accept_source_route` 등에서
> `Invalid argument` 경고가 날 수 있습니다. 배포판 기본 설정(`/usr/lib/sysctl.d/50-default.conf`)의
> 와일드카드 규칙에서 나오는 것으로, 위 3개 값이 `1` 이면 무시해도 됩니다.

### 3-5. NFS 서버 (export)

플랫폼 볼륨·NFS provisioner·레지스트리가 모두 NFS 를 씁니다. NFS 서버(단일 노드면 같은 서버)에서
경로를 만들고 노드 대역(`<NODE_CIDR>`, 예: `10.0.0.0/24`)에 export 합니다. 아래 경로는
`values.yaml.template` 기본값이며, values 에서 바꿨다면 그 경로를 씁니다. export 옵션
`rw,sync,no_root_squash,no_subtree_check` 는 템플릿이 전제하는 값입니다(NFS provisioner 가 root 로
PVC 하위 디렉터리를 만들기 때문에 `no_root_squash` 가 필요합니다).

```bash
sudo apt-get install -y nfs-kernel-server

# values.yaml.template 의 jfData·jfBin·jfStorage·markerData·hfModelCache 기본 경로
sudo mkdir -p /opt/dynamic-storage/{jf-data,jf-bin,tmp-storage,marker-data,hf-model-cache}
# gaip_nfs_provisioner(values-system/efk)·gaip_registry values 에 넣을 경로
sudo mkdir -p <NFS_PROVISIONER_SYSTEM_PATH> <NFS_PROVISIONER_EFK_PATH> <REGISTRY_IMAGES_PATH>

sudo tee -a /etc/exports >/dev/null <<'EOF'
/opt/dynamic-storage/jf-data         <NODE_CIDR>(rw,sync,no_root_squash,no_subtree_check)
/opt/dynamic-storage/jf-bin          <NODE_CIDR>(rw,sync,no_root_squash,no_subtree_check)
/opt/dynamic-storage/tmp-storage     <NODE_CIDR>(rw,sync,no_root_squash,no_subtree_check)
/opt/dynamic-storage/marker-data     <NODE_CIDR>(rw,sync,no_root_squash,no_subtree_check)
/opt/dynamic-storage/hf-model-cache  <NODE_CIDR>(rw,sync,no_root_squash,no_subtree_check)
<NFS_PROVISIONER_SYSTEM_PATH>        <NODE_CIDR>(rw,sync,no_root_squash,no_subtree_check)
<NFS_PROVISIONER_EFK_PATH>           <NODE_CIDR>(rw,sync,no_root_squash,no_subtree_check)
<REGISTRY_IMAGES_PATH>               <NODE_CIDR>(rw,sync,no_root_squash,no_subtree_check)
EOF
sudo exportfs -ra
```

소스 마운트 개발 모드(`global.jfb.volume.src.enabled: true`)를 쓰면 체크아웃의 `LLMOps/apps` 절대 경로
(`<SRC_PATH>`)도 같은 옵션으로 export 합니다.

**[검증]**
```bash
sudo exportfs -v                   # 위 경로가 모두 표시
showmount -e <NFS_SERVER_IP>       # 각 노드에서 실행 (nfs-common 에 포함)
```

---

## 4. containerd

```bash
CONTAINERD_VERSION=1.7.29
cd /tmp
curl -fLO https://github.com/containerd/containerd/releases/download/v${CONTAINERD_VERSION}/containerd-${CONTAINERD_VERSION}-linux-amd64.tar.gz
sudo tar Cxzvf /usr/local containerd-${CONTAINERD_VERSION}-linux-amd64.tar.gz

# systemd 유닛 (이미 있으면 생략)
sudo curl -fLo /usr/local/lib/systemd/system/containerd.service --create-dirs \
  https://raw.githubusercontent.com/containerd/containerd/main/containerd.service
sudo systemctl daemon-reload && sudo systemctl enable --now containerd
containerd --version          # [검증] v1.7.29
```

runc 가 없으면 함께 설치합니다.

```bash
curl -fLO https://github.com/opencontainers/runc/releases/latest/download/runc.amd64
sudo install -m 755 runc.amd64 /usr/local/sbin/runc && runc --version
```

### 4-1. containerd 설정

```bash
sudo mkdir -p /etc/containerd
sudo containerd config default | sudo tee /etc/containerd/config.toml >/dev/null
grep -n "^version" /etc/containerd/config.toml          # version = 2 여야 함

# cgroup 드라이버를 systemd 로 (kubeadm 의 cgroupDriver 와 반드시 일치)
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
# pause 이미지 고정
sudo sed -i 's#sandbox_image = ".*"#sandbox_image = "registry.k8s.io/pause:3.10.1"#' /etc/containerd/config.toml

sudo systemctl restart containerd
sudo grep -E "SystemdCgroup|sandbox_image" /etc/containerd/config.toml
```

> ⚠️ **기존 설정이 있는 서버**: `/etc/containerd/config.toml` 의 `version` 이 `3` 이상이면
> containerd 2.x 용 스키마이므로 1.7.x 에서 사용할 수 없습니다. 반드시 위처럼 재생성하고,
> 기존 파일은 백업해 두십시오(`certs.d/`·`conf.d/` 디렉터리도 함께 확인).

### 4-2. 사용자 레지스트리 (HTTP 사용 시)

플랫폼의 사용자 이미지 레지스트리를 HTTP 로 쓰는 경우에만 필요합니다
(`values_<서버명>.yaml` 의 `global.jfb.image.users.registry`).

```bash
sudo python3 - <<'PY'
import pathlib
REG = "<REGISTRY_HOST>:<PORT>"          # 예: 10.0.0.10:30500
p = pathlib.Path("/etc/containerd/config.toml")
lines = p.read_text().splitlines(keepends=True)
if REG in "".join(lines):
    print("이미 설정됨"); raise SystemExit
out = []
for ln in lines:
    out.append(ln); s = ln.strip()
    if s == '[plugins."io.containerd.grpc.v1.cri".registry.configs]':
        out += [f'        [plugins."io.containerd.grpc.v1.cri".registry.configs."{REG}".tls]\n',
                '          insecure_skip_verify = true\n']
    elif s == '[plugins."io.containerd.grpc.v1.cri".registry.mirrors]':
        out += [f'        [plugins."io.containerd.grpc.v1.cri".registry.mirrors."{REG}"]\n',
                f'          endpoint = ["http://{REG}"]\n']
p.write_text("".join(out)); print("추가 완료")
PY
sudo systemctl restart containerd
sudo containerd config dump >/dev/null && echo "파싱 OK"
```

> 기본 설정에는 `registry.configs` / `registry.mirrors` **빈 섹션이 이미 존재**합니다.
> 파일 끝에 블록을 덧붙이면 중복 키로 파싱 오류가 나므로, 위처럼 기존 섹션 **뒤에 삽입**합니다.

---

## 5. crictl (선택)

```bash
CRICTL_VERSION=v1.34.0
cd /tmp
curl -fLO "https://github.com/kubernetes-sigs/cri-tools/releases/download/${CRICTL_VERSION}/crictl-${CRICTL_VERSION}-linux-amd64.tar.gz"
sudo tar -C /usr/local/bin -xzf "crictl-${CRICTL_VERSION}-linux-amd64.tar.gz"
sudo tee /etc/crictl.yaml >/dev/null <<'EOF'
runtime-endpoint: unix:///run/containerd/containerd.sock
image-endpoint: unix:///run/containerd/containerd.sock
timeout: 10
EOF
sudo crictl version           # [검증] RuntimeName: containerd
```

---

## 6. kubeadm / kubelet / kubectl / helm

```bash
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates curl gpg
sudo mkdir -p -m 755 /etc/apt/keyrings
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.34/deb/Release.key \
  | sudo gpg --dearmor --yes -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.34/deb/ /' \
  | sudo tee /etc/apt/sources.list.d/kubernetes.list

sudo apt-get update
apt-cache madison kubeadm | head -5        # 설치 가능한 버전 확인

K8S_VER=1.34.0-1.1                         # madison 결과에 맞춰 조정
sudo apt-get install -y kubelet=$K8S_VER kubeadm=$K8S_VER kubectl=$K8S_VER
sudo apt-mark hold kubelet kubeadm kubectl
sudo systemctl enable kubelet

curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
kubeadm version -o short && helm version --short
```

> `apt-mark hold` 는 자동 업그레이드가 kubelet 버전을 몰래 올려 control-plane 과
> 스큐를 만드는 것을 막습니다.
>
> `kubeadm init` 전까지 kubelet 은 설정이 없어 **CrashLoop 이 정상**입니다. `enable` 만 하고
> `start` 는 하지 않습니다.

### 🔴 CNI 플러그인을 수동으로 설치하지 마십시오

`kubeadm` 설치 시 의존성으로 **`kubernetes-cni` 패키지가 자동 설치**되어
`/opt/cni/bin` 에 표준 플러그인을 배치합니다(아키텍처가 항상 올바릅니다).

별도로 `cni-plugins-linux-*.tgz` 를 내려받아 덮어쓰면 **아키텍처가 어긋날 위험**이 있습니다.
실제로 x86_64 노드에 arm64 플러그인을 푼 사례가 있었고, 파드가 `exec format error` 로
`Terminating` 상태에서 고착되어 원인 파악에 오래 걸렸습니다.

**[검증]** — ELF 바이너리만 골라 검사합니다. 패키지에 `LICENSE`·`README.md` 같은
텍스트 파일이 함께 들어 있어 단순 `grep -v` 는 오탐합니다.

```bash
bad=0; n=0
for f in /opt/cni/bin/*; do
  d=$(file -b "$f")
  case "$d" in *ELF*) n=$((n+1));
    case "$d" in *x86-64*) ;; *) echo "BAD: $f -> $d"; bad=$((bad+1));; esac;;
  esac
done
echo "ELF $n 개 검사, 불일치 $bad 개"
```

---

## 7. kubeadm init

설정 파일로 실행합니다. 값이 문서로 남아 재구축 시 그대로 재현할 수 있습니다.

```bash
cat > ~/kubeadm-config.yaml <<'EOF'
apiVersion: kubeadm.k8s.io/v1beta4
kind: InitConfiguration
localAPIEndpoint:
  advertiseAddress: <NODE_IP>
  bindPort: 6443
nodeRegistration:
  criSocket: unix:///run/containerd/containerd.sock
  imagePullPolicy: IfNotPresent
  name: <NODE_NAME>
---
apiVersion: kubeadm.k8s.io/v1beta4
kind: ClusterConfiguration
kubernetesVersion: v1.34.0
imageRepository: registry.k8s.io
certificatesDir: /etc/kubernetes/pki
etcd:
  local:
    dataDir: /var/lib/etcd
networking:
  dnsDomain: cluster.local
  podSubnet: <POD_CIDR>
  serviceSubnet: <SERVICE_CIDR>
---
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
cgroupDriver: systemd
maxPods: 250   # 기본 110 이면 플랫폼·인프라만으로 거의 찬다
EOF

# 이미지 선당김 (네트워크 문제를 init 실패와 분리)
sudo kubeadm config images pull --config ~/kubeadm-config.yaml

sudo kubeadm init --config ~/kubeadm-config.yaml
```

**[검증]** `Your Kubernetes control-plane has initialized successfully!`

실패 시 `sudo journalctl -u kubelet -n 80 --no-pager` 로 원인을 확인하고,
재시도 전에 [12장 재설치를 위한 초기화](#12-재설치를-위한-초기화) 로 정리합니다.

출력 끝의 `kubeadm join ...` 명령은 워커 노드 추가에 필요하므로 보관하십시오
(토큰 24시간 만료, `sudo kubeadm token create --print-join-command` 로 재발급).

---

## 8. 클러스터 초기 설정

### 8-1. kubeconfig

```bash
mkdir -p ~/.kube
sudo cp -f /etc/kubernetes/admin.conf ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
kubectl get nodes -o wide
```

이 시점 노드 상태는 **`NotReady` 가 정상**입니다(CNI 미설치).

플랫폼 차트가 참조하는 위치에도 복사합니다(`devops` 디렉터리에서 실행).

```bash
mkdir -p ./fb_common_app/helm/file/kube
cp ~/.kube/config ./fb_common_app/helm/file/kube/config
```

### 8-2. 단일 노드 구성 시 taint 제거

control-plane 노드에 워크로드를 배치하려면(단일 노드 구성) taint 를 제거해야 합니다.
**이 단계를 빠뜨리면 이후 모든 애플리케이션 파드가 `Pending` 상태가 됩니다.**

```bash
kubectl taint nodes <NODE_NAME> node-role.kubernetes.io/control-plane:NoSchedule-
```

### 8-3. 노드 라벨

플랫폼 차트가 사용하는 역할 라벨을 부여합니다. 다중 노드 구성이면 용도에 맞는 노드에 각각 부여합니다.

```bash
kubectl label node <NODE_NAME> node-role.kubernetes.io/db=""
kubectl label node <NODE_NAME> node-role.kubernetes.io/compute=""
kubectl label node <NODE_NAME> node-role.kubernetes.io/manage=""
kubectl get nodes        # [검증] ROLES 에 반영
```

> 노드 상태에 남아 있는 `node.kubernetes.io/not-ready` taint 는 제거 대상이 아닙니다.
> CNI 설치 후 자동으로 사라집니다.

---

## 9. CNI — Calico (tigera-operator)

```bash
CALICO_VERSION=v3.32.1
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/${CALICO_VERSION}/manifests/tigera-operator.yaml
kubectl -n tigera-operator rollout status deploy/tigera-operator --timeout=5m
```

오퍼레이터가 Running 이 된 뒤 `Installation` 리소스를 적용합니다.
**`cidr` 을 `<POD_CIDR>` 과 반드시 일치시킵니다.**

```bash
cd /tmp
curl -fsSLO https://raw.githubusercontent.com/projectcalico/calico/${CALICO_VERSION}/manifests/custom-resources.yaml
sed -i 's#cidr: 192.168.0.0/16#cidr: <POD_CIDR>#' custom-resources.yaml
grep -n "cidr:" custom-resources.yaml        # 눈으로 확인 후 적용
kubectl create -f custom-resources.yaml
```

**[검증]**
```bash
kubectl get pods -n calico-system      # calico-node·typha·kube-controllers·apiserver 등
kubectl get tigerastatus               # 전 항목 AVAILABLE=True
kubectl get nodes                      # STATUS 가 Ready 로 전환
```

> 파드가 `Terminating` 에서 멈추거나 로그에 `exec format error` 가 보이면
> 6장의 CNI 아키텍처 검증을 다시 확인합니다.

---

## 10. metrics-server

대시보드의 자원 사용량 표시, `kubectl top`, HPA 에 필요합니다. 이 리포에 차트가 포함되어
있지 않으므로 별도로 설치합니다.

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# kubelet 인증서에 노드 IP 의 SAN 이 없는 일반적인 온프레미스 환경에서는 필수
kubectl -n kube-system patch deploy metrics-server --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

kubectl -n kube-system rollout status deploy/metrics-server --timeout=5m
```

**[검증]** — 기동 후 약 60초 뒤 수치가 출력됩니다.

```bash
kubectl top nodes
```

**주의사항**

- `--kubelet-insecure-tls` 를 빼면 `x509: cannot validate certificate for <NODE_IP>` 로
  계속 실패합니다. 사설 CA 로 kubelet 인증서에 IP SAN 을 포함시킨 환경에서만 생략할 수 있습니다.
- **`hostNetwork: true` 로 바꾸지 마십시오.** metrics-server 의 secure-port(10250)가
  kubelet 포트와 충돌해 CrashLoop 에 빠집니다.

---

## 11. 최종 검증

```bash
kubectl get nodes -o wide
kubectl get pods -A
kubectl top nodes
```

**통과 기준**

- 노드가 `Ready`, VERSION 이 목표 버전, CONTAINER-RUNTIME 이 `containerd://1.7.29`
- `kube-system` · `calico-system` · `tigera-operator` 의 모든 파드가 `Running`
- `kubectl top nodes` 가 수치를 출력
- 단일 노드 구성이면 ROLES 에 `compute,control-plane,db,manage` 가 모두 표시

여기까지 통과하면 [INSTALL.md](./INSTALL.md) 또는
`Tango GenAI Platform 설치 간소화 매뉴얼.md` 의 **1단계(기반 인프라)** 로 진행합니다.

---

## 12. 재설치를 위한 초기화

`kubeadm init` 이 실패했거나 클러스터를 다시 만들어야 할 때 사용합니다.

```bash
sudo systemctl stop kubelet
sudo rm -rf /etc/kubernetes/manifests
sudo kubeadm reset -f --cri-socket unix:///run/containerd/containerd.sock
sudo rm -rf /etc/kubernetes /var/lib/kubelet /var/run/kubernetes ~/.kube
sudo rm -rf /etc/cni/net.d /var/lib/cni
# etcd 데이터까지 지울 때만
sudo rm -rf /var/lib/etcd

# 잔존 컨테이너 정리
if command -v crictl >/dev/null 2>&1; then
  for id in $(sudo crictl ps -aq); do sudo crictl stop "$id"; sudo crictl rm "$id"; done
  for pid in $(sudo crictl pods -q); do sudo crictl rmp "$pid"; done
fi
sudo systemctl restart containerd

# 포트 점유 확인 (비어 있어야 함)
ss -lntup | egrep ':(6443|10250|2379|2380)\b' || echo "ports clean"
```

> ⚠️ 이 절차는 **클러스터만** 제거합니다. NFS 스토리지의 데이터는 건드리지 않습니다.
> 다만 플랫폼을 재설치할 때 기존 데이터를 재사용하려면 StorageClass 설정과 PVC 이름이
> 이전과 같아야 합니다. 자세한 내용은 [INSTALL.md 의 "데이터를 보존한 재설치"](./INSTALL.md#데이터를-보존한-재설치)를
> 참고하십시오(이 경우 MariaDB 를 초기화하는 `run_step2_core_infra.sh` 는 쓰지 않습니다).

---

## 13. 문제 해결

| 증상 | 확인 사항 |
|---|---|
| `kubeadm init` 이 `[kubelet-check]` 에서 멈춤 | cgroup 드라이버 불일치(containerd `SystemdCgroup = true` ↔ kubelet `cgroupDriver: systemd`), `journalctl -u kubelet` |
| 노드가 계속 `NotReady` | CNI 미설치 또는 `calico-system` 파드 비정상 |
| 파드가 `Terminating` 고착 / `exec format error` | `/opt/cni/bin` 플러그인 아키텍처 (6장 검증) |
| 모든 앱 파드가 `Pending` | 단일 노드인데 control-plane taint 미제거 (8-2) |
| `kubectl top` 실패 | metrics-server 미설치 또는 `--kubelet-insecure-tls` 누락 (10장) |
| 이미지 pull 실패 (사설 레지스트리) | containerd registry 설정 (4-2), 설정 후 containerd 재시작 여부 |
| API 서버 주소가 의도와 다름 | `advertiseAddress` 미지정 상태로 init — 인터페이스가 여러 개인 서버에서 발생 |
