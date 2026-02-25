# 📘 GenAI Platform 설치 간소화 매뉴얼

본 문서는 Tango 2 프로젝트의 GenAI Platform 설치 절차를 
`run_step1_infra_base.sh`, `run_step2_core_infra.sh`, `run_step3_optional_obs.sh` 스크립트로 간소화하여
실제 설치자가 그대로 따라할 수 있도록 단계별 절차를 구체화한 가이드입니다.

상세한 설명은 아래의 Notion 링크를 참조해주시기 바랍니다.
[상세 설치 가이드](https://www.notion.so/Tango-GenAI-Platform-2f69d352990380d28ea0f4767aa0393a?pvs=21)

설치에 필요한 코드와 Helm 차트는 TANGO2 저장소의 main 브랜치에 포함되어 있습니다. 
설치 대상 서버에서 저장소를 내려받은 뒤 절차를 진행합니다.

[https://github.com/ML-TANGO/TANGO2](https://github.com/ML-TANGO/TANGO2)

---

## 📑 목차

- [시스템 요구사항]
- [설치 전 준비사항]
- [설치 단계별 가이드]
- [플랫폼 설치 후 초기 설정]

---

## 0. 개요

- 본 가이드는 **온라인 환경** 기준입니다.
- 오프라인 설치는 별도 이미지 미러링/레지스트리 구성이 필요합니다.
- 설치 순서:
  1) 공통 values 준비  
  2) Step1 기반 인프라  
  3) Step2 코어 인프라  
  4) Step3 옵션 인프라  
  5) 앱 설치(`run.sh`, `run_llm.sh`)  
  6) 초기 설정

---

## 1. 설치 전 준비사항 (공통)

### 1-1. 시스템 요구사항

- OS: Ubuntu 22.04.5 Jammy LTS 이상
- Kubernetes: v1.30.x 권장 (테스트 v1.30.14)
- Helm 3.x, kubectl 설치 및 대상 클러스터 접근 가능

### 1-2. 기본 동작 검증

아래 명령이 모두 정상 응답해야 설치를 시작할 수 있습니다.

```bash
kubectl cluster-info
kubectl get nodes -o wide
helm version
```

추가로 현재 컨텍스트를 반드시 확인합니다.

```bash
kubectl config current-context
```

### 1-3. 작업 디렉터리 확인

모든 통합 스크립트는 `GenAI_Platform/devops`에서 실행합니다.

```bash
cd GenAI_Platform/devops
ls run_step1_infra_base.sh run_step2_core_infra.sh run_step3_optional_obs.sh
```

### 1-4. 핵심 입력값 확정 (필수)

설치 전에 아래 값들을 미리 파악해 두고, 이후 2-2절에서 `values_<서버명>.yaml`에 기입합니다.

- `global.jfb.settings.external.host`
- `global.jfb.volume.*.server` (NFS 서버 IP)
- `global.jfb.volume.*.path` (NFS export 경로)
- `global.jfb.image.users.registry` (사용자 이미지 레지스트리)
- `global.jfb.settings.initRootPassword`
- `global.jfb.settings.kafka.sasl_username`, `global.jfb.settings.kafka.sasl_password`
- `global.jfb.settings.mongoDb.password`

---

## 2. 공통 values 파일 준비 (필수)

### 2-1. 템플릿 복사

```bash
cd GenAI_Platform/devops
cp values.yaml.template values_<서버명>.yaml
# 예: cp values.yaml.template values_tango2.yaml
```

### 2-2. 필수 항목 입력

`values_<서버명>.yaml`에서 아래 키를 실제 환경 값으로 수정합니다.

- `global.jfb.namespace` (기본: `jonathan-system`)
- `global.jfb.volume.jfData.server/path`
- `global.jfb.volume.jfBin.server/path`
- `global.jfb.volume.jfStorage[0].server/path/name`
- `global.jfb.volume.markerData.server/path`
- `global.jfb.volume.src.enabled/path/server` (개발환경 사용 시 enable)
- `global.jfb.settings.external.host/port/protocol`
- `global.jfb.settings.initRootPassword`
- `global.jfb.settings.kafka.sasl_username/sasl_password`
- `global.jfb.settings.mongoDb.password`
- `global.jfb.image.users.registry`

