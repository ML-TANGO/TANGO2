# 📘 Tango2 GenAI Platform 설치 간소화 매뉴얼

본 문서는 **Tango2 GenAI Platform** 설치 절차를 `run_step1_infra_base.sh`, `run_step2_core_infra.sh`,
`run_step3_optional_obs.sh` 세 스크립트와 앱 설치 스크립트(`run.sh`, `run_llm.sh`)로 간소화한 표준 가이드입니다.
설치에 필요한 핵심 절차는 모두 이 문서에 들어 있습니다. 차트별 옵션·문제 해결의 상세 내용은 같은 디렉터리의
`Tango GenAI Platform 설치 매뉴얼.md` 를 참고합니다.

설치에 필요한 코드와 Helm 차트는 TANGO2 저장소에 포함되어 있습니다. 설치 대상 서버(Linux)에서 저장소를
`git clone` 으로 내려받은 뒤 `LLMOps/devops` 디렉터리에서 진행합니다.

[https://github.com/ML-TANGO/TANGO2](https://github.com/ML-TANGO/TANGO2)

---

## 📑 목차

0. 개요
1. 설치 전 준비사항
2. 공통 values 파일 준비
3. 단계형 인프라 설치 (Step 1 ~ 3)
4. 앱 설치
5. 설치 후 초기 설정
6. 문제 해결 / 복구

---

## 0. 개요

- 본 가이드는 **온라인 환경** 기준입니다. 앱 이미지는 Docker Hub 공개 이미지(`docker.io/acrylaaai/genai-platform-*`)를 받습니다.
  오프라인 설치는 이미지·차트 미러링과 내부 레지스트리 구성이 별도로 필요합니다.
- 본 매뉴얼은 Tango2 GenAI Platform 의 핵심 엔진인 **조나단(Jonathan) 프레임워크** 기반 설치 절차를 다룹니다.
  (설치 스크립트/values 의 `jfb` 는 *Jonathan Framework Base* 의 약어입니다.)
- 설치 순서:
  1) 설치 전 준비 (클러스터 · kubelet · 노드 라벨 · NFS)
  2) 공통 values · 인프라 values 준비
  3) Step 1 기반 인프라 → Step 2 코어 인프라 → Step 3 옵션 인프라
  4) 앱 설치(`run.sh`, `run_llm.sh`)
  5) 초기 설정 (스토리지 등록 · 사용자 · 워크스페이스)

---

## 1. 설치 전 준비사항 (공통)

### 1-1. 시스템 요구사항

- OS: Ubuntu 22.04.5 Jammy LTS 이상
- Kubernetes: v1.34.x 권장 (검증 v1.34.0), 컨테이너 런타임 **containerd** (검증 1.7.29), CNI Calico
- Helm 3.x, kubectl 설치 및 대상 클러스터 접근 가능
- metrics-server 설치 완료
- kubelet `maxPods: 250` (1-3절)
- NFS 서버 1대, 모든 노드에 `nfs-common` (1-5절)

> 📌 **클러스터가 아직 없다면 [CLUSTER-SETUP.md](./CLUSTER-SETUP.md) 를 먼저 수행합니다.**
> containerd · Calico · kubeadm(`maxPods: 250` 포함) · metrics-server 설치와 노드 라벨 · taint 설정, NFS export 를 다룹니다.

### 1-2. 기본 동작 검증

아래 명령이 모두 **오류 없이 출력**되어야 설치를 시작할 수 있습니다.

```bash
kubectl cluster-info
kubectl get nodes -o wide        # 모든 노드 Ready, CONTAINER-RUNTIME 이 containerd
helm version
kubectl top nodes                # metrics-server 동작 확인
kubectl config current-context   # 설치할 클러스터가 맞는지 반드시 확인
```

### 1-3. kubelet `maxPods: 250`

플랫폼·인프라 파드만으로 90개를 넘으므로 기본값 110 이면 워크스페이스 잡이 스케줄되지 않습니다.
클러스터를 새로 만들면 `CLUSTER-SETUP.md` 의 kubeadm 설정에 이미 들어 있습니다. 기존 노드는 각 노드에서 다음을 수행합니다.

```bash
sudo grep -q '^maxPods:' /var/lib/kubelet/config.yaml \
  && sudo sed -i 's/^maxPods:.*/maxPods: 250/' /var/lib/kubelet/config.yaml \
  || echo 'maxPods: 250' | sudo tee -a /var/lib/kubelet/config.yaml
sudo systemctl restart kubelet
kubectl get nodes -o custom-columns=NAME:.metadata.name,PODS:.status.capacity.pods   # 250
```

### 1-4. 노드 라벨 · taint

