# 📚 GenAI Platform 문서 안내

이 폴더는 Tango2 GenAI Platform의 사용자/운영자/개발자 문서를 모아둔 곳입니다.
**무엇을 하고 싶은지에 따라 어떤 문서를 먼저 보면 되는지** 안내합니다.

설치/실행 절차 같은 운영 문서는 `devops/`에, 협력기관용 계약·템플릿은 `examples/`에, 서비스별 README는 각 `apps/<service>/`에 함께 있습니다. 여기 `docs/`에는 **플랫폼 전반의 가이드, 활용 사례, 기능 설계 문서**가 들어 있습니다.

---

## 🗺️ 목적별 문서 가이드

### 🟢 처음 보는 분 — 입문

| 무엇을 하고 싶은가 | 어떤 문서 |
|---|---|
| 플랫폼이 뭐 하는 건지부터 보고 싶다 | [`../README.md`](../README.md) (LLMOps 개요) → [`Tango 사용자 매뉴얼_20260323.pdf`](./Tango%20사용자%20매뉴얼_20260323.pdf) |
| 이 문서/코드에서 쓰는 용어가 낯설다 | [`Tango2_GenAI_Platform_용어_정의서_v1.3.md`](./Tango2_GenAI_Platform_용어_정의서_v1.3.md) (문서 내용은 v1.4) |
| 활용 예시(해양 분야 VLM)가 보고 싶다 | [`Tango2_Platform_활용_가이드_해양VLM.pdf`](./Tango2_Platform_활용_가이드_해양VLM.pdf) |

> ⚠️ **사용자 매뉴얼 PDF(2026-03-23)는 메뉴 개편 이전 화면 기준입니다.** 현재 사용자 메뉴는 대시보드·드라이브(사이드바 상단 카드)와 **데이터 · 모델 · 배포 · 추론 · 평가**로 구성되며, 예전 '플레이그라운드'는 배포/추론으로 나뉘었습니다. 현재 메뉴와 기능 범위는 [`../README.md`](../README.md)의 "주요 기능"과 용어 정의서 v1.4를 기준으로 보세요.

### ⚙️ 설치 · 운영자

| 무엇을 하고 싶은가 | 어떤 문서 |
|---|---|
| Kubernetes 클러스터부터 만들어야 한다 | [`../devops/CLUSTER-SETUP.md`](../devops/CLUSTER-SETUP.md) — containerd·Calico·kubeadm·metrics-server, kubelet `maxPods: 250`, 단일 노드 taint 해제 |
| 클러스터 위에 플랫폼을 설치 (기준 문서) | [`../devops/INSTALL.md`](../devops/INSTALL.md) — values 준비, 인프라(`run_step1/2/3`), 앱(`run.sh`)·LLM 앱(`run_llm.sh`), 스토리지 등록, 외부 컨테이너 manifest, HF 가중치 사전 스테이징 |
| 처음부터 끝까지 자세하게 설치 (한국어 매뉴얼) | [`../devops/Tango GenAI Platform 설치 매뉴얼.md`](../devops/Tango%20GenAI%20Platform%20설치%20매뉴얼.md) |
| 빠르게 핵심 경로만 따라 설치 (한국어 매뉴얼) | [`../devops/Tango GenAI Platform 설치 간소화 매뉴얼.md`](../devops/Tango%20GenAI%20Platform%20설치%20간소화%20매뉴얼.md) |
| values 파일 레퍼런스 | `../devops/values.yaml.template` (환경별 `values_<서버명>.yaml`로 복사해 사용 — 환경별 파일은 git에 올리지 않습니다) |
| 코드 수정 후 이미지를 다시 빌드해 반영 | [`GenAI_Platform 빌드 및 재배포 가이드.md`](./GenAI_Platform%20빌드%20및%20재배포%20가이드.md) |
| 스케줄러 admission/리소스 운영의 알려진 한계와 향후 작업 | [`FUTURE_WORK_scheduler_instance_ceiling.md`](./FUTURE_WORK_scheduler_instance_ceiling.md) |

> 한국어 설치 매뉴얼 2종과 INSTALL.md 의 내용이 다르면 **INSTALL.md(와 CLUSTER-SETUP.md)를 우선**합니다 — 스크립트·values 변경이 먼저 반영되는 문서입니다.

### 🧩 협력기관 / 외부 서비스 개발자

