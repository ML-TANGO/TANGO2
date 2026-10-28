# GenAI Platform 빌드 및 재배포 가이드

> 📌 이 문서는 **GenAI Platform 자체 서비스**(`apps/fb_*`, `apps/llm_*`, `front`)의 코드를 수정한 뒤 이미지를 빌드하고
> Kubernetes 클러스터에 다시 배포하는 운영자용 가이드입니다. 외부 컨테이너(평가·양자화) 이미지와 서빙 엔진 이미지는 6장에 간단히 정리했습니다.
>
> 외부 협력기관이 **자체 서비스**를 플랫폼에 탑재하는 방법은 [Tango MSA 서비스 Docker 이미지 빌드 가이드](Tango%20MSA%20서비스%20Docker%20이미지%20빌드%20가이드.md) 를 참고하세요.

경로는 모두 저장소의 `LLMOps/` 기준입니다. 아래에서 `<REGISTRY>` 는 이미지를 올릴 레지스트리(예: `<노드 IP>:30500` 또는 사내 레지스트리 주소),
`NS` 는 플랫폼 네임스페이스(`${JF_NAMESPACE:-jonathan-system}`, 기본 `jonathan-system`)입니다.

---

## 0. 사전 조건

- 빌드 도구: `nerdctl`(containerd + buildkit) 또는 `docker`
- `<REGISTRY>` 에 push 할 수 있고, 클러스터 노드가 그 레지스트리에서 pull 할 수 있어야 함
  (HTTP 레지스트리면 모든 노드 containerd 에 설정 필요 — 설치 매뉴얼의 containerd 레지스트리 설정 참고)
- `kubectl` · `helm` 설치, 대상 클러스터 컨텍스트 확인
- 환경별 `devops/values_<env>.yaml` (없다면 `devops/values.yaml.template` 에서 복사). `LLMOps/.gitignore` 가 `/devops/values_*.yaml` 을
  제외하므로 저장소에 커밋되지 않습니다.

---

## 1. 전체 흐름

```
[코드 수정] → [이미지 빌드·push] → [values 의 이미지 태그 갱신] → [helm upgrade] → [Pod 재시작 확인]
```

| 대상 | 빌드 entry | 빌드 컨텍스트 | 결과 이미지 |
|---|---|---|---|
| 백엔드 일괄 | `apps/build.sh` (build ALL = y) | `apps/` (부모) | `<REGISTRY>/jfb-system/<APP>_app:<VERSION>` |
| 백엔드 단일 | `apps/build.sh` (build ALL = n) 또는 `apps/<svc>/build.sh` | `apps/` (부모) | 위와 같음 (crictl 방식 스크립트는 2-3절) |
| 프론트엔드 | `front/build.sh` | `front/` (자체) | `<REGISTRY>/jfb-system/front_app:<VERSION>` |

> 💡 백엔드는 공통 라이브러리 `fb_utils` 를 함께 COPY 하기 때문에 부모(`apps/`) 컨텍스트로 빌드합니다
> (`Dockerfile` 의 `COPY fb_<svc> /app`, `COPY fb_utils /utils`). 프론트엔드는 공통 lib 의존성이 없어 자기 디렉터리만 씁니다.

---

## 2. 백엔드 서비스 빌드 (fb_*, llm_*)

### 2-1. 일괄 빌드 — `apps/build.sh`

```bash
cd apps
./build.sh
```

대화형 입력 (`y` = 표시된 기본값 사용, `n` = 직접 입력):

```
Image Build CLI? nerdctl? (y/n)        ← n 이면 docker
Image registry protocol? http (y/n)    ← nerdctl 일 때만. http 면 --insecure-registry 로 push
Image registry url? <기본값> (y/n)      ← 기본값은 개발팀 내부 레지스트리 — 다른 환경은 n 후 <REGISTRY> 입력
Image registry version? 0.3.0 (y/n)    ← n 후 태그 입력 (예: 1.0.0)
build ALL? (y/n)                       ← y = 아래 21개 일괄
Image save tar? (y/n)                  ← y 면 오프라인 반입용 <APP>.tar 를 각 앱 디렉터리에 저장
```

