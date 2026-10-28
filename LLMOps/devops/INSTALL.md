# GenAI Platform (devops) 설치 가이드

이 문서는 `LLMOps/devops` 아래에 포함된 **기본 인프라 차트**와 **플랫폼 앱 차트**를 현재 소스/스크립트 기준으로 설치하는 방법을 정리합니다.

## 전제 조건

- **Kubernetes**: v1.34.x 권장 (검증 v1.34.0)
- **helm**, **kubectl** 사용 가능
- 설치 권한(ClusterRole/CRD 설치 등) 보유
- **metrics-server** 설치 완료 (`kubectl top nodes` 가 수치를 출력)
- **kubelet `maxPods: 250`** — 플랫폼·인프라 파드만으로 90개를 넘어, 기본값 110 이면 워크스페이스 잡이
  스케줄되지 않습니다 ([CLUSTER-SETUP.md](./CLUSTER-SETUP.md) 의 KubeletConfiguration 에 포함).
- **NFS export** — values 의 볼륨 경로(`jfData`·`jfBin`·`jfStorage`·`hfModelCache`), NFS provisioner
  system/efk 경로, registry 이미지 경로를 미리 만들고 노드 대역에 export 합니다. 소스·프론트를 NFS 로
  마운트하는 개발 모드(`src.enabled`·`front.enabled`)면 체크아웃의 `LLMOps/apps`·`LLMOps/front` 도 export 합니다.
  모든 노드에 `nfs-common` 이 설치되어 있어야 합니다([CLUSTER-SETUP.md](./CLUSTER-SETUP.md) 3-4·3-5).

> 📌 **클러스터가 아직 없다면** [CLUSTER-SETUP.md](./CLUSTER-SETUP.md) 를 먼저 수행하십시오.
> containerd·CNI(Calico)·kubeadm·metrics-server 설치와 노드 라벨·taint 설정까지 다룹니다.
> 이 문서는 클러스터가 준비된 상태에서 시작합니다.

## 값 파일(values) 준비

### 1) 공통 values 파일 생성(앱/LLM 차트용)

`devops/run.sh`, `devops/run_llm.sh`는 공통 values 파일을 **필수로 요구**합니다.

#### 템플릿 파일 복사 및 수정

```bash
cd LLMOps/devops

# 템플릿 파일을 복사하여 환경별 values 파일 생성
cp values.yaml.template values_<서버명>.yaml
# 예: cp values.yaml.template values_prod.yaml

# 템플릿 상단의 [필수 설정 체크리스트] 를 따라 실제 환경에 맞게 수정
# placeholder (모두 채워야 함):
# - <NFS_SERVER_IP>: NFS 서버 IP (jfData·jfBin·jfStorage·markerData·hfModelCache·src·front 의 server)
# - <EXTERNAL_HOST_IP>: 외부 접근 IP 또는 도메인 (settings.external.host)
# - <USER_REGISTRY_IP>:<PORT>: 사용자 레지스트리 주소 (gaip_registry 사용 시 <노드 IP>:30500)
# - <SRC_PATH>: 소스 마운트 경로 (src.enabled: true 일 때만 — 아래 "소스 마운트 여부 결정" 참고)
# - <NODE_HOSTNAME>: front 를 hostPath 로 마운트할 노드 (front.enabled: true 일 때만)
# placeholder 는 아니지만 직접 정해야 하는 값 (비밀번호는 예시 기본값이 들어 있음):
# - settings.initRootPassword: 플랫폼 루트 비밀번호
# - settings.mongoDb.password: gaip_mongodb/mongodb/values.yaml 의 auth.rootPassword 와 같아야 함 (두 곳을 같이 바꿔야 한다)
# - secrets.workspace.integration.encryptionKey: 현재 차트·앱에서 읽지 않는 예약 값 (비워 둬도 됨)
# - settings.huggingface.token: 선택 (HF 모델/private repo 사용 시 필수)
# 참고: settings.kafka.protocol·sasl_* 는 미사용입니다 (cm_settings 는 JF_KAFKA_DNS 만 내보내고
#       gaip_kafka 리스너는 PLAINTEXT) — 바꿀 필요 없습니다.
```

인프라 차트 values 에도 placeholder 가 있습니다 — 설치 전에 함께 채웁니다.