| 무엇을 하고 싶은가 | 어떤 문서 |
|---|---|
| 자체 서비스를 플랫폼에 탑재 (기본 계약 `/health`·`/info`·`/run`, Helm Chart) | [`Tango MSA 탑재 가이드.md`](./Tango%20MSA%20탑재%20가이드.md) |
| 서비스의 Docker 이미지를 빌드해 레지스트리에 등록 | [`Tango MSA 서비스 Docker 이미지 빌드 가이드.md`](./Tango%20MSA%20서비스%20Docker%20이미지%20빌드%20가이드.md) |
| 학습·추론·변환·평가 컨테이너를 manifest 로 등록 (외부 컨테이너 계약) | [`../examples/hello-plugin/external-container-spec.md`](../examples/hello-plugin/external-container-spec.md) — 외부 컨테이너 인터페이스 계약서 v1 (spec 버전 v1.1) |
| 위 계약을 따르는 시작 템플릿 | [`../examples/hello-plugin/`](../examples/hello-plugin/) (`manifest.yaml` · `app.py` · `Dockerfile`) |
| 학습/추론 짝(hybrid) manifest 작성 예시 | [`../examples/external-container-manifests/`](../examples/external-container-manifests/) (`eva-vlm-train.yaml` / `eva-vlm-infer.yaml`) |
| 엣지 디바이스 에이전트를 구현해 온디바이스 배포와 연동 | [`../examples/edge-agent/README.md`](../examples/edge-agent/README.md) — 엣지 에이전트 연동 규약 v1 (contract_version 1.2) + 적합성 검사기 `conformance.py` |
| 로그 수집 미들웨어(Go PoC)를 보고 싶다 | [`../apps/fb_log_middleware/go-poc/README.md`](../apps/fb_log_middleware/go-poc/README.md) (설치 차트 없음) |

### 🤖 모델 엔지니어 / LLM 운영자

| 무엇을 하고 싶은가 | 어떤 문서 |
|---|---|
| 새로운 LLM 모델을 플랫폼에서 파인튜닝/서빙/양자화하도록 탑재 | [`Tango 모델 탑재 가이드.md`](./Tango%20모델%20탑재%20가이드.md) |
| 파인튜닝 엔진 버전 확인 | `../apps/llm_model/fine_tuning_image/Dockerfile`, `../apps/llm_model/fine_tuning_image/requirements.txt` |
| 서빙 엔진(6종) 이미지·버전 확인 | `../apps/fb_utils/settings.py` 의 `SERVING_ENGINE_IMAGE_MAP` (엔진 → 이미지) + 각 이미지의 빌드 소스 `../libs/fb_image/llm*/Dockerfile` |

> 📝 **엔진 버전은 코드가 기준입니다.** 가이드 문서의 버전 표기와 차이가 있으면 위 파일을 우선 확인하세요. 서빙 이미지는 `deployment_llm` 차트 values 가 아니라 `settings.py` 의 엔진별 상수에서 정해집니다.

### 🛠️ 플랫폼 내부 개발자 (이 저장소를 직접 수정)

| 무엇을 하고 싶은가 | 어떤 문서 |
|---|---|
| 백엔드·프론트 이미지 빌드, helm upgrade, 소스 마운트 개발 모드 | [`GenAI_Platform 빌드 및 재배포 가이드.md`](./GenAI_Platform%20빌드%20및%20재배포%20가이드.md) |
| 번들/배포 산출물 구조 | [`../bundles/README.md`](../bundles/README.md) |
| 기능별 설계 배경(왜 이렇게 만들었나) | 아래 "기능 설계 문서" 5종 |

---

## 📂 docs/ 폴더 안에 있는 문서

### 가이드 · 레퍼런스

