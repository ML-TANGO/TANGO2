# Tango2 GenAI Platform (LLMOps)

[![License](https://img.shields.io/badge/License-GPLv3%20%7C%20Commercial-blue.svg)](../LICENSE.md)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-1.34-blue.svg)](devops/CLUSTER-SETUP.md)

TANGO2 프로젝트의 LLMOps 플랫폼입니다. 쿠버네티스 위에서 **학습 데이터 구축 → 파인튜닝 → 양자화 → 배포/추론 → 평가**까지 LLM·VLM 개발 전 과정을 웹 UI로 제공하고, 협력기관 컨테이너와 엣지 디바이스를 같은 흐름에 붙일 수 있게 합니다.

## 개요

| 항목 | 내용 |
|---|---|
| 버전 | **v2.0.1** — 플랫폼 앱 이미지 태그 `tango_v2.0.1` (`devops/values.yaml.template` 의 `global.jfb.image.*`, 기본 레지스트리 docker.io `acrylaaai/genai-platform-*`) |
| 형태 | 마이크로서비스(FastAPI) + React 프론트엔드, Helm 차트로 설치 |
| 대상 | 단일 노드부터 다중 노드 쿠버네티스 클러스터, 폐쇄망 설치 지원(HF 토큰 선택, 레지스트리 교체) |
| 설치 | [`devops/CLUSTER-SETUP.md`](devops/CLUSTER-SETUP.md) → [`devops/INSTALL.md`](devops/INSTALL.md) |
| 문서 목차 | [`docs/README.md`](docs/README.md) |

---

## 주요 기능

### 사용자 메뉴

워크스페이스를 고르면 사이드바 상단의 **대시보드 · 드라이브** 카드와 아래 다섯 메뉴가 보입니다.

| 메뉴 | 할 수 있는 일 |
|---|---|
| **대시보드** | 워크스페이스 자원(인스턴스·GPU·스토리지) 사용 현황과 진행 중인 작업 |
| **드라이브** | 데이터셋 파일 업로드·관리. 데이터셋 상세에서 **포맷 변환**(CSV / TXT / Parquet → JSON·JSONL, `text`·`instruction`·`chat` 형식)과 **SDS → LLaVA 학습 형식 변환** |
| **데이터** | **학습 데이터 파이프라인** — 업로드 → 전처리 → 필터 → 생성 → VLM 심사 → 사람 검수 → 분포 분석 → 구성·분할 → 버전 릴리스. 단계마다 독립 잡으로 실행되고 실행 이력·실행 간 비교가 남습니다. 프리셋은 **범용**과 **해양 COLREG**(SDS 영상 프레임·AIS 정제·장면 구성·조인·COLREG 조우 판정 단계 추가) |
| **모델** | 모델 생성 3종 — ① Hugging Face 모델 ② 플랫폼에 있는 모델(커밋)에서 시작 ③ **도메인(SDS)**: 협력기관 VLM 학습 컨테이너 기반. LoRA 파인튜닝(DeepSpeed, 정밀도 자동, 8-bit 로딩 옵션)·실시간 학습 그래프·커밋. SDS 는 **레시피 phase 단위 실행**(그래프·로그·학습 파일·재학습), **체크포인트 관리**(목록·best 지정·삭제·이어서 학습). **양자화** 탭에서 커밋을 llama.cpp **GGUF**(Q4_K_M / Q5_K_M / Q6_K) 포팅 패키지로 변환 — SDS 는 LoRA merge 후 비전 인코더(`mmproj`) 동봉 |
| **배포** | 배포 유형 4종 — **클러스터**(서빙 엔진 vLLM · llama.cpp · TGI · Ollama · Triton · TensorRT-LLM 중 선택), **온디바이스(엣지)**(GGUF 패키지를 등록된 엣지 디바이스로 전달·실행), **독립 패키지**(오프라인 번들 + 실행 스크립트), **외부 LLM(API)**(ChatGPT · Claude · Gemini 또는 사용자 엔드포인트를 플랫폼 배포처럼 사용). 배포 상세의 **외부 API 게시**로 API 키를 발급해 클러스터 밖에서 호출(키 회전·게시 해제) |
| **추론** | 실행 중인 배포를 골라 채팅·데이터셋 추론. VLM 배포는 **이미지 입력**, 추론 화면에서 **프롬프트 최적화**(few-shot 최적 프롬프트 탐색 후 주입) |
| **평가** | **평가 프로젝트** 단위 관리. 평가 유형 4종 — **정답 대조**(lm-evaluation-harness 실채점: ARC·MMLU·GSM8K·KMMLU 등 + 사용자 파일), **LLM 심사**(LogicKor, 심판 LLM), **의도/슬롯 평가**(MixATIS), **전문가 검수**(사람 채점, 멀티모달 샘플·SDS AIS 표). 평가 대상 출력은 실행 중인 배포로 생성, 실행 로그 조회, **리포트 내보내기**(실행 1건·프로젝트 전체, Markdown 다운로드·브라우저 인쇄 PDF) |

### 관리자 메뉴

| 메뉴 | 할 수 있는 일 |
|---|---|
| **워크스페이스** | 워크스페이스 생성·자원 할당 |
| **데이터셋** | 전체 워크스페이스의 데이터셋 조회 |
| **노드** | 쿠버네티스 노드 현황 + **엣지 디바이스 등록·관리**(등록 위저드, heartbeat 상태, ops 토큰 조회·재발급) |
| **Edge API 규격** | 엣지 에이전트가 구현할 통신 규약(OpenAPI) 뷰어 |
| **스토리지** | 워크스페이스용 NFS 스토리지 등록 (워크스페이스 생성 전 필수) |
| **기록** | 워크스페이스·인스턴스 사용 기록 |
| **사용자** | 사용자 계정 관리 |

> 화면에서 **가려 두거나 비활성화한 기능**(백엔드 코드는 유지): 이중모델(프롬프트 생성 LLM + 추론 LLM) 배포(`front/src/featureFlags.js` 의 `SHOW_DUAL_DEPLOY = false`), 라벨링, 데이터 수집, 도커 이미지 메뉴는 화면·라우트에서 빠져 있고, 범용 Multimodal 모델 생성과 SDM·SDF 도메인은 모델 생성 화면에 비활성 선택지로만 보입니다. 지원 기능으로 안내하지 않습니다.

### 운영 기능

- **서빙·개발 인스턴스 병행** — `JF_NAMESPACE` 환경변수로 `run.sh`·`run_llm.sh` 의 설치 네임스페이스를 바꿔 한 클러스터에 인스턴스를 나란히 띄웁니다(기본 `jonathan-system`, 워크스페이스는 `<네임스페이스>-<id>`).
- **외부 컨테이너 자동 등록** — 플랫폼 표준 manifest(양자화·평가 채점기·프롬프트 최적화·SDS 학습/추론)는 `fb_external_container` 기동 시 시드됩니다.
- **EFK 로그** — 날짜별 인덱스 + 분류별 보존기간(ILM) 정책(`devops/gaip_efk/elastic_init.sh` → `retention_setup.sh`).
- **공유 HF 캐시** — 워크스페이스 네임스페이스마다 `hf-model-cache-pvc` 를 만들고, 폐쇄망 학습용 가중치는 `devops/hf-prefetch/run.sh` 로 미리 받아 둡니다.
- **MetalLB 없이 설치** — Kong 기본 proxy 는 NodePort 32080(HTTP)/32443(HTTPS).

---

## 아키텍처

```
 브라우저  ── 웹 UI(/) + API 호출(/api/<서비스>/...)
   │
   ▼
 Kong (Ingress) ──── / ──▶ front (nginx + React 빌드)
   │   /api/* 경로에 인증 자동 부착 (fb_ingress_management)
   │   외부 API 게시 = /ext/<api_path> + key-auth(API 키)
   ▼
 MSA 백엔드 (FastAPI, apps/fb_* · llm_*)
   │   ├─ MariaDB(메타데이터) · Redis(큐·캐시) · Kafka(이벤트·경보) · MongoDB(알림 등)
   │   │
   │   ├─ fb_scheduler ── helm install ──▶ 워크스페이스 네임스페이스(<ns>-<id>)의 잡·서빙 파드
   │   │                                   파인튜닝 · LLM 서빙(deployment_llm, 엔진 6종)
   │   │                                   빌트인 잡(포맷 변환·데이터 파이프라인 노드) · 외부 컨테이너
   │   │
   │   ├─ fb_external_container (BFF) ── ClusterIP ──▶ 외부 컨테이너
   │   │      manifest 레지스트리·실행·정규화           (양자화 · 평가 채점기 · 프롬프트 최적화 · SDS 학습/추론)
   │   │
   │   └─ fb_resource (엣지) ── /ops · /metrics ──▶ 엣지 디바이스 에이전트 (클러스터 밖)
   │                         ◀── heartbeat · 아티팩트(GGUF) 수신 ──
   ▼
 NFS (데이터셋 · 모델 · 체크포인트 · 공유 HF 캐시)
```

- **외부(협력기관) 컨테이너** — manifest(`apiVersion: tango.acryl.ai/v1`)로 등록한 컨테이너를 플랫폼이 직접 띄우고 **ClusterIP 로만** 호출합니다. 공개 Ingress 는 만들지 않으며, 필요하면 manifest `spec.network.isolate: true` 로 egress 전면 차단·BFF 외 ingress 차단을 켭니다. 계약: [`examples/hello-plugin/external-container-spec.md`](examples/hello-plugin/external-container-spec.md) (외부 컨테이너 인터페이스 계약서 v1, spec 버전 v1.1).
- **엣지** — 클러스터에 합류하지 않는 디바이스의 에이전트와 양방향 토큰(플랫폼→디바이스 `OPS_TOKEN`, 디바이스→플랫폼 `DEVICE_TOKEN`)으로 통신합니다. 규약: [`examples/edge-agent/README.md`](examples/edge-agent/README.md) (엣지 에이전트 연동 규약 v1, contract_version 1.2).

---

## 구성요소

### 코어 플랫폼 (`apps/fb_*`)

| 디렉터리 | 역할 |
|---|---|
| `fb_user` | 로그인·사용자 계정 |
| `fb_workspace` | 워크스페이스·네임스페이스·스토리지 PVC 생성(공유 HF 캐시 PVC 포함) |
| `fb_dashboard` | 대시보드 **API**(워크스페이스·관리자 대시보드 집계, SSE). 화면은 `front` |
| `fb_dataset` | 데이터셋(드라이브) 파일 업로드·다운로드·관리 |
| `fb_resource` | 노드·스토리지·사용 기록·**엣지 디바이스**(등록·heartbeat·배포 지시) |
| `fb_scheduler` | 작업 큐·자원 admission, Helm 차트(`helm_chart/`)로 잡·서빙·외부 컨테이너 파드 설치 |
| `fb_external_container` | 외부 컨테이너 manifest 레지스트리 + 실행·정규화 BFF, 표준 manifest 자동 시드(`manifests/`) |
| `fb_preprocessing` | 빌트인 전처리 잡(포맷 변환·SDS → LLaVA 변환 등) |
| `fb_pipeline` | 작업 노드 DAG(통합 파이프라인) API |
| `fb_collect` · `fb_analyzing` · `fb_synthesis` | 데이터 수집·분석·합성 앱(수집 메뉴는 현재 숨김) |
| `fb_monitoring` | 학습·배포 파드 상태 감시, GPU 사용량 기록 |
| `fb_notification` · `fb_alert_management` | 알림·진행 상태, Kafka 기반 경보 수집·전파 |
| `fb_ingress_management` | Kong 라우트·consumer·key-auth 관리, `/api/*` 인증 자동 부착, 게시 orphan 정리 |
| `fb_option` | 공통 옵션 조회 API(Hugging Face·빌트인 모델 카탈로그, 사용자 목록 등) |
| `fb_image` | 컨테이너 이미지 관리(pull·build·tar·commit·copy) |
| `fb_deployment` | **레거시** 배포 API(구 워커 기반 배포). 현재 배포 화면의 컨트롤 플레인은 `llm_playground` 이며, 외부 API 게시 엔드포인트(`/{deployment_id}/api-publish`)가 이 앱에 남아 있음 |
| `fb_logger` | 로깅 모듈 PoC(`module_poc/`)만 있음 — 배포 대상 아님 |
| `fb_log_middleware` | 로그 조회 미들웨어 Go PoC — 설치 차트 없음 |
| `fb_utils` | 공통 라이브러리(settings·DB·K8s·Kong 헬퍼·`errors.yaml`) — 모든 백엔드 이미지에 포함 |

### LLM 서비스 (`apps/llm_*`)

| 디렉터리 | 역할 |
|---|---|
| `llm_model` | 모델 생성(HF·플랫폼·도메인 SDS)·다운로드, 파인튜닝·커밋·체크포인트, 양자화, 외부 컨테이너 작업 프록시(`/external/*`) |
| `llm_playground` | **배포/추론 컨트롤 플레인** — 배포 유형 4종 디스패치, 서빙 엔진 선택, 채팅·데이터셋 추론, VLM 이미지 입력, 프롬프트 최적화, OpenAI 호환 shim |
| `llm_evaluation` | 평가 프로젝트·실행, 채점 컨테이너 디스패치, 리포트 생성 |
| `llm_data_pipeline` | 학습 데이터 파이프라인 API(단계·실행 이력·검수·구성·릴리스) |

### 잡 · 외부 컨테이너 이미지

| 디렉터리 | 역할 |
|---|---|
| `apps/builtin_data_pipeline` | 데이터 파이프라인 노드 스크립트(`dp_prep`·`dp_filter`·`dp_generate`·`dp_judge`·`dp_assemble`, SDS `dp_sds_*`·`dp_colreg`) |
| `apps/builtin_transform` | 빌트인 변환 스크립트(`format_convert.py`, `sds_llava_convert.py`) |
| `apps/convert` | `convert-llamacpp` — GGUF 양자화·포팅 패키지(플랫폼 소유 외부 컨테이너) |
| `apps/evaluate` | `evaluate-selfmetric` — BLEU·ROUGE·perplexity 자동평가 |
| `apps/evaluate_lmeval` | `evaluate-lmeval`(+ 코드 실행용 `evaluate-lmeval-code`) — 정답 대조 실채점. 두 manifest 모두 `network.isolate: true` |
| `apps/evaluate_logickor` · `apps/evaluate_logickor_judge` | LogicKor 채점·심판 |
| `apps/evaluate_intent` | MixATIS 의도/슬롯 평가 |
| `apps/evaluate_benchmark_mock` | 벤치마크 mock 채점기(실채점기 도입 이전 판본) |
| `Data_Augmentation/fewshot_prompting` | `fewshot-prompt-optimizer` — 프롬프트 최적화 |
| `apps/remote_api_proxy` | 외부 LLM(API) 배포의 워커 파드 — 플랫폼 서빙 계약 + OpenAI 호환 중계, API 키는 K8s Secret 으로만 주입 |

빌트인 스크립트는 이미지에 굽지 않고 NFS 로 `/built_in` 에 마운트되어 `libs/fb_image/preprocessing` 베이스 이미지 파드에서 실행됩니다. SDS 학습/추론(`eva-vlm-train` / `eva-vlm-infer`)은 협력기관이 제공하는 이미지이며, manifest 만 `apps/fb_external_container/manifests/` 에 있습니다.

### 엣지 (`apps/edge_*`, `examples/edge-agent`)

| 디렉터리 | 역할 |
|---|---|
| `apps/edge_remote_manager` | 엣지 에이전트 참조 구현(Python) — `/ops` 배포 지시 수신, 모델 아티팩트 다운로드, 컨테이너 실행 |
| `apps/edge_virtual_device` | 가상 디바이스 e2e 하네스(받은 GGUF 로 llama-server 기동) |
| `examples/edge-agent` | 엣지 에이전트 연동 규약 + 적합성 검사기 `conformance.py` |

### 인프라 · 공유 자원 · 프론트

| 디렉터리 | 역할 |
|---|---|
| `devops/` | Helm 차트와 설치 스크립트 — 인프라 `gaip_*`(NFS provisioner, MetalLB(선택), Kong, Registry, MariaDB, Kafka, Redis, MongoDB, Prometheus/Grafana, EFK, GPU Operator), 앱 차트 `fb_*`·`llm_*`, `run_step1/2/3_*.sh`·`run.sh`·`run_llm.sh`, `hf-prefetch/`, 라벨링(marker, 선택) |
| `libs/fb_bin` | 잡 파드가 쓰는 공용 스크립트(파인튜닝·VLM 파인튜닝·모델 다운로드 등) |
| `libs/fb_image` | 이미지 소스 — 서빙 엔진 6종(`llm*/`), 빌트인 베이스(`built_in_image/`), 전처리·데이터 파이프라인 lean 베이스(`preprocessing/`) |
| `libs/fb_logger` | 로깅 모듈 PoC |
| `front/` | 웹 UI(React + Vite, yarn 4) — 배포 대상 프론트엔드 |
| `front_etri/` | 화면 기획용 목업 UI — 배포 대상 아님 |
| `Evaluation/` | 평가 알고리즘 원본·웹 데모(LogicKor, 의도 분류 등) — `apps/evaluate_*` 채점 컨테이너의 이식 원본 |
| `examples/` | 협력기관용 계약·템플릿 — `hello-plugin`(외부 컨테이너 템플릿 + 계약서), `external-container-manifests`, `mock-convert-plugin`·`mock-generate-plugin`, `edge-agent`, `openapi-template.yaml` |
| `bundles/` | 번들 설치 정보 관리 경로 |
| `docs/` | 가이드·용어 정의서·설계 문서 ([목차](docs/README.md)) |

---

## 요구사항

[`devops/CLUSTER-SETUP.md`](devops/CLUSTER-SETUP.md) 의 검증 조합을 기준으로 합니다.

| 항목 | 기준 |
|---|---|
| OS | Ubuntu 22.04.5 LTS 이상 |
| Kubernetes | **v1.34.x**(검증 v1.34.0), containerd 1.7.29, Calico v3.32.1, helm 3.x |
| 노드 | **단일 노드 가능**(control-plane taint 제거), 다중 노드 확장 가능 |
| kubelet | **`maxPods: 250`** — 플랫폼·인프라 파드만으로 90개를 넘어 기본값 110 이면 워크스페이스 잡이 스케줄되지 않음 |
| metrics-server | 필수(`kubectl top nodes` 동작) |
| 스토리지 | **NFS export** — values 의 볼륨 경로(`jfData`·`jfBin`·`jfStorage`·`hfModelCache`), NFS provisioner 경로, registry 이미지 경로 |
| GPU | 파인튜닝·GPU 서빙에는 NVIDIA GPU 노드 필요(`gaip_gpu_operators`) |
| 이미지 | 기본은 docker.io 에서 pull. 폐쇄망이면 values 의 레지스트리를 내부 레지스트리로 변경 |

---

## 설치 개요

1. **클러스터 준비** — [`devops/CLUSTER-SETUP.md`](devops/CLUSTER-SETUP.md): containerd·Calico·kubeadm·metrics-server, kubelet `maxPods`, 단일 노드 taint, 노드 라벨.
2. **values 준비** — `devops/values.yaml.template` 을 `values_<서버명>.yaml` 로 복사해 `<NFS_SERVER_IP>` 등 자리표시자를 채웁니다. kubeconfig 를 `devops/fb_common_app/helm/file/kube/config` 로 복사합니다.
3. **인프라 설치** — `devops/` 에서 순서대로 실행합니다.
   ```bash
   cd LLMOps/devops
   ./run_step1_infra_base.sh  --system ./gaip_nfs_provisioner/values-system.yaml --efk ./gaip_nfs_provisioner/values-efk.yaml
   # Step 2 = Kong → Registry → MariaDB(install + init) → Kafka → Redis → MongoDB
   #   ⚠️ MariaDB init 은 DB 를 재생성하므로 신규 설치에서만 실행
   ./run_step2_core_infra.sh  --kong ./gaip_kong/values.yaml --registry ./gaip_registry/values.yaml --mariadb ./gaip_maraidb/values.yaml
   ./run_step3_optional_obs.sh --prometheus   # 선택: --efk, --efk --efk-init, --gpu
   ```
4. **앱 설치** — 플랫폼 앱과 LLM 앱(`run_llm.sh` 는 `model`·`playground`·`evaluation`·`data-pipeline` 릴리스 설치).
   ```bash
   ./run.sh     install -f ./values_<서버명>.yaml
   ./run_llm.sh install -f ./values_<서버명>.yaml
   # 다른 네임스페이스에 별도 인스턴스: JF_NAMESPACE=<네임스페이스> ./run.sh install -f ...
   ```
5. **설치 후** — 관리자 화면에서 **스토리지 등록**(워크스페이스 생성 전 필수), 외부 컨테이너 manifest 시드 확인, 폐쇄망 SDS 학습이면 `devops/hf-prefetch/run.sh` 로 가중치 사전 스테이징.

세부 절차·옵션·데이터 보존 재설치는 [`devops/INSTALL.md`](devops/INSTALL.md) 가 기준입니다. 한국어 매뉴얼: [설치 매뉴얼](devops/Tango%20GenAI%20Platform%20설치%20매뉴얼.md) · [설치 간소화 매뉴얼](devops/Tango%20GenAI%20Platform%20설치%20간소화%20매뉴얼.md) (내용이 다르면 INSTALL.md 우선).

---

## 빌드 · 개발

코드를 바꾼 뒤 클러스터에 반영하는 방법은 두 가지입니다. 자세한 절차는 [`docs/GenAI_Platform 빌드 및 재배포 가이드.md`](docs/GenAI_Platform%20빌드%20및%20재배포%20가이드.md) 를 보세요.

**1) 소스 마운트 개발 모드 (이미지 재빌드 없음)** — values 의 `global.jfb.volume.src.enabled: true`(경로 = 체크아웃의 `LLMOps/apps`, NFS export 필요)이면 백엔드 파드가 체크아웃 소스를 그대로 씁니다.

```bash
# 백엔드: 코드 수정 후 해당 deployment 재시작
kubectl rollout restart deployment/<deployment 이름> -n <네임스페이스>

# 프론트: front.enabled: true 일 때 호스트에서 빌드만 다시 (yarn 4 — yarn 1·npm 불가, 재시작 불필요)
cd LLMOps/front
corepack enable && corepack prepare yarn@4.17.1 --activate   # 버전은 front/Dockerfile 과 동일
yarn install --immutable && yarn vite build
```

**2) 이미지 빌드 + helm upgrade (운영 반영)** — `apps/<서비스>/build.sh`(또는 `apps/build.sh` 일괄)로 이미지를 빌드·push 하고, values 의 이미지 태그를 올린 뒤 helm upgrade 합니다.