`build ALL = y` 의 대상은 `devops/run.sh`·`run_llm.sh` 가 배포하는 앱 중 Dockerfile 이 있는 21개입니다.

```
dashboard dataset deployment external_container image monitoring notification resource scheduler
user workspace option alert_management ingress_management collect preprocessing pipeline analyzing
synthesis evaluation data_pipeline
```

- `evaluation`·`data_pipeline` 은 `apps/llm_<APP>`, 나머지는 `apps/fb_<APP>` 디렉터리에서 빌드합니다.
- **`llm_model`·`llm_playground` 는 일괄 대상이 아닙니다.** `build ALL = n` 에서 `model` / `playground` 로 따로 빌드합니다.
- 디렉터리가 없으면 그 자리에서 중단합니다(예전처럼 직전 앱을 다른 태그로 다시 빌드하지 않습니다).

### 2-2. 단일 빌드

**방법 A — `apps/build.sh` 단일 모드 (모든 앱 공통)**

`build ALL? n` → `APP NAME?` 에 디렉터리 접두어(`fb_`/`llm_`)를 뺀 이름을 입력합니다.

| 입력 | 빌드 디렉터리 | 결과 이미지 |
|---|---|---|
| `user`, `dataset`, `scheduler`, `external_container` … | `apps/fb_<APP>` | `<REGISTRY>/jfb-system/<APP>_app:<VERSION>` |
| `model`, `playground`, `evaluation`, `data_pipeline` | `apps/llm_<APP>` | `<REGISTRY>/jfb-system/<APP>_app:<VERSION>` |

**방법 B — 앱 디렉터리의 `build.sh`**

앱마다 스크립트 형태가 다릅니다.

| 형태 | 앱 | 동작 |
|---|---|---|
| 대화형 (`apps/build.sh` 단일 모드와 같음, 기본 버전 `dev`) | `fb_alert_management`, `fb_analyzing`, `fb_collect`, `fb_deployment`, `fb_image`, `fb_ingress_management`, `fb_monitoring`, `fb_option`, `fb_preprocessing`, `fb_synthesis`, `fb_user`, `fb_workspace`, `llm_model`, `llm_playground` | CLI·프로토콜·레지스트리·버전·tar 저장 여부를 묻고 `APP NAME?`(예: `user`, `model`)을 받아 `<REGISTRY>/jfb-system/<APP NAME>_app:<VERSION>` 을 build·push. `llm_playground` 는 `REGISTRY=<REGISTRY> ./build.sh` 로 기본 레지스트리를 지정할 수 있음 |
| crictl 방식 (x.y.z 태그) | `fb_dashboard`, `fb_dataset`, `fb_notification`, `fb_resource`, `fb_pipeline` | 2-3절 |
| `build.sh` 없음 | `fb_scheduler`, `fb_external_container`, `llm_evaluation`, `llm_data_pipeline` | 방법 A 사용 (`scheduler`, `external_container`, `evaluation`, `data_pipeline`) |

```bash
cd apps/fb_user && ./build.sh      # APP NAME? user
cd apps/llm_model && ./build.sh    # APP NAME? model
```

### 2-3. crictl 방식 스크립트 (fb_dashboard · fb_dataset · fb_notification · fb_resource · fb_pipeline)

- 노드의 `sudo crictl images` 에서 같은 이름의 최신 이미지를 찾아 보여 주고, 새 태그를 **x.y.z** 형식으로 받아 build·push 합니다
  (`fb_pipeline` 은 형식 검사 없음). 이전 이미지가 없으면 스크립트에 적힌 첫 버전으로 빌드합니다.
- `sudo nerdctl` 또는 `sudo docker` 를 스크립트마다 고정해 씁니다.
- **이미지 이름이 `apps/build.sh` 와 다릅니다** — `<레지스트리>/jfb-system/<디렉터리명>:<x.y.z>` (예: `.../jfb-system/fb_dashboard:1.2.3`).
  `fb_pipeline` 만 `pipeline_app` 입니다. values 에 넣을 때 이 이름을 그대로 씁니다.
- 레지스트리는 스크립트 첫 줄의 `IMAGE_REGI` 입니다. `fb_dashboard`·`fb_notification` 은 `REGISTRY=<REGISTRY> ./build.sh` 로 지정합니다.

