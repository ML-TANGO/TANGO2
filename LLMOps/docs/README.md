# 📚 GenAI Platform 문서 안내

이 폴더는 Tango2 GenAI Platform의 사용자/운영자/개발자 문서를 모아둔 곳입니다.
**무엇을 하고 싶은지에 따라 어떤 문서를 먼저 보면 되는지** 안내합니다.

설치/실행 절차 같은 운영 문서는 `devops/`에, 서비스별 README는 각 `apps/<service>/`에 함께 있습니다. 여기 `docs/`에는 **플랫폼 전반의 가이드와 활용 사례**가 들어 있습니다.

---

## 🗺️ 목적별 문서 가이드

### 🟢 처음 보는 분 — 입문

| 무엇을 하고 싶은가 | 어떤 문서 |
|---|---|
| 플랫폼이 뭐 하는 건지부터 보고 싶다 | 루트의 [`../README.md`](../README.md) → [`Tango 사용자 매뉴얼_20260323.pdf`](./Tango%20사용자%20매뉴얼_20260323.pdf) |
| 이 문서/코드에서 쓰는 용어가 낯설다 | [`Tango2_GenAI_Platform_용어_정의서_v1.3.md`](./Tango2_GenAI_Platform_용어_정의서_v1.3.md) |
| 활용 예시(해양 분야 VLM)가 보고 싶다 | [`Tango2_Platform_활용_가이드_해양VLM.pdf`](./Tango2_Platform_활용_가이드_해양VLM.pdf) |

### ⚙️ 설치 · 운영자

| 무엇을 하고 싶은가 | 어떤 문서 |
|---|---|
| 처음부터 끝까지 자세하게 설치 | [`../devops/Tango GenAI Platform 설치 매뉴얼.md`](../devops/Tango%20GenAI%20Platform%20설치%20매뉴얼.md) |
| 빠르게 핵심 경로만 따라 설치 | [`../devops/Tango GenAI Platform 설치 간소화 매뉴얼.md`](../devops/Tango%20GenAI%20Platform%20설치%20간소화%20매뉴얼.md) |
| values 파일/스크립트 레퍼런스 | [`../devops/INSTALL.md`](../devops/INSTALL.md) + `../devops/values.yaml.template` (환경별 `values_<서버명>.yaml`로 복사해 사용 — 환경별 파일은 git에 올리지 않습니다) |
| 스케줄러 admission/리소스 운영의 알려진 한계와 향후 작업 | [`FUTURE_WORK_scheduler_instance_ceiling.md`](./FUTURE_WORK_scheduler_instance_ceiling.md) |

### 🧩 협력기관 / MSA 개발자

| 무엇을 하고 싶은가 | 어떤 문서 |
|---|---|
| 새로운 마이크로서비스를 플랫폼에 탑재 | [`Tango MSA 탑재 가이드.md`](./Tango%20MSA%20탑재%20가이드.md) |
| 기존/신규 서비스의 Docker 이미지를 빌드해 등록 | [`Tango MSA 서비스 Docker 이미지 빌드 가이드.md`](./Tango%20MSA%20서비스%20Docker%20이미지%20빌드%20가이드.md) |
| 로그 수집 미들웨어를 붙이고 싶다 | [`../apps/fb_log_middleware/go-poc/README.md`](../apps/fb_log_middleware/go-poc/README.md) |

### 🤖 모델 엔지니어 / LLM 운영자

| 무엇을 하고 싶은가 | 어떤 문서 |
|---|---|
| 새로운 LLM 모델을 플랫폼에서 파인튜닝/서빙하도록 탑재 | [`Tango 모델 탑재 가이드.md`](./Tango%20모델%20탑재%20가이드.md) |
| 현재 지원 엔진/모델 범위 확인 | `apps/llm_model/fine_tuning_image/requirements.txt` 및 vLLM 이미지 태그 |

> 📝 **모델 엔진 버전은 코드/엔진 차트가 최신 기준입니다.** 가이드 문서의 버전 표기와 차이가 있을 경우 `apps/llm_model/`, `apps/fb_scheduler/helm_chart/deployment_llm/`의 실제 이미지 태그를 우선 확인하세요.

### 🛠️ 플랫폼 내부 개발자 (이 저장소를 직접 수정)

| 무엇을 하고 싶은가 | 어떤 문서 |
|---|---|
| 번들/배포 산출물 구조 | [`../bundles/README.md`](../bundles/README.md) |
| 스케줄러 admission/리소스 운영의 알려진 한계와 향후 작업 | [`FUTURE_WORK_scheduler_instance_ceiling.md`](./FUTURE_WORK_scheduler_instance_ceiling.md) |

---

## 📂 docs/ 폴더 안에 있는 문서

| 파일 | 갱신일 | 내용 요약 |
|---|---|---|
| [`Tango 사용자 매뉴얼_20260323.pdf`](./Tango%20사용자%20매뉴얼_20260323.pdf) | 2026-03-23 | 일반 사용자용 매뉴얼(웹 UI 기준 사용 흐름) |
| [`Tango2_Platform_활용_가이드_해양VLM.pdf`](./Tango2_Platform_활용_가이드_해양VLM.pdf) | 2026-04-22 | 해양 VLM 도메인 적용 사례 가이드 |
| [`Tango2_GenAI_Platform_용어_정의서_v1.3.md`](./Tango2_GenAI_Platform_용어_정의서_v1.3.md) | 2026-03-17 | 핵심 개념·인프라·학습·배포·파라미터 용어 정의 |
| [`Tango MSA 탑재 가이드.md`](./Tango%20MSA%20탑재%20가이드.md) | 2026-03-17 | 협력기관이 자체 MSA를 플랫폼에 통합하는 절차 |
| [`Tango MSA 서비스 Docker 이미지 빌드 가이드.md`](./Tango%20MSA%20서비스%20Docker%20이미지%20빌드%20가이드.md) | 2026-03-17 | MSA 이미지 빌드/레지스트리 등록 절차 |
| [`Tango 모델 탑재 가이드.md`](./Tango%20모델%20탑재%20가이드.md) | 2026-03-17 | LLM 엔진/모델 신규 탑재 절차 |
| [`FUTURE_WORK_scheduler_instance_ceiling.md`](./FUTURE_WORK_scheduler_instance_ceiling.md) | 2026-04-21 | 스케줄러 instance ceiling/admission 후속 개선 항목 |
| `files/` | — | 본 문서들이 참조하는 이미지 자산 |

---

## 🔗 다른 위치의 주요 문서

플랫폼 사용/운영에 필요한 문서가 모두 `docs/` 안에 있는 것은 아닙니다. 자주 찾게 되는 문서를 모아둡니다.

- 루트 개요: [`../README.md`](../README.md)
- 설치 (정식 매뉴얼): [`../devops/Tango GenAI Platform 설치 매뉴얼.md`](../devops/Tango%20GenAI%20Platform%20설치%20매뉴얼.md)
- 설치 (간소화 매뉴얼): [`../devops/Tango GenAI Platform 설치 간소화 매뉴얼.md`](../devops/Tango%20GenAI%20Platform%20설치%20간소화%20매뉴얼.md)
- 설치 (스크립트 레퍼런스): [`../devops/INSTALL.md`](../devops/INSTALL.md)
- 번들 산출물: [`../bundles/README.md`](../bundles/README.md)
- 로그 미들웨어 Go PoC: [`../apps/fb_log_middleware/go-poc/README.md`](../apps/fb_log_middleware/go-poc/README.md)