> 권장: 작성 후 `TODO` 문자열이 남았는지 한 번 더 확인합니다.

```bash
rg -n "TODO|<NFS_SERVER_IP>|<EXTERNAL_HOST_IP>|<SRC_PATH>" ./values_<서버명>.yaml
```

### 2-3. 스토리지 경로 생성 및 권한

`values_<서버명>.yaml`에 적은 NFS 경로가 실제로 존재해야 합니다.  
NFS 서버에서 경로를 생성하고 export 설정을 확인합니다.

예시(환경에 맞게 경로 수정):

```bash
sudo mkdir -p /storage/tango-storage/jf-data \
             /storage/tango-storage/jf-bin \
             /storage/tango-storage/tmp-storage \
             /storage/tango-storage/marker-data
sudo chmod -R 775 /storage/tango-storage
```

---

## 3. 단계형 설치 흐름 (의존성 분산)

각 단계는 반드시 **게이트 체크** 후 다음 단계로 진행합니다.

### 3-1. 1단계: 기반 인프라 (필수)

대상: NFS Provisioner 
(+ 베어메탈/온프레미스 환경에서 LoadBalancer 타입 서비스가 필요하면 MetalLB 설치)

#### 실행 명령 (표준)

```bash
cd GenAI_Platform/devops
chmod +x run_step1_infra_base.sh

./run_step1_infra_base.sh \
  --system ./gaip_nfs_provisioner/values-system.yaml \
  --efk ./gaip_nfs_provisioner/values-efk.yaml \
  --metallb
```

옵션:
- EFK 미사용이면 `--efk` 생략
- 클라우드 LB 사용 중이면 `--metallb` 생략

#### 체크 게이트 명령

```bash
kubectl get sc
kubectl get pv
kubectl get pvc -A
```

#### 정상 기준

- `jonathan-system-sc`(또는 사용 환경 StorageClass)가 생성됨
- 관련 PVC가 `Bound` 상태

#### 비정상 기준 및 즉시 조치

- StorageClass 없음: values 파일 경로/파라미터 재확인 후 Step1 재실행
- PVC `Pending`: NFS 경로/권한/export 설정 확인
- PVC `Lost`: 기존 PV/PVC 잔존 여부 확인 후 정리

---

### 3-2. 2단계: 코어 인프라 (필수)

대상: Kong / Registry / MariaDB / Kafka / Redis / MongoDB

#### 실행 명령

```bash
cd GenAI_Platform/devops
chmod +x run_step2_core_infra.sh

# 별도로 --kong, --registry, --mariadb 인자에 넘기는 파일들을 변경하지 않았으면 뒤의 인자는 생략
./run_step2_core_infra.sh \
  --kong ./gaip_kong/values.yaml \
  --registry ./gaip_registry/values.yaml \
  --mariadb ./gaip_maraidb/values.yaml
```

#### 체크 게이트 명령

```bash
kubectl get pods -A
kubectl get svc -A
kubectl get pods -A | rg -n "kong|registry|mariadb|kafka|redis|mongo"
```

#### 정상 기준

- 코어 인프라 관련 Pod가 `Running` 또는 `Completed`
- Kong/Registry 서비스가 생성되어 조회됨

#### 비정상 기준 및 즉시 조치

- `ImagePullBackOff`: 이미지 레지스트리 접근/인증/containerd 설정 확인
- `CrashLoopBackOff`: `kubectl logs -n <ns> <pod>`로 원인 확인
- `Pending`: 노드 라벨/스토리지/PVC 바인딩 상태 확인

---

### 3-3. 3단계: 관측/옵션 (선택)

대상: Prometheus / GPU Operators / EFK

#### 실행 명령

```bash
cd GenAI_Platform/devops
chmod +x run_step3_optional_obs.sh

# 예시 1) Prometheus만
./run_step3_optional_obs.sh --prometheus

# 예시 2) GPU Operators만
./run_step3_optional_obs.sh --gpu

# 예시 3) EFK 설치
./run_step3_optional_obs.sh --efk

# Elastic Pod Running 확인 후 초기화 + Fluent
./run_step3_optional_obs.sh --efk --efk-init
```

#### 체크 게이트 명령

```bash
kubectl get pods -A | rg -n "prometheus|grafana|nvidia|elastic|fluent|kibana"
```