```bash
cd LLMOps/devops
./run.sh     upgrade -f ./values_<서버명>.yaml   # 플랫폼 앱
./run_llm.sh upgrade -f ./values_<서버명>.yaml   # LLM 앱
```

> 운영 환경에서는 `src.enabled: false`(이미지에 구운 코드)를 권장합니다. 외부 컨테이너 manifest 는 DB 에 등록되므로, 내용만 바꾼 manifest 는 버전을 올리거나 기존 행을 지운 뒤 재시작해야 기존 설치에 반영됩니다.

---

## 문서

| 문서 | 내용 |
|---|---|
| [`docs/README.md`](docs/README.md) | 문서 전체 목차(목적별 안내) |
| [`devops/CLUSTER-SETUP.md`](devops/CLUSTER-SETUP.md) | 쿠버네티스 클러스터 구축 |
| [`devops/INSTALL.md`](devops/INSTALL.md) | 플랫폼 설치 기준 문서 |
| [`devops/Tango GenAI Platform 설치 매뉴얼.md`](devops/Tango%20GenAI%20Platform%20설치%20매뉴얼.md) · [`설치 간소화 매뉴얼.md`](devops/Tango%20GenAI%20Platform%20설치%20간소화%20매뉴얼.md) | 한국어 설치 매뉴얼 |
| [`docs/GenAI_Platform 빌드 및 재배포 가이드.md`](docs/GenAI_Platform%20빌드%20및%20재배포%20가이드.md) | 이미지 빌드·helm upgrade·소스 마운트 개발 모드 |
| [`docs/Tango 모델 탑재 가이드.md`](docs/Tango%20모델%20탑재%20가이드.md) | 모델 탑재 요건, 서빙 엔진, GGUF 양자화, 폐쇄망 참고 |
| [`docs/Tango MSA 탑재 가이드.md`](docs/Tango%20MSA%20탑재%20가이드.md) · [`Docker 이미지 빌드 가이드`](docs/Tango%20MSA%20서비스%20Docker%20이미지%20빌드%20가이드.md) | 협력기관 서비스 탑재(기본 계약, 호스팅·인증·격리) |
| [`examples/hello-plugin/external-container-spec.md`](examples/hello-plugin/external-container-spec.md) | 외부 컨테이너 인터페이스 계약서 v1 |
| [`examples/edge-agent/README.md`](examples/edge-agent/README.md) | 엣지 에이전트 연동 규약 v1 |
| [`docs/Tango2_GenAI_Platform_용어_정의서_v1.3.md`](docs/Tango2_GenAI_Platform_용어_정의서_v1.3.md) | 용어 정의서(내용 v1.4) |