```bash
# DB(MariaDB·Redis·MongoDB 등) / compute(GPU) / manage(Kafka·앱) 노드 지정 — 단일 노드면 같은 노드에 모두
kubectl label node <NODE_NAME> node-role.kubernetes.io/db=""
kubectl label node <NODE_NAME> node-role.kubernetes.io/compute=""
kubectl label node <NODE_NAME> node-role.kubernetes.io/manage=""

# 단일 노드면 control-plane taint 제거 (빠뜨리면 모든 파드가 Pending)
kubectl taint nodes <NODE_NAME> node-role.kubernetes.io/control-plane:NoSchedule-
```

### 1-5. NFS 경로 생성 · export

values 에 적을 NFS 경로가 실제로 존재하고 노드 대역에 export 되어 있어야 합니다. 아래는
`values.yaml.template` 기본 경로를 쓰는 예시이며, 경로를 바꾸면 values 도 같은 값으로 맞춥니다.

| 경로 | 적는 곳 |
|---|---|
| `/opt/dynamic-storage/jf-data` | 공통 values `global.jfb.volume.jfData.path` |
| `/opt/dynamic-storage/jf-bin` | 공통 values `global.jfb.volume.jfBin.path` |
| `/opt/dynamic-storage/tmp-storage` | 공통 values `global.jfb.volume.jfStorage[0].path` (5장 스토리지 등록과 같은 값) |
| `/opt/dynamic-storage/marker-data` | 공통 values `global.jfb.volume.markerData.path` |
| `/opt/dynamic-storage/hf-model-cache` | 공통 values `global.jfb.volume.hfModelCache.path` |
| `<NFS_PROVISIONER_SYSTEM_PATH>` (예: `/opt/dynamic-storage/system`) | `gaip_nfs_provisioner/values-system.yaml` `nfs.path` |
| `<NFS_PROVISIONER_EFK_PATH>` (예: `/opt/dynamic-storage/efk`) | `gaip_nfs_provisioner/values-efk.yaml` `nfs.path` |
| `<REGISTRY_IMAGES_PATH>` (예: `/opt/dynamic-storage/registry`) | `gaip_registry/values.yaml` `volume.path` |

```bash
# 모든 노드
sudo apt-get install -y nfs-common

# NFS 서버
sudo apt-get install -y nfs-kernel-server
sudo mkdir -p /opt/dynamic-storage/{jf-data,jf-bin,tmp-storage,marker-data,hf-model-cache}
sudo mkdir -p <NFS_PROVISIONER_SYSTEM_PATH> <NFS_PROVISIONER_EFK_PATH> <REGISTRY_IMAGES_PATH>

# export — <NODE_CIDR> 는 노드 대역 (예: 10.0.0.0/24)
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
sudo exportfs -ra && sudo exportfs -v
```

- export 옵션은 템플릿이 전제하는 `rw,sync,no_root_squash,no_subtree_check` 입니다. provisioner 와 플랫폼 파드가 root 로
  하위 디렉터리를 만들기 때문에 **`no_root_squash` 가 필요**합니다(별도 `chown`/`chmod` 는 필요 없습니다).
- 소스 마운트 개발 모드(2-2절 `src.enabled: true`)면 체크아웃의 `LLMOps/apps` 절대 경로도 같은 옵션으로 export 합니다.

### 1-6. 작업 디렉터리 확인

모든 통합 스크립트는 `LLMOps/devops` 에서 실행합니다(다른 위치에서 실행하면 스크립트가 중단합니다).

```bash
cd LLMOps/devops
ls run_step1_infra_base.sh run_step2_core_infra.sh run_step3_optional_obs.sh run.sh run_llm.sh
```

### 1-7. 접속 방식 결정

Kong(API 게이트웨이) proxy 의 **기본값은 NodePort 32080(HTTP) / 32443(HTTPS)** 이며 MetalLB 가 필요 없습니다.
브라우저 접속 주소는 `http://<노드 IP>:32080` 입니다.

80/443 표준 포트로 접속해야 할 때만 MetalLB LoadBalancer 를 씁니다. 이 경우 설치 전에 다음 세 곳을 바꿉니다.

- `gaip_metallb/metallb-config.yaml`: `addresses: ["<시작 IP>-<끝 IP>"]` (또는 `["<VIP>/32"]`)
- `gaip_kong/values.yaml`: `proxy.type: LoadBalancer`, `global.jfb.static.enabled: true`, `global.jfb.static.ip: <VIP>`
- 공통 values: `settings.external.host: "<VIP>"`, `port: "80"`, `redirect: "true"`

> MetalLB L2 모드는 VIP 와 클라이언트가 **같은 서브넷**일 때만 동작합니다. 다른 서브넷이고 라우팅이 없으면 NodePort 를 씁니다.

---

## 2. 공통 values 파일 준비 (필수)

### 2-1. 템플릿 복사

```bash
cd LLMOps/devops
cp values.yaml.template values_<서버명>.yaml
```