- `gaip_nfs_provisioner/values-system.yaml`·`values-efk.yaml`: `<NFS_SERVER_IP>`, `<NFS_PROVISIONER_SYSTEM_PATH>`, `<NFS_PROVISIONER_EFK_PATH>`
- `gaip_registry/values.yaml`: `<NFS_SERVER_IP>`, `<REGISTRY_IMAGES_PATH>`
- `gaip_metallb/metallb-config.yaml`(MetalLB 를 쓸 때만): `<METALLB_ADDRESS_RANGE>`

#### 소스 마운트 여부 결정 (`global.jfb.volume.src`)

템플릿 기본값은 `src.enabled: true` + `path: <SRC_PATH>` 입니다. 그대로 두면 소스 볼륨 마운트가 실패해
앱 파드가 기동하지 않으므로 둘 중 하나를 고릅니다.

- **이미지에 포함된 코드로 실행**: `src.enabled: false`. 앱 이미지가 코드를 포함하고 있어 추가 작업이 없습니다.
- **체크아웃 소스를 마운트**: `src.path` 에 체크아웃의 `LLMOps/apps` 절대 경로를 넣고, 그 경로를 NFS 로
  export 합니다(앱별 하위 디렉터리가 각 파드에 마운트됨). 코드 수정은 이미지 재빌드 없이
  `kubectl rollout restart` 로 반영합니다.

> 📌 **HuggingFace 토큰 (`global.jfb.settings.huggingface.token`)**: HuggingFace 모델/private 레포를 사용할 경우 토큰을 입력합니다. nexus 등 오프라인 환경에서는 빈 값으로 두면 startup 시 HF login을 자동 스킵합니다. 토큰은 ConfigMap `jfb-settings`의 `HUGGINGFACE_TOKEN` 환경변수로 주입되며, 값이 변경되면 `llm_model`/`llm_playground` Pod이 자동 rollout 됩니다 (`checksum/config` annotation 적용).

#### 실행 예

```bash
cd LLMOps/devops
./run.sh install -f ./values_<서버명>.yaml
./run_llm.sh install -f ./values_<서버명>.yaml
```

#### kubeconfig 준비

위 스크립트들은 kubeconfig를 아래 경로에서 찾습니다.

```bash
mkdir -p LLMOps/devops/fb_common_app/helm/file/kube   # 클론에는 없는 디렉터리
cp ~/.kube/config LLMOps/devops/fb_common_app/helm/file/kube/config
```

### 2) 로컬/개별 인프라 차트 values 파일

인프라 차트(`gaip_*`)는 차트별로 values 파일 구조가 다릅니다.

- `gaip_nfs_provisioner/run.sh`: `-f <values.yaml>` **필수**. 현재 시스템/EFK/마커 용도로 values가 분리되어 있습니다 (`values-system.yaml`, `values-efk.yaml`, `values-marker.yaml`). 환경별 `values-*_dev.yaml` 은 gitignore 대상이라 클론에는 없습니다.
- `gaip_kong/run.sh`: `-f <values.yaml>` **필수** (`developer:` 값을 namespace로 사용)
- `gaip_registry/run.sh`: `-f <values.yaml>` **필수**
- `gaip_maraidb/run.sh`: `install`은 기본 값으로 설치, `init -f <values.yaml>`은 **values 필요**
- `gaip_kafka/run.sh`: 기본적으로 `values.yaml`을 사용(스크립트 내부 고정)
- `gaip_redis/run.sh`: 기본 설정으로 설치(스크립트 내부 고정). 단일 노드 환경에서도 `redis-cluster` 차트를 사용합니다.
- `gaip_mongodb/run.sh`: 기본 설정으로 설치(스크립트 내부 고정)
- `gaip_prometheus/run.sh`: 스크립트 내부 `value.yaml` 사용 + `helm dependency build kube-prometheus-stack` 수행
- `gaip_efk/`: `run.sh` 단일 진입점 대신 `helm_repo_add.sh` → `helm_upgrade_elastic.sh` → (Elastic Pod Running 확인) → `elastic_init.sh` → `helm_upgrade_fluent.sh` 순서로 분리되어 있습니다.
- `gaip_gpu_operators/run.sh`: 인자 없이 실행. NVIDIA GPU 노드가 있는 경우에만 필요합니다.

