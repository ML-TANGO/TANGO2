# 📘 GenAI Platform 설치 매뉴얼

본 문서는 Tango 2 프로젝트의 GenAI Platform 설치 절차를 단계별로 안내합니다.

설치에 필요한 코드와 Helm 차트는 TANGO2 저장소의 main 브랜치에 포함되어 있습니다. 
설치 대상 서버에서 저장소를 내려받은 뒤 절차를 진행합니다.

[https://github.com/ML-TANGO/TANGO2](https://github.com/ML-TANGO/TANGO2)

---

## 📑 목차

- [시스템 요구사항](https://www.notion.so/Tango-GenAI-Platform-2f69d352990380d28ea0f4767aa0393a?pvs=21)
- [설치 전 준비사항](https://www.notion.so/Tango-GenAI-Platform-2f69d352990380d28ea0f4767aa0393a?pvs=21)
- [설치 단계별 가이드](https://www.notion.so/Tango-GenAI-Platform-2f69d352990380d28ea0f4767aa0393a?pvs=21)
- [플랫폼 설치 후 초기 설정](https://www.notion.so/Tango-GenAI-Platform-2f69d352990380d28ea0f4767aa0393a?pvs=21)

---

## 📌 개요

본 문서는 GenAI Platform 설치를 위한 전체 프로세스를 단계별로 설명합니다. 

---

## 💻 시스템 요구사항

- **OS:** Ubuntu 22.04.5 Jammy LTS 이상
- **쿠버네티스**: v1.30.x 계열 권장(테스트 기준 v1.30.14)
- Helm/kubectl은 설치 서버에서 실행 가능해야 하며, kubectl은 대상 클러스터에 접근 가능한 kubeconfig를 사용해야 합니다.
- 본 매뉴얼은 인터넷 연결이 가능한 온라인 환경을 기준으로 작성되었습니다. 오프라인 설치가 필요한 경우 별도 문의가 필요합니다.

---

## ✅ 설치 전 준비사항

- [ ]  도커, 쿠버네티스 설치
- [ ]  Calico, Helm, Kubectl 등 필수 유틸리티 설치 및 동작 확인
    
    설치 전 아래 명령이 정상 동작해야 합니다: `kubectl cluster-info`, `kubectl get nodes`, `helm version`
    
- [ ]  쿠버네티스 클러스터 생성
- [ ]  저장 위치에 동적 프로비저닝 세팅
    
    동적 프로비저닝은 **NFS Provisioner(gaip_nfs_provisioner)** 설치를 의미하며, 설치 후 StorageClass가 생성되는지 확인합니다.
    
- [ ]  삭제 후 재설치 시 기존 PV, PVC 삭제 확인

- 쿠버네티스 설치가 필요한 경우 다음 가이드를 참고하시기 바랍니다.
    
    [Kubernetes 설치 및 사용 가이드](https://www.notion.so/Kubernetes-2f69d352990380b1853ee46c3343ec19?pvs=21)
    

- EFK 사용을 위해 NFS(Network File System) 구성이 필요합니다. 
클라우드 환경에서는 서비스 제공자(CSP)가 세팅해놓은 경우가 많지만, 일반 로컬 서버에 설치할 경우에는 별도의 설정이 필요합니다. 다음 가이드를 참고하시기 바랍니다. (단일 노드에서도 가능)
    
    [**NFS 생성 / 동적 프로비저닝 가이드**](https://www.notion.so/NFS-2f79d352990380f6be6ce1eb8b9f3d20?pvs=21)
    

---

## **CLI 기반 쿠버네티스 관리 도구 K9s**

[https://github.com/derailed/k9s](https://github.com/derailed/k9s)

```bash
sudo wget https://github.com/derailed/k9s/releases/latest/download/k9s_linux_amd64.deb && sudo apt install ./k9s_linux_amd64.deb && sudo rm k9s_linux_amd64.deb
```

<aside>

Notion의 모든 코드는 복사가 가능합니다

</aside>

K9s는 복잡한 명령어 입력 없이 키보드 단축키만으로 쿠버네티스 클러스터를 모니터링하고 관리할 수 있는 오픈소스 도구입니다. 쿠버네티스에 익숙하지 않은 경우 K9s 설치를 권장합니다.

[[kubernetes] k9s 설치 및 사용법](https://peterica.tistory.com/276)

상세한 사용 방법 및 단축키는 위 링크를 참조하시기 바랍니다.

---

## 🔧 설치 단계별 가이드

> 💡 **권장: 통합 설치 스크립트(`run_step1/2/3`) 사용**
> 본 문서는 각 인프라 차트를 **수동으로** 단계별 설치하는 상세 레퍼런스입니다. 새로 설치하는 환경이라면 [`Tango GenAI Platform 설치 간소화 매뉴얼.md`](./Tango%20GenAI%20Platform%20설치%20간소화%20매뉴얼.md) 의 통합 스크립트(`run_step1_infra_base.sh` / `run_step2_core_infra.sh` / `run_step3_optional_obs.sh`)를 먼저 활용하시고, 본 문서는 개별 차트 옵션·트러블슈팅 참고용으로 사용하시기 바랍니다.

## **값 파일(values) 준비**

### **1) 공통 values 파일 생성(앱/LLM 차트용)**

- 본 섹션의 `values_<서버명>.yaml`은 **플랫폼 앱 설치(devops/run.sh, devops/run_llm.sh) 전용 공통 values**입니다
- NFS/Kong/Registry 등 **인프라 차트(gaip_*)는 각 디렉토리의 values.yaml(또는 별도 values 파일)을 별도로 사용**합니다(다음 섹션 참고).

### **템플릿 파일 복사 및 수정**

템플릿을 복사해 환경별 values 파일을 생성하고, 템플릿 내 `TODO` 항목을 실제 환경 값으로 치환합니다. 

```bash
cd GenAI_Platform/devops
cp values.yaml.template values_<서버명>.yaml
# 예: cp values.yaml.template values_prod.yaml
```

> 📌 `values_<서버명>.yaml` 파일은 운영 환경의 IP/계정/비밀번호가 들어가므로 **저장소에 커밋하지 않습니다.** 저장소 루트의 `.gitignore` 가 `/devops/values_*.yaml` 패턴으로 자동 차단합니다.

코드 편집기(예: Vim, Nano, VSCode 등)를 사용하여 복사한 파일을 실제 환경에 맞게 수정합니다.

```markdown
# 템플릿 파일의 TODO 주석을 확인하며 실제 환경에 맞게 수정
 - <NFS_SERVER_IP>: NFS 서버 IP 주소
 - <EXTERNAL_HOST_IP>: 외부 접근 IP 또는 도메인
 - <SYSTEM_REGISTRY_IP>: 시스템 레지스트리 주소
 - <USER_REGISTRY_IP>: 사용자 레지스트리 주소
 - <INIT_ROOT_PASSWORD>: 초기 루트 비밀번호
 - <KAFKA_USERNAME>, <KAFKA_PASSWORD>: Kafka 인증 정보
 - <MONGODB_PASSWORD>: MongoDB 비밀번호
# 기타 TODO 주석이 있는 항목들 확인

# `devops/values.yaml.template` 파일에는 다음 주요 섹션이 포함되어 있습니다:
 -`global.jfb.namespace`: 기본 네임스페이스
 -`global.jfb.volume.*`: 볼륨 설정 (jfData, jfBin, jfStorage, src, front 등)
 -`global.jfb.settings.*`: 앱 설정 (db, redis, kafka, mongodb, monitoring 등)
 -`global.jfb.image.*`: 이미지 레지스트리 및 이미지 태그 설정
 -`global.jfb.dir.*`: 디렉토리 매핑
 -`global.jfb.name.*`: Helm release 이름
```

`<NFS_SERVER_IP>`는 **NFS 서버의 IP**이며, 설치 서버(마스터) IP와 동일하지 않을 수 있습니다.”

```yaml
# 외부 접근 설정
external:
		protocol:"http" # http 또는 https
		host:"XXX.XXX.XXX.XXX" # TODO: 외부 접근 가능한 IP 또는 도메인
```

- `external.host`는 **사용자가 브라우저로 접속할 주소(IP/도메인)** 입니다.
- 로컬 서버 설치이며 MetalLB/LoadBalancer를 사용하는 경우, Kong 설치 후 아래 명령으로 외부 IP를 확인한 뒤 `external.host`에 반영합니다.
    
    `kubectl -n <kong-namespace> get svc`”
    
- 외부 IP를 즉시 확정할 수 없으면, 우선 내부 접근 가능한 IP로 설치를 완료한 뒤 `external.host`만 수정하여 재배포합니다.

각 앱들의 이미지 태그를 지정합니다.
공유용 오픈소스 앱 이미지들은 Docker Hub에 저장되어 있습니다. [https://hub.docker.com/u/acrylaaai](https://hub.docker.com/u/acrylaaai)


저장소 내 저장 경로를 생성합니다. (values 파일의 값과 일치해야 합니다.)

아래 경로는 **예시**입니다. 실제 생성 경로는 `values_<환경>.yaml`의 `global.jfb.volume.*.path`(또는 스토리지 설정 값)와 **반드시 동일**해야 합니다. (예: `/storage/jonathan-storage` 또는 `/opt/dynamic-storage`)

```bash
# App들이 바라볼 저장 공간 디렉토리를 생성
sudo mkdir -p /storage/jonathan-storage/jf-bin # 바이너리 파일
sudo mkdir -p /storage/jonathan-storage/jf-data
sudo mkdir -p /storage/jonathan-storage/jf-data/images # 도커 이미지 관련
sudo mkdir -p /storage/jonathan-storage/system # 시스템 스토리지
sudo mkdir -p /storage/jonathan-storage/tmp-storage # 조나단 스토리지
sudo mkdir -p /storage/jonathan-storage/efk # EFK 관련

# 권한 설정
sudo chown -R nobody:nogroup /storage/jonathan-storage/jf-bin
sudo chown -R nobody:nogroup /storage/jonathan-storage/jf-data
sudo chown -R nobody:nogroup /storage/jonathan-storage/jf-data/images
sudo chown -R nobody:nogroup /storage/jonathan-storage/system
sudo chown -R nobody:nogroup /storage/jonathan-storage/tmp-storage
sudo chown -R nobody:nogroup /storage/jonathan-storage/efk
```

NFS가 `root_squash`로 동작하면 파드에서 접근 가능한 UID/GID로 소유자를 맞춰야 합니다. 기본 예시는 `nobody:nogroup`이며, 환경에 따라 UID/GID를 조정합니다.

kubeconfig 준비

```bash
# 복사할 경로가 없으면 생성
mkdir -p /TANGO2/GenAI_Platform/devops/fb_common_app/helm/file/kube

# 위 스크립트들은 kubeconfig를 아래 경로에서 찾습니다.
cp ~/.kube/config /TANGO2/GenAI_Platform/devops/fb_common_app/helm/file/kube/config
```

- `devops/run.sh` 및 `devops/run_llm.sh`는 kubeconfig를 `/TANGO2/GenAI_Platform/devops/fb_common_app/helm/file/kube/config`에서 참조합니다.
- 복사 전, 아래 명령이 정상 출력되는지 확인합니다:
    
    `kubectl get nodes`
    
    `kubectl get ns`
    
- 정상 동작하지 않으면 kubeconfig 경로/권한/컨텍스트를 먼저 수정한 후 진행합니다.
- 실패할 경우 `mkdir -p` 명령으로 디렉터리를 생성합니다.

### **2) 로컬/개별 인프라 차트 values 파일 실행**

인프라 차트(`gaip_*`)는 차트별로 values 파일 구조가 상이하며, 각각 독립적인 values 파일 구조를 가집니다:
인프라 차트 실행 전, 해당 디렉토리에서 **(1) values 파일 존재 여부(또는 심볼릭 링크 대상 존재 여부)**를 먼저 확인하고, 문서에 명시된 방식(`-f`/`--values`/기본값)으로 설치합니다.

- `gaip_nfs_provisioner/run.sh`: `f <values.yaml>` **필수**
- `gaip_kong/run.sh`: `f <values.yaml>` **필수** (`developer:` 값을 namespace로 사용)
- `gaip_registry/run.sh`: `f <values.yaml>` **필수**
- `gaip_maraidb/run.sh`: `install`은 기본 값으로 설치, `init -f <values.yaml>`은 **values 필요**
- `gaip_kafka/run.sh`: 기본적으로 `values.yaml`을 사용(스크립트 내부 고정)
- `gaip_redis/run.sh`, `gaip_mongodb/run.sh`: 기본 설정으로 설치(스크립트 내부 고정)
- `gaip_prometheus/run.sh`: 스크립트 내부 `value.yaml` 사용 + `helm dependency build kube-prometheus-stack` 수행

### **인프라 차트별 values 파일**

- `gaip_nfs_provisioner`: `nfs.server`, `nfs.path`, `nfs.volumeName`, `storageClass.name`
- `gaip_kong`: `global.developer`, `global.jfb.static.*`, `global.jfb.storageClass.*`, `global.jfb.volume.*`
- `gaip_registry`: `namespace`, `service.*`, `volume.*`
- `gaip_maraidb (init)`: `global.jfb.namespace`, `global.jfb.settings.db.*`, `global.jfb.image.*`

### **주의사항**

- **helm uninstall 후 재설치** 시, PV/PVC/실제 디렉토리가 남아 있을 경우 충돌이 발생할 수 있습니다.
    
    스크립트 uninstall 후 `CHECK DELETE volume - pvc, pv, directory` 항목을 확인하시기 바랍니다.
    
- **containerd 설정(참고)**
    
    insecure registry로 레지스트리를 연결해야 하는 경우, `/etc/containerd/config.toml`에 registry 설정이 필요할 수 있습니다.
    레지스트리가 HTTPS가 아니거나 사설 인증서를 사용할 때, 이미지 pull에서 `x509`/`http: server gave HTTP response to HTTPS client` 오류가 나면 아래 설정을 적용합니다.
    
    ```yaml
    [plugins."io.containerd.grpc.v1.cri".registry.configs]
    	[plugins."io.containerd.grpc.v1.cri".registry.configs."$REGISTRYIP:$REGISTRYPORT"]
    		[plugins."io.containerd.grpc.v1.cri".registry.configs."$REGISTRYIP:$REGISTRYPORT".tls]
    			ca_file=""
    			cert_file=""
    			insecure_skip_verify=true
    			key_file=""
    [plugins."io.containerd.grpc.v1.cri".registry.mirrors]
    	[plugins."io.containerd.grpc.v1.cri".registry.mirrors."$REGISTRYIP:$REGISTRYPORT"]
    		endpoint=["http://$REGISTRYIP:$REGISTRYPORT"]
    ```
    
- 각 `gaip_*` 실행 전 체크: `ls -al values.yaml`(존재/링크 대상 확인) 및 `./run.sh --help`로 values 인자 필요 여부 확인.”

### 네트워크 대역 확인 및 서비스 타입 결정

인프라 차트 설치 전, 플랫폼에 접속할 클라이언트의 네트워크 대역과 클러스터 노드의 대역이 동일한지 확인합니다.
이 결정에 따라 MetalLB 설치 여부 및 Kong의 서비스 타입(LoadBalancer / NodePort)이 달라집니다.

**MetalLB L2 모드의 서브넷 제약**

MetalLB L2 모드는 **동일한 L2 브로드캐스트 도메인(동일 서브넷)** 내에서만 ARP 응답이 동작합니다.
MetalLB가 할당한 VIP와 접속 클라이언트가 서로 다른 서브넷에 있고, 두 대역 간 L3 라우팅이 구성되어 있지 않으면 접근이 불가합니다.

> **예시 상황:**
> - 마스터 노드 IP: `10.254.180.53` (내부망 A)
> - MetalLB VIP: `192.168.0.57` (내부망 B)
> - 두 대역 간 라우팅 미구성 → 내부망 A에서 VIP로 접근 불가

**서비스 타입 결정 기준**

| 조건 | 권장 서비스 타입 | 비고 |
|------|-----------------|------|
| 클라이언트와 클러스터가 동일 서브넷 | **LoadBalancer** (MetalLB) | 기본 설치 방식 |
| 서브넷이 다르지만 L3 라우팅 구성됨 | **NodePort** | 마스터 노드 IP로 직접 접근 |
| 서브넷이 다르고 라우팅 미구성 | **NodePort** + 라우팅 요청 | 네트워크 담당자에게 inter-VLAN routing 요청 |
| 클라우드 환경 (CSP LB 사용) | **LoadBalancer** | MetalLB 불필요 |

**라우팅 구성 여부 확인 방법**

클라이언트 PC에서 마스터 노드로 ping을 보내 확인합니다.

```bash
# 다른 서브넷의 PC에서 실행
ping <마스터_노드_IP>
# 예: ping 10.254.180.53
```

- **ping 성공**: 라우팅이 이미 구성된 상태 → NodePort 전환만으로 접속 가능
- **ping 실패**: 네트워크 담당자에게 **서브넷 간 라우팅(inter-VLAN routing)** 구성을 요청한 뒤 진행

> **결정 결과에 따른 설치 진행:**
> - **LoadBalancer 방식**: 아래 인프라 차트를 순서대로 설치합니다. (MetalLB → Kong 순서)
> - **NodePort 방식**: MetalLB 설치를 건너뛰고, Kong 설치 시 서비스 타입을 NodePort로 설정합니다. 상세 설정은 아래 [IP 변경 및 서비스 타입 전환 가이드](#-ip-변경-및-서비스-타입-전환-가이드)를 참고합니다.

---

### 인프라 차트 설치

1. **NFS Provisioner** (`gaip_nfs_provisioner`)
EFK 사용을 위해 동적 프로비저닝을 지원하는 도구입니다.
“NFS Provisioner values 필수 항목: `nfs.server`(NFS 서버 IP), `nfs.path`(export 경로), `storageClass.name`(예: local-nfs). 아래 3개 파일에 동일 기준으로 반영합니다.”
    
    ```bash
    # `gaip_nfs_provisioner/run.sh`는 values 파일에서 `volumeName`을 읽어 namespace로 사용
    cd TANGO2/GenAI_Platform/devops/gaip_nfs_provisioner
    ```
    
    `values-system.yaml`, `values-marker.yaml`, `values-efk.yaml`
    
    3개 파일에 앞서 설정한 NFS 경로를 입력합니다.
    
    ```bash
    # values-system.yaml (예시)
    nfs:
      server: 192.168.0.44
      path: /storage/jonathan-storage/system # 시스템 데이터 저장경로
      mountOptions: 
      volumeName: jonathan-system
      # Reclaim policy for the main nfs volume
      reclaimPolicy: Retain
    ```
    
    ```bash
    # values-efk.yaml (예시)
    nfs:
      server: 192.168.0.44
      path: /storage/jonathan-storage/efk # EFK 저장 경로
      mountOptions: 
      volumeName: jonathan-efk
      # Reclaim policy for the main nfs volume
      reclaimPolicy: Retain
    ```
    
    또는 `values.yaml` 파일을 사용하여 커스터마이징할 수 있습니다.
    
    값 세팅이 완료되면 설치 스크립트를 실행합니다.
    
    ```bash
    ./run.sh install --values ./values-system.yaml # 시스템 기본 NFS
    ./run.sh install --values ./values-marker.yaml # (Optional) Jonathan Marker 
    ./run.sh install --values ./values-efk.yaml # EFK
    ```
    
2. **(Optional) MetalLB** (`gaip_metallb`)
    
    클라우드가 아닌 로컬 서버에 설치할 경우 필요합니다.
    
    ```bash
    # `gaip_metallb`는 manifest 기반입니다.
    cd ../gaip_metallb
    ./install.sh
    ```
    
    로컬(온프레미스) 환경에서 LoadBalancer 타입 서비스에 External IP를 할당해야 하는 경우 MetalLB가 필요합니다. 이미 외부 LB/대체 수단이 있으면 생략 가능합니다.
    
3. **Kong** (`gaip_kong`)
    
    ```bash
    # `gaip_kong/run.sh`는 values 파일에서 `developer:` 값을 읽어 namespace로 사용합니다.
    cd ../gaip_kong
    ./run.sh install -f ./values.yaml
    # DB 워크로드를 실행할 노드에 라벨을 지정하여 해당 노드에서 스케줄링되도록 설정
    kubectl label node {node_name} node-role.kubernetes.io/db=""
    ```
    
    `developer`는 Kong이 설치될 namespace 이름입니다(예: `tango-system`). 
    
    values에서 지정한 namespace가 없으면 스크립트가 생성하거나, 사전에 생성해야 합니다(스크립트 동작 기준 명시)
    
4. **Registry** (`gaip_registry`)
    
    ```bash
    # values.yaml 수정
    volume: # data volume
      type: nfs
      path: /storage/jonathan-storage/jf-data/images # 위에서 도커 이미지 경로로 설정했던 경로
      server: 192.168.0.44
    ```
    
    ```bash
    cd ../gaip_registry
    ./run.sh install -f ./values.yaml
    ```
    
5. **MariaDB (run → init)** (`gaip_maraidb`)
    
    ```bash
    cd ../gaip_maraidb
    # DB 설치 (galera)
    ./run.sh install
    # DB 초기화 (init 차트)
    ./run.sh init -f ./values.yaml
    ```
    
    <aside>
    ⚠️ 주의: MariaDB 설치 시 configmap과 chart의 접속 패스워드가 일치하는지 확인
    
    </aside>
    
6. **Kafka** (`gaip_kafka`)
    
    ```bash
    cd ../gaip_kafka
    ./run.sh install
    
    # Kafka를 실행할 manage 노드에 라벨 지정
    kubectl label node {node_name} node-role.kubernetes.io/manage=""
    ```
    
    MariaDB 등 DB 컴포넌트를 특정 노드에 고정 배치하려는 목적입니다. 단일 노드 클러스터면 해당 노드에 라벨을 부여하면 됩니다.
    
7. **Redis** (`gaip_redis`)
    
    ```bash
    cd ../gaip_redis
    ./run.sh install
    ```

    > 📌 **Redis 리소스 기본값 (2026-04-21 기준)**: `gaip_redis/redis-cluster/values.yaml` 의 CPU/Memory `requests` 가 단일 노드 환경에서 파인튜닝 admission 거부를 피하도록 실측 사용량 수준으로 축소되어 있습니다 (CPU 2→500m, Memory 8Gi→2Gi 등, 6 replicas 누적 회수: −9 CPU / −36 GiB). 노드 자원이 충분한 클러스터에서 더 큰 워크로드를 받게 하려면 해당 values 의 `resources.requests` 를 환경에 맞게 상향하세요.

    - Redis AOF 파일 손상으로 인해 Pod error 발생 시
        
        최초 설치 시에는 거의 없는데, 간혹 서버가 갑자기 멈추거나 리부트될 경우에는 AOF 파일이 깨져서 문제가 있을 수 있습니다.
        
        K9s 에서 pod 의 shell로 접근하거나(`s`) `docker exec -it {redis_name} bash` 등을 사용해서 bash로 접근하여 
        
        ```bash
        /src/redis-check-aof appendonly.aof
        ```
        
        로 AOF 파일을 복원하면 되는데, 
        
        여의치 않거나 실행 데이터가 필요 없는 경우에는 전부 지우고 재설치하는 편이 훨씬 좋습니다.
        
        아래 스크립트는 모든 pvc, pv를 다 지우고 재설치하기 때문에 데이터 손실에 주의해야 합니다.
        
        ```bash
        DISABLE_AOF="yes" ./clean_reinstall.sh 
        ```
        
8. **MongoDB** (`gaip_mongodb`)
    
    ```bash
    cd ../gaip_mongodb
    ./run.sh install
    ```
    
    <aside>
    ⚠️ values.yaml의 DB 비밀번호 설정(`global.jfb.settings.db.*` 등)과, 설치 과정에서 생성되는 ConfigMap/Secret의 값이 일치해야 합니다. 
    
    불일치 시 로그인/연결 실패가 발생합니다(재설치 시 잔존 리소스 삭제 필요).
    
    </aside>
    
9. **Prometheus** (`gaip_prometheus`)
    
    ```bash
    # `gaip_prometheus/run.sh`는 내부에서 `helm dependency build kube-prometheus-stack`를 수행하고, 설치 후 `ingress.yaml`도 적용합니다.
    cd ../gaip_prometheus
    
    # 프로메테우스 차트 사용을 위해 Helm repository 등록
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo add grafana https://grafana.github.io/helm-charts
    helm repo update
    
    ./run.sh install
    ```
    
10. **GPU Operators** (`gaip_gpu_operators`)
    
    ```bash
    cd ../gaip_gpu_operators
    ./run.sh
    
    # GPU를 실행할 노드에 compute 라벨 지정
    kubectl label node {node_name} node-role.kubernetes.io/compute=""
    ```
    
    - `gaip_gpu_operators`는 **쿠버네티스 클러스터에 GPU 관련 컴포넌트(Device plugin 등)를 설치**합니다. 설치 전에 **(1) GPU가 장착된 모든 노드에서 `nvidia-smi`가 정상 동작**하는지 확인합니다. (본 설치는 기본 설정 기준으로 **호스트 드라이버가 선행되어야 합니다/또는 드라이버 설치 옵션을 활성화해야 합니다** — 아래 ‘드라이버 선행 여부’ 항목 참고).
    - 실행 위치: `GenAI_Platform/devops/gaip_gpu_operators` 디렉터리에서 **마스터 노드에서 1회 실행**합니다.
    
    <aside>
    ⚠️ 설치 중 아래 유형의 오류가 발생하면 먼저 `nvidia-smi`로 **드라이버/라이브러리 상태를 확인**합니다.
    
    - `nvidia-smi: command not found` → 드라이버/유틸 미설치
    - `Driver/library version mismatch` → 드라이버 버전 꼬임
    - Secure Boot enabled → 커널 모듈 로딩 차단
        
        이후 조치 방법은 아래 ‘드라이버 오류 해결’ 절차를 따릅니다.”
        
    </aside>
    
    - Nvidia 드라이버 오류 해결방법
    아래 버전은 검증 환경 예시(A100)입니다. GPU 모델/OS/커널 조합에 따라 권장 버전이 달라질 수 있으므로, 최종 기준은 **해당 서버에서 `nvidia-smi` 정상 동작** 여부입니다.
        - Driver Version: 580.95.05
        - NVIDIA-SMI 580.95.05
        - CUDA Version: 13.0
        
        ```bash
        # 먼저 PCI 장치로 인식이 되는지 확인 
        sudo apt-get update
        sudo apt-get install -y pciutils
        
        sudo lspci -nn | grep -i nvidia
        sudo lspci -nnk | grep -A3 -i nvidia
        # 여기서 NVIDIA 관련 하드웨어가 보여야 합니다. 보이지 않으면 하드웨어 문제이므로 서버/인프라 담당자에게 문의해주세요.
        ```
        
        ```bash
        # 새로 포맷 설치한 경우 - Ubuntu 기본 방식으로 드라이버 설치 
        sudo apt-get update
        sudo apt-get install -y ubuntu-drivers-common
        
        ubuntu-drivers devices
        sudo ubuntu-drivers autoinstall
        sudo reboot # 재부팅
        
        # 드라이버 설치는 했는데 nvidia-smi 명령어가 작동을 안할 경우
        dpkg -l | grep -E "nvidia-(driver|utils)"
        which nvidia-smi || true
        # 설치된 드라이버 버전에 맞춰 nvidia-utils-XXX 형태로 설치되는 경우가 많습니다.
        # 예: sudo apt-get install -y nvidia-utils-535
        ```
        
        ```bash
        # 커널 모듈 로딩 여부 확인
        lsmod | grep -i nvidia
        sudo modprobe nvidia
        sudo dmesg -T | grep -i nvidia | tail -n 100
        
        # Secure Boot 때문에 드라이버 모듈이 막히는 경우
        mokutil --sb-state
        
        # Driver/library version mismatch (드라이버 버전 꼬임)
        nvidia-smi
        dpkg -l | grep -i nvidia
        uname -r
        ```
        
11. **EFK**
    - EFK는 `jonathan-efk` 네임스페이스에 설치됩니다.
    - EFK 데이터는 NFS에 저장되며, 경로는 공통 values에서 지정한 `<JONATHAN_STORAGE_ROOT>/efk`를 사용합니다. (예시는 `/storage/jonathan-storage/efk`)

    > 📌 **Elasticsearch 리소스 기본값 (2026-04-21 기준)**: `gaip_efk/esvalues.yaml` 의 master/data/coordinating/ingest/Kibana CPU·`heapSize` 가 단일 노드 환경에서도 동작 가능한 수준으로 축소되어 있습니다 (master CPU 3→500m, data CPU 3→1, coordinating/ingest/kibana CPU 도 비례 축소, heapSize 도 함께 축소). 더 큰 로그 트래픽을 받는 환경에서는 `resources.requests` 와 `heapSize` 를 다시 상향해 주세요.

    ```bash
    cd ../gaip_efk
    ./helm_repo_add.sh # 레포 추가
    ./helm_upgrade_elastic.sh # Elastic 설치(혹은 업그레이드)
    
    # 모든 Elastic 파드의 동작을 확인한 후 진행 (K9s 등으로 확인했을 때 Running 으로 바뀌었을 때)
    ./elastic_init.sh # Elastic 인덱스 설정 등
    ./helm_upgrade_fluent.sh # Fluent 설정
    ```
    
    ```bash
    # 오류 발생 시
    # 아래 정리 작업은 NFS 서버의 EFK 데이터 디렉터리를 삭제합니다. 실행 전, 공통 values에서 설정한 스토리지 루트 경로(<JONATHAN_STORAGE_ROOT>)가 무엇인지 확인한 뒤 진행하십시오.
    # 1) Elasticsearch Release 제거
    helm uninstall -n jonathan-efk elasticsearch
    
    # 2) EFK 저장소 정리
    # PVC는 제거되나 PV가 release 상태로 남아있을 수 있으므로 확인 후 삭제
    # NFS 서버에 SSH 접속 후 데이터 디렉토리 삭제
    
    # 아래 rm -rf는 데이터를 영구 삭제합니다. 운영 데이터가 있으면 수행하면 안 됩니다.
    rm -rf <JONATHAN_STORAGE_ROOT>/efk/data-elasticsearch-master-0/*
    rm -rf <JONATHAN_STORAGE_ROOT>/efk/data-elasticsearch-data-0/*
    rm -rf <JONATHAN_STORAGE_ROOT>/efk/elasticsearch-kibana/*
    
    # Elastic init
    ./helm_upgrade_elastic.sh
    ```
    

### 어플리케이션 설치

1. **Platform Apps** (`devops/run.sh`)
2. **LLM Apps** (`devops/run_llm.sh`)
- Platform Apps 설치 전 체크(필수):
    1. `gaip_*` 인프라 차트 설치가 완료되어야 합니다(NFS, Kong, Registry, DB, Kafka/Redis/Mongo, Prometheus, (필요 시) GPU Operator, EFK).
    2. 공통 values 파일이 준비되어 있어야 합니다(`values_<서버명>.yaml`).
    3. `devops` 하위 앱 차트가 참조하는 `values.yaml` 심볼릭 링크가 유효해야 합니다. 링크가 깨져 있다면 **레포 버전(태그/브랜치)을 맞추거나**, 심볼릭 링크를 재생성해야 합니다.

```bash
cd GenAI_Platform/devops

# `devops/run.sh`는 `fb_common_app`, `fb_dashboard`, `fb_dataset`, ... 등 앱 차트를 `jonathan-system` namespace에 설치합니다.
# 앞에서 수정한 자신의 values 파일을 선택
./run.sh install -f ./values_<서버명>.yaml

# `devops/run_llm.sh`는 `llm_model/helm`, `llm_playground/helm`을 설치합니다.
./run_llm.sh install -f ./values_<서버명>.yaml
```

---

## 🔄 IP 변경 및 서비스 타입 전환 가이드

설치 후 네트워크 환경이 변경되거나, MetalLB VIP와 실제 접근 대역이 다른 경우 아래 절차에 따라 IP 변경 또는 서비스 타입(LoadBalancer ↔ NodePort) 전환을 수행합니다.

### 방법 A: 할당 IP 변경 (LoadBalancer 유지)

MetalLB VIP를 접근 가능한 대역의 IP로 변경하는 방법입니다. 동일 서브넷 내 접근만 필요한 경우 적합합니다.

**1) MetalLB IP 풀 변경**

```bash
cd TANGO2/GenAI_Platform/devops/gaip_metallb
```

`metallb-config.yaml`의 `spec.addresses`를 변경합니다.

```yaml
# metallb-config.yaml
spec:
  addresses:
    - <새로운_VIP>/32   # /32 서브넷마스크 권장 (단일 IP 할당)
```

```bash
# MetalLB 설정 재적용
kubectl apply -f metallb-config.yaml
```

**2) Kong static IP 변경**

```bash
cd ../gaip_kong
```

`values.yaml`의 `global.jfb.static.ip`를 변경합니다.

```yaml
# gaip_kong/values.yaml
global:
  jfb:
    static:
      enabled: true
      ip: <새로운_VIP>   # MetalLB에서 할당한 IP와 동일하게 설정
```

```bash
# Kong 관련 PV, PVC 삭제 후 재설치 (필수)
./run.sh uninstall
kubectl delete pvc -l app=kong -n <kong-namespace>   # 잔존 PVC 삭제
kubectl delete pv <kong-관련-pv>                       # 잔존 PV 삭제
./run.sh install -f ./values.yaml
```

<aside>
⚠️ Kong 재설치 시 기존 PV/PVC를 반드시 삭제해야 합니다. 잔존 리소스가 있으면 IP 변경이 반영되지 않습니다.
</aside>

**3) 어플리케이션 external.host 변경**

`values_<서버명>.yaml`의 외부 접근 설정을 변경합니다.

```yaml
# values_<서버명>.yaml
global:
  jfb:
    settings:
      external:
        protocol: "http"
        host: "<새로운_VIP>"   # MetalLB에서 할당한 새 IP
```

```bash
cd TANGO2/GenAI_Platform/devops
./run.sh install -f ./values_<서버명>.yaml
./run_llm.sh install -f ./values_<서버명>.yaml
```

### 방법 B: NodePort 방식 전환 (LoadBalancer → NodePort)

MetalLB VIP 대신 **마스터 노드의 고정 IP + NodePort**로 직접 접근하는 방법입니다. 서브넷이 다른 환경에서 가장 확실한 해결책입니다.

**1) Kong 서비스 타입 변경**

`gaip_kong/values.yaml`에서 아래 3가지를 변경합니다.

```yaml
# (1) proxy.type 변경
proxy:
  type: NodePort          # LoadBalancer → NodePort

# (2) HTTP nodePort 주석 해제
  http:
    servicePort: 80
    containerPort: 8000
    nodePort: 32080       # 주석 해제

# (3) TLS nodePort 주석 해제
  tls:
    servicePort: 443
    containerPort: 8443
    nodePort: 32443       # 주석 해제
```

```bash
cd TANGO2/GenAI_Platform/devops/gaip_kong

# Kong 관련 PV, PVC 삭제 후 재설치 (필수)
./run.sh uninstall
kubectl delete pvc -l app=kong -n <kong-namespace>
kubectl delete pv <kong-관련-pv>
./run.sh install -f ./values.yaml
```

<aside>
⚠️ NodePort 범위는 30000~32767로 제한됩니다. 기존 80/443 포트 대신 별도 포트 번호를 URL에 명시해야 합니다.
</aside>

**2) 어플리케이션 external.host 변경**

NodePort 전환 후에는 `external.host`를 **마스터 노드 IP**로, 포트도 NodePort에 맞게 변경해야 합니다.
프론트엔드가 이 값을 기준으로 API 요청 URL을 생성하므로 반드시 일치시켜야 합니다.

```yaml
# values_<서버명>.yaml
global:
  jfb:
    settings:
      external:
        protocol: "http"
        host: "<마스터_노드_IP>"          # 예: "10.254.180.53"
        port: 32080                       # NodePort에 맞게 설정
```

```bash
cd TANGO2/GenAI_Platform/devops
./run.sh install -f ./values_<서버명>.yaml
./run_llm.sh install -f ./values_<서버명>.yaml
```

**3) 접속 확인**

```bash
# HTTP 접속 확인
curl http://<마스터_노드_IP>:32080
# 예: curl http://10.254.180.53:32080

# HTTPS 접속 확인 (자체 서명 인증서 사용 시 -k 옵션)
curl -k https://<마스터_노드_IP>:32443
```

브라우저에서도 `http://<마스터_노드_IP>:32080`으로 접속하여 정상 동작을 확인합니다.

### NodePort → LoadBalancer 복원

NodePort에서 다시 LoadBalancer로 전환하려면 위 과정을 역순으로 수행합니다.

1. `gaip_kong/values.yaml`에서 `proxy.type`을 `LoadBalancer`로 변경하고, `nodePort` 항목을 다시 주석 처리
2. Kong PV/PVC 삭제 후 재설치
3. `values_<서버명>.yaml`의 `external.host`를 MetalLB VIP로, `port` 설정을 제거(또는 80/443 기본값)
4. 어플리케이션 재설치

### 다른 서브넷에서도 접속이 필요한 경우

NodePort 전환은 **마스터 노드 IP에 접근 가능한 대역**에서의 문제를 해결합니다.
서브넷이 다른 곳에서도 접속이 필요하다면, **네트워크 담당자(전산팀)에게 라우터 또는 L3 스위치에서 서브넷 간 라우팅(inter-VLAN routing) 구성을 요청**해야 합니다.

라우팅이 구성되면 NodePort 방식으로 모든 대역에서 접속이 가능합니다.

---

## ✔️ 플랫폼 설치 후 초기 설정

- [ ]  Jonathan 정상 실행 확인
- [ ]  스토리지 생성
- [ ]  사용자 생성
- [ ]  워크스페이스 생성
- [ ]  사용자 계정으로 로그인

### GenAI Platform(Jonathan) 정상 실행 확인

설치가 정상적으로 완료되면 브라우저를 통해 설정한 `EXTERNAL_HOST_IP`로 접속 시 초기 화면이 표시됩니다.

신규 설치 시 관리자 계정은 `admin`이며, 비밀번호는 **설치에 사용한 values 파일(`values_<서버명>.yaml`)의 `initRootPassword` 값**입니다.

- 로그인이 되지 않으면, `jonathan-system` 네임스페이스의 `user` 관련 파드를 재시작합니다.
1. `kubectl get pod -n jonathan-system | grep user`로 파드명을 확인합니다.
2. `kubectl delete pod -n jonathan-system <pod_name>`로 재시작합니다.
    
    (K9s 사용 시 `jonathan-system`에서 해당 pod 선택 후 Ctrl+d)
    

### 스토리지 생성

관리자 로그인 후 서버에서 사용할 저장소를 활성화해야 합니다.

관리자 로그인 후 **스토리지 메뉴**에서 스토리지를 추가/활성화합니다.

(참고: 2.5 버전 UI에서는 ‘스토리지 추가’ 버튼이 헤더 영역의 메뉴 안에 숨겨져 있습니다. 전체 스토리지 원을 10번 이상 누르고 헤더 버튼을 누르면 모달이 활성화됩니다. (잘 안될 수 있어서 계속 시도)

- 스토리지 이름(예: local-nfs)
- IP 주소 (다른 서버일 경우 해당 서버 IP, 현재 서버일 경우 현재 서버 IP 입력)
    
    스토리지 타입이 `nfs`인 경우: **NFS 서버 IP**를 입력
    
    스토리지 타입이 `local`인 경우: 현재 노드 IP 입력
    
- `nfs` 선택 시 마운트 포인트에는 NFS 서버에 export된 경로(예: /opt/dynamic-storage)를 입력합니다.
    
    `local` 선택 시 마운트 포인트에는 클러스터 노드의 로컬 경로를 입력합니다.
    
    이 값은 설치에 사용한 values 파일의 스토리지 루트 경로와 반드시 동일해야 합니다.”(‘어느 키인지’까지 적으면 더 좋음)
    
- 스토리지 타입은 nfs 또는 local로 설정합니다.
- 스토리지 등록 후, 스토리지 exporter가 배포된 네임스페이스에서 Pod 상태를 확인합니다. (예: `kubectl get pod -A | grep -i storage`)

```bash
# 다음과 같은 storage exporter pod이 running 상태여야 합니다
storage-local-nfs-data-nfs-provisioner
storage-local-nfs-main-nfs-provisioner
storage-local-nfs-storage-exporter
```

### 사용자 생성

`사용자 > 사용자 추가`에서 **아이디/비밀번호/이름(필수)**를 입력하고, 사용자 그룹, 이메일, 이름, 소속, 직책 등의 정보를 입력합니다.

### 인스턴스 생성

1. <노드> 탭에서 맨 아래로 스크롤하여, 활성화된 노드를 선택하여 설정 버튼을 누릅니다
(만약 GPU 자원의 MIG, NVLink 등이 필요한 경우에는 별도로 문의 바랍니다.)

2. 클러스터 노드에 설치된 GPU를 인스턴스 단위로 가상화하여 할당할 수 있도록 설정합니다.

3. 앞에서 GPU exporter 설정이 정상적으로 되었다면, 할당 가능한 GPU 자원이 표시됩니다.

4. 인스턴스의 vCPU, vRAM, 개수를 선택한 뒤, 유효성 검사를 실시합니다.

5. 유효성 검사가 완료되면, 저장 버튼을 눌러 인스턴스를 활성화합니다.

6. 인스턴스 설정 초기화가 필요하다면 초기화 버튼을 눌러 진행하시면 됩니다.

### 워크스페이스 생성

워크스페이스 탭에서 워크스페이스를 생성합니다.

앞선 설정에 문제가 없을 경우에만 인스턴스, 스토리지 목록이 정상적으로 표시됩니다.
워크스페이스 생성 후 **워크스페이스 상세 화면 > 멤버(또는 사용자) 탭**에서 방금 만든 사용자를 추가합니다.

### 사용자 계정으로 로그인

생성한 사용자 계정으로 로그인하여 워크스페이스 목록에 표시되면 설치가 완료됩니다.

워크스페이스 상세 화면 상단(또는 좌측 메뉴)의 `GenAI Platform` 버튼을 클릭하면 대시보드로 이동합니다.

<aside>
✅ 여기까지 정상적으로 진행하셨다면 초기 설정이 모두 완료된 것입니다.

</aside>

---

<aside>

💬 위 방법으로 해결되지 않는 문제는 담당자를 통해 문의해주세요.

</aside>