> 📌 `values_<서버명>.yaml` 파일은 운영 IP/계정/비밀번호가 들어가므로 **저장소에 커밋하지 않습니다.**
> `LLMOps/.gitignore` 의 `/devops/values_*.yaml` 규칙이 자동으로 제외합니다.

### 2-2. 필수 항목 입력

`values_<서버명>.yaml` 에서 아래 키를 실제 환경 값으로 수정합니다(템플릿 상단 [필수 설정 체크리스트]와 같습니다).

- `global.jfb.namespace` — 기본 `jonathan-system` (그대로 두는 것을 권장)
- `global.jfb.volume.jfData.server/path` — 플랫폼 데이터 NFS
- `global.jfb.volume.jfBin.server/path`
- `global.jfb.volume.jfStorage[0].server/path/name` — 워크스페이스 스토리지 (기본 이름 `local-nfs`. 5장 스토리지 등록과 같아야 함)
- `global.jfb.volume.markerData.server/path` — 마커 미사용이어도 필요
- `global.jfb.volume.hfModelCache.server/path` — 외부 컨테이너 학습용 공유 HuggingFace 캐시
- `global.jfb.volume.src.enabled/path/server` — **반드시 선택** (아래)
- `global.jfb.settings.external.host/port/redirect` — 브라우저 접속 주소. 기본(NodePort): `host: <노드 IP>`, `port: "32080"`, `redirect: "false"`
- `global.jfb.settings.initRootPassword` — 초기 **관리자(admin) 비밀번호** (비우면 admin 이 빈 비밀번호로 생성 — 반드시 설정)
- `global.jfb.image.users.registry` — 사용자 이미지 레지스트리. Step 2 의 `gaip_registry` 를 쓰면 `<노드 IP>:30500` (`protocol: http://`)
- `global.jfb.settings.huggingface.token` — 선택 (아래 박스)

**소스 마운트 여부 (`global.jfb.volume.src`)** — 템플릿 기본값은 `enabled: true` + `path: <SRC_PATH>` 입니다.
그대로 두면 소스 볼륨 마운트가 실패해 앱 파드가 기동하지 않으므로 둘 중 하나를 고릅니다.

- **이미지에 포함된 코드로 실행 (운영 권장)**: `src.enabled: false`
- **체크아웃 소스를 마운트 (개발용)**: `src.path` 에 체크아웃의 `LLMOps/apps` 절대 경로를 넣고 그 경로를 NFS export.
  코드 수정은 이미지 재빌드 없이 `kubectl rollout restart` 로 반영됩니다.

**이미지** — 템플릿 기본값(`system.registry: docker.io` + `acrylaaai/genai-platform-*:tango_v2.0.1`)을 그대로 쓰면 됩니다.
내부 레지스트리로 바꿀 때 `image.external_container` 만은 `system.registry` 가 앞에 붙지 않으므로 레지스트리 주소를 값에 직접 넣습니다.

**비밀번호** — 여러 차트에 같은 값이 들어가야 하는 항목이 있으므로 아래 기준으로만 바꿉니다.

| 항목 | 변경 |
|---|---|
| `settings.initRootPassword` | **변경 권장.** 플랫폼에서만 쓰이고, DB 에 `admin` 이 처음 만들어질 때 한 번 적용됩니다 |
| `settings.mongoDb.password` | 바꾸려면 `gaip_mongodb/mongodb/values.yaml` 의 `auth.rootPassword` 도 **같은 값으로, Step 2 전에** 바꿉니다 |
| MariaDB · Redis 비밀번호 | values 템플릿에 키가 없고 인프라 차트와 `fb_common_app` 에 같은 값이 고정되어 있습니다. 모두 함께 바꾸지 않으면 접속이 끊기므로 **임의 변경 비권장** |
| `settings.kafka.protocol` · `sasl_*` | 미사용 (차트가 참조하지 않음) — 바꿀 필요 없음 |
| `secrets.workspace.integration.encryptionKey` | 현재 어떤 차트도 참조하지 않음 |

> 💡 **HuggingFace 토큰 (`global.jfb.settings.huggingface.token`)**
> - HuggingFace 모델/private 레포를 받을 때 사용합니다. 사내 모델 레포만 쓰면 **빈 값으로 두세요** — 기동 시 HF login 을 건너뜁니다.
> - gated 모델(예: `meta-llama/*`)을 5-7 사전 스테이징으로 받으려면 필요합니다.
> - 토큰 발급: https://huggingface.co/settings/tokens
> - 적용 경로: `values_<서버명>.yaml` → `jfb-settings` ConfigMap 의 `HUGGINGFACE_TOKEN` → `llm_model`/`llm_playground`/`fb_scheduler` 등.
> - 토큰을 바꿔 `upgrade` 하면 `checksum/config` annotation 이 있는 Pod 는 자동 rollout 됩니다.
> - ⚠️ **실제 토큰은 `values_<서버명>.yaml`(gitignore 대상)에만** 입력합니다. `values.yaml.template` 등 추적 파일에는 빈 문자열로 둡니다.

