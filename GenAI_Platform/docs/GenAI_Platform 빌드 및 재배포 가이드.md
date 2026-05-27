# GenAI Platform 빌드 및 재배포 가이드

> 📌 이 문서는 **GenAI Platform 자체 서비스** (`fb_*`, `llm_*`, `front`) 의 코드를 수정한 뒤 Docker 이미지를 빌드하고 Kubernetes 클러스터에 재배포하는 운영자용 가이드입니다.
>
> 외부 협력기관이 **자체 서비스**를 platform 에 탑재하는 가이드는 [Tango MSA 서비스 Docker 이미지 빌드 가이드](Tango%20MSA%20서비스%20Docker%20이미지%20빌드%20가이드.md) 를 참고하세요.

---

## 0. 사전 조건

- Docker 또는 nerdctl 설치
- 컨테이너 레지스트리 접근 (예: `registry.jonathan.acryl.ai` 또는 자체 레지스트리)
- `kubectl` + `helm` 설치 + 클러스터 컨텍스트 설정
- 운영 환경별 `devops/values_<env>.yaml` 작성됨 (없다면 `devops/values.yaml.template` 에서 복사)

---

## 1. 전체 흐름

```
[코드 수정] → [이미지 빌드] → [레지스트리 Push] → [Helm Upgrade] → [Pod 재시작 확인]
```

서비스 종류별 빌드 entry:

| 서비스 종류 | 빌드 entry | 빌드 컨텍스트 | 이미지명 패턴 |
|---|---|---|---|
| 일괄 (전체 backend) | `apps/build.sh` | `apps/` (부모) | `<REGISTRY>/jfb-system/<APP>_app:<TAG>` |
| 개별 backend | `apps/<svc>/build.sh` | `apps/` (부모) | `<REGISTRY>/jfb-system/<APP>_app:<TAG>` |
| 프론트엔드 | `front/build.sh` | `front/` (자체) | `<REGISTRY>/jfb-system/front_app:<TAG>` |

> 💡 백엔드가 부모 컨텍스트를 쓰는 이유는 공통 라이브러리 `fb_utils` 를 같이 COPY 하기 위함입니다. 프론트엔드는 공통 lib 의존성이 없어 자기 디렉터리만 사용합니다.

---

## 2. 백엔드 서비스 빌드 (fb_*, llm_*)

### 2.1 단일 서비스 빌드

```bash
cd apps/fb_user      # 또는 fb_dataset, llm_model, llm_playground 등
./build.sh
```

interactive 입력 (default 값 받으려면 `y`, 변경하려면 `n`):

```
Image Build CLI? nerdctl? (y/n)         ← nerdctl 또는 docker 선택
Image registry protocol? http (y/n)     ← http / https (nerdctl 만)
Image registry url? registry.jonathan.acryl.ai (y/n)
Image registry version? dev (y/n)       ← 예: v1.0.0, tango_v2.0.1
Image save tar? (y/n)                   ← 오프라인 배포용 .tar 저장 여부
APP NAME? (ex. dashboard)               ← user, dataset, model 등 (디렉터리 prefix 제외)
```

결과 이미지: `<REGISTRY>/jfb-system/user_app:<VERSION>` 가 빌드 + push 됨.

### 2.2 전체 일괄 빌드

```bash
cd apps
./build.sh
# build ALL? (y/n) → y
```

다음 13개 서비스 (+ llm_* 4개) 가 순차 빌드됩니다:
`dashboard, dataset, deployment, external_container, image, monitoring, notification, resource, scheduler, ssh, training, user, workspace, llm_model, llm_playground, llm_prompt, llm_rag`

---

## 3. 프론트엔드 빌드 (front)

### 3.1 빌드

```bash
cd front
./build.sh
```

interactive 입력은 backend 와 동일. `APP NAME` 입력은 없습니다 (front 전용).

결과 이미지: `<REGISTRY>/jfb-system/front_app:<VERSION>`

> ⚠️ 빌드 전에 호스트에서 `yarn install --frozen-lockfile` 이 되어 있는지 확인. Dockerfile 안에서 다시 install 하지만, 일관성 위해 호스트와 동일 lock 사용 권장.

### 3.2 운영 cluster 가 NFS 패턴을 쓰는 경우 (선택)

GenAI_Platform 의 **운영 cluster 1대 (control node `192.168.0.35`)** 는 이미지 재빌드 없이 호스트의 `yarn build` 산출물을 NFS 로 pod 에 실시간 반영하는 빠른 패턴을 함께 운영합니다:

```bash
cd front
yarn build                              # build/ 생성
# pod 안 /app/build 가 이미 /front-data/build 로 symlink 되어 있으면 즉시 반영됨
# 첫 설정 시:
FRONT_POD=$(kubectl get pod -n jonathan-system -l app=front -o name | head -1)
kubectl exec -n jonathan-system $FRONT_POD -- sh -c \
  "rm -rf /app/build && ln -s /front-data/build /app/build && nginx -s reload"
```

> 다른 cluster (NFS 없거나 호스트 직접 접근 불가) 는 위 패턴을 못 씁니다 → **이미지 빌드 방식으로 배포**.

---

## 4. Helm Upgrade (이미지 적용)

빌드/Push 된 이미지의 **tag** 를 `devops/values_<env>.yaml` 에 반영한 뒤 helm upgrade.

### 4.1 values 파일에서 image tag 갱신

`devops/values_<env>.yaml` 의 image 섹션 (서비스별로 다름):