이름을 `<APP>_app` 으로 통일하고 싶다면 방법 A(`apps/build.sh` 단일 모드)를 씁니다.

### 2-4. 의존성을 바꿀 때 — `constraints.txt` 유지

배포 중인 이미지(`tango_v2.0.1`)와 같은 런타임이 다시 빌드되도록 의존성과 베이스 이미지가 고정되어 있습니다.

- 19개 앱(`fb_alert_management`, `fb_analyzing`, `fb_collect`, `fb_dataset`, `fb_deployment`, `fb_external_container`, `fb_image`,
  `fb_monitoring`, `fb_pipeline`, `fb_preprocessing`, `fb_resource`, `fb_scheduler`, `fb_synthesis`, `fb_user`, `fb_workspace`,
  `llm_data_pipeline`, `llm_evaluation`, `llm_model`, `llm_playground`)은 `constraints.txt`(서빙 이미지의 pip freeze)를 두고
  Dockerfile 이 `pip install -r requirements.txt -c constraints.txt` 로 설치합니다(추가 `pip install` 에도 `-c` 적용).
- `fb_dashboard`·`fb_ingress_management`·`fb_notification`·`fb_option` 은 `requirements.txt` 자체가 서빙 freeze 입니다.
- 패키지를 추가·변경할 때는 `requirements.txt` 만 고치지 말고 **`constraints.txt` 의 고정 버전도 함께** 맞춥니다. `-c` 를 빼거나
  `constraints.txt` 를 지우면 고정 안 된 패키지가 새 버전으로 올라가 서빙과 다른 런타임이 됩니다.
- Dockerfile 의 베이스 이미지 태그(예: `fb_user` 의 `python:3.12.0-bookworm`)도 서빙과 맞춘 값이므로 함부로 올리지 않습니다.

---

## 3. 프론트엔드 빌드 (front)

### 3-1. 이미지 빌드

```bash
cd front
./build.sh
```

대화형 입력은 백엔드와 같고(기본 버전 `dev`), `APP NAME` 입력은 없습니다. 결과 이미지: `<REGISTRY>/jfb-system/front_app:<VERSION>`.
레지스트리 기본값은 개발팀 내부 주소이므로 다른 환경에서는 `n` 을 눌러 `<REGISTRY>` 를 입력합니다.

`front/Dockerfile` 이 컨테이너 안에서 yarn 4 로 빌드하므로 호스트에서 미리 설치할 것은 없습니다.

```dockerfile
FROM node:20 as build-stage
...
RUN corepack enable && corepack prepare yarn@4.17.1 --activate
RUN yarn install --immutable
RUN yarn vite build        # → /app/build, nginx 가 8001 포트로 서빙
```

### 3-2. 개발 모드 (`front.enabled: true`) — 이미지 재빌드 없이 반영

values 의 `global.jfb.volume.front.enabled: true` 이면 front 파드가 `front.path`(체크아웃의 `LLMOps/front`)를 `/front-data` 로
마운트하고, **기동할 때 `/app/build` 를 `/front-data/build` 로 자동 연결**합니다(`devops/fb_front/helm/templates/deployment.yaml`).
수동으로 심볼릭 링크를 만들 필요가 없습니다.

`yarn.lock` 이 yarn 4(berry) 형식이라 yarn 1·npm 으로는 설치되지 않습니다. 호스트에서 이미지와 같은 방식으로 빌드합니다.

```bash
cd front
corepack enable && corepack prepare yarn@4.17.1 --activate   # 버전은 front/Dockerfile 과 동일
yarn install --immutable
yarn vite build                                              # → front/build
```

빌드가 끝나면 브라우저 강력 새로고침으로 반영됩니다(파드 재시작 불필요).
이 모드를 쓰지 않는 클러스터(`front.enabled: false`)는 **3-1 이미지 빌드 방식으로 배포**합니다.

---

## 4. Helm 반영 (이미지 적용)

### 4-1. values 의 이미지 키 갱신

이미지는 `global.jfb.image.system.registry` 와 앱별 키 `global.jfb.image.<앱>` 을 이어 붙여 만듭니다
(`<system.registry>/<image.앱>`). **`external_container` 만 예외로 값 전체를 그대로 이미지로 씁니다.**