### 2-3. 인프라 values 의 placeholder 채우기

| 파일 | 채울 값 |
|---|---|
| `gaip_nfs_provisioner/values-system.yaml` | `nfs.server: <NFS_SERVER_IP>`, `nfs.path: <NFS_PROVISIONER_SYSTEM_PATH>` |
| `gaip_nfs_provisioner/values-efk.yaml` | `nfs.server: <NFS_SERVER_IP>`, `nfs.path: <NFS_PROVISIONER_EFK_PATH>` |
| `gaip_registry/values.yaml` | `volume.server: <NFS_SERVER_IP>`, `volume.path: <REGISTRY_IMAGES_PATH>` |
| `gaip_metallb/metallb-config.yaml` | MetalLB 를 쓸 때만 — `addresses: ["<시작 IP>-<끝 IP>"]` |
| `gaip_kong/values.yaml` | MetalLB 를 쓸 때만 — 1-7절 |

### 2-4. kubeconfig 복사

`run.sh`·`run_llm.sh` 는 kubeconfig 를 아래 위치에서 찾고, 없으면 중단합니다. 파일 안의 `server:` 는 파드에서 닿는
노드 IP 주소여야 합니다(`127.0.0.1` 이면 안 됨).

```bash
cd LLMOps/devops
mkdir -p ./fb_common_app/helm/file/kube
cp ~/.kube/config ./fb_common_app/helm/file/kube/config
```

---

## 3. 단계형 인프라 설치

각 단계는 반드시 **[검증 항목]** 을 확인한 뒤 다음 단계로 진행합니다.

### 3-1. 1단계: 기반 인프라 (필수)

대상: NFS Provisioner — 시스템용(`jonathan-system-sc`) **과 EFK용(`jonathan-efk-sc`)을 기본으로 함께 설치**합니다.
MetalLB 는 `--metallb` 를 줄 때만 설치합니다.

```bash
cd LLMOps/devops

# 기본 (NodePort 접속) — 시스템 + EFK NFS provisioner
./run_step1_infra_base.sh \
  --system ./gaip_nfs_provisioner/values-system.yaml \
  --efk ./gaip_nfs_provisioner/values-efk.yaml
```

옵션:
- `--efk` 를 생략해도 기본값 `./gaip_nfs_provisioner/values-efk.yaml` 로 **EFK provisioner 가 설치됩니다.**
  따라서 `values-efk.yaml` 의 placeholder 를 채워 두어야 합니다. EFK 를 전혀 쓰지 않는다면 `--efk ""` 처럼 빈 값을 주면 건너뜁니다
  (이 경우 Step 3 의 `--efk` 도 실행할 수 없습니다).
- `--metallb` — LoadBalancer(80/443) 접속을 쓸 때만 추가합니다. 실행 전에 `gaip_metallb/metallb-config.yaml` 의
  `addresses` 를 수정해야 하며, 수정하지 않으면 적용 단계에서 거부됩니다.
- `--marker ./gaip_nfs_provisioner/values-marker.yaml` — Jonathan Marker 를 쓸 때만 (`server`/`path` 를 채운 뒤).

#### [검증 항목]

```bash
kubectl get sc
kubectl get pod -n jonathan-system
kubectl get pod -n jonathan-efk
```

#### 정상 기준

- `jonathan-system-sc`, `jonathan-efk-sc` StorageClass 가 생성됨
- 두 네임스페이스의 nfs provisioner Pod 가 `Running`

#### 비정상 기준 및 즉시 조치

- StorageClass 없음: values 파일 경로·파라미터 재확인 후 재실행 (이미 설치된 릴리스는 `cd gaip_nfs_provisioner && ./run.sh uninstall -f <values>` 후)
- provisioner Pod `ContainerCreating`/오류: NFS 서버 IP·경로·export(`no_root_squash`) 확인, 노드의 `nfs-common` 설치 확인

---

### 3-2. 2단계: 코어 인프라 (필수)

대상: Kong → Registry → MariaDB(install + **init**) → Kafka → Redis → MongoDB (스크립트가 이 순서로 모두 설치합니다)

> ⚠️ 이 스크립트는 MariaDB `init` 을 항상 실행하며, init 은 `jonathan_llm` 데이터베이스를 **DROP 후 재생성**합니다.
> **신규 설치에서만** 실행합니다. 기존 DB 를 살리는 재설치는 6-6절을 따릅니다.

> 📌 **Redis 리소스 기본값**: `gaip_redis/redis-cluster/values.yaml` 의 CPU/Memory `requests` 는 단일 노드에서 파인튜닝 잡이
> 들어갈 수 있도록 실측 사용량 수준으로 낮춰져 있습니다. 자원이 넉넉하면 `resources.requests` 를 올려도 됩니다.

