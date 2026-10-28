# Kubernetes 서비스 운영 가이드: 자동 확장과 우선순위 스케줄링

사설 Docker 레지스트리에 올린 컨테이너(FastAPI, Ubuntu)를 Kubernetes 클러스터에 배포하고, **Pod 자동 확장(HPA)** 과 **우선순위 기반 스케줄링(PriorityClass)** 을 구성·평가한 내용을 정리한 저장소다.

| 문서 | 내용 |
|---|---|
| `README.md` (이 문서) | 개요, 클러스터 구성, 준비사항 (레지스트리 연동, 대시보드, 모니터링) |
| [`Autoscaling.md`](Autoscaling.md) | CPU · 메모리 · API 요청률 3종 지표 기반 HPA 구성, 동작 원리, 부하 시험과 실측 결과 |
| [`Priority_Scheduling.md`](Priority_Scheduling.md) | PriorityClass 설계, 선점(Preemption) 동작 원리, 선점 시험과 실측 결과 |

## 목차

- [1. 클러스터 구성](#1-클러스터-구성)
  - [네임스페이스와 서비스 포트](#네임스페이스와-서비스-포트)
- [2. 디렉토리 구성](#2-디렉토리-구성)
- [3. 준비사항](#3-준비사항)
  - [3-1. 사설 Docker Registry 연동](#3-1-사설-docker-registry-연동)
  - [3-2. Kubernetes Dashboard + metrics-server 설치](#3-2-kubernetes-dashboard--metrics-server-설치)
  - [3-3. Prometheus + Grafana (kube-prometheus-stack)](#3-3-prometheus--grafana-kube-prometheus-stack)
  - [3-4. 디스크 여유가 작은 worker 노드의 kubelet 설정 (해당 노드만)](#3-4-디스크-여유가-작은-worker-노드의-kubelet-설정-해당-노드만)
  - [3-5. 준비 완료 체크리스트](#3-5-준비-완료-체크리스트)
- [4. 다음 단계](#4-다음-단계)

---

## 1. 클러스터 구성

| 노드 | 역할 | CPU | 메모리 | 아키텍처 |
|---|---|---|---|---|
| ketis | control-plane | 28 core | 125 GiB | amd64 |
| ubuntu2204-worker | worker (GPU) | 16 core | 31 GiB | amd64 |
| jetson-2204-arm | worker | 8 core | 61 GiB | arm64 |
| k8s-mobile | worker | 8 core | 15 GiB | amd64 |

| 구성요소 | 버전 |
|---|---|
| Kubernetes (kubeadm) | v1.30.14 |
| containerd | 1.7.29 |
| Docker Engine (ketis, 이미지 빌드용) | 29.8.0 |
| OS | Ubuntu 22.04.5 LTS |
| CNI | flannel (pod CIDR 10.244.0.0/16) |
| 노드 간 네트워크 | Tailscale (InternalIP 100.x.x.x) |

노드 간 통신은 Tailscale로 구성해 각 노드의 Tailscale IP(100.x.x.x)를 INTERNAL-IP로 사용하며, 노드의 실제 네트워크 환경이 바뀌어도 고정 IP처럼 운영할 수 있다. 노드 접근 주소는 `kubectl get nodes -o wide`의 INTERNAL-IP를 쓴다. 이 문서에서 `<노드IP>`는 그 값을 뜻하며, NodePort 서비스는 어느 노드의 IP로 접근해도 된다.

### 네임스페이스와 서비스 포트

| 네임스페이스 | 용도 | NodePort |
|---|---|---|
| docker-conn | FastAPI(HPA 대상), Ubuntu(DaemonSet) | FastAPI 30810 |
| monitoring | Prometheus, Grafana, prometheus-adapter | Grafana 30300, Prometheus 30090 |
| kubernetes-dashboard | Kubernetes Dashboard | 31000 (HTTPS) |

---

## 2. 디렉토리 구성

아래 명령의 상대 경로는 모두 `Deployment/k8s_autoscaling/` 기준이다.

```
k8s_autoscaling/
├── README.md                  ← 이 문서
├── Autoscaling.md             ← HPA 가이드
├── Priority_Scheduling.md     ← 우선순위 스케줄링 가이드
├── .env.example               ← 민감 정보 템플릿 (.env로 복사해 사용, .env는 커밋 제외)
│
├── docker-repo/               # 레지스트리 이미지 배포 + HPA
│   ├── fastapi-repo.yaml              Deployment + Service (HPA 대상, priorityClassName 적용)
│   ├── ubuntu-repo.yaml               DaemonSet (노드별 1개 배포)
│   ├── fastapi-monitor.yaml           ServiceMonitor (Prometheus 수집)
│   ├── fastapi-hpa-custom-metrics.yaml prometheus-adapter 규칙 (custom metric)
│   └── fastapi-hpa.yaml               HorizontalPodAutoscaler
│
├── scheduler/                 # 우선순위 스케줄링
│   ├── priority.yaml                  PriorityClass 3종
│   ├── priority-test.yaml             선점 시험: 저우선순위 filler
│   ├── priority-test-high.yaml        선점 시험: 고우선순위 pod
│   └── priority-test-never.yaml       선점 시험: preemptionPolicy Never 비교
│
├── prometheus/                # 모니터링 스택
│   ├── monitoring-config.yaml         kube-prometheus-stack helm values (유일한 설정 원본)
│   └── dashboards/*.json              Grafana 사용자 대시보드 백업
│
├── dashboard_k8s/             # Kubernetes Dashboard + metrics-server
│   ├── dashboard.yaml                 Dashboard v2.7.0 (NodePort 31000)
│   ├── dashboard-admin.yaml           admin-user ServiceAccount + cluster-admin 바인딩
│   └── metrics.yaml                   metrics-server v0.8.0 (HPA의 CPU/메모리 지표 공급원)
```

---

## 3. 준비사항

아래 순서대로 구성한다. 3-1은 이미지를 받기 위한 필수 조건이고, 3-2는 자동 확장의 CPU · 메모리 지표에 필요하며, 3-3은 API 요청률 지표와 시각화에 필요하다.

```
3-1 레지스트리 연동 ──▶ 3-2 Dashboard + metrics-server ──▶ 3-3 Prometheus + Grafana ──▶ Autoscaling.md / Priority_Scheduling.md
```

### 3-1. 사설 Docker Registry 연동

사설 레지스트리 `<REGISTRY_HOST>:5003`(HTTP, Basic 인증)에 이미지를 올리고 모든 노드가 받을 수 있게 한다. 역할이 셋으로 나뉘므로 어디에 무엇을 설정하는지 먼저 구분한다.

이 문서의 `<REGISTRY_HOST>`는 레지스트리 서버의 IP 또는 호스트 이름을 뜻하고, 포트는 5003으로 고정이다. 실제 값은 운영 담당자에게 확인한다.

```
[개발 PC / ketis]                        [레지스트리]                      [각 노드 containerd]
 docker build ──▶ docker tag ──▶ docker push ──▶ <REGISTRY_HOST>:5003 ◀── pull ── kubelet
      │                                          (HTTP, Basic 인증)           ▲
      └ /etc/docker/daemon.json                                               │
        insecure-registries                       /etc/containerd/config.toml ┘
                                                  (HTTP 허용)
                                                  + Secret regcred (인증)
```

| 역할 | 설정 위치 | 필요한 곳 |
|---|---|---|
| 이미지 push (docker CLI) | `/etc/docker/daemon.json` + `docker login` | build, push를 수행하는 머신만 |
| 이미지 pull (containerd) | `/etc/containerd/config.toml` | **모든 노드** (master, worker) |
| pull 인증 | Secret `regcred` + `imagePullSecrets` | 이미지를 쓰는 **네임스페이스마다** |

Kubernetes 1.24부터 kubelet은 Docker를 거치지 않고 containerd에 직접 pull을 요청한다. 따라서 노드의 Docker 설정은 Kubernetes pull과 무관하며, Docker가 없는 worker에서도 containerd 설정만 있으면 된다.

#### (1) 레지스트리 정보와 접속 확인

| 항목 | 값 |
|---|---|
| 주소 | `<REGISTRY_HOST>:5003` |
| 프로토콜 | HTTP (TLS 없음) |
| 인증 | Basic. 자격 정보는 문서에 적지 않고 Secret `regcred`에만 보관 |

```bash
curl -u <ID>:<PW> http://<REGISTRY_HOST>:5003/v2/_catalog
curl -u <ID>:<PW> http://<REGISTRY_HOST>:5003/v2/fastapi/tags/list
```

등록된 이미지 목록은 위 `_catalog` 명령으로 확인한다.

자격 정보를 다시 확인해야 할 때는 Secret에서 꺼낸다.

```bash
kubectl get secret regcred -n docker-conn -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d | jq .
```

#### (2) push 측 설정 (Docker CLI가 있는 머신)

`/etc/docker/daemon.json`에 HTTP 레지스트리 예외를 등록한다. 기존 항목(nvidia runtime 등)은 유지한다.

```json
{
  "runtimes": {
    "nvidia": { "args": [], "path": "nvidia-container-runtime" }
  },
  "insecure-registries": [ "<REGISTRY_HOST>:5003" ]
}
```

```bash
sudo systemctl restart docker.service
docker info | grep -A2 "Insecure Registries"
docker login <REGISTRY_HOST>:5003
```

kubelet 재시작은 필요 없다. 빌드와 push:

```bash
docker build -t <REGISTRY_HOST>:5003/fastapi:external .
docker push <REGISTRY_HOST>:5003/fastapi:external

# 기존 이미지를 올릴 때
docker tag ubuntu:22.04 <REGISTRY_HOST>:5003/ubuntu:external
docker push <REGISTRY_HOST>:5003/ubuntu:external
```

jetson-2204-arm(arm64)이 있으므로 amd64 전용 이미지는 그 노드에서 `exec format error`로 실패한다. 두 아키텍처를 한 태그로 올리려면 buildx를 쓴다.

```bash
docker buildx create --name multi --use      # 최초 1회
docker buildx build --platform linux/amd64,linux/arm64 \
  -t <REGISTRY_HOST>:5003/fastapi:external --push .
docker buildx imagetools inspect <REGISTRY_HOST>:5003/fastapi:external
```

현재 `fastapi:external`은 두 아키텍처를 모두 포함한다 (amd64 919 MB, arm64 795 MB).

#### (3) pull 측 설정 (모든 Kubernetes 노드)

containerd가 HTTP 레지스트리에 접속할 수 있도록 **master, worker 모든 노드**에서 수행한다. 빠진 노드가 있으면 그 노드에 배정된 Pod만 `ImagePullBackOff`가 난다.

**현재 적용 방식: `config.toml`의 mirrors (containerd 1.7)**

`/etc/containerd/config.toml`에서 `[plugins."io.containerd.grpc.v1.cri".registry.mirrors]` 블록을 찾아 그 아래에 추가한다. cri 플러그인의 registry 섹션 안에 있어야 하므로 들여쓰기와 위치를 맞춘다. 파일 끝에 붙이면 인식되지 않는다.

```toml
    [plugins."io.containerd.grpc.v1.cri".registry]
      config_path = ""

      [plugins."io.containerd.grpc.v1.cri".registry.configs]

      [plugins."io.containerd.grpc.v1.cri".registry.mirrors]
        [plugins."io.containerd.grpc.v1.cri".registry.mirrors."<REGISTRY_HOST>:5003"]
          endpoint = ["http://<REGISTRY_HOST>:5003"]
```

```bash
sudo systemctl restart containerd.service
sudo systemctl restart kubelet.service     # CRI 재연결
sudo crictl info | jq '.config.registry'   # mirrors 에 주소가 보이면 적용됨
```

**containerd 2.x 호환 방식: `certs.d/hosts.toml`**

`registry.mirrors`는 containerd 1.7에서 deprecated이고 2.0에서 제거되었다. 아래 방식은 1.7과 2.x 모두에서 동작한다. 두 방식을 동시에 쓰면 `config_path`가 우선하고 mirrors는 무시된다.

```bash
sudo mkdir -p /etc/containerd/certs.d/<REGISTRY_HOST>:5003
sudo tee /etc/containerd/certs.d/<REGISTRY_HOST>:5003/hosts.toml <<'EOF'
server = "http://<REGISTRY_HOST>:5003"

[host."http://<REGISTRY_HOST>:5003"]
  capabilities = ["pull", "resolve", "push"]
  skip_verify = true
EOF
sudo sed -i 's|config_path = ""|config_path = "/etc/containerd/certs.d"|' /etc/containerd/config.toml
sudo systemctl restart containerd.service
```

**신규 노드 join 체크리스트**

containerd 설정은 노드 로컬 파일이라 마스터에서 설정해도 새 노드에 전파되지 않는다. `kubeadm join` 전에 위 pull 측 설정을 반드시 수행한다. 반면 Secret `regcred`는 API 서버에 있으므로 새 노드에서도 바로 쓰인다.

```bash
# 노드별 pull 테스트 (각 노드에서)
sudo crictl pull --creds <ID>:<PW> <REGISTRY_HOST>:5003/ubuntu:external

# 클러스터에서 노드별 이미지 보유 현황
kubectl get nodes -o json \
  | jq -r '.items[] | .metadata.name as $n | .status.images[]?.names[]? | select(test("<REGISTRY_HOST>")) | "\($n)\t\(.)"'
```

#### (4) Kubernetes 인증 설정 (네임스페이스마다)

레지스트리가 Basic 인증을 요구하므로 containerd 설정만으로는 `401 Unauthorized`가 난다.

```bash
kubectl create ns docker-conn

kubectl create secret docker-registry regcred \
  --docker-server=<REGISTRY_HOST>:5003 \
  --docker-username=<ID> \
  --docker-password=<PW> \
  -n docker-conn

kubectl get secret regcred -n docker-conn
```

- Secret은 네임스페이스 단위다. 다른 네임스페이스에서 같은 이미지를 쓰려면 거기에도 만든다.
- 이름 `regcred`는 관례이며 매니페스트의 `imagePullSecrets.name`과 일치하면 된다.

매니페스트에서는 전체 경로 이미지와 `imagePullSecrets`를 함께 쓴다 (`docker-repo/ubuntu-repo.yaml`, `fastapi-repo.yaml`).

```yaml
spec:
  template:
    spec:
      containers:
        - name: ubuntu
          image: <REGISTRY_HOST>:5003/ubuntu:external
          command: ["sleep", "infinity"]
      imagePullSecrets:
        - name: regcred
```

매니페스트마다 적지 않으려면 default ServiceAccount에 붙여 둘 수 있다.

```bash
kubectl patch serviceaccount default -n docker-conn -p '{"imagePullSecrets": [{"name": "regcred"}]}'
```

`imagePullPolicy`는 같은 태그를 덮어쓰는 개발 단계에서는 `Always`(현재 fastapi-repo.yaml), 버전 태그를 쓰는 운영 단계에서는 `IfNotPresent`를 쓴다. `Always`는 레지스트리가 내려가면 노드에 이미지가 있어도 Pod 생성이 실패한다.

#### (5) 배포 확인

```bash
kubectl apply -f docker-repo/ubuntu-repo.yaml
kubectl get pods -n docker-conn -o wide
kubectl describe pod <pod> -n docker-conn | tail -15     # 실패 시
```

#### (6) 트러블슈팅

| 증상 (이벤트 메시지) | 원인 | 조치 |
|---|---|---|
| `http: server gave HTTP response to HTTPS client` | 해당 노드의 containerd에 HTTP 허용 설정이 없거나 위치가 틀림 | (3)의 블록 위치, 들여쓰기 확인 후 containerd 재시작 |
| `401 Unauthorized` | Secret 없음, 다른 네임스페이스, `imagePullSecrets` 누락 | (4) 확인 |
| `ImagePullBackOff` + `not found` | 이미지 경로나 태그 오타, push 안 됨 | tags/list로 존재 확인 |
| `exec format error` | 이미지에 해당 노드 아키텍처(arm64)가 없음 | buildx 멀티 아키텍처 push |
| 특정 노드만 pull 실패 | 그 노드만 containerd 설정 누락 | 신규 노드 체크리스트 |
| pull 중 `Evicted` (DiskPressure) | 노드 디스크 여유 부족. 800 MB급 이미지는 pull 중 2~3 GB 일시 사용 | 디스크 정리 또는 kubelet eviction 임계치 조정 ([3-4 참조](#3-4-디스크-여유가-작은-worker-노드의-kubelet-설정-해당-노드만)) |
| 설정했는데도 HTTPS로 시도 | `config_path`와 mirrors 혼용으로 mirrors 무시됨 | 둘 중 하나만 사용 |

### 3-2. Kubernetes Dashboard + metrics-server 설치

Dashboard는 클러스터 상태를 웹에서 보는 용도이고, 함께 설치하는 **metrics-server는 HPA의 CPU · 메모리 지표 공급원**이므로 자동 확장에 필수다.

#### (1) Dashboard 설치 (`dashboard_k8s/dashboard.yaml`)

공식 v2.7.0 recommended.yaml을 받아 Service를 NodePort로 바꾼 파일이다. 원본과 다른 부분은 Service 블록뿐이다.

```yaml
kind: Service
apiVersion: v1
metadata:
  labels:
    k8s-app: kubernetes-dashboard
  name: kubernetes-dashboard
  namespace: kubernetes-dashboard
spec:
  type: NodePort                # 추가
  ports:
    - port: 443
      targetPort: 8443
      nodePort: 31000           # 고정 포트
  selector:
    k8s-app: kubernetes-dashboard
```

```bash
kubectl apply -f dashboard_k8s/dashboard.yaml
kubectl get svc,pods -n kubernetes-dashboard
```

```
service/kubernetes-dashboard        NodePort    443:31000/TCP
pod/kubernetes-dashboard-...        1/1   Running
pod/dashboard-metrics-scraper-...   1/1   Running
```

삭제는 `kubectl delete -f dashboard_k8s/dashboard.yaml`.

#### (2) 로그인 계정 (`dashboard_k8s/dashboard-admin.yaml`)

cluster-admin 권한의 ServiceAccount를 만들고 토큰으로 로그인한다.

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: admin-user
  namespace: kubernetes-dashboard
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: admin-user
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-admin
subjects:
  - kind: ServiceAccount
    name: admin-user
    namespace: kubernetes-dashboard
```

```bash
kubectl apply -f dashboard_k8s/dashboard-admin.yaml
kubectl -n kubernetes-dashboard create token admin-user      # 토큰 출력 (기본 1시간 유효)
```

브라우저에서 `https://<노드IP>:31000/#/login`에 접속해 Token 방식으로 위 토큰을 붙여 넣는다. 자체 서명 인증서라 브라우저 경고는 무시하고 진행한다. 토큰이 만료되면 같은 명령으로 다시 발급한다 (`--duration=24h` 옵션으로 늘릴 수 있다).

#### (3) metrics-server 설치 (`dashboard_k8s/metrics.yaml`)

공식 components.yaml(v0.8.0)을 받아 이 클러스터에 맞게 인자를 바꾼 파일이다.

```yaml
        args:
          - --cert-dir=/tmp
          - --secure-port=10251                            # 기본 10250 에서 변경, containerPort 도 동일하게 10251
          - --kubelet-preferred-address-types=InternalIP   # Tailscale IP(InternalIP) 로만 kubelet 접속
          - --metric-resolution=15s
          - --kubelet-insecure-tls                         # kubelet 자체 서명 인증서 허용 (추가)
```

- `--kubelet-insecure-tls`: kubeadm 기본 kubelet 인증서는 IP SAN이 없어 검증에 실패하므로 필요하다. 이 옵션이 없으면 metrics-server가 Running이어도 `kubectl top`이 비어 있다.
- `--kubelet-preferred-address-types=InternalIP`: 노드 간 통신이 Tailscale IP로 이루어지므로 Hostname 해석에 의존하지 않도록 고정한다.

```bash
kubectl apply -f dashboard_k8s/metrics.yaml
kubectl get deployment metrics-server -n kube-system
kubectl get apiservice v1beta1.metrics.k8s.io      # AVAILABLE True
kubectl top nodes
kubectl top pods -n docker-conn
```

`kubectl top`이 값을 보여주면 HPA의 CPU · 메모리 지표가 준비된 것이다. Dashboard의 CPU · 메모리 그래프도 이때부터 표시된다.

### 3-3. Prometheus + Grafana (kube-prometheus-stack)

API 요청률 기반 HPA(custom metric)와 Grafana 시각화를 위해 설치한다. 상세 구성과 prometheus-adapter 연동은 [`Autoscaling.md` 2장](Autoscaling.md#2-환경-구성)에 있다.

Grafana 관리자 비밀번호는 `.env.example`을 `.env`로 복사한 뒤 `GRAFANA_ADMIN_PASSWORD`에 채워서 쓴다. `.env`는 커밋하지 않는다.

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

set -a; source .env; set +a   # GRAFANA_ADMIN_PASSWORD 로드 (.env는 git에 올리지 않음)

# 신규 설치
helm install prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace --version 81.4.3 \
  -f prometheus/monitoring-config.yaml \
  --set-string grafana.adminPassword="$GRAFANA_ADMIN_PASSWORD"

# 설정 변경 시 (같은 파일을 수정한 뒤)
helm upgrade prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring --version 81.4.3 -f prometheus/monitoring-config.yaml \
  --set-string grafana.adminPassword="$GRAFANA_ADMIN_PASSWORD"
```

`prometheus/monitoring-config.yaml`이 유일한 설정 원본이며 다음을 담는다.

- Grafana 관리자 계정 (비밀번호는 파일에 없고 환경변수 `GRAFANA_ADMIN_PASSWORD`로 전달)
- Grafana NodePort 30300, Prometheus NodePort 30090
- 모든 구성요소를 control-plane 노드 `ketis`에 고정. Prometheus가 worker 노드에 뜨면 그 노드 장애 시 모니터링과 HPA의 custom metric이 함께 끊기므로, 반드시 control-plane에 고정해 설치한다

| 접근 | 주소 |
|---|---|
| Grafana | `http://<노드IP>:30300` |
| Prometheus | `http://<노드IP>:30090` |

Grafana와 Prometheus는 영구 볼륨 없이 동작하므로, Grafana pod가 새로 뜨면 UI에서 만든 대시보드가 사라진다. 사용자 대시보드는 `prometheus/dashboards/*.json`에 백업되어 있으며, API로 복원한다.

```bash
for f in prometheus/dashboards/*.json; do
  jq '{dashboard: ., overwrite: true, folderId: 0}' "$f" \
    | curl -s -u admin:<PW> -H 'Content-Type: application/json' \
        -X POST http://<노드IP>:30300/api/dashboards/db -d @-
done
```

Grafana에서 네임스페이스별 pod 수를 보려면 "The number of pods" 대시보드를 열거나, 새 패널에 다음 PromQL을 쓴다.

```promql
count(kube_pod_info) by (namespace)                         # 전체 pod 수
sum(kube_pod_status_ready{condition="true"}) by (namespace) # Ready 인 pod 만
```

### 3-4. 디스크 여유가 작은 worker 노드의 kubelet 설정 (해당 노드만)

kubelet은 기본적으로 디스크 여유가 15% 미만이면 노드를 DiskPressure로 판정하고 Pod를 퇴거하며, 디스크 사용률이 85%를 넘으면 미사용 이미지를 삭제한다. 루트 디스크 여유가 10 GB 안팎인 노드에서는 800 MB급 이미지를 pull하는 것만으로 임계치를 넘어 Pod가 `Evicted`되고, 받은 이미지도 곧바로 지워져 다음 확장 때 다시 pull하게 된다.

시험 환경에서 이를 피하려면 해당 노드의 `/var/lib/kubelet/config.yaml`에 아래를 추가하고 kubelet을 재시작한다. 운영 환경이라면 디스크 정리가 우선이다.

```yaml
evictionHard:
  nodefs.available: "500Mi"
  imagefs.available: "500Mi"
  nodefs.inodesFree: "5%"
  imagefs.inodesFree: "5%"
  memory.available: "100Mi"
imageGCHighThresholdPercent: 98
imageGCLowThresholdPercent: 95
```

```bash
sudo systemctl restart kubelet
```

- `evictionHard`를 퍼센트 대신 절대값(500Mi)으로 두면 디스크가 거의 찰 때까지 DiskPressure가 발생하지 않는다. 0으로 완전히 끄면 containerd가 쓰기 실패로 멈출 수 있으므로 최소치는 남긴다.
- `evictionHard:` 블록은 파일 최상위(`apiVersion:`과 같은 열)에 두어야 한다. 다른 키 아래에 들여쓰기되면 조용히 무시된다.
- 이 파일은 노드 로컬 설정이라 `kubeadm upgrade` 시 초기화될 수 있다.

반영 확인 (control-plane에서):

```bash
kubectl get --raw /api/v1/nodes/<노드이름>/proxy/configz | jq '.kubeletconfig | {evictionHard, imageGCHighThresholdPercent}'
```

### 3-5. 준비 완료 체크리스트

```bash
kubectl get nodes                                             # 사용할 노드가 모두 Ready
kubectl get pods -n docker-conn -o wide                       # 레지스트리 이미지가 모든 노드에서 Running
kubectl top pods -n docker-conn                               # metrics-server 동작
kubectl get svc -n kubernetes-dashboard                       # 31000
kubectl get pods -n monitoring -o wide                        # 모두 Running, ketis 에 배치
kubectl get --raw "/apis/custom.metrics.k8s.io/v1beta1" | jq '.resources | length'   # prometheus-adapter (Autoscaling.md 참조)
kubectl get priorityclass                                     # critical-service 등 3종 (Priority_Scheduling.md 참조)
```

---

## 4. 다음 단계

- **[`Autoscaling.md`](Autoscaling.md)**: FastAPI를 CPU · 메모리 · API 요청률로 자동 확장하는 HPA 구성, 계산식, stress-ng · hey 부하 시험, 트러블슈팅
- **[`Priority_Scheduling.md`](Priority_Scheduling.md)**: PriorityClass 3종(db 20000, critical 10000, algorithm 1000) 설계, FastAPI 적용, 노드를 포화시켜 선점을 관찰하는 시험과 실측 결과