```yaml
# devops/values_<env>.yaml
global:
  jfb:
    image:
      system:
        registry: "<REGISTRY>"              # 모든 앱 이미지 앞에 붙음
        protocol: http://                   # HTTP 레지스트리면 http://
      pullPolicy: Always                    # 템플릿 기본값 — 같은 태그도 재시작 시 다시 받음
      user: jfb-system/user_app:<NEW_TAG>
      dataset: jfb-system/dataset_app:<NEW_TAG>
      model: jfb-system/model_app:<NEW_TAG>
      front: jfb-system/front_app:<NEW_TAG>
      external_container: <REGISTRY>/jfb-system/external_container_app:<NEW_TAG>   # 레지스트리 포함 전체 참조
```

- 앱별 키 이름은 `values.yaml.template` 의 `global.jfb.image.*` 와 같습니다
  (`user`, `workspace`, `dashboard`, `resource`, `deployment`, `dataset`, `image`, `monitoring`, `scheduler`, `notification`, `collect`,
  `playground`, `model`, `evaluation`, `data_pipeline`, `pipeline`, `preprocessing`, `analyzing`, `synthesis`, `option`,
  `ingress_management`, `alert_management`, `external_container`, `front`, `bin` 등).
- `system.registry` 는 모든 앱(과 `bin` 등 시스템 이미지)에 공통으로 붙습니다. 레지스트리를 바꾸면 **바꾸지 않은 앱의 이미지도 그 레지스트리에 있어야** 합니다.
  템플릿 기본값(`docker.io` + `acrylaaai/genai-platform-*:tango_v2.0.1`)을 쓰는 중이라면 나머지 이미지를 `<REGISTRY>` 로 미러링하거나,
  새 이미지를 같은 레지스트리 체계에 올립니다.

### 4-2. 단일 차트 업그레이드

앱 차트의 의존성(`helm/charts/`, `Chart.lock`)은 대부분 저장소에서 제외되어 있으므로 **`helm dependency update` 를 먼저** 실행합니다.

```bash
cd devops
NS=${JF_NAMESPACE:-jonathan-system}
helm dependency update fb_user/helm
helm upgrade -n $NS user fb_user/helm --values ./values_<env>.yaml
```

릴리스 이름은 `run.sh`·`run_llm.sh` 가 만든 이름을 그대로 씁니다.

| 차트 디렉터리 | 릴리스 | Deployment (`global.jfb.name.*`) |
|---|---|---|
| `fb_<app>/helm` (run.sh) | `<app>` 의 `_` 를 `-` 로 (예: `user`, `dataset`, `common-app`, `alert-management`, `ingress-management`, `external-container`) | `jfb-app-<app>` (예: `jfb-app-user`, `jfb-app-external-container`) |
| `fb_monitoring/helm` | **`monitoring-app`** (예외) | `jfb-app-monitoring` |
| `fb_front/helm` | `front` | `jfb-app-front` |
| `llm_model/helm` | `model` | `jfb-llm-model` |
| `llm_playground/helm` | `playground` | `jfb-llm-playground` |
| `llm_evaluation/helm` | `evaluation` | `jfb-llm-evaluation` |
| `llm_data_pipeline/helm` | `data-pipeline` | `jfb-llm-data-pipeline` |

### 4-3. 일괄 업그레이드

```bash
cd devops
./run.sh upgrade -f ./values_<env>.yaml       # 플랫폼 앱 21개 (차트마다 helm dependency update 포함)
./run_llm.sh upgrade -f ./values_<env>.yaml   # model · playground · evaluation · data-pipeline
```

두 스크립트는 `JF_NAMESPACE` 환경변수(기본 `jonathan-system`)를 설치 네임스페이스로 씁니다. 다른 네임스페이스 인스턴스라면
`JF_NAMESPACE=<ns> ./run.sh upgrade -f ...` 처럼 지정하고, values 의 `global.jfb.namespace` 도 같은 값이어야 합니다.

### 4-4. Pod 재시작 확인

```bash
kubectl get pods -n $NS -l app=jfb-app-user
kubectl rollout status deployment/jfb-app-user -n $NS
```

태그가 같고 코드만 바뀐 이미지를 다시 받게 하려면(`pullPolicy: Always` 전제):