실행 전 확인:
- 1-4절의 노드 라벨(`db`, `manage`, `compute`)이 붙어 있어야 합니다.
- `gaip_registry/values.yaml` 의 placeholder 를 채웠습니다(2-3절).
- MongoDB 비밀번호를 바꿨다면 `gaip_mongodb/mongodb/values.yaml` 과 공통 values 가 같습니다.

#### 표준 설치 스크립트 실행

```bash
cd LLMOps/devops

# 스크립트 기본값이 아래 경로이므로, values 경로를 바꾼 경우에만 인자를 지정합니다.
./run_step2_core_infra.sh \
  --kong ./gaip_kong/values.yaml \
  --registry ./gaip_registry/values.yaml \
  --mariadb ./gaip_maraidb/values.yaml
```

- Kong 은 `gaip_kong/values.yaml` 의 `global.developer`(기본 `jonathan-kong`)를 네임스페이스·IngressClass 이름으로 씁니다.
  이 값은 공통 values 의 `settings.kong.namespace`·`settings.external.ingressClassName` 과 같아야 합니다.
- Registry 는 NodePort **30500**(HTTP)입니다. 이 레지스트리를 사용자 레지스트리로 쓰면 모든 노드 containerd 에 HTTP 레지스트리
  설정이 필요합니다(6-4절).
- MariaDB `init` 은 Galera 파드가 아직 준비되지 않았어도 init Job 이 DB 접속을 기다렸다가 진행합니다.

#### [검증 항목]

```bash
kubectl get pods -A | grep -E "kong|registry|mariadb|kafka|redis|mongo"
kubectl get svc -n jonathan-kong kong-kong-proxy     # NodePort 80:32080, 443:32443 (LoadBalancer 면 EXTERNAL-IP)
kubectl get ingressclass                              # jonathan-kong
```

#### 정상 기준

- 코어 인프라 관련 Pod 가 `Running` 또는 `Completed`
- Kong proxy · Registry 서비스가 조회됨

#### 비정상 기준 및 즉시 조치

- `ImagePullBackOff`: 레지스트리 접근·containerd 설정 확인
- `CrashLoopBackOff`: `kubectl logs -n <ns> <pod>` 로 원인 확인
- `Pending`: 노드 라벨·taint·`maxPods`·PVC 바인딩 상태 확인

---

### 3-3. 3단계: 관측/옵션

| 대상 | 필요 여부 |
|---|---|
| Prometheus (`--prometheus`) | **권장.** 플랫폼 모니터링·자원 화면이 조회합니다. 없으면 자원 사용량·GPU 지표가 비어 보입니다 |
| GPU Operators (`--gpu`) | GPU 노드가 있으면 필요. 드라이버는 설치하지 않으므로(`driver.enabled: false`) 각 GPU 노드에서 `nvidia-smi` 가 먼저 동작해야 합니다 |
| EFK (`--efk`, `--efk-init`) | 선택. 로그 조회 미들웨어 차트가 아직 없어 대시보드 최근 실행 기록·파인튜닝 시스템 로그 화면은 EFK 유무와 관계없이 비어 보입니다 |

> 📌 **EFK 설치 순서 주의**: `--efk` 만 먼저 실행해 Elastic Pod 가 모두 `Running` 인지 확인한 뒤 `--efk --efk-init` 으로
> 인덱스 초기화와 Fluent 설치를 진행합니다. EFK 데이터는 `values-efk.yaml` 의 `nfs.path` 아래에 저장됩니다.
>
> 📌 **Elasticsearch 리소스 기본값**: `gaip_efk/esvalues.yaml` 의 CPU·heapSize 는 단일 노드에서도 동작하도록 낮춰져 있습니다.

#### 표준 설치 스크립트 실행

```bash
cd LLMOps/devops

# Prometheus (helm repo 등록까지 스크립트가 수행)
./run_step3_optional_obs.sh --prometheus

# GPU Operators (GPU 노드가 있는 경우)
./run_step3_optional_obs.sh --gpu

# EFK — Elastic 설치
./run_step3_optional_obs.sh --efk
# Elastic 관련 Pod 가 Running 이 된 뒤 초기화 + Fluent
./run_step3_optional_obs.sh --efk --efk-init
```

#### [검증 항목]

```bash
kubectl get pods -A | grep -E "prometheus|grafana|nvidia|elastic|fluent|kibana"
```

#### 정상 기준

- 선택한 컴포넌트 Pod 가 `Running`
- EFK 사용 시 `--efk-init` 이후 Fluent/Elastic 관련 Pod 가 정상

#### 비정상 기준 및 즉시 조치

