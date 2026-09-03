# GenAI Platform (devops) 설치 가이드

이 문서는 `GenAI_Platform/devops` 아래에 포함된 **기본 인프라 차트**와 **플랫폼 앱 차트**를 현재 소스/스크립트 기준으로 설치하는 방법을 정리합니다.

## 전제 조건

- **Kubernetes**: v1.24+
- **helm**, **kubectl** 사용 가능
- 설치 권한(ClusterRole/CRD 설치 등) 보유

## 값 파일(values) 준비

### 1) 공통 values 파일 생성(앱/LLM 차트용)

`devops/run.sh`, `devops/run_llm.sh`는 공통 values 파일을 **필수로 요구**합니다.

#### 템플릿 파일 복사 및 수정

```bash
cd GenAI_Platform/devops

# 템플릿 파일을 복사하여 환경별 values 파일 생성
cp values.yaml.template values_<서버명>.yaml
# 예: cp values.yaml.template values_prod.yaml

# 템플릿 파일의 TODO 주석을 확인하며 실제 환경에 맞게 수정
# - <NFS_SERVER_IP>: NFS 서버 IP 주소
# - <EXTERNAL_HOST_IP>: 외부 접근 IP 또는 도메인
# - <SYSTEM_REGISTRY_IP>: 시스템 레지스트리 주소
# - <USER_REGISTRY_IP>: 사용자 레지스트리 주소
# - <INIT_ROOT_PASSWORD>: 초기 루트 비밀번호
# - <KAFKA_USERNAME>, <KAFKA_PASSWORD>: Kafka 인증 정보
# - <MONGODB_PASSWORD>: MongoDB 비밀번호
# - <HUGGINGFACE_TOKEN>: HuggingFace 액세스 토큰 (선택, HF 모델/private repo 사용 시 필수)
# 기타 TODO 주석이 있는 항목들 확인
```

> 📌 **HuggingFace 토큰 (`global.jfb.settings.huggingface.token`)**: HuggingFace 모델/private 레포를 사용할 경우 토큰을 입력합니다. nexus 등 오프라인 환경에서는 빈 값으로 두면 startup 시 HF login을 자동 스킵합니다. 토큰은 ConfigMap `jfb-settings`의 `HUGGINGFACE_TOKEN` 환경변수로 주입되며, 값이 변경되면 `llm_model`/`llm_playground` Pod이 자동 rollout 됩니다 (`checksum/config` annotation 적용).

#### 실행 예

```bash
cd GenAI_Platform/devops
./run.sh install -f ./values_<서버명>.yaml
./run_llm.sh install -f ./values_<서버명>.yaml
```

#### kubeconfig 준비

위 스크립트들은 kubeconfig를 아래 경로에서 찾습니다.

```bash
cp ~/.kube/config GenAI_Platform/devops/fb_common_app/helm/file/kube/config
```

### 2) 로컬/개별 인프라 차트 values 파일

인프라 차트(`gaip_*`)는 차트별로 values 파일 구조가 다릅니다.