#### 정상 기준

- 선택한 컴포넌트 Pod가 `Running`
- EFK 사용 시 `--efk-init` 이후 Fluent/Elastic 관련 Pod가 정상 상태

#### 비정상 기준 및 즉시 조치

- EFK `Init` 멈춤/권한 오류: NFS 경로 소유권/권한 재확인
- GPU Pod 실패: 각 GPU 노드에서 `nvidia-smi` 정상 동작 재확인

---

## 4. 앱 설치 (필수)

Step1~3 완료 후 앱 차트를 설치합니다.

```bash
cd GenAI_Platform/devops
./run.sh install -f ./values_<서버명>.yaml
./run_llm.sh install -f ./values_<서버명>.yaml
```

### 체크 게이트 명령

```bash
kubectl get pods -n jonathan-system
kubectl get ingress -A
```

### 정상 기준

- `jonathan-system`의 주요 Pod가 `Running` 또는 `Completed`
- 브라우저에서 `external.host` 접속 시 로그인 화면 진입 가능

### 비정상 기준 및 즉시 조치

- 로그인 불가: `user` 관련 Pod 재시작 후 재확인

```bash
kubectl get pod -n jonathan-system | rg user
kubectl delete pod -n jonathan-system <user-pod-name>
```

---

## 5. 설치 후 초기 설정 (UI 기준)

아래 순서로 진행하면 된다. (Notion 상세 가이드의 설명과 이미지 참고)

1. **관리자 로그인**
   - 계정: `admin`
   - 비밀번호: `values_<서버명>.yaml`의 `global.jfb.settings.initRootPassword` 확인

2. **스토리지 등록**
   - 메뉴: 스토리지
   - 등록값:
     - 이름: `local-nfs` (예시)
     - 타입: `nfs`
     - IP: NFS 서버 IP
     - 마운트 경로: values에 넣은 `jfStorage.path` 스토리지 루트 경로와 동일
   - 등록 후 확인:
     ```bash
     kubectl get pod -A | rg -i "storage|provisioner"
     ```

3. **사용자 생성**
   - 메뉴: 사용자 > 사용자 추가
   - 필수 입력: 아이디, 비밀번호, 이름

4. **인스턴스/GPU 자원 활성화(필요 시)**
   - 노드별 자원 표시 여부 확인 후 저장

5. **워크스페이스 생성 및 멤버 추가**
   - 워크스페이스 생성 후, 상세 화면에서 사용자 멤버 할당

6. **사용자 계정 재로그인 확인**
   - 생성한 사용자로 로그인
   - 워크스페이스 목록/대시보드 진입 확인

---

## 6. 문제 해결/복구

### 6-1. PV/PVC 잔존 정리

재설치 전 잔존 리소스를 먼저 확인합니다.

```bash
kubectl get pv
kubectl get pvc -A
```

특정 네임스페이스 PVC 일괄 삭제 예시:

```bash
kubectl delete pvc --all -n <namespace>
```

### 6-2. Redis AOF 복구

Redis AOF 손상 시 Pod 내부에서 복구를 시도합니다.

```bash
/src/redis-check-aof appendonly.aof
```

데이터 보존이 필요 없으면 `devops/gaip_redis/clean_reinstall.sh` 사용을 검토합니다.

### 6-3. EFK 데이터 정리

- EFK 데이터 경로를 먼저 재확인한 뒤 정리
- Elastic 재설치 후 `elastic_init.sh` 재실행

### 6-4. containerd Registry 설정

사설 레지스트리를 HTTP 또는 자체 인증서로 사용할 경우 `/etc/containerd/config.toml`에 registry 설정이 필요할 수 있습니다.  
설정 변경 후 containerd 재시작이 필요합니다.

### 6-5. GPU 드라이버 이슈

GPU 관련 설치 실패 시 우선 확인:

```bash
nvidia-smi
```

- `command not found`: 드라이버/유틸 미설치
- 버전 불일치: 드라이버 재설치 필요
- Secure Boot 이슈: 커널 모듈 로딩 차단 여부 확인

---

## 참고

- 본 문서는 통합 설치 스크립트 기준 운영 가이드입니다.
- 환경별 네트워크/보안 정책에 따라 values 파일은 반드시 현장 값으로 조정해야 합니다.