- EFK `Init` 멈춤/권한 오류: EFK NFS 경로와 export(`no_root_squash`) 재확인
- GPU Pod 실패: 각 GPU 노드에서 `nvidia-smi` 정상 동작 재확인

---

## 4. 앱 설치 (필수)

Step 1~2(필요 시 3) 완료 후 앱 차트를 설치합니다. 차트 의존성(`helm/charts/`)은 대부분 저장소에 없고 스크립트가
`helm dependency update` 로 받습니다.

```bash
cd LLMOps/devops
./run.sh install -f ./values_<서버명>.yaml       # 플랫폼 앱 21개 → jonathan-system
./run_llm.sh install -f ./values_<서버명>.yaml   # LLM 앱 4개 (model, playground, evaluation, data-pipeline)
```

- `install` 은 이미 있는 릴리스에서 실패합니다. 값을 바꿔 다시 적용할 때는 `upgrade` 를 씁니다
  (`./run.sh upgrade -f ...`, `./run_llm.sh upgrade -f ...`).
- 대부분의 앱 차트 `helm/values.yaml` 은 `LLMOps/bundles/flightbase/helm/values-individual.yaml` 을 가리키는 심볼릭 링크입니다(일부는 일반 파일).
  Linux 에서 `git clone` 한 체크아웃을 그대로 사용합니다.

### 4-1. 프론트 (개발 모드일 때만)

기본(`global.jfb.volume.front.enabled: false`)은 front 이미지 안의 빌드를 서빙하므로 작업이 없습니다.
체크아웃 빌드를 서빙하는 개발 모드(`front.enabled: true`, `front.path` = `LLMOps/front` 절대 경로)에서는 먼저 빌드합니다.
`yarn.lock` 이 yarn 4(berry) 형식이라 yarn 1·npm 으로는 설치되지 않습니다.

```bash
cd LLMOps/front
corepack enable && corepack prepare yarn@4.17.1 --activate   # 버전은 front/Dockerfile 과 동일
yarn install --immutable
yarn vite build
```

### [검증 항목]

```bash
kubectl get pods -n jonathan-system
kubectl get ingress -A
```

### 정상 기준

- `jonathan-system` 의 주요 Pod 가 `Running` 또는 `Completed`
- 브라우저에서 `global.jfb.settings.external.*` 주소(기본 `http://<노드 IP>:32080`)로 접속 시 로그인 화면 진입

### 비정상 기준 및 즉시 조치

- 앱 Pod 가 `ContainerCreating` 에서 멈춤: `src.enabled: true` 인데 `<SRC_PATH>` 미설정·export 누락 (2-2절)
- 로그인 불가: user 앱 재시작 후 재확인

```bash
kubectl rollout restart deploy/jfb-app-user -n jonathan-system
kubectl get pod -n jonathan-system | grep user
```

---

## 5. 설치 후 초기 설정

아래 순서로 진행합니다.
타 기관 공유/제출용 문서로 활용하는 경우, 본 문서에는 UI 이미지가 없으므로 **UI 스크린샷을 본문에 넣거나 별도 첨부**하는 것을 권장합니다.

### 5-1. 관리자 로그인

- 계정: `admin`
- 비밀번호: `values_<서버명>.yaml` 의 `global.jfb.settings.initRootPassword`
  (DB 에 `admin` 이 처음 만들어질 때만 적용 — 기존 DB 를 재사용하면 예전 비밀번호 유지)

### 5-2. 스토리지 등록 (워크스페이스 생성 전 필수)

앱 설치만으로는 워크스페이스용 StorageClass 와 provisioner·exporter 가 생기지 않습니다. 등록값은 **`global.jfb.volume.jfStorage[0]` 과 같아야** 합니다.

| 입력 | 값 | 템플릿 기본값 예 |
|---|---|---|
| 이름 | `jfStorage[0].name` | `local-nfs` |
| IP | NFS 서버 IP (`jfStorage[0].server`) | `<NFS_SERVER_IP>` |
| 마운트 포인트 | `jfStorage[0].path` | `/opt/dynamic-storage/tmp-storage` |
| 타입 | `nfs` | `nfs` |

> 🔴 **이름이 다르면 데이터셋 파일이 보이지 않습니다.** 플랫폼은 등록 이름 앞에 `storage-` 를 붙여 저장하고(`storage-<입력값>`),
> 앱 차트는 values 의 `jfStorage[0].name` 으로 PVC `storage-<name>` 을 만들어 마운트합니다. 두 값이 어긋나면
> **UI 목록에는 데이터셋이 보이는데 내부 파일은 비어 있는** 상태가 됩니다.
> 예) values 가 `name: "local-nfs"` 인데 UI 에 `local` 을 입력하면 DB 는 `storage-local`, 실제 마운트는 `storage-local-nfs` 가 되어 불일치합니다.

