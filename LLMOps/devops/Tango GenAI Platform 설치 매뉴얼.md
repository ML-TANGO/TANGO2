# 📘 GenAI Platform 설치 매뉴얼

본 문서는 Tango 2 프로젝트의 GenAI Platform 을 **인프라 차트 단위로 하나씩** 설치하는 상세 절차입니다.
각 단계에서 무엇을 수정하고 무엇을 확인해야 하는지까지 이 문서만으로 따라갈 수 있도록 정리했습니다.

설치에 필요한 코드와 Helm 차트는 TANGO2 저장소에 포함되어 있습니다. 설치 대상 서버(Linux)에서
저장소를 `git clone` 으로 내려받은 뒤, 저장소 안의 `LLMOps/devops` 디렉터리에서 진행합니다.

[https://github.com/ML-TANGO/TANGO2](https://github.com/ML-TANGO/TANGO2)

> 💡 같은 절차를 스크립트 3개(`run_step1_infra_base.sh` / `run_step2_core_infra.sh` / `run_step3_optional_obs.sh`)로
> 묶어 실행하는 방법은 `Tango GenAI Platform 설치 간소화 매뉴얼.md` 에 있습니다. 본 문서는 차트별 옵션과
> 문제 해결까지 포함한 상세판입니다. 두 문서의 설치 결과는 같습니다.

---

## 📑 목차

1. 시스템 요구사항
2. 설치 전 준비 (클러스터 · kubelet · 노드 라벨 · NFS)
3. 값 파일(values) 준비
4. 접속 방식 결정 (NodePort / LoadBalancer)
5. 인프라 차트 설치
6. 플랫폼 앱 설치
7. 플랫폼 설치 후 초기 설정
8. 접속 방식 · IP 변경
9. 데이터를 보존한 재설치
10. 문제 해결

---

## 1. 💻 시스템 요구사항

| 항목 | 기준 |
|---|---|
| OS | Ubuntu 22.04.5 Jammy LTS 이상 |
| Kubernetes | v1.34.x 계열 (검증 기준 v1.34.0) |
| 컨테이너 런타임 | **containerd** (검증 1.7.29). Docker 엔진은 필요하지 않습니다 |
| CNI | Calico (검증 v3.32.1) |
| 도구 | `kubectl`, `helm` 3.x — 설치 서버에서 대상 클러스터에 접근 가능해야 함 |
| metrics-server | 설치 필수 (`kubectl top nodes` 가 수치를 출력해야 함) |
| kubelet `maxPods` | **250** (기본값 110 이면 부족 — 2장 참고) |
| NFS | NFS 서버 1대 + 모든 노드에 `nfs-common` |
| GPU (선택) | GPU 노드는 호스트에 NVIDIA 드라이버가 먼저 설치되어 있어야 함 (`nvidia-smi` 정상) |

- 본 매뉴얼은 인터넷 연결이 가능한 **온라인 환경**을 기준으로 합니다. 앱 이미지는 Docker Hub
  공개 이미지(`docker.io/acrylaaai/genai-platform-*`)를 받고, Elastic·Prometheus 차트도 외부 저장소에서 받습니다.
  폐쇄망이라면 이 이미지·차트를 내부 레지스트리로 미러링한 뒤 3장의 레지스트리 값을 바꿔야 합니다.
- 공개 앱 이미지 목록: [https://hub.docker.com/u/acrylaaai](https://hub.docker.com/u/acrylaaai)

---

## 2. ✅ 설치 전 준비

### 2-1. 쿠버네티스 클러스터

클러스터가 없다면 저장소의 [`CLUSTER-SETUP.md`](./CLUSTER-SETUP.md) 를 먼저 수행합니다
(containerd · Calico · kubeadm · metrics-server · 노드 라벨 · taint 까지 다룹니다).
이미 클러스터가 있다면 아래가 모두 오류 없이 출력되는지 확인합니다.

```bash
kubectl cluster-info
kubectl get nodes -o wide        # 모든 노드 Ready, CONTAINER-RUNTIME 이 containerd://...
helm version
kubectl top nodes                # metrics-server 동작 (수치 출력)
kubectl config current-context   # 설치할 클러스터가 맞는지
```

### 2-2. kubelet `maxPods: 250`

플랫폼·인프라 파드만으로 90개를 넘기 때문에 kubelet 기본값(노드당 110개)이면 워크스페이스 잡이
스케줄되지 않습니다. 새로 만드는 클러스터는 `kubeadm init` 설정의 `KubeletConfiguration` 에
`maxPods: 250` 을 넣습니다(`CLUSTER-SETUP.md` 7장). 이미 운영 중인 노드는 각 노드에서 다음을 수행합니다.

```bash
# 각 노드에서
sudo grep -q '^maxPods:' /var/lib/kubelet/config.yaml \
  && sudo sed -i 's/^maxPods:.*/maxPods: 250/' /var/lib/kubelet/config.yaml \
  || echo 'maxPods: 250' | sudo tee -a /var/lib/kubelet/config.yaml
sudo systemctl restart kubelet

# 확인 (노드마다 250)
kubectl get nodes -o custom-columns=NAME:.metadata.name,PODS:.status.capacity.pods
```

> 📌 `/var/lib/kubelet/config.yaml` 은 노드 재구축·업그레이드 시 kubeadm 이 다시 쓸 수 있습니다.
> 유지하려면 `kubectl -n kube-system edit cm kubelet-config` 에도 같은 값을 넣어 둡니다.

### 2-3. 노드 라벨 · taint

인프라 차트와 앱 차트는 역할 라벨로 노드를 고릅니다(MariaDB·Redis·MongoDB 등은 `db`, Kafka 등은 `manage`).
단일 노드면 그 노드에 세 라벨을 모두 붙입니다.

```bash
kubectl label node <NODE_NAME> node-role.kubernetes.io/db=""
kubectl label node <NODE_NAME> node-role.kubernetes.io/compute=""
kubectl label node <NODE_NAME> node-role.kubernetes.io/manage=""

# 단일 노드(컨트롤 플레인에 워크로드 배치)라면 taint 제거 — 빠뜨리면 모든 파드가 Pending
kubectl taint nodes <NODE_NAME> node-role.kubernetes.io/control-plane:NoSchedule-
```

### 2-4. NFS 서버와 export

플랫폼 볼륨, NFS provisioner(동적 프로비저닝), 레지스트리 저장소가 모두 NFS 를 씁니다.

**(1) 모든 노드에 NFS 클라이언트 설치**

```bash
sudo apt-get install -y nfs-common
```

**(2) NFS 서버에서 경로 생성**

아래는 `values.yaml.template` 의 기본 경로(`/opt/dynamic-storage/...`)를 그대로 쓰는 예시입니다.
values 에서 경로를 바꾸면 그 경로를 만듭니다. **values 파일의 `path` 와 실제 디렉터리가 반드시 같아야 합니다.**

| 경로 | 어디에 적는가 | 용도 |
|---|---|---|
| `/opt/dynamic-storage/jf-data` | 공통 values `global.jfb.volume.jfData.path` | 플랫폼 데이터 |
| `/opt/dynamic-storage/jf-bin` | 공통 values `global.jfb.volume.jfBin.path` | 플랫폼 바이너리 |
| `/opt/dynamic-storage/tmp-storage` | 공통 values `global.jfb.volume.jfStorage[0].path` | 워크스페이스 스토리지 루트 (7장 스토리지 등록과 같은 값) |
| `/opt/dynamic-storage/marker-data` | 공통 values `global.jfb.volume.markerData.path` | 마커 데이터 (미사용이어도 경로 필요) |
| `/opt/dynamic-storage/hf-model-cache` | 공통 values `global.jfb.volume.hfModelCache.path` | 외부 컨테이너용 공유 HuggingFace 캐시 |
| `<NFS_PROVISIONER_SYSTEM_PATH>` (예: `/opt/dynamic-storage/system`) | `gaip_nfs_provisioner/values-system.yaml` `nfs.path` | 인프라 PVC (Kong·DB·Kafka·Redis·Prometheus 등) |
| `<NFS_PROVISIONER_EFK_PATH>` (예: `/opt/dynamic-storage/efk`) | `gaip_nfs_provisioner/values-efk.yaml` `nfs.path` | EFK PVC |
| `<REGISTRY_IMAGES_PATH>` (예: `/opt/dynamic-storage/registry`) | `gaip_registry/values.yaml` `volume.path` | 사용자 이미지 레지스트리 저장소 |

```bash
sudo apt-get install -y nfs-kernel-server

sudo mkdir -p /opt/dynamic-storage/{jf-data,jf-bin,tmp-storage,marker-data,hf-model-cache}
sudo mkdir -p <NFS_PROVISIONER_SYSTEM_PATH> <NFS_PROVISIONER_EFK_PATH> <REGISTRY_IMAGES_PATH>
```

**(3) export 설정**

export 옵션은 템플릿이 전제하는 `rw,sync,no_root_squash,no_subtree_check` 를 사용합니다.
NFS provisioner 와 플랫폼 파드가 root 로 하위 디렉터리를 만들기 때문에 **`no_root_squash` 가 필요**합니다
(`root_squash` 로 두면 root 쓰기가 `nobody` 로 바뀌어 권한 오류가 날 수 있어 권장하지 않습니다).
`<NODE_CIDR>` 은 클러스터 노드 대역입니다(예: `10.0.0.0/24`).

```bash
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

# 확인
sudo exportfs -v                    # 위 경로가 모두 표시
showmount -e <NFS_SERVER_IP>        # 각 노드에서 실행
```

소스 마운트 개발 모드(3-2절 `src.enabled: true`)를 쓰면 체크아웃의 `LLMOps/apps` 절대 경로(`<SRC_PATH>`)도,
프론트 빌드를 NFS 로 마운트하면 `LLMOps/front` 경로도 같은 옵션으로 export 합니다.

### 2-5. (선택) CLI 관리 도구 K9s

K9s 는 키보드 단축키로 클러스터를 모니터링·관리하는 오픈소스 도구입니다. 쿠버네티스에 익숙하지 않다면 설치를 권장합니다.
[https://github.com/derailed/k9s](https://github.com/derailed/k9s)

```bash
sudo wget https://github.com/derailed/k9s/releases/latest/download/k9s_linux_amd64.deb \
  && sudo apt install ./k9s_linux_amd64.deb && sudo rm k9s_linux_amd64.deb
```

---

## 3. 값 파일(values) 준비

설치에는 두 종류의 values 가 쓰입니다.

- **공통 values** (`values_<서버명>.yaml`) — 플랫폼 앱 설치(`devops/run.sh`, `devops/run_llm.sh`) 전용
- **인프라 차트 values** — `gaip_*` 디렉터리마다 따로 있음 (3-6절)

### 3-1. 공통 values 파일 생성

```bash
cd LLMOps/devops
cp values.yaml.template values_<서버명>.yaml
# 예: cp values.yaml.template values_prod.yaml
```

> 📌 `values_<서버명>.yaml` 에는 운영 IP·비밀번호·토큰이 들어가므로 **저장소에 커밋하지 않습니다.**
> `LLMOps/.gitignore` 의 `/devops/values_*.yaml` · `/devops/**/values_*.yaml` 규칙이 자동으로 제외합니다.

템플릿 상단의 **[필수 설정 체크리스트]** 를 따라 아래 placeholder 를 모두 실제 값으로 바꿉니다.

| placeholder | 키 | 값 |
|---|---|---|
| `<NFS_SERVER_IP>` | `global.jfb.volume.{jfData,jfBin,jfStorage[0],markerData,hfModelCache}.server` (+ `src`/`front` 사용 시) | NFS 서버 IP. 모두 같은 서버여도 됩니다 |
| `<EXTERNAL_HOST_IP>` | `global.jfb.settings.external.host` | 사용자가 브라우저로 접속할 IP 또는 도메인 (4장) |
| `<USER_REGISTRY_IP>:<PORT>` | `global.jfb.image.users.registry` | 사용자 이미지 레지스트리. 5-4절 `gaip_registry` 를 쓰면 `<노드 IP>:30500` |
| `<SRC_PATH>` | `global.jfb.volume.src.path` | `src.enabled: true` 일 때만 (3-2절) |
| `<NODE_HOSTNAME>` | `global.jfb.volume.front.hostname` | `front.enabled: true` + `hostPath` 일 때만 |

`<NFS_SERVER_IP>` 는 **NFS 서버의 IP** 이며 설치 서버(마스터) IP 와 다를 수 있습니다.
경로(`path`)를 바꿨다면 2-4절에서 만든 디렉터리와 같아야 합니다.

템플릿의 주요 섹션은 다음과 같습니다.

- `global.jfb.namespace` — 앱 네임스페이스 (기본 `jonathan-system`. 인프라 차트도 이 이름을 전제하므로 그대로 두는 것을 권장)
- `global.jfb.volume.*` — 볼륨 (jfData, jfBin, jfStorage, markerData, hfModelCache, src, front)
- `global.jfb.settings.*` — 앱 설정 (db, redis, kafka, kong, mongoDb, monitoring, huggingface, external 등)
- `global.jfb.image.*` — 레지스트리와 앱별 이미지
- `global.jfb.dir.*` — 소스 디렉터리 매핑 (`src.enabled` 일 때만 의미, 보통 수정 불필요)
- `global.jfb.name.*` — 앱별 Deployment/리소스 이름 (보통 수정 불필요)

### 3-2. 소스 마운트 여부 결정 (`global.jfb.volume.src`) — 반드시 선택

템플릿 기본값은 `src.enabled: true` + `path: <SRC_PATH>` 입니다. **그대로 두면 소스 볼륨 마운트가 실패해
앱 파드가 기동하지 않으므로** 둘 중 하나를 고릅니다.

- **(a) 이미지에 포함된 코드로 실행 (운영 권장)** — `src.enabled: false`. 추가 작업이 없습니다.
- **(b) 체크아웃 소스를 마운트 (개발용)** — `src.path` 에 체크아웃의 `LLMOps/apps` **절대 경로**를 넣고
  그 경로를 NFS 로 export 합니다. 각 앱 파드에 `<SRC_PATH>/<앱 디렉터리>` 가 `/app` 으로,
  `<SRC_PATH>/fb_utils` 가 함께 마운트되어 이미지 안의 코드를 덮어씁니다. 코드 수정은 이미지 재빌드 없이
  `kubectl rollout restart deploy/<이름> -n jonathan-system` 로 반영합니다.

```yaml
# (a) 운영
src:
  enabled: false
# (b) 개발
src:
  enabled: true
  type: nfs
  path: <체크아웃 경로>/LLMOps/apps
  server: <NFS_SERVER_IP>
```

프론트(`global.jfb.volume.front`)는 기본이 `enabled: false` 로, 이미지 안의 빌드를 서빙합니다(6-3절).

### 3-3. 외부 접속 설정 (`global.jfb.settings.external`)

```yaml
external:
  protocol: "http"
  host: "<EXTERNAL_HOST_IP>"    # 브라우저 접속 주소
  port: "32080"                 # 기본 Kong proxy = NodePort 32080
  sshPort: "30022"
  redirect: "false"             # 포트를 URL 에 포함 (NodePort 이므로 false)
  ingressClassName: jonathan-kong
```

- 기본값(NodePort)에서는 `host` 에 **노드 IP**, `port: "32080"`, `redirect: "false"` 를 씁니다.
- MetalLB LoadBalancer 로 80 포트를 쓰는 경우는 `host: <VIP>`, `port: "80"`, `redirect: "true"` 입니다(4장).
- `ingressClassName` 과 `settings.kong.namespace` 는 Kong 차트의 `global.developer`(기본 `jonathan-kong`)와 같아야 합니다.
- 외부 IP 를 아직 확정할 수 없으면 내부에서 접근 가능한 IP 로 설치를 마친 뒤 `external.host` 만 바꿔
  `upgrade` 할 수 있습니다(8장).

### 3-4. 이미지 · 레지스트리 설정 (`global.jfb.image`)

```yaml
image:
  runtime: containerd
  system:
    registry: "docker.io"         # 플랫폼 앱 이미지를 받는 레지스트리
    protocol: https://
  users:
    registry: "<노드 IP>:30500"   # 사용자 이미지 레지스트리 (gaip_registry 사용 시)
    protocol: http://
  dataRoot: "/var/lib/containerd"
  # 앱별 이미지 — 템플릿 기본값(공개 이미지) 그대로 사용 가능
  user: acrylaaai/genai-platform-user_app:tango_v2.0.1
  ...
  external_container: acrylaaai/genai-platform-external_container_app:tango_v2.0.1
```

- 앱 이미지는 `<system.registry>/<image.앱이름>` 으로 조합됩니다. 템플릿 기본값은 Docker Hub 공개 이미지입니다.
- **예외: `external_container`** 는 `system.registry` 를 앞에 붙이지 않고 값을 그대로 씁니다.
  내부 레지스트리로 바꿀 때는 이 값에 레지스트리 주소를 직접 포함해야 합니다.
- 사용자 레지스트리를 `gaip_registry`(NodePort 30500, HTTP)로 쓰면 모든 노드의 containerd 에 HTTP 레지스트리
  설정이 필요합니다(10-2절).
- 프라이빗 레지스트리 인증이 필요하면 `pullSecrets.enabled: true` + Secret 이름을 지정합니다.

### 3-5. 비밀번호 · 토큰

비밀번호는 여러 차트에 같은 값이 들어가야 하는 것이 있으므로, **아래 표대로만 바꿉니다.**

| 항목 | 위치 | 변경 |
|---|---|---|
| 플랫폼 관리자(`admin`) 초기 비밀번호 | 공통 values `settings.initRootPassword` | **변경 권장.** 비워 두면 `admin` 이 빈 비밀번호로 만들어지므로 반드시 값을 넣습니다. DB 에 `admin` 이 처음 만들어질 때 한 번만 쓰입니다 |
| MongoDB 비밀번호 | 공통 values `settings.mongoDb.password` **와** `gaip_mongodb/mongodb/values.yaml` `auth.rootPassword` | 바꾸려면 **두 곳을 같은 값으로, MongoDB 설치 전에** 바꿉니다 |
| MariaDB 비밀번호 | `gaip_maraidb/mariadb-galera/values.yaml`, `gaip_maraidb/mariadb-init/templates/configmap.yaml`, `fb_common_app/helm/templates/configmap/cm_settings.yaml` 에 고정값 | values 템플릿에 키가 없습니다. 세 곳이 일치해야 하므로 임의 변경은 권장하지 않습니다 |
| Redis 비밀번호 | `gaip_redis/redis-cluster/values.yaml`, `fb_common_app/.../cm_settings.yaml` 에 고정값 | 위와 같음 — 임의 변경 비권장 |
| Kafka `settings.kafka.protocol` · `sasl_*` | 공통 values | **미사용**입니다(차트가 참조하지 않고 Kafka 리스너는 PLAINTEXT). 바꿀 필요 없습니다 |
| `secrets.workspace.integration.encryptionKey` | 공통 values | 템플릿 체크리스트 항목이지만 현재 어떤 차트도 참조하지 않습니다 |
| HuggingFace 토큰 | 공통 values `settings.huggingface.token` | 선택 (아래) |

#### HuggingFace 토큰 (선택)

`llm_model`, `llm_playground`, `fb_scheduler`(LLM 배포 잡) 등이 HuggingFace 모델·private 레포를 받을 때 씁니다.
빈 값이면 기동 시 HF login 을 건너뛰므로 사내 모델 레포만 쓰는 환경에서는 설정하지 않아도 됩니다.
gated 모델(예: `meta-llama/*`)을 7-7절 사전 스테이징으로 받으려면 필요합니다.

```yaml
global:
  jfb:
    settings:
      huggingface:
        token: "hf_xxxxxxxxxxxxxxxx"   # https://huggingface.co/settings/tokens
```

- 토큰은 `jfb-settings` ConfigMap 의 `HUGGINGFACE_TOKEN` 환경변수로 들어가 `envFrom` 을 쓰는 앱에 전파됩니다.
- 값을 바꿔 `upgrade` 하면 `checksum/config` annotation 이 있는 Deployment 는 자동으로 재시작됩니다.
- ⚠️ 실제 토큰은 `values_<서버명>.yaml`(gitignore 대상)에만 넣고, `values.yaml.template` 등 추적 파일에는 넣지 않습니다.

### 3-6. 인프라 차트 values

인프라 차트(`gaip_*`)는 차트마다 values 구조와 인자 방식이 다릅니다.

| 차트 | 실행 방식 | 설치 전 채울 값 |
|---|---|---|
| `gaip_nfs_provisioner` | `./run.sh install -f <values>` (필수). `nfs.volumeName` 을 네임스페이스로, `<volumeName>-sc` 를 릴리스명으로 사용 | `values-system.yaml`·`values-efk.yaml` 의 `nfs.server`(`<NFS_SERVER_IP>`), `nfs.path`(`<NFS_PROVISIONER_SYSTEM_PATH>`/`<NFS_PROVISIONER_EFK_PATH>`) |
| `gaip_metallb` (선택) | `./install.sh` (manifest 기반) | `metallb-config.yaml` 의 `addresses` (`<METALLB_ADDRESS_RANGE>`) |
| `gaip_kong` | `./run.sh install -f ./values.yaml` (필수). `global.developer` 를 네임스페이스·IngressClass 이름으로 사용 | 기본값 그대로 사용 가능 (MetalLB 사용 시 4장) |
| `gaip_registry` | `./run.sh install -f ./values.yaml` (필수). `namespace`(기본 `jonathan-system`) 사용 | `volume.server`(`<NFS_SERVER_IP>`), `volume.path`(`<REGISTRY_IMAGES_PATH>`) |
| `gaip_maraidb` | `./run.sh install` (기본값) → `./run.sh init -f ./values.yaml` | 기본값 그대로 |
| `gaip_kafka` / `gaip_redis` / `gaip_mongodb` | `./run.sh install` (스크립트 내부 values 고정) | 기본값 그대로 (MongoDB 비밀번호는 3-5절) |
| `gaip_prometheus` | `./run.sh install` (내부 `value.yaml` + `helm dependency build`) | 기본값 그대로 |
| `gaip_gpu_operators` | `./run.sh` (인자 없음) | 기본값 그대로 |
| `gaip_efk` | `helm_repo_add.sh` → `helm_upgrade_elastic.sh` → `elastic_init.sh` → `helm_upgrade_fluent.sh` | 기본값 그대로 (저장 경로는 `values-efk.yaml` 의 `nfs.path`) |

> 📌 인프라 스크립트들은 필요한 네임스페이스(`jonathan-system`, `jonathan-efk`, `jonathan-kong`, `jonathan-mariadb`,
> `jonathan-kafka`, `jonathan-redis`, `jonathan-mongodb`)를 `--create-namespace` 로 직접 만듭니다. 미리 만들 필요는 없습니다.
> 단, `jonathan-system` 은 NFS provisioner(system) 설치 때 생기므로 그 단계를 빼면 안 됩니다.

### 3-7. kubeconfig 복사

`devops/run.sh`, `devops/run_llm.sh` 는 kubeconfig 를 아래 위치에서 찾고, 없으면 중단합니다.
플랫폼 파드가 이 파일로 클러스터 API 를 호출하므로, 파일 안의 `server:` 주소가 `127.0.0.1` 이 아니라
파드에서 닿는 노드 IP(예: `https://<NODE_IP>:6443`)여야 합니다.

```bash
cd LLMOps/devops
kubectl get nodes && kubectl get ns     # 현재 kubeconfig 가 정상인지 먼저 확인
mkdir -p ./fb_common_app/helm/file/kube
cp ~/.kube/config ./fb_common_app/helm/file/kube/config
```

---

## 4. 접속 방식 결정 (NodePort / LoadBalancer)

Kong(API 게이트웨이)의 proxy 서비스가 사용자 접속 지점입니다. **기본값은 NodePort** 이며 MetalLB 가 필요 없습니다.

| 방식 | Kong 설정 (`gaip_kong/values.yaml`) | 공통 values `settings.external` | 접속 주소 |
|---|---|---|---|
| **NodePort (기본)** | `proxy.type: NodePort` (HTTP 32080 / HTTPS 32443), `global.jfb.static.enabled: false` | `host: <노드 IP>`, `port: "32080"`, `redirect: "false"` | `http://<노드 IP>:32080` |
| LoadBalancer (MetalLB) | `proxy.type: LoadBalancer`, `global.jfb.static.enabled: true`, `global.jfb.static.ip: <VIP>` | `host: <VIP>`, `port: "80"`, `redirect: "true"` | `http://<VIP>` |
| LoadBalancer (클라우드 LB) | `proxy.type: LoadBalancer`, `global.jfb.static.enabled: false` | `host: <LB 주소>`, `port: "80"`, `redirect: "true"` | `http://<LB 주소>` |

**선택 기준**

- 클라이언트가 노드 IP 에 닿는다면 NodePort 로 충분합니다. 다른 서브넷에서 접속한다면 그 서브넷에서
  노드로의 라우팅만 있으면 됩니다(`ping <노드 IP>` 로 확인. 실패하면 네트워크 담당자에게 서브넷 간 라우팅
  (inter-VLAN routing) 구성을 요청합니다).
- 80/443 표준 포트가 꼭 필요할 때만 LoadBalancer 를 씁니다. 온프레미스는 MetalLB 가 필요합니다.

**MetalLB L2 모드 제약** — MetalLB L2 모드는 **같은 L2 브로드캐스트 도메인(같은 서브넷)** 안에서만 ARP 응답이
동작합니다. VIP 와 클라이언트가 서로 다른 서브넷이고 두 대역 사이에 L3 라우팅이 없으면 VIP 로 접근할 수 없습니다.

> 예) 노드 IP `<대역 A 의 IP>`, MetalLB VIP `<대역 B 의 IP>`, 두 대역 간 라우팅 미구성 → 대역 A 에서 VIP 접근 불가.
> 이 경우 VIP 를 클라이언트와 같은 대역으로 잡거나 NodePort 를 씁니다.

**LoadBalancer(MetalLB)를 쓰기로 했다면 설치 전에 다음을 수정합니다.**

```yaml
# gaip_metallb/metallb-config.yaml — MetalLB 가 나눠 줄 주소 (리스트로 적습니다)
spec:
  addresses: ["<시작 IP>-<끝 IP>"]      # 또는 ["<VIP>/32"]
```

```yaml
# gaip_kong/values.yaml
global:
  developer: jonathan-kong
  jfb:
    static:
      enabled: true
      ip: <VIP>          # 위 MetalLB 주소 범위 안의 IP
...
proxy:
  type: LoadBalancer
```

```yaml
# values_<서버명>.yaml
global:
  jfb:
    settings:
      external:
        host: "<VIP>"
        port: "80"
        redirect: "true"
```

---

## 5. 🔧 인프라 차트 설치

모든 명령은 저장소의 `LLMOps/devops` 기준 경로입니다. 각 단계의 확인 명령이 정상인지 본 뒤 다음으로 넘어갑니다.

### 5-1. NFS Provisioner (`gaip_nfs_provisioner`) — 필수

인프라 PVC 용 StorageClass 를 만듭니다. 시스템용(`jonathan-system-sc`)과 EFK용(`jonathan-efk-sc`)을 설치합니다.
두 파일의 `<NFS_SERVER_IP>`·경로 placeholder 를 먼저 채웁니다(2-4절의 경로).

```yaml
# gaip_nfs_provisioner/values-system.yaml
nfs:
  server: <NFS_SERVER_IP>
  path: <NFS_PROVISIONER_SYSTEM_PATH>     # 예: /opt/dynamic-storage/system
  volumeName: jonathan-system             # 네임스페이스 — 수정하지 않음
storageClass:
  name: jonathan-system-sc
```

```yaml
# gaip_nfs_provisioner/values-efk.yaml
nfs:
  server: <NFS_SERVER_IP>
  path: <NFS_PROVISIONER_EFK_PATH>        # 예: /opt/dynamic-storage/efk  ← EFK 데이터 저장 위치
  volumeName: jonathan-efk
storageClass:
  name: jonathan-efk-sc
```

```bash
cd LLMOps/devops/gaip_nfs_provisioner
./run.sh install -f ./values-system.yaml   # 필수 (jonathan-system 네임스페이스도 이때 생김)
./run.sh install -f ./values-efk.yaml      # EFK 를 쓸 때 (jonathan-efk 네임스페이스 생성)
# ./run.sh install -f ./values-marker.yaml # (선택) Jonathan Marker 를 쓸 때만 — server/path 를 채운 뒤
```

> 기본 `values.yaml` 은 `volumeName`·`server`·`path`·`storageClass.name` 이 비어 있어 그대로는 쓸 수 없습니다.

**확인**

```bash
kubectl get sc | grep -E "jonathan-system-sc|jonathan-efk-sc"
kubectl get pod -n jonathan-system      # nfs provisioner 파드 Running
```

### 5-2. MetalLB (`gaip_metallb`) — LoadBalancer 를 쓸 때만

4장에서 LoadBalancer(MetalLB)를 골랐을 때만 설치합니다. `install.sh` 는 kube-proxy `strictARP` 를 켜고
MetalLB(v0.13.7)를 설치한 뒤 `metallb-config.yaml` 을 `kubectl create` 합니다.
**`addresses` 를 수정하지 않으면 적용 단계에서 거부됩니다.**

```bash
cd LLMOps/devops/gaip_metallb
vi metallb-config.yaml     # addresses: ["<시작 IP>-<끝 IP>"]
./install.sh
kubectl get ipaddresspool -n metallb-system
```

### 5-3. Kong (`gaip_kong`) — 필수

`run.sh` 는 values 의 `global.developer`(기본 `jonathan-kong`)를 네임스페이스와 IngressClass 이름으로 씁니다.
이 값은 공통 values 의 `settings.kong.namespace`·`settings.external.ingressClassName` 과 같아야 합니다.
Kong 의 PostgreSQL 은 `jonathan-system-sc` 를 쓰므로 5-1 이 먼저 끝나 있어야 합니다.

```bash
cd LLMOps/devops/gaip_kong
./run.sh install -f ./values.yaml
```

- 기본 proxy 는 **NodePort 32080(HTTP) / 32443(HTTPS)** 입니다. NodePort 범위(30000~32767) 포트이므로 URL 에 포트를 붙여 접속합니다.
- LoadBalancer 로 바꾸는 방법은 4장(설치 전)과 8장(설치 후)을 참고합니다. 예전처럼 `nodePort` 주석을 풀거나 다는 작업은 필요 없습니다.

**확인**

```bash
kubectl get pod -n jonathan-kong
kubectl get svc -n jonathan-kong kong-kong-proxy   # TYPE NodePort, 80:32080, 443:32443
kubectl get ingressclass                            # jonathan-kong
```

### 5-4. Registry (`gaip_registry`) — 필수

사용자 이미지 레지스트리입니다. NodePort **30500**(HTTP)으로 열립니다.

```yaml
# gaip_registry/values.yaml
namespace: jonathan-system
service:
  type: NodePort
  port: 30500
volume:
  type: nfs
  path: <REGISTRY_IMAGES_PATH>    # 예: /opt/dynamic-storage/registry
  server: <NFS_SERVER_IP>
```

```bash
cd LLMOps/devops/gaip_registry
./run.sh install -f ./values.yaml
kubectl get svc -n jonathan-system | grep 30500
```

이 레지스트리를 쓰면 공통 values 의 `image.users.registry` 를 `<노드 IP>:30500`, `protocol: http://` 로 두고,
모든 노드의 containerd 에 HTTP 레지스트리 설정을 넣습니다(10-2절).

### 5-5. MariaDB (`gaip_maraidb`) — 필수

```bash
cd LLMOps/devops/gaip_maraidb
./run.sh install                 # Galera 클러스터 (jonathan-mariadb)
# mariadb-galera 파드가 Running 이 된 뒤
./run.sh init -f ./values.yaml   # 스키마 초기화 (mariadb-init 차트)
```

> ⚠️ `init` 은 `jonathan_llm` 데이터베이스를 **DROP 후 재생성**합니다(`mariadb-init/file/check.py`).
> **신규 설치에서만** 실행합니다. 이미 데이터가 있는 DB 에는 절대 다시 실행하지 않습니다(9장).

DB 비밀번호는 3-5절의 세 곳이 일치하는 기본값을 그대로 씁니다.

### 5-6. Kafka (`gaip_kafka`) — 필수

```bash
cd LLMOps/devops/gaip_kafka
./run.sh install                 # jonathan-kafka, 브로커 3개(단일 노드에도 함께 배치됨)
```

### 5-7. Redis (`gaip_redis`) — 필수

```bash
cd LLMOps/devops/gaip_redis
./run.sh install                 # jonathan-redis, redis-cluster 차트
```

> 📌 `gaip_redis/redis-cluster/values.yaml` 의 CPU/Memory `requests` 는 단일 노드에서도 파인튜닝 잡이 들어갈 수 있도록
> 실측 사용량 수준으로 낮춰져 있습니다. 자원이 넉넉한 클러스터라면 `resources.requests` 를 올려도 됩니다.

### 5-8. MongoDB (`gaip_mongodb`) — 필수

```bash
cd LLMOps/devops/gaip_mongodb
./run.sh install                 # jonathan-mongodb
```

> ⚠️ 공통 values 의 `settings.mongoDb.password` 와 `gaip_mongodb/mongodb/values.yaml` 의 `auth.rootPassword` 가
> 같아야 합니다(3-5절). 다르면 앱이 MongoDB 에 접속하지 못합니다. 재설치 시에는 남은 PVC 도 지워야 새 비밀번호가 적용됩니다.

**5-3 ~ 5-8 확인**

```bash
kubectl get pods -A | grep -E "kong|registry|mariadb|kafka|redis|mongo"   # Running / Completed
```

### 5-9. Prometheus (`gaip_prometheus`) — 선택 (권장)

플랫폼의 모니터링·자원 화면(`fb_monitoring`, `fb_resource`)이 Prometheus 를 조회합니다. 설치하지 않아도
플랫폼은 설치되지만 자원 사용량·GPU 지표가 표시되지 않습니다.
`run.sh` 는 `helm dependency build kube-prometheus-stack` 후 `jonathan-system` 에 릴리스 `monitoring` 으로 설치하고
`ingress.yaml` 을 적용합니다.

```bash
cd LLMOps/devops/gaip_prometheus
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
./run.sh install
kubectl get pod -n jonathan-system | grep -E "prometheus|grafana"
```

### 5-10. GPU Operators (`gaip_gpu_operators`) — GPU 노드가 있을 때

```bash
cd LLMOps/devops/gaip_gpu_operators
./run.sh                         # NVIDIA GPU Operator + Network Operator, 마스터 노드에서 1회
kubectl label node <GPU_NODE_NAME> node-role.kubernetes.io/compute=""   # GPU 노드에 compute 라벨
```

- 이 설치는 `gpu-operator/values.yaml` 의 `driver.enabled: false` 기준입니다. 즉 **드라이버를 설치하지 않으므로**
  모든 GPU 노드에서 호스트 드라이버가 먼저 동작해야 합니다(`nvidia-smi` 정상).
- `nvidia-smi` 가 실패하면 10-5절의 드라이버 점검 절차를 따릅니다.

### 5-11. EFK (`gaip_efk`) — 선택

로그 수집용입니다. `jonathan-efk` 네임스페이스에 설치되며 데이터는 `values-efk.yaml` 의 `nfs.path`
(`<NFS_PROVISIONER_EFK_PATH>`) 아래에 PVC 이름별 디렉터리로 저장됩니다. 5-1 의 EFK provisioner 가 먼저 설치되어 있어야 합니다.

```bash
cd LLMOps/devops/gaip_efk
./helm_repo_add.sh              # fluent helm 저장소 등록
./helm_upgrade_elastic.sh       # Elasticsearch 설치(또는 업그레이드)

# Elastic 파드가 모두 Running 인지 확인한 뒤 진행
kubectl -n jonathan-efk get pods

./elastic_init.sh               # 인덱스 템플릿·보존기간 정책 적용
./helm_upgrade_fluent.sh        # Fluent Bit 설치
```

> 📌 `gaip_efk/esvalues.yaml` 의 master/data/coordinating/ingest/Kibana 자원 요청과 `heapSize` 는 단일 노드에서도
> 동작하도록 낮춰져 있습니다. 로그가 많은 환경에서는 다시 올립니다.
>
> 📌 로그 조회 미들웨어(`apps/fb_log_middleware`)는 아직 설치 차트가 없어 이 절차로 설치되지 않습니다.
> 대시보드의 최근 실행 기록과 파인튜닝 시스템 로그 화면은 비어 보이며, 설치 자체는 정상입니다.

---

## 6. 🚀 플랫폼 앱 설치

### 6-1. 설치 전 확인

1. 5장의 필수 인프라(NFS provisioner, Kong, Registry, MariaDB init, Kafka, Redis, MongoDB)가 정상입니다.
2. 공통 values(`values_<서버명>.yaml`)의 placeholder 를 모두 채웠고, `src.enabled` 를 3-2절대로 정했습니다.
3. kubeconfig 를 `fb_common_app/helm/file/kube/config` 에 복사했습니다(3-7절).
4. 대부분의 앱 차트 `helm/values.yaml` 은 `LLMOps/bundles/flightbase/helm/values-individual.yaml` 을 가리키는
   **심볼릭 링크**(저장소에 링크로 커밋됨)로, 차트 기본값을 담고 있습니다(일부 차트는 일반 파일). Linux 에서 `git clone` 하면 그대로
   동작합니다. 심볼릭 링크를 지원하지 않게 체크아웃(예: `core.symlinks=false`)하면 링크가 깨지므로 다시 clone 합니다.
5. 차트 의존성(`helm/charts/`, `Chart.lock`)은 대부분 저장소에 없고, 아래 스크립트가 `helm dependency update` 로 받습니다.

### 6-2. 설치

```bash
cd LLMOps/devops

# 플랫폼 앱 21개 (common-app, dashboard, dataset, deployment, front, image, monitoring-app, notification,
#   option, resource, scheduler, user, workspace, alert-management, ingress-management, external-container,
#   collect, preprocessing, pipeline, analyzing, synthesis) → jonathan-system
./run.sh install -f ./values_<서버명>.yaml

# LLM 앱 4개 (model, playground, evaluation, data-pipeline) → jonathan-system
./run_llm.sh install -f ./values_<서버명>.yaml
```

- 두 스크립트는 `jonathan-system-image` 네임스페이스(이미지 빌드용)도 만듭니다.
- 설치 네임스페이스는 기본 `jonathan-system` 이며 환경변수 `JF_NAMESPACE` 로 바꿀 수 있습니다
  (바꾸면 공통 values 의 `global.jfb.namespace` 도 같은 값이어야 합니다).
- `install` 은 이미 있는 릴리스에서 실패합니다. 다시 적용할 때는 `upgrade` 를 씁니다.

```bash
./run.sh upgrade -f ./values_<서버명>.yaml
./run_llm.sh upgrade -f ./values_<서버명>.yaml
```

**확인**

```bash
kubectl get pods -n jonathan-system     # 주요 파드 Running
kubectl get ingress -A
```

### 6-3. 프론트(front)

기본(`global.jfb.volume.front.enabled: false`)은 프론트 이미지에 들어 있는 빌드를 서빙하므로 별도 작업이 없습니다.

체크아웃의 빌드를 서빙하는 개발 모드(`front.enabled: true`)에서는 `front.path` 에 `LLMOps/front` 절대 경로를 넣고,
호스트에서 빌드합니다. `yarn.lock` 이 yarn 4(berry) 형식이라 yarn 1 이나 npm 으로는 설치되지 않습니다 —
프론트 이미지(`LLMOps/front/Dockerfile`)와 같은 방식으로 빌드합니다.

```bash
cd LLMOps/front
corepack enable && corepack prepare yarn@4.17.1 --activate   # 버전은 front/Dockerfile 과 동일
yarn install --immutable
yarn vite build                                              # → LLMOps/front/build
```

개발 모드의 front 파드는 시작할 때 `/app/build` 를 마운트된 빌드로 자동 연결하므로, 빌드 후 브라우저를 강력 새로고침하면 반영됩니다.

---

## 7. ✔️ 플랫폼 설치 후 초기 설정

- [ ] 관리자 로그인
- [ ] 스토리지 등록 (**워크스페이스 생성 전 필수**)
- [ ] 사용자 생성
- [ ] 인스턴스(GPU/CPU 자원) 설정
- [ ] 워크스페이스 생성 · 멤버 추가
- [ ] 외부 컨테이너 manifest 확인
- [ ] (외부 컨테이너 학습을 쓸 때) 모델 가중치 사전 스테이징

### 7-1. 관리자 로그인

브라우저에서 접속 주소(NodePort 기본: `http://<노드 IP>:32080`)를 열면 로그인 화면이 나옵니다.

- 계정: `admin`
- 비밀번호: 공통 values 의 `global.jfb.settings.initRootPassword`
  (DB 에 `admin` 이 처음 만들어질 때 한 번만 적용됩니다. 기존 DB 를 재사용하면 예전 비밀번호가 유지됩니다.)

로그인이 되지 않으면 user 앱을 재시작합니다.

```bash
kubectl rollout restart deploy/jfb-app-user -n jonathan-system
kubectl get pod -n jonathan-system | grep user
```

### 7-2. 스토리지 등록 (워크스페이스 생성 전 필수)

앱 설치만으로는 워크스페이스용 StorageClass(`storage-<이름>-data-sc` / `-main-sc`)와 provisioner·exporter 가
생기지 않습니다. 스토리지를 한 번 등록해야 워크스페이스 생성 화면에 스토리지가 나타납니다.

등록값은 **공통 values 의 `global.jfb.volume.jfStorage[0]` 과 같아야 합니다.**

| 입력 | 값 | 템플릿 기본값 예 |
|---|---|---|
| 이름 | `jfStorage[0].name` | `local-nfs` |
| IP | `jfStorage[0].server` (NFS 서버 IP) | `<NFS_SERVER_IP>` |
| 마운트 포인트 | `jfStorage[0].path` | `/opt/dynamic-storage/tmp-storage` |
| 타입 | `jfStorage[0].type` | `nfs` |

> 🔴 **이름이 다르면 데이터셋 파일이 보이지 않습니다.** 플랫폼은 입력한 이름 앞에 `storage-` 를 붙여 저장하고
> (`storage-local-nfs`), 앱 차트는 values 의 `jfStorage[0].name` 으로 PVC `storage-<name>` 을 만들어 마운트합니다.
> 둘이 어긋나면 UI 목록에는 데이터셋이 보이는데 내부 파일은 비어 있는 상태가 됩니다.

**방법 A — 관리자 화면**

'스토리지 추가' 버튼은 화면에 드러나 있지 않습니다.

1. 관리자 화면 › **스토리지** 메뉴로 이동합니다.
2. 왼쪽 원형 차트 카드의 제목 **'전체 스토리지 현황'** 글자를 **10번 이상** 클릭합니다.
3. 페이지 상단의 **'스토리지'** 제목 영역을 클릭하면 스토리지 추가 창이 열립니다.
4. 위 표의 값을 입력합니다(이름 칸에는 `storage-` 없이 `local-nfs` 처럼 입력).

**방법 B — API**

```bash
POD=$(kubectl get pods -n jonathan-system --no-headers | awk '/jfb-app-resource/{print $1; exit}')
kubectl exec -n jonathan-system $POD -- curl -sS -X POST -H "Jf-User: admin" \
  -F name=local-nfs -F ip=<NFS_SERVER_IP> -F mountpoint=/opt/dynamic-storage/tmp-storage -F type=nfs \
  http://localhost:8000/api/storage
```

**확인**

```bash
kubectl get sc | grep storage-local-nfs               # storage-local-nfs-data-sc, storage-local-nfs-main-sc
kubectl get pod -n jonathan-system | grep storage-local-nfs   # provisioner(data/main) · storage-exporter Running
```

### 7-3. 사용자 생성

`사용자 > 사용자 추가` 에서 **아이디 · 비밀번호 · 이름(필수)** 을 입력하고, 필요하면 사용자 그룹·이메일·소속·직책을 입력합니다.

### 7-4. 인스턴스 설정

1. **노드** 탭에서 아래로 스크롤해 활성화된 노드를 선택하고 설정 버튼을 누릅니다.
2. 노드의 GPU/CPU 를 인스턴스 단위로 나눠 할당하도록 설정합니다(5-10 GPU Operator 가 정상이면 할당 가능한 GPU 가 표시됩니다).
3. 인스턴스의 vCPU · vRAM · 개수를 고른 뒤 유효성 검사를 실행합니다.
4. 검사가 끝나면 저장해 인스턴스를 활성화합니다. 다시 설정하려면 초기화 버튼을 씁니다.

(MIG · NVLink 등 GPU 분할/연결 구성이 필요하면 별도로 문의합니다.)

### 7-5. 워크스페이스 생성

워크스페이스 탭에서 워크스페이스를 만듭니다. 7-2 스토리지와 7-4 인스턴스가 정상이어야 목록에 나타납니다.
생성 후 **워크스페이스 상세 › 멤버(사용자)** 탭에서 7-3 의 사용자를 추가합니다.

워크스페이스마다 쿠버네티스 네임스페이스 `jonathan-system-<워크스페이스 ID>` 가 만들어지고,
`global.jfb.volume.hfModelCache` 가 설정되어 있으면 그 안에 공유 HF 캐시 PVC(`hf-model-cache-pvc`)가 함께 생깁니다.

### 7-6. 외부 컨테이너 manifest 확인

평가·양자화·프롬프트 최적화·SDS VLM 학습 등은 외부 컨테이너 manifest 로 동작합니다. **표준 manifest 는
`fb_external_container` 가 기동할 때 `apps/fb_external_container/manifests/` 의 YAML 을 자동 등록(시드)하므로
별도 작업이 필요 없습니다.** 이미 있는 `(name, version)` 은 건너뜁니다.

```bash
kubectl logs -n jonathan-system deploy/jfb-app-external-container | grep "manifest seed"
# 예(최초 기동): manifest seed: {'seeded': 11, 'paired': 1, 'skipped': 0, 'invalid': 0}
```

이 로그는 새로 등록했거나 잘못된 파일이 있을 때만 찍히므로, 이미 모두 등록된 상태에서 재시작하면 아무것도 나오지 않는 것이 정상입니다.
YAML 내용만 바꾼 경우는 기존 설치에 반영되지 않습니다 — `metadata.version` 을 올린 뒤
`kubectl rollout restart deploy/jfb-app-external-container -n jonathan-system` 합니다.

### 7-7. 모델 가중치 사전 스테이징 (외부 컨테이너 학습을 쓸 때)

외부 컨테이너 잡 파드는 공유 HF 캐시를 `/hf-cache` 에 **읽기 전용**으로 마운트하고, manifest 가 `HF_HUB_OFFLINE=1`
(폐쇄망 전제)이라 **잡 안에서는 가중치를 내려받을 수 없습니다.** 캐시에 가중치가 없으면 학습 컨테이너가
`/health` 503 으로 준비 상태에 들어가지 못하고 멈춥니다. 그래서 운영자가 미리 받아 둡니다.

```bash
cd LLMOps
# 기본 목록 = SDS VLM 학습용 2종 (openai/clip-vit-large-patch14-336, meta-llama/Llama-3.1-8B-Instruct)
devops/hf-prefetch/run.sh jonathan-system-<워크스페이스 ID>
devops/hf-prefetch/run.sh jonathan-system-<워크스페이스 ID> <추가 모델 repo id>
kubectl -n jonathan-system-<워크스페이스 ID> logs -f job/<출력된 Job 이름>
# 끝나면 스크립트가 안내하는 cleanup 명령으로 Job 과 토큰 Secret 을 지웁니다.
```

- 모든 워크스페이스의 `hf-model-cache-pvc` 는 같은 NFS 경로(`hfModelCache.path`)를 가리키므로, 워크스페이스 하나에서 받으면 공유됩니다.
- gated 모델(meta-llama)은 HF 토큰(3-5절)이 필요합니다. 스크립트가 플랫폼 네임스페이스의 `jfb-settings` 에서 읽어 대상 네임스페이스 Secret 으로만 넣습니다.
- safetensors 가 없는 저장소는 `.bin` → `model.safetensors` 로 변환하고, 비-root 잡 파드가 읽도록 권한을 보정합니다.
- 이 Job 은 `python:3.11-slim` 이미지 · PyPI · HuggingFace Hub 에 접근해야 합니다. 외부망이 전혀 없는 환경에서는
  외부망 호스트에서 `HF_HOME=<임시 경로> huggingface-cli download <repo id>` 로 받은 캐시(`hub/` 이하)를
  `hfModelCache.path` 아래로 복사하고, 같은 변환·권한 보정(`devops/hf-prefetch/run.sh` 주석 참고)을 직접 적용합니다.

<aside>
✅ 여기까지 정상적으로 진행했다면 초기 설정이 완료된 것입니다. 생성한 사용자로 로그인해 워크스페이스 목록과
대시보드(워크스페이스 화면의 `GenAI Platform` 버튼)에 들어가지는지 확인합니다.
</aside>

---

## 8. 🔄 접속 방식 · IP 변경

설치 후 접근 대역이 바뀌었거나 NodePort ↔ LoadBalancer 를 바꾸는 절차입니다. Kong 은 `helm upgrade` 로 바꿀 수 있습니다
(릴리스 `kong`, 네임스페이스 = `global.developer`).

### 8-1. NodePort → LoadBalancer(MetalLB)

1. `gaip_metallb/metallb-config.yaml` 의 `addresses` 를 수정하고 MetalLB 를 설치합니다(5-2절). 이미 설치되어 있다면
   `kubectl apply -f metallb-config.yaml` 로 주소만 반영합니다.
2. Kong 을 LoadBalancer 로 바꿉니다.

   ```yaml
   # gaip_kong/values.yaml
   global:
     jfb:
       static:
         enabled: true
         ip: <VIP>
   proxy:
     type: LoadBalancer
   ```

   ```bash
   cd LLMOps/devops/gaip_kong
   helm upgrade -n jonathan-kong kong . --values ./values.yaml
   kubectl get svc -n jonathan-kong kong-kong-proxy      # EXTERNAL-IP = <VIP>
   ```

3. 공통 values 의 `external.host: "<VIP>"`, `port: "80"`, `redirect: "true"` 로 바꾸고 앱을 업그레이드합니다.

   ```bash
   cd LLMOps/devops
   ./run.sh upgrade -f ./values_<서버명>.yaml
   ./run_llm.sh upgrade -f ./values_<서버명>.yaml
   ```

### 8-2. LoadBalancer → NodePort

1. `gaip_kong/values.yaml` 에서 `proxy.type: NodePort`, `global.jfb.static.enabled: false` 로 바꾸고
   `helm upgrade -n jonathan-kong kong . --values ./values.yaml` 합니다. HTTP 32080 / HTTPS 32443 이 열립니다.
2. 공통 values 의 `external.host: "<노드 IP>"`, `port: "32080"`, `redirect: "false"` 로 바꾸고 8-1 의 3번처럼 업그레이드합니다.
   프론트가 이 값으로 API 요청 URL 을 만들기 때문에 반드시 맞춥니다.
3. 확인:

   ```bash
   curl -I http://<노드 IP>:32080
   curl -kI https://<노드 IP>:32443     # 자체 서명 인증서면 -k
   ```

### 8-3. VIP(또는 노드 IP)만 바꾸는 경우

- MetalLB VIP: `metallb-config.yaml` 주소 → `kubectl apply -f metallb-config.yaml`, `gaip_kong/values.yaml` 의
  `global.jfb.static.ip` → Kong `helm upgrade`, 공통 values `external.host` → 앱 `upgrade`.
- NodePort 접속 주소: 공통 values `external.host` 만 바꿔 앱 `upgrade`.

> ConfigMap 값이 바뀌어도 일부 Deployment 는 자동 재시작되지 않습니다. 반영이 안 되면
> `kubectl rollout restart deploy -n jonathan-system` 로 재시작합니다.
>
> `helm upgrade` 가 실패해 Kong 을 지우고 다시 설치해야 한다면 `./run.sh uninstall -f ./values.yaml` 후
> 스크립트가 안내하는 대로 남은 PVC·PV·디렉터리를 정리하고 `./run.sh install -f ./values.yaml` 합니다.

---

## 9. 데이터를 보존한 재설치

클러스터를 다시 만들되 NFS 의 데이터(DB · 스토리지)를 살리는 경우입니다.

- **MariaDB 는 `gaip_maraidb/run.sh install` 만** 실행합니다. **`init` 은 `jonathan_llm` 을 DROP 하므로 금지**입니다.
  같은 이유로 MariaDB init 을 포함하는 `run_step2_core_infra.sh` 도 쓰지 않고, 5장의 차트별 `run.sh` 로 설치합니다.
- NFS provisioner 는 같은 PVC 이름이면 기존 디렉터리에 다시 붙습니다(`pathPattern: ${.PVC.name}`, `reclaimPolicy: Retain`).
  `values-system.yaml`·`values-efk.yaml` 의 `nfs.path` 를 이전과 같게 둡니다.
- 앱 설치 뒤 스토리지는 **새로 등록하지 않습니다.** DB 의 스토리지 행 기준으로 StorageClass·provisioner·exporter 를
  다시 만드는 리콘사일만 호출합니다(멱등).

  ```bash
  POD=$(kubectl get pods -n jonathan-system --no-headers | awk '/jfb-app-resource/{print $1; exit}')
  kubectl exec -n jonathan-system $POD -- curl -sS -X POST -H "Jf-User: admin" http://localhost:8000/api/storage/update
  ```

- 외부 컨테이너 manifest 는 DB 에 남은 등록분을 그대로 쓰고, 빠진 표준 판본만 시드됩니다.
- 관리자 비밀번호는 기존 DB 의 값이 유지됩니다(`initRootPassword` 는 적용되지 않음).

---

## 10. 문제 해결

### 10-1. 재설치 시 PV/PVC 충돌

`helm uninstall` 후 다시 설치할 때 PV·PVC·실제 디렉터리가 남아 있으면 충돌할 수 있습니다. 인프라 스크립트도
uninstall 후 `CHECK DELETE volume - pvc, pv, directory` 를 안내합니다.

```bash
kubectl get pv
kubectl get pvc -A
# ⚠️ 아래는 PVC 를 삭제합니다. 대상 네임스페이스를 반드시 다시 확인하십시오.
kubectl delete pvc --all -n <namespace>
```

`Released` 상태로 남은 PV 는 확인 후 `kubectl delete pv <pv 이름>` 으로 지웁니다.

### 10-2. 이미지 pull 실패 — containerd 레지스트리 설정

HTTP 레지스트리(예: `gaip_registry` 의 `<노드 IP>:30500`)나 사설 인증서 레지스트리에서 받을 때
`http: server gave HTTP response to HTTPS client` · `x509` 오류가 나면 **모든 노드**의 `/etc/containerd/config.toml` 에
설정을 넣고 containerd 를 재시작합니다.

containerd 1.7 기본 설정에는 `registry.configs` / `registry.mirrors` **빈 섹션이 이미 있으므로**, 파일 끝에 블록을
덧붙이면 중복 키로 파싱 오류가 납니다. 기존 섹션 **아래에 삽입**합니다.

```bash
sudo python3 - <<'PY'
import pathlib
REG = "<REGISTRY_HOST>:<PORT>"          # 예: <노드 IP>:30500
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

### 10-3. Redis AOF 손상

서버가 갑자기 멈추거나 재부팅된 뒤 Redis 파드가 AOF 파일 손상으로 기동하지 못할 수 있습니다.

```bash
kubectl get pod -n jonathan-redis
kubectl exec -it -n jonathan-redis <redis 파드> -- bash
# 데이터 경로는 /bitnami/redis/data — 손상된 AOF 파일에 대해
redis-check-aof --fix <AOF 파일>
```

복구가 어렵거나 Redis 데이터가 필요 없으면 PVC/PV 까지 지우고 다시 설치하는 편이 빠릅니다(**데이터 삭제 주의**).

```bash
cd LLMOps/devops/gaip_redis
DISABLE_AOF="yes" ./clean_reinstall.sh
```

### 10-4. EFK 오류 후 정리

아래는 EFK 데이터를 삭제합니다. 실행 전 `values-efk.yaml` 의 `nfs.path`(`<NFS_PROVISIONER_EFK_PATH>`)를 확인합니다.

```bash
# 1) Elasticsearch 릴리스 제거
helm uninstall -n jonathan-efk elasticsearch

# 2) PVC 확인·정리 (PV 가 Released 로 남을 수 있음)
kubectl get pvc,pv -A | grep -i elastic

# 3) NFS 서버에서 PVC 이름별 디렉터리 정리 — ⚠️ 영구 삭제, 운영 데이터가 있으면 수행하지 않습니다
#    (kubectl get pvc -n jonathan-efk 로 본 이름 기준. 예: data-elasticsearch-master-0, data-elasticsearch-data-0)
rm -rf <NFS_PROVISIONER_EFK_PATH>/<PVC 이름>/*

# 4) 다시 설치 후 init
cd LLMOps/devops/gaip_efk
./helm_upgrade_elastic.sh
# Elastic 파드 Running 확인 후
./elastic_init.sh && ./helm_upgrade_fluent.sh
```

EFK 파드가 `Init` 에서 멈추거나 권한 오류가 나면 EFK export 경로와 `no_root_squash` 설정(2-4절)을 확인합니다.

### 10-5. GPU 드라이버 점검

GPU Operator 설치 중 오류가 나면 먼저 각 GPU 노드에서 `nvidia-smi` 로 드라이버 상태를 확인합니다.

- `nvidia-smi: command not found` → 드라이버/유틸 미설치
- `Driver/library version mismatch` → 드라이버 버전 꼬임
- Secure Boot 활성 → 커널 모듈 로딩 차단

검증 환경 예시(A100): Driver 580.95.05 / CUDA 13.0. GPU 모델·OS·커널 조합에 따라 권장 버전이 다르므로 최종 기준은
**해당 서버에서 `nvidia-smi` 가 정상 동작하는지**입니다.

```bash
# PCI 장치 인식 — 여기서 NVIDIA 장치가 안 보이면 하드웨어 문제이므로 서버 담당자에게 문의
sudo apt-get update && sudo apt-get install -y pciutils
sudo lspci -nn | grep -i nvidia
sudo lspci -nnk | grep -A3 -i nvidia

# 새로 설치한 서버 — Ubuntu 기본 방식으로 드라이버 설치
sudo apt-get install -y ubuntu-drivers-common
ubuntu-drivers devices
sudo ubuntu-drivers autoinstall
sudo reboot

# 드라이버는 있는데 nvidia-smi 가 없을 때
dpkg -l | grep -E "nvidia-(driver|utils)"
which nvidia-smi || true
# 설치된 드라이버 버전에 맞춰 nvidia-utils-XXX 설치 (예: sudo apt-get install -y nvidia-utils-535)

# 커널 모듈 로딩 확인
lsmod | grep -i nvidia
sudo modprobe nvidia
sudo dmesg -T | grep -i nvidia | tail -n 100

# Secure Boot 확인
mokutil --sb-state

# 버전 꼬임 확인
nvidia-smi
dpkg -l | grep -i nvidia
uname -r
```

### 10-6. 자주 보는 증상

| 증상 | 확인 사항 |
|---|---|
| 앱 파드가 `ContainerCreating` 에서 멈춤 (src 볼륨) | `src.enabled: true` 인데 `<SRC_PATH>` 미설정 또는 export 누락 (3-2절) |
| 모든 파드 `Pending` | 단일 노드 taint 미제거, 노드 라벨 누락, `maxPods` 초과 (2장) |
| PVC `Pending` | NFS provisioner 미설치 또는 NFS 경로·export 오류 (2-4, 5-1) |
| `ImagePullBackOff` | 레지스트리 주소·containerd 설정 (3-4, 10-2) |
| 워크스페이스 생성 화면에 스토리지 없음 | 스토리지 미등록 (7-2) |
| 데이터셋 목록은 보이는데 파일이 비어 있음 | 스토리지 등록 이름 ≠ `jfStorage[0].name` (7-2) |
| 외부 컨테이너 학습이 `/health` 503 에서 멈춤 | HF 캐시에 가중치 없음 (7-7) |
| 자원 사용량 · GPU 지표가 비어 있음 | Prometheus 미설치 (5-9) |

<aside>
💬 위 방법으로 해결되지 않는 문제는 담당자를 통해 문의해 주세요.
</aside>