```yaml
global:
  jfb:
    image:
      registry:
        host: registry.jonathan.acryl.ai
        prefix: jfb-system
      tag: <NEW_TAG>          # ← 일괄 변경하려면 여기
      front: acrylaaai/genai-platform-front:<NEW_TAG>   # ← front 만 다르면 여기
```

> 💡 환경별 values 파일은 gitignored (`devops/values_*_dev.yaml` 등). 운영 IP/비밀번호 포함하므로 별도 채널로 공유.

### 4.2 단일 서비스 helm upgrade

```bash
cd devops
helm upgrade -n jonathan-system <release-name> <chart-dir>/helm --values values_<env>.yaml
# 예시:
helm upgrade -n jonathan-system front fb_front/helm --values values_tango2.yaml
helm upgrade -n jonathan-system user fb_user/helm --values values_tango2.yaml
```

### 4.3 일괄 helm upgrade

```bash
cd devops
./run.sh upgrade -f ./values_<env>.yaml
# 또는 LLM 서비스만:
./run_llm.sh upgrade -f ./values_<env>.yaml
```

### 4.4 Pod 재시작 확인

```bash
kubectl get pods -n jonathan-system | grep <service>
kubectl rollout status deployment/<deployment-name> -n jonathan-system
```

특정 deployment 강제 재배포 (image tag 가 같지만 코드 변경 반영하고 싶을 때):

```bash
kubectl rollout restart deployment/jfb-app-front -n jonathan-system
```

---

## 4.5 개발용 소스코드 마운트 (이미지 재빌드 없이 코드 반영)

`devops/values_<env>.yaml` 의 `src.enabled: true` / `front.enabled: true` 설정으로 호스트 소스를 pod 에 NFS 또는 hostPath mount 하는 개발 모드가 있습니다. 운영자 cluster 에서 이 모드를 쓰는 경우 코드 변경 반영 방법:

| 대상 | 변경 반영 방법 |
|---|---|
| 백엔드 (fb_*, llm_*) | 호스트에서 `apps/<svc>/src/...` 수정 → `kubectl rollout restart deployment/<name> -n jonathan-system` → 새 코드로 uvicorn 재기동 |
| 프론트엔드 (front) | 호스트에서 `cd front && yarn build` → NFS 가 새 `build/` 를 즉시 반영 → 브라우저 강력 새로고침 (pod restart 불필요) |

> 💡 backend 는 `uvicorn --reload` 를 운영에서 끄는 경우가 많아 pod restart 가 필요합니다. front 는 nginx 가 static `/app/build` 만 serving 하므로 build 산출물만 갱신되면 됨.
>
> ⚠️ 운영 배포에선 mount 모드 끄기 권장 (`src.enabled: false`) — 이미지에 baked-in 된 코드가 재현성/롤백 측면에서 안전.

---

## 5. 자주 발생하는 문제

| 증상 | 원인 | 해결 |
|---|---|---|
| `ImagePullBackOff` | 이미지 경로 오타 또는 인증 실패 | `docker push` 성공 확인, `imagePullSecrets` 설정 확인 |
| Pod 안 코드가 옛 버전 | helm upgrade 후에도 `imagePullPolicy: IfNotPresent` 라 캐시된 이미지 사용 | `kubectl rollout restart deployment/...` 또는 image tag 변경 |
| front 변경이 안 보임 (NFS 패턴) | pod 재시작 후 `/app/build` symlink 휘발 | 3.2 의 symlink 재설정 명령 실행 |
| `helm upgrade` 가 PV 갱신 실패 | NFS path 같은 immutable field 변경 시도 | PVC delete → PV finalizer 해제 → helm upgrade 로 새 PV 생성 |
| backend 가 `fb_utils` import 실패 | 빌드 컨텍스트가 service 디렉터리 (`.`) 였음 | `apps/<svc>/build.sh` 사용 (컨텍스트 `..` 자동 지정) |

---

## 6. 빠른 reference

```bash
# backend 단일
cd apps/fb_user && ./build.sh

# backend 전체
cd apps && ./build.sh   # build ALL? y

# frontend
cd front && ./build.sh

# helm upgrade (단일)
cd devops && helm upgrade -n jonathan-system <release> <chart>/helm --values values_<env>.yaml

# helm upgrade (전체 app)
cd devops && ./run.sh upgrade -f ./values_<env>.yaml

# helm upgrade (LLM 만)
cd devops && ./run_llm.sh upgrade -f ./values_<env>.yaml

# 강제 재배포 (코드만 변경, tag 동일)
kubectl rollout restart deployment/<name> -n jonathan-system

# [개발 모드 — src.enabled: true 인 경우]
# backend: 호스트 코드 수정 후
kubectl rollout restart deployment/jfb-app-<svc> -n jonathan-system
# frontend: 호스트에서 빌드만 (pod restart 불필요)
cd front && yarn build
```

---

## 7. 관련 문서

- [Tango MSA 서비스 Docker 이미지 빌드 가이드](Tango%20MSA%20서비스%20Docker%20이미지%20빌드%20가이드.md) — 외부 협력기관이 자체 service 를 만들 때
- [Tango MSA 탑재 가이드](Tango%20MSA%20탑재%20가이드.md) — Helm chart 작성 + 등록
- [Tango 모델 탑재 가이드](Tango%20모델%20탑재%20가이드.md) — LLM 모델 등록
- `devops/INSTALL.md` — 인프라 설치 순서 (Kong/MariaDB/Kafka/Redis 등)