> **2026-04-21 기준 기본 리소스 조정**: `gaip_redis/redis-cluster/values.yaml` 와 `gaip_efk/esvalues.yaml` 의 CPU/메모리 request 가 실측 사용량 수준으로 축소되었습니다 (단일 노드 환경에서 파인튜닝 admission 거부 완화 목적). 별도 노드 자원 여유가 충분한 클러스터에서 더 큰 워크로드를 받게 하려면 두 values 의 `resources.requests` 를 환경에 맞게 상향 조정하세요.

## 설치 순서(권장)

아래 순서는 `devops`에 포함된 기본 차트(스토리지/네트워크/DB/메시징/모니터링) 의존성을 기준으로 정리한 권장 순서입니다.

1. **NFS Provisioner** (`gaip_nfs_provisioner`) — system / efk / (선택) marker
2. **(Optional) MetalLB** (`gaip_metallb`)
3. **Kong** (`gaip_kong`)
4. **Registry** (`gaip_registry`)
5. **MariaDB (run → init)** (`gaip_maraidb`)
6. **Kafka** (`gaip_kafka`)
7. **Redis** (`gaip_redis`)
8. **MongoDB** (`gaip_mongodb`)
9. **(Optional) Prometheus** (`gaip_prometheus`)
10. **(Optional) EFK** (`gaip_efk`) — Elastic 설치 → Pod Running 확인 → init/Fluent 설치
11. **(Optional) GPU Operators** (`gaip_gpu_operators`) — NVIDIA GPU 노드가 있는 경우
12. **Platform Apps** (`devops/run.sh`)
13. **LLM Apps** (`devops/run_llm.sh`) — 모델·배포/추론·평가·데이터 파이프라인 메뉴의 백엔드
14. **외부 컨테이너 manifest 확인** — 표준 판본은 앱 기동 시 자동 등록됩니다.
    아래 [외부 컨테이너 manifest 등록](#외부-컨테이너-manifest-등록) 참고.

### 권장 설치 흐름 (`run_step1/2/3` 스크립트 사용)

위 순서를 단계별로 묶어 실행하는 래퍼 스크립트가 추가되어 있습니다. **신규 환경 설치 시에는 이 흐름을 권장합니다.**

```bash
cd LLMOps/devops

# Step 1 — 스토리지/네트워크 베이스 (NFS + 선택적 MetalLB)
#   values-system.yaml·values-efk.yaml 의 placeholder 를 먼저 채웁니다.
./run_step1_infra_base.sh \
  --system ./gaip_nfs_provisioner/values-system.yaml \
  --efk    ./gaip_nfs_provisioner/values-efk.yaml
# MetalLB 가 필요할 때만(기본 Kong NodePort 면 불필요) 위 명령 끝에 `--metallb` 를 붙입니다.
#   먼저 gaip_metallb/metallb-config.yaml 의 <METALLB_ADDRESS_RANGE> 를 수정해야 합니다 —
#   그대로 두면 적용 단계에서 거부되어 step1 이 중단됩니다.

# Step 2 — 핵심 인프라 (Kong → Registry → MariaDB install+init → Kafka → Redis → MongoDB)
#   ⚠️ MariaDB init 이 jonathan_llm 을 DROP 후 재생성합니다 — 신규 설치에서만 실행하세요.
./run_step2_core_infra.sh \
  --kong     ./gaip_kong/values.yaml \
  --registry ./gaip_registry/values.yaml \
  --mariadb  ./gaip_maraidb/values.yaml

# Step 3 — 선택 옵저버빌리티 / GPU
./run_step3_optional_obs.sh --prometheus
./run_step3_optional_obs.sh --efk           # Elastic 설치만
# Elastic Pod이 모두 Running 된 뒤
./run_step3_optional_obs.sh --efk --efk-init   # Elastic init + Fluent
./run_step3_optional_obs.sh --gpu            # GPU 노드가 있는 경우만
```

> 각 스크립트는 모두 `devops/` 디렉터리에서 실행해야 합니다. 옵션을 생략하면 default values 파일을 사용합니다.

## 설치 예시

### 1) NFS Provisioner

`gaip_nfs_provisioner/run.sh`는 values 파일에서 `volumeName`을 읽어 namespace로 사용합니다(릴리스명 `<volumeName>-sc`).
시스템용(`values-system.yaml` → `jonathan-system-sc`)과 EFK용(`values-efk.yaml` → `jonathan-efk-sc`) 두 개를 설치합니다.
두 파일의 `<NFS_SERVER_IP>`·`<NFS_PROVISIONER_SYSTEM_PATH>`·`<NFS_PROVISIONER_EFK_PATH>` 를 먼저 채우고,
그 경로를 NFS 서버에서 export 해 둡니다. (기본 `values.yaml` 은 `volumeName`·`server`·`path`·`storageClass.name` 이
모두 비어 있어 그대로는 쓸 수 없습니다.)

```bash
cd LLMOps/devops/gaip_nfs_provisioner
./run.sh install -f ./values-system.yaml
./run.sh install -f ./values-efk.yaml
```

### 2) (Optional) MetalLB

`gaip_metallb`는 manifest 기반입니다. 기본 Kong proxy 는 NodePort(32080/32443)라 **MetalLB 가 필요 없습니다** —
80/443 을 LoadBalancer 로 쓸 때만 설치합니다(아래 Kong 주의사항 참고).

`install.sh` 는 `metallb-config.yaml` 을 그대로 `kubectl create` 하므로, 실행 전에 `addresses` 의
`<METALLB_ADDRESS_RANGE>` 를 실제 주소 대역(리스트)으로 바꿉니다. 수정하지 않으면 적용 단계에서 거부됩니다.

```bash
cd LLMOps/devops/gaip_metallb
vi metallb-config.yaml     # addresses: ["<시작 IP>-<끝 IP>"] 형태로 수정
./install.sh
```

### 3) Kong

`gaip_kong/run.sh`는 values 파일에서 `developer:` 값을 읽어 namespace로 사용합니다.

```bash
cd LLMOps/devops/gaip_kong
./run.sh install -f ./values.yaml
```

#### 주의사항

- 기본 proxy 는 **NodePort 32080(HTTP)/32443(HTTPS)** 입니다(MetalLB 불필요). 공통 values 의
  `settings.external.port: "32080"`·`redirect: "false"` 와 짝입니다. MetalLB 로 80/443 을 쓰려면
  `gaip_kong/values.yaml` 의 `proxy.type: LoadBalancer`·`global.jfb.static.enabled: true`(+ip) 로 바꾸고
  external.port `"80"`·redirect `"true"` 로 맞춥니다.
- **helm uninstall 후 재설치** 시, PV/PVC/실제 디렉토리가 남아 있으면 충돌할 수 있습니다. 스크립트도 uninstall 후 `CHECK DELETE volume - pvc, pv, directory`를 안내합니다.

### 4) Registry

```bash
cd LLMOps/devops/gaip_registry
./run.sh install -f ./values.yaml
```

#### containerd 설정(참고)

레지스트리를 insecure registry로 붙여야 하는 경우, `/etc/containerd/config.toml`에 registry 설정이 필요할 수 있습니다.
기본 설정 파일에는 `registry.configs`·`registry.mirrors` 헤더가 이미 있으므로 **파일 끝에 덧붙이지 말고 기존 헤더 아래에
하위 블록만 넣습니다**(헤더가 두 번 나오면 containerd 가 설정을 읽지 못합니다). 자세한 절차는 [CLUSTER-SETUP.md](./CLUSTER-SETUP.md) 4-2.

```text
  [plugins."io.containerd.grpc.v1.cri".registry.configs]
    [plugins."io.containerd.grpc.v1.cri".registry.configs."$REGISTRYIP:$REGISTRYPORT"]
      [plugins."io.containerd.grpc.v1.cri".registry.configs."$REGISTRYIP:$REGISTRYPORT".tls]
        ca_file = ""
        cert_file = ""
        insecure_skip_verify = true
        key_file = ""

  [plugins."io.containerd.grpc.v1.cri".registry.mirrors]
    [plugins."io.containerd.grpc.v1.cri".registry.mirrors."$REGISTRYIP:$REGISTRYPORT"]
      endpoint = ["http://$REGISTRYIP:$REGISTRYPORT"]
```

### 5) MariaDB (run → init)

```bash
cd LLMOps/devops/gaip_maraidb

# DB 설치 (galera)
./run.sh install

# DB 초기화 (init 차트) — jonathan_llm 을 DROP 후 재생성하므로 신규 설치에서만
./run.sh init -f ./values.yaml
```

### 6) Kafka / Redis / MongoDB

`run_step2_core_infra.sh` 를 썼다면 이미 설치되어 있습니다. 개별 설치할 때만 실행합니다.

```bash
cd LLMOps/devops/gaip_kafka
./run.sh install

cd ../gaip_redis
./run.sh install

cd ../gaip_mongodb
./run.sh install
```

### 7) Prometheus

`gaip_prometheus/run.sh`는 내부에서 `helm dependency build kube-prometheus-stack`를 수행하고, 설치 후 `ingress.yaml`도 적용합니다.

```bash
cd LLMOps/devops/gaip_prometheus
# 처음 설치하는 호스트면 의존 차트 저장소를 먼저 등록합니다 (run_step3_optional_obs.sh --prometheus 는 자동 수행)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
./run.sh install
```

### 8) EFK (선택)

`gaip_efk`는 단일 `run.sh`가 아닌, 단계가 분리된 스크립트들로 구성됩니다. Elastic 클러스터가 정상 기동된 뒤에 init/Fluent를 실행하는 것이 안전합니다.

```bash
cd LLMOps/devops/gaip_efk

# 1) Helm 저장소 등록
./helm_repo_add.sh

# 2) Elastic 설치
./helm_upgrade_elastic.sh

# 3) Elastic Pod이 모두 Running 인지 확인
kubectl -n jonathan-efk get pods

# 4) 인덱스/유저 초기화 + Fluent 설치
./elastic_init.sh
./helm_upgrade_fluent.sh
```

> `esvalues.yaml`의 master/data/coordinating/ingest/Kibana 리소스는 2026-04-21 기준 단일 노드 환경에서도 동작 가능한 수준으로 축소되어 있습니다. 더 큰 워크로드를 다루는 환경에서는 `resources.requests`/`heapSize`를 다시 상향하세요.

> `elastic_init.sh` 는 날짜별 인덱스 템플릿과 보존기간 정책(`retention_setup.sh`)까지 적용합니다.
> 로그 조회 미들웨어(`apps/fb_log_middleware`)는 아직 설치 차트가 없어 이 가이드로 설치되지 않습니다 —
> 대시보드의 최근 실행 기록과 파인튜닝 시스템 로그 화면은 비어 보입니다(설치는 정상 진행).

### 9) GPU Operators (선택)

NVIDIA GPU 노드가 있는 환경에서만 설치합니다.

```bash
cd LLMOps/devops/gaip_gpu_operators
./run.sh
```

## Platform Apps / LLM Apps 설치

### 1) Platform Apps (fb_*)

`devops/run.sh`는 `fb_common_app`, `fb_dashboard`, `fb_dataset`, ... 등 앱 차트를 `jonathan-system` namespace에 설치합니다.

```bash
cd LLMOps/devops
./run.sh install -f ./values_<서버명>.yaml
```

### 2) LLM Apps (llm_model, llm_playground, llm_evaluation, llm_data_pipeline)

`devops/run_llm.sh`는 `llm_model/helm`, `llm_playground/helm`, `llm_evaluation/helm`,
`llm_data_pipeline/helm` 을 설치합니다.

```bash
cd LLMOps/devops
./run_llm.sh install -f ./values_<서버명>.yaml
```

### 3) 프론트(front)

기본(`global.jfb.volume.front.enabled: false`)은 front 이미지에 들어 있는 빌드를 서빙하므로 별도 작업이 없습니다.
체크아웃의 빌드를 서빙하는 개발 모드(`front.enabled: true`)면 먼저 빌드합니다(yarn 만 사용, npm 금지).
`yarn.lock` 이 yarn 4(berry) 형식이라 yarn 1 로는 설치되지 않습니다 — 프론트 이미지(`front/Dockerfile`)와 같은 방식으로 빌드합니다.

```bash
cd LLMOps/front
corepack enable && corepack prepare yarn@4.17.1 --activate && yarn install --immutable && yarn vite build
```

ETRI 로그인 브랜딩(`VITE_REACT_APP_BRAND=tango`)은 `configs/app-config/vite-env/.env.production` 에 들어 있습니다.

### 4) 스토리지 등록 (워크스페이스 생성 전 필수)

앱 설치만으로는 워크스페이스용 StorageClass(`storage-<name>-data-sc`/`-main-sc`)와 provisioner·exporter 가
생기지 않습니다. 관리자 화면의 스토리지 추가 또는 API 로 등록합니다. 이름·경로·서버는 values 의
`global.jfb.volume.jfStorage[0]` 과 같은 값을 씁니다(같은 이름의 PVC 는 common-app 이 이미 만들어 둡니다).

```bash
POD=$(kubectl get pods -n jonathan-system --no-headers | awk '/jfb-app-resource/{print $1; exit}')
kubectl exec -n jonathan-system $POD -- curl -sS -X POST -H "Jf-User: <관리자 계정>" \
  -F name=<jfStorage name> -F ip=<NFS_SERVER_IP> -F mountpoint=<jfStorage path> -F type=nfs \
  http://localhost:8000/api/storage
```

## 외부 컨테이너 manifest 등록

**표준 판본은 부팅 시 자동 등록되므로 별도 작업이 필요 없습니다.**
`apps/fb_external_container/manifests/` 안의 YAML 을 `fb_external_container` 가
기동하면서 시드합니다(`src/manifest/seed.py`, MariaDB 연결이 붙는 시점에 실행).
이미 있는 `(name, version)` 은 건너뛰므로 재시작마다 돌아도 안전하고(대신 **내용만 바꾼 YAML 은 기존 설치에
반영되지 않습니다** — 버전을 올리거나 기존 행을 지운 뒤 재시작합니다),
같은 `service_family` 두 짝은 자동으로 pair 등록됩니다.

기동 로그에서 결과를 확인할 수 있습니다. 이 로그는 새로 시드했거나(`seeded`) 잘못된 파일(`invalid`)이
있을 때만 찍히므로, 이미 모두 등록된 상태에서 재시작하면 아무것도 나오지 않는 것이 정상입니다.

```bash
kubectl logs -n jonathan-system deploy/jfb-app-external-container | grep "manifest seed"
# 예(최초 기동): manifest seed: {'seeded': 11, 'paired': 1, 'skipped': 0, 'invalid': 0}
```

자동 시드되는 판본은 다음과 같습니다.

| manifest name | version | 이 manifest가 없으면 |
|---|---|---|
| `convert-llamacpp` | `1.1.3` | 양자화·포팅(변환) |
| `evaluate-selfmetric` | `1.0.0` | 자동평가(BLEU/ROUGE/perplexity) |
| `evaluate-lmeval` / `evaluate-lmeval-code` | `0.1.2` | 벤치마크 평가(lm-eval 실채점) |
| `evaluate-benchmark-mock` | `0.2.0` | 벤치마크 평가(mock) |
| `evaluate-logickor` / `evaluate-logickor-judge` | `0.1.0` / `0.2.5` | LogicKor 평가 |
| `evaluate-intent` | `0.2.5` | 의도분류 평가 |
| `fewshot-prompt-optimizer` | `1.0.0` | 프롬프트 최적화 |
| `eva-vlm-train` / `eva-vlm-infer` | `1.1.0` | SDS 도메인 VLM 학습·추론 |

플랫폼이 어느 manifest 에 바인딩할지는 `apps/fb_utils/settings.py` 의
`*_MANIFEST_NAME` / `*_MANIFEST_VERSION` 상수가 정하며, 환경변수로 덮을 수 있습니다.
`llm_model` 차트는 `CONVERT_MANIFEST_NAME=convert-llamacpp` 와
`SDS_MANIFEST_NAME=eva-vlm-train` 을 템플릿에서 명시 지정합니다
(`devops/llm_model/helm/templates/deployment.yaml`). SDS 학습 manifest 버전은
values 의 `global.jfb.sds_manifest_version` 으로 바꿉니다(기본 `1.1.0`).

**수동 등록이 필요한 경우** — 레포에 없는 판본(내부 패치 이미지 등)을 쓰는 인스턴스뿐입니다.
`EXTERNAL_MANIFEST_SEED_DIR` 로 다른 시드 디렉터리를 가리키거나, 아래 절차로 직접 등록합니다.
시드 디렉터리에 YAML 을 추가한 뒤에는
`kubectl rollout restart deploy/jfb-app-external-container` 만 하면 됩니다.

### 모델 가중치 사전 스테이징 (외부 컨테이너 학습에 필수)

manifest 를 등록해도 **가중치가 공유 HF 캐시에 없으면 학습이 못 돕니다.** 잡 파드의
`/hf-cache` 는 RO 마운트이고 manifest env 가 `HF_HUB_OFFLINE=1`(폐쇄망 전제)이라
런타임에 내려받을 수 없기 때문입니다 — 이 단계를 빼면 파트너 컨테이너가
`model_loaded:false` → `/health` 503 으로 readiness 를 통과하지 못해 교착합니다.

공유 캐시 PVC(`hf-model-cache-pvc`)는 워크스페이스를 만들 때 values 의 `global.jfb.volume.hfModelCache` 로
워크스페이스 네임스페이스마다 자동 생성됩니다(값이 비면 생성되지 않아 외부 잡이 FailedMount 로 멈춥니다).
이 기능 이전에 만든 워크스페이스에는 생기지 않으므로, 그 네임스페이스에는 같은 이름의 PVC 를 직접 만들거나
워크스페이스를 다시 만듭니다.

```bash
# 워크스페이스 네임스페이스(<플랫폼 ns>-<워크스페이스 ID>, 예: jonathan-system-2) 하나를 지정합니다.
# 모든 워크스페이스의 hf-model-cache-pvc 는 같은 NFS 경로(hfModelCache.path)를 가리키므로 한 번이면 됩니다.
# 기본 목록 = SDS VLM 학습용 2종 (openai/clip-vit-large-patch14-336, meta-llama/Llama-3.1-8B-Instruct)
devops/hf-prefetch/run.sh jonathan-system-<워크스페이스 ID>
devops/hf-prefetch/run.sh jonathan-system-<워크스페이스 ID> <추가-모델-repo-id>
```

스크립트가 함께 처리하는 것(전부 실제로 밟은 함정입니다):

- gated repo(meta-llama)용 토큰을 플랫폼 ns `jfb-settings` 에서 읽어 대상 ns Secret 으로만 주입
- 워크스페이스 ns 의 ResourceQuota 대응(limits 명시 없으면 파드 생성 거부)
- **safetensors 보정** — `openai/clip-vit-large-patch14-336` 처럼 업스트림에 safetensors 가
  없는 저장소는 `.bin` → `model.safetensors` 로 변환(`weights_only=True`). 파트너 컨테이너가
  `from_pretrained(..., use_safetensors=True)` 로 부르기 때문
- **권한 보정(0644)** — 잡 파드는 차트 기본값이 비-root(UID 1000)라 0600 파일을 못 읽고,
  safetensors 가 그 권한 오류를 `FileNotFoundError` 로 표면화해 오진을 유발함

끝나면 안내되는 cleanup 명령으로 Job 과 토큰 Secret 을 지웁니다.

나머지 manifest 등록 방법 — BFF(`jfb-app-external-container`)에 직접 POST 합니다.
등록 API는 Kong/`llm_model`로 프록시되지 않습니다 (`GET /api/external/manifests`는
조회 전용) — 따라서 port-forward 또는 클러스터 내부에서 호출해야 합니다.

요청 본문은 raw YAML이 아니라 **JSON envelope** `{"manifest_yaml": "<YAML 전문>"}` 입니다
(`apps/fb_external_container/src/api/manifest_router.py`의 `ManifestEnvelope`).

```bash
# Service 포트는 80, 컨테이너 포트는 8000
kubectl -n jonathan-system port-forward deploy/jfb-app-external-container 8000:8000 &

# 단건 등록 (YAML 파일 → JSON envelope 변환은 python 으로)
register() {
  python3 -c 'import json,sys; print(json.dumps({"manifest_yaml": open(sys.argv[1]).read()}))' "$1" \
  | curl -sS -X POST http://localhost:8000/api/v1/manifests \
         -H 'Content-Type: application/json' --data-binary @- ; echo "  <- $1"
}

# 경로는 LLMOps/ 기준. 레포의 표준 판본(apps/convert/manifest.yaml 등)은 이미 자동 시드되어
# 있으므로 다시 등록하면 409 입니다 — 레포에 없는 manifest 만 등록합니다.
register <사용자 manifest>.yaml

# 등록 확인
curl -sS http://localhost:8000/api/v1/manifests
```

**hybrid 페어**(`eva-vlm-train` + `eva-vlm-infer`처럼 학습/추론이 짝인 경우)는 단건이 아니라
`POST /api/v1/manifests/pair` 로 한 번에 등록해 같은 `pair_id`로 묶습니다. 본문은
`{"manifests": [{"manifest_yaml": "..."}, {"manifest_yaml": "..."}]}` (정확히 2개).
페어는 `service_family` · `contract_version` · image identity · (infer + workload) 형태가
서로 일치해야 하며, 불일치 시 422로 거부됩니다.
표준 `eva-vlm-train`/`eva-vlm-infer` 페어(`1.1.0`)는 이미 자동 시드되므로 다시 등록할 필요가 없습니다
(`examples/external-container-manifests/` 의 두 파일은 작성 양식 참고용 `1.0.0` 예시입니다).

```bash
# 경로는 LLMOps/ 기준
python3 -c '
import json,sys
print(json.dumps({"manifests": [{"manifest_yaml": open(p).read()} for p in sys.argv[1:]]}))' \
  <사용자 학습 manifest>.yaml \
  <사용자 추론 manifest>.yaml \
| curl -sS -X POST http://localhost:8000/api/v1/manifests/pair \
       -H 'Content-Type: application/json' --data-binary @-
```

> 같은 `(name, version)`을 다시 등록하면 409로 거부됩니다 — 버전을 올리거나 기존 항목을
> 먼저 삭제하세요.

## 데이터를 보존한 재설치

클러스터를 다시 만들되 NFS 데이터(DB·스토리지)를 살리는 경우의 차이입니다.

> ⚠️ **`run_step2_core_infra.sh` 를 실행하지 마십시오.** 이 스크립트는 MariaDB `install` 뒤에 항상
> `init` 까지 실행하고, init(`mariadb-init/file/check.py`)은 `jonathan_llm` 을 무조건 DROP 후 재생성합니다.
> Kong·Registry·Kafka·Redis·MongoDB 는 [설치 예시](#설치-예시)의 개별 `run.sh` 로 설치합니다.

- MariaDB 는 `gaip_maraidb/run.sh install` 만 실행합니다. **`init` 은 `jonathan_llm` 을 DROP 하므로 금지**입니다.
- NFS provisioner 는 같은 PVC 이름이면 기존 디렉터리에 다시 붙습니다(`pathPattern: ${.PVC.name}`, Retain).
- 앱 설치 뒤 스토리지는 새로 등록하지 않고 리콘사일만 합니다: 위 스토리지 등록 예시와 같은 파드에서
  `curl -sS -X POST -H "Jf-User: <관리자 계정>" http://localhost:8000/api/storage/update`
  (DB 의 storage 행 기준으로 StorageClass·provisioner·exporter 를 다시 만듭니다).
- manifest 는 DB 에 남은 등록분이 그대로 쓰이고, 시드가 빠진 표준 판본만 채웁니다.

> **DB 테이블**: manifest는 `msa_jfb.external_container_manifest`에 저장되며, 이 테이블은
> `gaip_maraidb` init 스키마(5단계)에 포함되어 있으므로 별도 마이그레이션이 필요 없습니다.
> 신규 설치에서는 `apps/*/migrations/*.sql`을 실행하지 않아도 됩니다 — 해당 DDL은 모두
> `mariadb-init/file/schema.sql` · `schema_llm.sql`에 반영되어 있습니다.
> (이미 운영 중인 클러스터에 한해, 개별 migration 파일을 수동 적용합니다.
> ⚠️ 라이브 클러스터에서 `gaip_maraidb/run.sh init`을 재실행하면 `jonathan_llm`이
> **DROP** 되므로 절대 재실행하지 마세요.)

## values.yaml 항목 정리(참고)

### 공통 values 파일 (values.yaml.template)

`devops/values.yaml.template` 파일에는 다음 주요 섹션이 포함되어 있습니다:

- **`global.jfb.namespace`**: 기본 네임스페이스
- **`global.jfb.volume.*`**: 볼륨 설정 (jfData, jfBin, jfStorage, src, front 등)
- **`global.jfb.settings.*`**: 앱 설정 (db, redis, kafka, mongodb, monitoring 등)
- **`global.jfb.image.*`**: 이미지 레지스트리 및 이미지 태그 설정
- **`global.jfb.dir.*`**: 디렉토리 매핑
- **`global.jfb.name.*`**: Helm release 이름

템플릿 파일의 TODO 주석을 따라 실제 환경에 맞게 수정하세요.

### 인프라 차트별 values 파일

인프라 차트는 각각 독립적인 values 파일 구조를 가집니다:

- **`gaip_nfs_provisioner`**: `nfs.server`, `nfs.path`, `nfs.volumeName`, `storageClass.name`
- **`gaip_kong`**: `global.developer`, `global.jfb.static.*`, `global.jfb.storageClass.*`, `global.jfb.volume.*`
- **`gaip_registry`**: `namespace`, `service.*`, `volume.*`
- **`gaip_maraidb (init)`**: `global.jfb.namespace`, `global.jfb.settings.db.*`, `global.jfb.image.*`

각 차트의 `values.yaml` 파일을 참고하여 설정하세요.