---

## 라이선스

이 저장소(TANGO2)는 **TANGO2 License and Service Agreement(LSA)** 를 따릅니다 — [`../LICENSE.md`](../LICENSE.md) (영문) · [`../LICENSE_ko.md`](../LICENSE_ko.md) (한국어).

- LSA 는 **오픈 소스 라이선스**와 **상용 라이선스** 두 정책을 둡니다. 사용 목적에 따라 둘 중 하나가 적용되며, 이 프로젝트의 전부 또는 일부를 사용하면 LSA 에 동의한 것으로 간주됩니다.
- **오픈 소스 라이선스** — 이 프로젝트의 소스·실행 코드를 사용해 개발한 코드는 원칙적으로 **GNU General Public License v3.0 or later(GPLv3)** 를 따릅니다.
- **상용 라이선스** — 결과물을 유상 판매하거나 광고 등으로 무상 배포하는 등 직·간접 이익을 얻는 **상업화**를 하려면 상용 라이선스 대상이며, 한국전자통신연구원(ETRI)의 기술이전 계약에 따릅니다.
- 라이선스·기술 지원 문의처는 LICENSE 파일에 있습니다.

저장소에 포함되거나 이미지로 가져다 쓰는 서드파티 구성요소(Helm 차트, 서빙 엔진 등)는 각 프로젝트의 라이선스를 따릅니다.