**방법 A — 관리자 화면** ('스토리지 추가' 버튼은 숨겨져 있습니다)
1. 관리자 화면 › **스토리지** 메뉴로 이동
2. 원형 차트 카드의 제목 **'전체 스토리지 현황'** 글자를 **10번 이상** 클릭
3. 페이지 상단 **'스토리지'** 제목 영역을 클릭 → 스토리지 추가 창이 열림
4. 위 표의 값 입력 (이름 칸에는 `storage-` 없이 입력)

**방법 B — API**

```bash
POD=$(kubectl get pods -n jonathan-system --no-headers | awk '/jfb-app-resource/{print $1; exit}')
kubectl exec -n jonathan-system $POD -- curl -sS -X POST -H "Jf-User: admin" \
  -F name=local-nfs -F ip=<NFS_SERVER_IP> -F mountpoint=/opt/dynamic-storage/tmp-storage -F type=nfs \
  http://localhost:8000/api/storage
```

등록 후 확인:

```bash
kubectl get sc | grep -E "data-sc|main-sc"                     # storage-local-nfs-data-sc / -main-sc
kubectl get pod -n jonathan-system | grep -Ei "storage|provisioner"
```

### 5-3. 사용자 생성

- 메뉴: 사용자 › 사용자 추가
- 필수 입력: 아이디, 비밀번호, 이름

### 5-4. 인스턴스/GPU 자원 활성화 (GPU 사용 시)

- 노드 탭에서 노드를 선택해 인스턴스(vCPU·vRAM·개수)를 설정하고 유효성 검사 후 저장합니다.

### 5-5. 워크스페이스 생성 및 멤버 추가

- 워크스페이스 생성 후 상세 화면에서 사용자 멤버를 할당합니다.
- 워크스페이스마다 네임스페이스 `jonathan-system-<워크스페이스 ID>` 가 생깁니다.

### 5-6. 외부 컨테이너 manifest 확인

평가·양자화·프롬프트 최적화·SDS VLM 학습용 표준 manifest 는 `fb_external_container` 가 **기동 시 자동 등록**합니다(별도 작업 없음).

```bash
kubectl logs -n jonathan-system deploy/jfb-app-external-container | grep "manifest seed"
# 예(최초 기동): manifest seed: {'seeded': 11, 'paired': 1, 'skipped': 0, 'invalid': 0}
```

이미 모두 등록된 상태에서 재시작하면 로그가 나오지 않는 것이 정상입니다.

### 5-7. 모델 가중치 사전 스테이징 (외부 컨테이너 학습을 쓸 때)

외부 컨테이너 잡은 공유 HF 캐시를 읽기 전용으로 마운트하고 `HF_HUB_OFFLINE=1` 이라 잡 안에서 가중치를 받을 수 없습니다.
미리 받아 두지 않으면 학습 컨테이너가 `/health` 503 에서 멈춥니다.

```bash
cd LLMOps
# 기본 목록 = SDS VLM 학습용 2종. 워크스페이스 하나에서 실행하면 같은 NFS 캐시를 모든 워크스페이스가 공유합니다.
devops/hf-prefetch/run.sh jonathan-system-<워크스페이스 ID>
devops/hf-prefetch/run.sh jonathan-system-<워크스페이스 ID> <추가 모델 repo id>
# 완료 후 스크립트가 안내하는 cleanup 명령으로 Job·토큰 Secret 삭제
```

- gated 모델(meta-llama)은 HF 토큰이 필요합니다(2-2절).
- 이 Job 은 `python:3.11-slim` 이미지·PyPI·HuggingFace Hub 에 접근해야 합니다. 외부망이 없으면 외부망 호스트에서
  `HF_HOME=<임시 경로> huggingface-cli download <repo id>` 로 받은 캐시를 `hfModelCache.path` 아래로 복사하고,
  `devops/hf-prefetch/run.sh` 주석의 safetensors 변환·권한(0644) 보정을 직접 적용합니다.

### 5-8. 사용자 계정 재로그인 확인

- 생성한 사용자로 로그인
- 워크스페이스 목록/대시보드 진입 확인

---

## 6. 문제 해결/복구

본 장은 운영 환경에서 발생 가능한 이슈에 대비한 **점검 및 복구 시나리오(운영 절차)** 입니다.

### 6-1. PV/PVC 잔존 정리

재설치 전 잔존 리소스를 먼저 확인합니다.

```bash
kubectl get pv
kubectl get pvc -A
```

**[주의: 데이터 유실 위험]** 아래 명령은 PVC 를 삭제하며, 스토리지 구성에 따라 데이터가 유실될 수 있습니다.
실행 전 대상 네임스페이스/리소스를 반드시 재확인하십시오.

```bash
kubectl delete pvc --all -n <namespace>
```

### 6-2. Redis AOF 복구