- `gaip_nfs_provisioner/run.sh`: `-f <values.yaml>` **필수**. 현재 시스템/EFK/마커 용도로 values가 분리되어 있습니다 (`values-system.yaml`, `values-efk.yaml`, `values-marker.yaml`, `*_dev.yaml`).
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
13. **LLM Apps(선택)** (`devops/run_llm.sh`)
14. **외부 컨테이너 manifest 등록** — 아래 [외부 컨테이너 manifest 등록](#외부-컨테이너-manifest-등록-필수) 참고. **자동화되어 있지 않으므로 반드시 수동 수행**합니다.

### 권장 설치 흐름 (`run_step1/2/3` 스크립트 사용)

위 순서를 단계별로 묶어 실행하는 래퍼 스크립트가 추가되어 있습니다. **신규 환경 설치 시에는 이 흐름을 권장합니다.**

```bash
cd GenAI_Platform/devops

# Step 1 — 스토리지/네트워크 베이스 (NFS + 선택적 MetalLB)
./run_step1_infra_base.sh \
  --system ./gaip_nfs_provisioner/values-system.yaml \
  --efk    ./gaip_nfs_provisioner/values-efk.yaml \
  --metallb            # MetalLB가 필요할 때만

# Step 2 — 핵심 인프라 (Kong → Registry → MariaDB init)
./run_step2_core_infra.sh \
  --kong     ./gaip_kong/values.yaml \
  --registry ./gaip_registry/values.yaml \
  --mariadb  ./gaip_maraidb/values.yaml

# Kafka / Redis / MongoDB 는 step 스크립트로 묶여 있지 않습니다.
# 아래 "설치 예시 → 6) Kafka / Redis / MongoDB" 항목을 참고하여 개별 실행하세요.

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

`gaip_nfs_provisioner/run.sh`는 values 파일에서 `volumeName`을 읽어 namespace로 사용합니다.

```bash
cd GenAI_Platform/devops/gaip_nfs_provisioner
./run.sh install -f ./values.yaml
```

### 2) (Optional) MetalLB

`gaip_metallb`는 manifest 기반입니다.

```bash
cd GenAI_Platform/devops/gaip_metallb
./install.sh
```

### 3) Kong

`gaip_kong/run.sh`는 values 파일에서 `developer:` 값을 읽어 namespace로 사용합니다.

```bash
cd GenAI_Platform/devops/gaip_kong
./run.sh install -f ./values.yaml
```

#### 주의사항

- **helm uninstall 후 재설치** 시, PV/PVC/실제 디렉토리가 남아 있으면 충돌할 수 있습니다. 스크립트도 uninstall 후 `CHECK DELETE volume - pvc, pv, directory`를 안내합니다.

### 4) Registry

```bash
cd GenAI_Platform/devops/gaip_registry
./run.sh install -f ./values.yaml
```

#### containerd 설정(참고)

레지스트리를 insecure registry로 붙여야 하는 경우, `/etc/containerd/config.toml`에 registry 설정이 필요할 수 있습니다.

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
cd GenAI_Platform/devops/gaip_maraidb

# DB 설치 (galera)
./run.sh install

# DB 초기화 (init 차트)
./run.sh init -f ./values.yaml
```

### 6) Kafka / Redis / MongoDB

```bash
cd GenAI_Platform/devops/gaip_kafka
./run.sh install

cd ../gaip_redis
./run.sh install

cd ../gaip_mongodb
./run.sh install
```

### 7) Prometheus

`gaip_prometheus/run.sh`는 내부에서 `helm dependency build kube-prometheus-stack`를 수행하고, 설치 후 `ingress.yaml`도 적용합니다.

```bash
cd GenAI_Platform/devops/gaip_prometheus
./run.sh install
```

### 8) EFK (선택)

`gaip_efk`는 단일 `run.sh`가 아닌, 단계가 분리된 스크립트들로 구성됩니다. Elastic 클러스터가 정상 기동된 뒤에 init/Fluent를 실행하는 것이 안전합니다.

```bash
cd GenAI_Platform/devops/gaip_efk

# 1) Helm 저장소 등록
./helm_repo_add.sh

# 2) Elastic 설치
./helm_upgrade_elastic.sh

# 3) Elastic Pod이 모두 Running 인지 확인
kubectl -n efk get pods

# 4) 인덱스/유저 초기화 + Fluent 설치
./elastic_init.sh
./helm_upgrade_fluent.sh
```

> `esvalues.yaml`의 master/data/coordinating/ingest/Kibana 리소스는 2026-04-21 기준 단일 노드 환경에서도 동작 가능한 수준으로 축소되어 있습니다. 더 큰 워크로드를 다루는 환경에서는 `resources.requests`/`heapSize`를 다시 상향하세요.

### 9) GPU Operators (선택)

NVIDIA GPU 노드가 있는 환경에서만 설치합니다.

```bash
cd GenAI_Platform/devops/gaip_gpu_operators
./run.sh
```

## Platform Apps / LLM Apps 설치

### 1) Platform Apps (fb_*)

`devops/run.sh`는 `fb_common_app`, `fb_dashboard`, `fb_dataset`, ... 등 앱 차트를 `jonathan-system` namespace에 설치합니다.

```bash
cd GenAI_Platform/devops
./run.sh install -f ./values_<서버명>.yaml
```

### 2) LLM Apps (llm_model, llm_playground, llm_evaluation)

`devops/run_llm.sh`는 `llm_model/helm`, `llm_playground/helm`, `llm_evaluation/helm`을 설치합니다.

```bash
cd GenAI_Platform/devops
./run_llm.sh install -f ./values_<서버명>.yaml
```

## 외부 컨테이너 manifest 등록 (필수)

**이 단계는 자동화되어 있지 않습니다.** `fb_external_container` 차트에는 seed Job도
post-install hook도 없으므로, 앱 설치 후 manifest를 직접 등록해야 합니다.
등록하지 않으면 아래 기능들이 "manifest not found"로 실패합니다.

| manifest name | version | 원본 파일 | 이 manifest가 없으면 |
|---|---|---|---|
| `mock-convert` | `1.0.0` | `apps/convert/manifest.yaml` | 양자화·포팅(변환) |
| `evaluate-selfmetric` | `1.0.0` | `apps/evaluate/manifest.yaml` | 자동평가(BLEU/ROUGE/perplexity) |
| `evaluate-benchmark-mock` | `0.2.0` | `apps/evaluate_benchmark_mock/manifest.yaml` | 벤치마크 평가 |
| `fewshot-prompt-optimizer` | `1.0.0` | `Data_Augmentation/fewshot_prompting/manifest.yaml` | 프롬프트 최적화 |
| `eva-vlm-train` / `eva-vlm-infer` | `1.1.0` | `apps/fb_external_container/manifests/` | SDS 도메인 VLM 학습·추론 (**부팅 시 자동 시드**) |

이름/버전 기본값은 `apps/fb_utils/settings.py`의 `*_MANIFEST_NAME` / `*_MANIFEST_VERSION`
상수이며, 다른 버전을 쓰려면 해당 환경변수로 flip 합니다 (예: `SDS_MANIFEST_VERSION`).

`apps/fb_external_container/manifests/` 안의 YAML은 **부팅 시 자동 등록**됩니다
(`src/manifest/seed.py`, MariaDB 연결이 붙는 시점에 실행). 이미 있는 `(name, version)`은
건너뛰므로 재시작마다 돌아도 안전하고, 같은 `service_family` 두 짝은 자동으로 pair 등록됩니다.
파일을 추가한 뒤 `kubectl rollout restart deploy/jfb-app-external-container` 만 하면 됩니다.
레포에 없는 판본(내부 패치 이미지 등)을 쓰는 인스턴스는 `EXTERNAL_MANIFEST_SEED_DIR` 로
다른 디렉터리를 가리키거나, 아래 수동 등록을 씁니다.

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

register apps/convert/manifest.yaml
register apps/evaluate/manifest.yaml
register apps/evaluate_benchmark_mock/manifest.yaml
register Data_Augmentation/fewshot_prompting/manifest.yaml

# 등록 확인
curl -sS http://localhost:8000/api/v1/manifests
```

**hybrid 페어**(`eva-vlm-train` + `eva-vlm-infer`처럼 학습/추론이 짝인 경우)는 단건이 아니라
`POST /api/v1/manifests/pair` 로 한 번에 등록해 같은 `pair_id`로 묶습니다. 본문은
`{"manifests": [{"manifest_yaml": "..."}, {"manifest_yaml": "..."}]}` (정확히 2개).
페어는 `service_family` · `contract_version` · image identity · (infer + workload) 형태가
서로 일치해야 하며, 불일치 시 422로 거부됩니다 (SP-1 v2 §1.1).

```bash
python3 -c '
import json,sys
print(json.dumps({"manifests": [{"manifest_yaml": open(p).read()} for p in sys.argv[1:]]}))' \
  examples/external-container-manifests/eva-vlm-train.yaml \
  examples/external-container-manifests/eva-vlm-infer.yaml \
| curl -sS -X POST http://localhost:8000/api/v1/manifests/pair \
       -H 'Content-Type: application/json' --data-binary @-
```

> 같은 `(name, version)`을 다시 등록하면 409로 거부됩니다 — 버전을 올리거나 기존 항목을
> 먼저 삭제하세요.

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