```bash
kubectl rollout restart deployment/jfb-app-front -n $NS
kubectl get pods -n $NS -l app=jfb-app-front
```

### 4-5. 소스 마운트 개발 모드 (`src.enabled: true`)

values 의 `global.jfb.volume.src.enabled: true` 이면 각 백엔드 파드에 `<src.path>/<앱 디렉터리>` 가 `/app` 으로, `fb_utils` 가 함께
마운트되어 **이미지 안의 코드를 덮어씁니다.**

| 대상 | 변경 반영 방법 |
|---|---|
| 백엔드 (fb_*, llm_*) | 체크아웃의 `apps/<svc>/src/...` 수정 → `kubectl rollout restart deployment/<Deployment> -n $NS` (대부분 앱의 `run.sh` 는 uvicorn `--reload` 가 꺼져 있어 재시작 필요) |
| 프론트엔드 | `front.enabled: true` 면 3-2 의 호스트 빌드만 (재시작 불필요) |

> ⚠️ 이 모드에서는 이미지를 새로 빌드해도 마운트된 소스가 우선합니다. 운영 배포는 `src.enabled: false` 로 이미지에 포함된 코드를
> 쓰는 것을 권장합니다(재현성·롤백).

---

## 5. 자주 발생하는 문제

| 증상 | 원인 | 해결 |
|---|---|---|
| `ImagePullBackOff` | 이미지 경로·태그 오타, 인증 실패, HTTP 레지스트리 미설정 | push 성공·태그 확인, `pullSecrets` 설정, 노드 containerd 레지스트리 설정 |
| 다른 앱 이미지까지 `ImagePullBackOff` | `system.registry` 를 바꿨는데 나머지 이미지가 새 레지스트리에 없음 | 4-1 — 나머지 이미지를 미러링하거나 레지스트리를 되돌림 |
| Pod 안 코드가 옛 버전 | 같은 태그 + 캐시 이미지, 또는 `src.enabled: true` 로 소스가 마운트됨 | `kubectl rollout restart`, 태그 변경, 4-5 확인 |
| `helm upgrade` 가 의존성 오류 | `helm/charts/` 가 비어 있음 | `helm dependency update <chart>/helm` 후 재실행 |
| `helm upgrade` 가 PV 갱신 실패 | NFS path 같은 immutable 필드 변경 | PVC 삭제 → PV finalizer 해제 → helm upgrade 로 새 PV 생성 |
| 백엔드가 `fb_utils` import 실패 | 빌드 컨텍스트를 서비스 디렉터리(`.`)로 지정 | `apps/build.sh` 또는 `apps/<svc>/build.sh` 사용 (컨텍스트 `..`) |
| 프론트 빌드가 lockfile 오류 | yarn 1 · npm 사용 | 3-2 의 corepack + yarn 4 사용 |
| values 에 넣은 이미지가 없음 | crictl 방식 스크립트의 이미지 이름(`fb_<app>`)과 `<app>_app` 혼동 | 2-3 확인 |

---

## 6. 외부 컨테이너 · 서빙 엔진 이미지 (참고)

플랫폼 앱 차트가 아니라 잡/배포 파드가 쓰는 이미지입니다. values 가 아니라 manifest·설정 상수가 이미지를 가리킵니다.

### 6-1. 외부 컨테이너 (평가 · 양자화)

| 앱 | 빌드 | 기본 이미지 |
|---|---|---|
| `evaluate_lmeval`, `evaluate_intent`, `evaluate_logickor_judge` | 디렉터리의 `build.sh` — 필요한 파일만 스테이징해 `sudo buildctl` 로 빌드하고 **이 노드** containerd(k8s.io)에 적재. `TAG=<이미지> ./build.sh` 로 태그 지정. 레지스트리 push 는 `evaluate_lmeval` 만 `PUSH=1` 로 지원 — 나머지는 적재된 이미지를 직접 push 하거나 다른 노드에 반입 | `docker.io/acrylaaai/evaluate-*` |
| `convert`, `evaluate`, `evaluate_benchmark_mock`, `evaluate_logickor` | `build.sh` 없음 — 디렉터리 자체가 컨텍스트: `docker build -t <이미지> apps/<dir>` 후 push | `docker.io/acrylaaai/convert-llamacpp` 등 |