Redis AOF 손상 시 Pod 내부(데이터 경로 `/bitnami/redis/data`)에서 복구를 시도합니다.

```bash
kubectl exec -it -n jonathan-redis <redis 파드> -- bash
redis-check-aof --fix <AOF 파일>
```

데이터 보존이 필요 없으면 `cd devops/gaip_redis && DISABLE_AOF="yes" ./clean_reinstall.sh` 로 PVC/PV 까지 지우고 재설치합니다.

### 6-3. EFK 데이터 정리

- `values-efk.yaml` 의 `nfs.path` 를 먼저 확인한 뒤, PVC 이름별 디렉터리를 정리합니다.
- Elastic 재설치(`./run_step3_optional_obs.sh --efk`) 후 Pod 가 `Running` 이 되면 `--efk --efk-init` 을 다시 실행합니다.

### 6-4. containerd Registry 설정

HTTP 레지스트리(예: `gaip_registry` 의 `<노드 IP>:30500`)나 자체 인증서 레지스트리를 쓰면 **모든 노드**의
`/etc/containerd/config.toml` 에 설정이 필요합니다. containerd 1.7 기본 설정에는 `registry.configs`/`registry.mirrors`
빈 섹션이 이미 있으므로, 파일 끝에 덧붙이지 말고 **기존 섹션 아래에 삽입**합니다(덧붙이면 중복 키로 파싱 오류).

```toml
[plugins."io.containerd.grpc.v1.cri".registry.configs]
  [plugins."io.containerd.grpc.v1.cri".registry.configs."<REGISTRY_HOST>:<PORT>".tls]
    insecure_skip_verify = true
[plugins."io.containerd.grpc.v1.cri".registry.mirrors]
  [plugins."io.containerd.grpc.v1.cri".registry.mirrors."<REGISTRY_HOST>:<PORT>"]
    endpoint = ["http://<REGISTRY_HOST>:<PORT>"]
```

설정 후 `sudo systemctl restart containerd` 와 `sudo containerd config dump >/dev/null` 로 파싱을 확인합니다.
자동 삽입 스크립트는 `CLUSTER-SETUP.md` 4-2절에 있습니다.

### 6-5. GPU 드라이버 이슈

GPU 관련 설치 실패 시 우선 각 GPU 노드에서 다음을 확인합니다.

```bash
nvidia-smi
```

- `command not found`: 드라이버/유틸 미설치
- 버전 불일치: 드라이버 재설치 필요
- Secure Boot 이슈: 커널 모듈 로딩 차단 여부 확인 (`mokutil --sb-state`)

### 6-6. 기존 DB 를 보존한 재설치

클러스터를 다시 만들되 NFS 의 DB·스토리지 데이터를 살리는 경우입니다.

> ⚠️ **`run_step2_core_infra.sh` 를 실행하지 마십시오.** 이 스크립트는 MariaDB `install` 뒤에 항상 `init` 을 실행하고,
> init 은 `jonathan_llm` 을 무조건 DROP 후 재생성합니다.

1. Step 1 은 그대로 실행합니다(같은 `nfs.path` 를 쓰면 같은 PVC 이름의 기존 디렉터리에 다시 붙습니다).
2. Step 2 대신 차트별로 설치합니다 — **MariaDB 는 `install` 만, `init` 은 실행하지 않습니다.**

   ```bash
   cd LLMOps/devops
   (cd gaip_kong && ./run.sh install -f ./values.yaml)
   (cd gaip_registry && ./run.sh install -f ./values.yaml)
   (cd gaip_maraidb && ./run.sh install)          # init 금지
   (cd gaip_kafka && ./run.sh install)
   (cd gaip_redis && ./run.sh install)
   (cd gaip_mongodb && ./run.sh install)
   ```

3. Step 3 · 앱 설치는 동일합니다.
4. 스토리지는 **UI 에서 다시 등록하지 않습니다.** 스토리지 행은 DB 에 있고 StorageClass·provisioner 만 없는 상태이므로,
   리콘사일러를 호출하면 DB 기준으로 재생성됩니다(멱등).

   ```bash
   POD=$(kubectl get pods -n jonathan-system --no-headers | awk '/jfb-app-resource/{print $1; exit}')
   kubectl exec -n jonathan-system $POD -- \
     curl -sS -X POST -H "Jf-User: admin" http://localhost:8000/api/storage/update
   ```

5. 관리자 비밀번호는 기존 DB 값이 유지됩니다.

---

## 참고

- 본 문서는 통합 설치 스크립트 기준 운영 가이드입니다. 차트별 수동 설치·접속 방식 전환·상세 문제 해결은
  `Tango GenAI Platform 설치 매뉴얼.md` 를 참고합니다.
- 환경별 네트워크/보안 정책에 따라 values 파일은 반드시 현장 값으로 조정해야 합니다.
