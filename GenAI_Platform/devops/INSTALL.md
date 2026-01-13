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
# 기타 TODO 주석이 있는 항목들 확인
```

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

인프라 차트(`aaai_*`)는 차트별로 values 파일 구조가 다릅니다.

- `aaai_nfs_provisioner/run.sh`: `-f <values.yaml>` **필수**
- `aaai_kong/run.sh`: `-f <values.yaml>` **필수** (`developer:` 값을 namespace로 사용)
- `aaai_registry/run.sh`: `-f <values.yaml>` **필수**
- `aaai_maraidb/run.sh`: `install`은 기본 값으로 설치, `init -f <values.yaml>`은 **values 필요**
- `aaai_kafka/run.sh`: 기본적으로 `values.yaml`을 사용(스크립트 내부 고정)
- `aaai_redis/run.sh`, `aaai_mongodb/run.sh`: 기본 설정으로 설치(스크립트 내부 고정)
- `aaai_prometheus/run.sh`: 스크립트 내부 `value.yaml` 사용 + `helm dependency build kube-prometheus-stack` 수행

## 설치 순서(권장)

아래 순서는 `devops`에 포함된 기본 차트(스토리지/네트워크/DB/메시징/모니터링) 의존성을 기준으로 정리한 권장 순서입니다.

1. **NFS Provisioner** (`aaai_nfs_provisioner`)
2. **(Optional) MetalLB** (`aaai_metallb`)
3. **Kong** (`aaai_kong`)
4. **Registry** (`aaai_registry`)
5. **MariaDB (run → init)** (`aaai_maraidb`)
6. **Kafka** (`aaai_kafka`)
7. **Redis** (`aaai_redis`)
8. **MongoDB** (`aaai_mongodb`)
9. **Prometheus** (`aaai_prometheus`)
10. **Platform Apps** (`devops/run.sh`)
11. **LLM Apps(선택)** (`devops/run_llm.sh`)

## 설치 예시

### 1) NFS Provisioner

`aaai_nfs_provisioner/run.sh`는 values 파일에서 `volumeName`을 읽어 namespace로 사용합니다.

```bash
cd GenAI_Platform/devops/aaai_nfs_provisioner
./run.sh install -f ./values.yaml
```

### 2) (Optional) MetalLB

`aaai_metallb`는 manifest 기반입니다.

```bash
cd GenAI_Platform/devops/aaai_metallb
./install.sh
```

### 3) Kong

`aaai_kong/run.sh`는 values 파일에서 `developer:` 값을 읽어 namespace로 사용합니다.

```bash
cd GenAI_Platform/devops/aaai_kong
./run.sh install -f ./values.yaml
```

#### 주의사항

- **helm uninstall 후 재설치** 시, PV/PVC/실제 디렉토리가 남아 있으면 충돌할 수 있습니다. 스크립트도 uninstall 후 `CHECK DELETE volume - pvc, pv, directory`를 안내합니다.

### 4) Registry

```bash
cd GenAI_Platform/devops/aaai_registry
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
cd GenAI_Platform/devops/aaai_maraidb

# DB 설치 (galera)
./run.sh install

# DB 초기화 (init 차트)
./run.sh init -f ./values.yaml
```

### 6) Kafka / Redis / MongoDB

```bash
cd GenAI_Platform/devops/aaai_kafka
./run.sh install

cd ../aaai_redis
./run.sh install

cd ../aaai_mongodb
./run.sh install
```

### 7) Prometheus

`aaai_prometheus/run.sh`는 내부에서 `helm dependency build kube-prometheus-stack`를 수행하고, 설치 후 `ingress.yaml`도 적용합니다.

```bash
cd GenAI_Platform/devops/aaai_prometheus
./run.sh install
```

## Platform Apps / LLM Apps 설치

### 1) Platform Apps (fb_*)

`devops/run.sh`는 `fb_common_app`, `fb_dashboard`, `fb_dataset`, ... 등 앱 차트를 `jonathan-system` namespace에 설치합니다.

```bash
cd GenAI_Platform/devops
./run.sh install -f ./values_<서버명>.yaml
```

### 2) LLM Apps (llm_model, llm_playground)

`devops/run_llm.sh`는 `llm_model/helm`, `llm_playground/helm`을 설치합니다.

```bash
cd GenAI_Platform/devops
./run_llm.sh install -f ./values_<서버명>.yaml
```

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

- **`aaai_nfs_provisioner`**: `nfs.server`, `nfs.path`, `nfs.volumeName`, `storageClass.name`
- **`aaai_kong`**: `global.developer`, `global.jfb.static.*`, `global.jfb.storageClass.*`, `global.jfb.volume.*`
- **`aaai_registry`**: `namespace`, `service.*`, `volume.*`
- **`aaai_maraidb (init)`**: `global.jfb.namespace`, `global.jfb.settings.db.*`, `global.jfb.image.*`

각 차트의 `values.yaml` 파일을 참고하여 설정하세요.