이미지를 바꾼 뒤에는 manifest 를 함께 갱신합니다.

1. 정본 `apps/<dir>/manifest.yaml` 과 부팅 시드 사본 `apps/fb_external_container/manifests/<name>.yaml` 의 `spec.image` 를 새 이미지로,
   **`metadata.version` 을 올립니다**(시드는 이미 있는 `(name, version)` 을 건너뛰므로 버전을 올리지 않으면 반영되지 않습니다).
2. 플랫폼이 어느 판본에 바인딩할지는 `apps/fb_utils/settings.py` 의 `*_MANIFEST_NAME` / `*_MANIFEST_VERSION` 이 정하며 환경변수로 덮을 수 있습니다
   (`llm_model` 차트는 `CONVERT_MANIFEST_*`·`SDS_MANIFEST_*` 를 템플릿에서 지정).
3. `kubectl rollout restart deployment/jfb-app-external-container -n $NS` 로 시드합니다.

### 6-2. 서빙 엔진 (LLM 배포 파드)

- 소스: `libs/fb_image/llm*/` (`llm` = vLLM, `llm_llamacpp`, `llm_tgi`, `llm_ollama`, `llm_triton`, `llm_tensorrt`) 의 `Dockerfile`·`build.sh`.
- 이미지 이름은 `apps/fb_utils/settings.py` 의 `DEPLOYMENT_LLM_*_IMAGE`(예: `acrylaaai/llm_deployment:dev`, `acrylaaai/llm_deployment_llamacpp:dev`)와
  **같아야** 합니다. 배포 시 플랫폼이 앞에 **사용자 레지스트리**(`global.jfb.image.users.registry`)를 붙이므로
  `<USER_REGISTRY>/acrylaaai/llm_deployment...:dev` 경로로 push 합니다.
- `llm_playground` 가 기동할 때 이 이미지들을 image 테이블에 등록(레지스트리가 바뀌었으면 갱신)합니다. 레지스트리를 바꿨다면
  `kubectl rollout restart deployment/jfb-llm-playground -n $NS` 합니다.
- `libs/fb_image/llm/build.sh`(vLLM)는 태그·버전 기본값이 settings 값과 다르므로 프롬프트에서 `acrylaaai/llm_deployment` / `dev` 를 입력합니다.

---

## 7. 빠른 reference

```bash
NS=${JF_NAMESPACE:-jonathan-system}

# 백엔드 단일 / 전체
cd apps && ./build.sh                 # build ALL? n → APP NAME? user   |   build ALL? y (21개)
cd apps/llm_model && ./build.sh       # APP NAME? model

# 프론트 이미지
cd front && ./build.sh

# helm upgrade (단일)
cd devops && helm dependency update fb_user/helm \
  && helm upgrade -n $NS user fb_user/helm --values ./values_<env>.yaml

# helm upgrade (전체 앱 / LLM 앱)
cd devops && ./run.sh upgrade -f ./values_<env>.yaml
cd devops && ./run_llm.sh upgrade -f ./values_<env>.yaml

# 강제 재배포 (같은 태그, pullPolicy: Always)
kubectl rollout restart deployment/<Deployment> -n $NS

# [개발 모드 — src.enabled: true]
kubectl rollout restart deployment/jfb-app-<svc> -n $NS
# [개발 모드 — front.enabled: true] 호스트 빌드만
cd front && corepack enable && corepack prepare yarn@4.17.1 --activate && yarn install --immutable && yarn vite build
```

---

## 8. 관련 문서

- [Tango MSA 서비스 Docker 이미지 빌드 가이드](Tango%20MSA%20서비스%20Docker%20이미지%20빌드%20가이드.md) — 외부 협력기관이 자체 서비스를 만들 때
- [Tango MSA 탑재 가이드](Tango%20MSA%20탑재%20가이드.md) — Helm chart 작성 + 등록
- [Tango 모델 탑재 가이드](Tango%20모델%20탑재%20가이드.md) — LLM 모델 등록
- `devops/INSTALL.md`, `devops/Tango GenAI Platform 설치 매뉴얼.md` — 인프라·플랫폼 설치