| 파일 | 갱신일 | 내용 요약 |
|---|---|---|
| [`Tango 사용자 매뉴얼_20260323.pdf`](./Tango%20사용자%20매뉴얼_20260323.pdf) | 2026-03-23 | 일반 사용자용 매뉴얼(웹 UI 사용 흐름). **메뉴 개편 이전 화면 기준** |
| [`Tango2_Platform_활용_가이드_해양VLM.pdf`](./Tango2_Platform_활용_가이드_해양VLM.pdf) | 2026-04-22 | 해양 VLM 도메인 적용 사례 가이드 |
| [`Tango2_GenAI_Platform_용어_정의서_v1.3.md`](./Tango2_GenAI_Platform_용어_정의서_v1.3.md) | 2026-10-28 | 핵심 개념·인프라·학습·배포·평가·파라미터 용어 정의 (문서 내 버전 v1.4, 파일명은 유지) |
| [`Tango MSA 탑재 가이드.md`](./Tango%20MSA%20탑재%20가이드.md) | 2026-10-28 | 협력기관 서비스 탑재 기본 계약, Helm Chart 작성, 외부 컨테이너 호스팅·인증·격리 방식 |
| [`Tango MSA 서비스 Docker 이미지 빌드 가이드.md`](./Tango%20MSA%20서비스%20Docker%20이미지%20빌드%20가이드.md) | 2026-10-28 | 협력기관 서비스 이미지 빌드/레지스트리 등록 절차 |
| [`Tango 모델 탑재 가이드.md`](./Tango%20모델%20탑재%20가이드.md) | 2026-10-28 | LLM 모델 탑재 요건, 서빙 엔진 6종, `max_model_len`, GGUF 양자화, 폐쇄망(HF 오프라인) 참고 |
| [`GenAI_Platform 빌드 및 재배포 가이드.md`](./GenAI_Platform%20빌드%20및%20재배포%20가이드.md) | 2026-10-28 | 플랫폼 자체 서비스(`fb_*`·`llm_*`·`front`) 이미지 빌드 → helm upgrade → 재기동, 소스·프론트 마운트 개발 모드, 외부 컨테이너·서빙 엔진 이미지 참고 |
| [`FUTURE_WORK_scheduler_instance_ceiling.md`](./FUTURE_WORK_scheduler_instance_ceiling.md) | 2026-10-28 | 스케줄러 instance ceiling/admission 후속 개선 항목과 해결 상태 |
| `files/` | — | 본 문서들이 참조하는 이미지 자산 |

### 기능 설계 문서

구현 당시의 요구사항·실측·결정을 남긴 설계 기록입니다. 현재 동작의 기준은 코드이며, 설계 이후 바뀐 부분이 있을 수 있습니다.

| 파일 | 작성일 | 내용 요약 |
|---|---|---|
| [`2026-07-28-phase4-legacy-playground-contracts.md`](./2026-07-28-phase4-legacy-playground-contracts.md) | 2026-07-28 | `llm_playground` 레거시(이중모델 세션 등) 호환 계약 보존 목록 |
| [`2026-08-14-llm-data-pipeline-design.md`](./2026-08-14-llm-data-pipeline-design.md) | 2026-08-14 | LLM·VLM 학습 데이터 파이프라인(`apps/llm_data_pipeline` + 화면 12종) 설계 |
| [`2026-08-14-data-pipeline-node-porting-design.md`](./2026-08-14-data-pipeline-node-porting-design.md) | 2026-08-14 | 데이터 파이프라인 노드(전처리·필터·생성·심사 등)를 독립 잡으로 이식하는 설계 |
| [`2026-08-31-external-api-deployment-design.md`](./2026-08-31-external-api-deployment-design.md) | 2026-08-31 | 외부 LLM 배포 유형(`deploy_type=remote_api` — 상용 API 3사 + 사용자 엔드포인트) 설계 |
| [`2026-09-28-lmeval-benchmark-scorer-design.md`](./2026-09-28-lmeval-benchmark-scorer-design.md) | 2026-09-28 | 정답 대조 벤치마크 실채점기(`evaluate-lmeval`, lm-evaluation-harness) 설계 |

---

## 🔗 다른 위치의 주요 문서

플랫폼 사용/운영에 필요한 문서가 모두 `docs/` 안에 있는 것은 아닙니다. 자주 찾게 되는 문서를 모아둡니다.

- LLMOps 개요: [`../README.md`](../README.md)
- 클러스터 구축: [`../devops/CLUSTER-SETUP.md`](../devops/CLUSTER-SETUP.md)
- 설치 (기준 문서): [`../devops/INSTALL.md`](../devops/INSTALL.md)
- 설치 (한국어 정식 매뉴얼): [`../devops/Tango GenAI Platform 설치 매뉴얼.md`](../devops/Tango%20GenAI%20Platform%20설치%20매뉴얼.md)
- 설치 (한국어 간소화 매뉴얼): [`../devops/Tango GenAI Platform 설치 간소화 매뉴얼.md`](../devops/Tango%20GenAI%20Platform%20설치%20간소화%20매뉴얼.md)
- 외부 컨테이너 계약서: [`../examples/hello-plugin/external-container-spec.md`](../examples/hello-plugin/external-container-spec.md)
- 외부 컨테이너 템플릿: [`../examples/hello-plugin/README.md`](../examples/hello-plugin/README.md)
- 외부 컨테이너 manifest 예시: [`../examples/external-container-manifests/README.md`](../examples/external-container-manifests/README.md)
- 엣지 에이전트 연동 규약: [`../examples/edge-agent/README.md`](../examples/edge-agent/README.md)
- 번들 산출물: [`../bundles/README.md`](../bundles/README.md)
- 로그 미들웨어 Go PoC: [`../apps/fb_log_middleware/go-poc/README.md`](../apps/fb_log_middleware/go-poc/README.md)
