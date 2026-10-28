# 외부 API 배포(remote_api) 설계

작성 2026-08-31 · 선행 실측 세션 기준 · 브랜치 `Acryl-LLMOps-dev`

## 1. 요구사항 재정의

배포 탭에 **네 번째 배포 유형**을 추가한다. 하나의 유형 안에서 provider 로 두 갈래를
받는다 — ① 상용 API(ChatGPT/Claude/Gemini) 를 사용자 키로 호출, ② 외부에서 이미
서빙 중인 LLM 엔드포인트를 중간자(어댑터)로 중계. 두 갈래 모두 기존 추론 화면과
평가(벤치마크·LogicKor·전문가)에서 **클러스터 배포와 동일하게** 소비된다.

## 2. 활성 토폴로지 확인 결과 (실측)

| 항목 | 실측값 |
|---|---|
| 네임스페이스 | 개발 인스턴스(`${JF_NAMESPACE}`), 서빙 `jonathan-system` 과 분리 |
| 배포 서비스 | `jfb-llm-playground` / `docker.io/acrylaaai/genai-platform-playground_app:tango_v2.0.1` |
| 레거시 | `jfb-app-deployment`(fb_deployment) — 배포 탭 소스 아님, 건드리지 않음 |
| **소스 반영** | `/app`=`jf-src-playground-pvc`, `/fb_utils`=`jf-src-utils-pvc` → NFS `<NFS 서버>:<개발 워크트리>/LLMOps/apps/...` |
| 검증 | pod 내 `/app/src/playground/service.py` md5 = 워크트리 md5 (일치) |
| FE | `jfb-app-front` → `jf-src-front-pvc` → `/front-data` |
| front repo | **단일 monorepo** (별도 repo 아님 — 스킬 문서의 "front=별도 repo" 는 stale) |
| egress | api.openai.com / api.anthropic.com / generativelanguage.googleapis.com **3사 TLS 통과** |
| RBAC | `jfb-playground-sa` — workspace ns 포함 secrets get/create **가능** |

→ **앱 코드 변경은 이미지 재빌드 불필요, `rollout restart` 만으로 반영된다.**

## 3. 네이밍 — `external_api` 대신 `remote_api` 권장

`external_*` 접두는 이 저장소에서 **이미 두 가지 다른 뜻**으로 점유돼 있다.

1. `external_job_id` / `external_manifest_name` / `fb_external_container`
   = **협력기관 컨테이너**(ETRI 등). `playground.deployment` JSON 의 분기 키.
2. `PlaygroundExternalApi.jsx` = **우리 배포를 외부에 게시**(D6, Kong key-auth, outbound).

신규 기능은 셋 중 어느 것도 아니다(외부 API 를 **우리가 소비**, inbound). `external_api`
로 두면 `_deployment_external_job_id()` 와 `PlaygroundExternalApi` 사이에서 사람도 grep 도
헷갈린다. 따라서 **`deploy_type='remote_api'`** 를 쓴다. 구조는 승인된 그대로(단일 타겟 +
provider 분기)이며 바뀌는 것은 식별자 문자열뿐이다.

```
deploy_type = 'remote_api'
  provider ∈ { chatgpt, claude, gemini }  → 호스트 고정 allowlist
  provider = 'endpoint'                   → 사용자 URL + SSRF 가드
```

## 4. 닿는 표면

| 표면 | 파일 | 상태 |
|---|---|---|
| 판별자 DTO | `apps/llm_playground/src/playground/dto.py:15` | 활성 |
| envelope 계약 | `apps/fb_utils/deployment_envelope.py` | 활성(공용) |
| 타겟 read-model | `service.py:219 get_deployment_targets` | 활성 |
| 배포 시작 | `service.py:1834 start_playground` | 활성 |
| 상태 파생 | `service.py:999 get_playground_status` | 활성 |
| 추론 디스패치 | `service.py:3033 playground_test` | 활성 |
| OpenAI shim | `service.py:3416 openai_chat_completions` | 활성 |
| 내부 URL 가드 | `service.py:3337 _playground_internal_test_url` | 활성 |
| provider 표(이식원) | `apps/llm_evaluation/src/evaluation/constants.py:202-214` | **휴면** |
| SSRF 가드(이식원) | `apps/llm_evaluation/src/evaluation/service.py:1299` | **휴면** |
| Secret 헬퍼 | `apps/fb_utils/kube.py:154 create_or_replace_secret` / `delete_secret` | 활성 |
| FE 생성 모달 | `front/src/components/Modal/NewDeploymentModal` | 활성 |
| FE 목록 | `front/src/pages/llm/Playground/PlaygroundMenu` | 활성 |
| FE 공용 셸 | `front/src/components/pageContents/llm/DeployDetail/DeployDetailShell` | 활성 |
| FE 라우트 | `front/src/pages/authRouter/UserRouter.jsx:799-960` | 활성 |
| DB | `playground.deploy_type VARCHAR(16)` | **DDL 변경 없음** |

## 5. 기존 패턴 재사용 (신규 추상화 0)

- **판별자 다형성** — edge/standalone 이 낸 길을 그대로. envelope 함수 1개 추가.
- **`deployment` JSON 분기** — 기존 `external_job_id` 키 분기와 동일 형태로
  `remote_api` 키를 둔다. 세 곳(status/test/shim)이 이미 if/else 분기 구조라 3번째 갈래를
  같은 자리에 끼운다.
- **provider allowlist** — `JUDGE_PROVIDER_HOSTS` 를 배포 표면으로 이식. 사용자 입력은
  키뿐, 호스트는 우리가 고정 → 키 유출·리다이렉트 SSRF 원천 차단.
- **SSRF 가드** — `_validate_local_url` 이식. resolve 한 IP 로 직접 connect(DNS rebinding
  TOCTOU 차단), 멀티레코드 전수 검사, link-local/multicast 차단.
- **시크릿** — `create_or_replace_secret(ns, name, string_data)`. playground row 에는
  `secret_ref` 이름만. 값은 Secret 객체(etcd+RBAC)에만 존재.
- **FE 상세** — `DeployDetailShell` 의 `sections` 계약(INFO/MODEL/MONITOR) 재사용.

## 6. 필수 경로 3건 — 처리 방식

기존 코드가 "pod 이 있는 배포"를 전제하는 지점. 셋 다 반드시 분기해야 한다.

### 6.1 `start_playground` 의 `deployment_run` 게이트 (service.py:1886)
`deployment` 가 비면 `"Not set up playground deployment"` 로 거부한다. remote_api 는
할당할 자원이 없어 이 게이트를 영원히 못 넘는다.
→ **함수 최상단에서 remote_api 를 먼저 분기**해 자원 경로 자체에 진입하지 않게 한다.
"시작" 은 키/엔드포인트 검증 + 도달성 확인(가벼운 호출) 후 `deployment` JSON 에
`{"remote_api": {...}}` 를 기록하는 것으로 끝난다. helm/GPU/instance 미사용.

### 6.2 `_playground_internal_test_url` 의 명시적 raise (service.py:3355)
external 배포를 "shim 은 internal 전용" 이라며 거부한다. remote_api 도 같은 곳에 걸린다.
→ **shim(`openai_chat_completions`)에 3번째 분기**를 추가해 이 함수에 도달하기 전에
가로챈다. 가드 자체는 그대로 둔다(의도가 옳다 — 그 함수는 svc DNS 규칙 전용).
이 분기가 열려야 **평가 연동(§8)** 이 성립한다.

### 6.3 `get_playground_status` 의 helm/pod 기반 파생 (service.py:999)
pod 이 없으므로 `deployment_worker_list`/redis 경로가 성립하지 않는다.
→ `external_job_id` 분기 바로 옆에 `remote_api` 분기 추가. 상태는 **마지막 도달성 결과**
로 파생: 검증 성공 후 `running`, 미구성 `stop`, 마지막 호출이 인증/네트워크 실패면 `error`.
`init_deployment` 는 구성 완료 여부.

## 7. 중간자 어댑터 — pod 없이

새 워커 pod 을 띄우지 않는다. GPU 쿼터·helm 릴리스·NFS·차트 페어 제약을 상속할 이유가
없고, egress 는 llm_playground pod 에서 이미 열려 있다(실측). 어댑터는 두 함수다.

```
우리 규격            어댑터                     외부
{test_question} ──▶ _remote_api_infer() ──▶ POST /v1/chat/completions
                     ├ provider→호스트 고정      (또는 provider 별 네이티브 스키마)
                     ├ 키는 헤더로만
                     └ 응답 → {"output": text}
```

- 기존 `_messages_to_prompt`(shim 의 정방향)의 **역방향**: 단일 질문 → `messages` 배열.
- 반환 계약은 `_infer_question`(service.py:2611) 과 동일한 `{"output": ...}` — 그래야
  추론 화면·일괄 추론·이중모델이 무수정으로 동작한다.
- provider 별 차이(Anthropic `x-api-key`+`anthropic-version`, Gemini 경로형 모델명)는
  어댑터 안에서 흡수. **키는 항상 헤더로만** — URL 쿼리 금지(예외·액세스로그 노출).
- 모델명을 URL 경로에 보간하기 전 인코딩(Gemini).

## 8. 파급 이득 — 평가 연동

평가는 배포를 `inference_playground_id` → `params.generate_base_url`(배포의 OpenAI shim
base)로 소비한다(`llm_evaluation/service.py:103`). §6.2 분기가 열리면 **벤치마크·LogicKor·
전문가평가가 상용 모델을 그대로 평가 대상으로 쓸 수 있다.** 별도 배선 없음.

⚠️ 단 채점 컨테이너는 클러스터 안에서 그 shim URL 을 호출한다 — shim 이 remote_api 를
받아 외부로 나가는 경로가 llm_playground pod 을 거치므로 egress 는 이미 검증된 경로다.

## 9. Cross-surface 계약 변경

| 짝 | 동기화 대상 |
|---|---|
| 판별자 | `dto.py` Literal ↔ `deployment_envelope.TARGET_*` ↔ `get_deployment_targets` 분기 ↔ FE `TARGETS` |
| 라우팅 | FE `detailPath()` ↔ `PlaygroundMenu` kind ↔ `UserRouter` path — 3곳 동시 |
| 앱↔차트 | **변경 없음** — 신규 env/이미지 불필요 |
| monitoring pod_type | **해당 없음** — pod 이 없어 GPU 귀속 대상이 아님 |
| BFF↔manifest | **해당 없음** — 외부 컨테이너 경로 미사용 |

## 10. 빌드/배포 시퀀스

실측(§2)상 소스가 NFS 마운트이므로 **이미지 재빌드 없음**.

```
1. apps/llm_playground/src, apps/fb_utils 수정
2. kubectl rollout restart deploy/jfb-llm-playground -n ${JF_NAMESPACE}
3. front/ 수정 후 yarn build  (npm 금지)
4. (필요 시) jfb-app-front rollout restart
```

운영(`jonathan-system`) 반영 시에는 관례대로 이미지 빌드 + values 태그 bump 가 필요하다
— dev 의 마운트 편의를 운영 절차로 착각하지 말 것.

## 11. 호환성 리스크

| # | 리스크 | 레벨 | 대응 |
|---|---|---|---|
| 1 | 기존 3종 배포 회귀 | **HIGH** | 분기는 전부 신규 키(`remote_api`) 유무로만 진입. 기존 경로 코드 무수정 |
| 2 | 키가 로그/예외/helm 에 노출 | **HIGH** | 헤더 전용·K8s Secret·예외 메시지에 키 미포함. `llm_model/service.py:38 _redact_secrets` 관용구 참조 |
| 3 | SSRF (endpoint provider) | **HIGH** | `_validate_local_url` 이식(resolve IP 직결·멀티레코드 전수·link-local 차단) |
| 4 | 배포 삭제 시 Secret 잔존 | MED | `delete_playground` 에 `delete_secret` 호출 추가(멱등) |
| 5 | Kong 60s 타임아웃 | MED | 상용 API 응답이 60s 넘으면 게이트웨이가 먼저 끊음. 어댑터 타임아웃을 그 아래로 |
| 6 | 이름 길이 | LOW | `playground.name VARCHAR(32)` — 기존 규약 그대로 |
| 7 | 비용 폭주 | LOW | 사용자 키·사용자 책임. 플랫폼은 과금 추적 안 함 |

## 12. 테스트 계획

**함수 단위**
- provider→호스트 매핑이 allowlist 밖 값을 거부하는가
- `_validate_local_url`: `169.254.169.254`, `::1` 우회, 멀티레코드 중 하나만 사설인 경우
- 어댑터 응답 정규화: 3사 응답 shape → `{"output": str}`
- 키가 예외 문자열·로그에 등장하지 않는가

**클러스터 e2e**
- remote_api 배포 생성 → 키 저장(Secret 실존 확인) → 추론 1건 → 출력
- 같은 배포로 벤치마크 런 1건 (shim 경유 확인)
- 배포 삭제 → Secret 소멸 확인
- 기존 cluster/edge/standalone 배포 3종 목록·상태 회귀 확인

**FE 브라우저 QA**
- 생성 모달 4번째 카드 → provider 선택 → 상세 진입 → 추론 탭 동작
- 목록에서 유형 배지 표시

## 13. 목업 정합

`front_etri` 에 **외부 API 배포 화면은 없다**(실측). provider 선택 UI 는 평가 쪽
`LlmJudgeEvaluationPage.jsx:12-16` 에만 존재하며, 그 기본 모델값이 우리 백엔드
`JUDGE_DEFAULT_MODEL` 과 정확히 일치한다(gpt-4o / claude-opus-4-8 / gemini-2.0-flash).

→ 목업 부재 구간이므로 신규 설계하되, **provider 카드의 시각 언어(아이콘+라벨+기본
모델명)를 목업에서 그대로 가져와** 플랫폼 내 일관성을 지킨다. 목업과 충돌하는 지점 없음.

---

## 14. 구현 중 확정된 설계 편차 (2026-09-01)

구현·실측 과정에서 설계와 달라진 3건. 모두 실측 근거가 있어 문서를 코드에 맞춘다.

### 14.1 저장(save)과 검증(verify)을 분리 — 검증 실패가 저장을 막지 않는다
설계 §6.1 은 "시작 = 검증 후 기록"이라 저장도 검증 실패 시 예외를 올렸다. 실측하니
대상이 잠깐 느리기만 해도(배포 28이 동시 최적화로 포화 → 42초) 사용자가 방금 입력한
**키까지 잃었다**. 상태 모델(phase 는 마지막 도달성 결과에서 파생)과도 어긋난다.
→ `save_remote_api_config` 는 구성이 유효하면 항상 저장하고, 검증 결과를
`state`/`last_error` 로 정직하게 남긴다. 확정적 재시도는 '연결 확인'(start) 버튼.

### 14.2 `VERIFY_TIMEOUT` 20s → 45s
상용 API 는 `max_tokens=8` ping 이 1~3초지만, 자체 서빙 엔드포인트는 `max_tokens` 를
무시하기도 한다 — **우리 OpenAI shim 이 그렇다**(body 의 생성 파라미터를 의도적으로 버림).
20s·30s 로는 정상 엔드포인트가 실패로 찍혔다. 저장 PUT·시작 POST 는 브라우저→Kong(60s)
경로라 45s 가 상한선이다.

### 14.3 envelope phase 는 전용 표가 아니라 형제와 같은 flat `status` 사용
목록 행(`get_playground_list`)은 `deployment` JSON 을 싣지 않고 이미 파생된 flat
`status` 만 준다. 전용 `normalize_remote_api_phase` 를 두면 목록에서 항상 `stopped` 로
보인다(실측). standalone/edge_deploy 형제와 같이 `_cluster_status_str` +
`normalize_cluster_phase` 를 쓰고, 전용 함수는 **삭제**했다(신규 추상화 0 유지).
provider/model 메타는 목록 행에 `remote_api` 키로 동봉한다(키는 제외).

## 15. 구현 검증 결과 (클러스터 e2e, 개발 인스턴스)

| # | 항목 | 결과 |
|---|---|---|
| 1 | SSRF 가드 6종(metadata·link-local·file://·`..`·미resolve·loopback 허용) | PASS |
| 2 | provider 검증 5종(미지원·URL누락·기본모델·길이상한) | PASS |
| 3 | 키가 URL/body 에 유출되지 않음 / Gemini 경로 주입 인코딩 | PASS |
| 4 | base_url 4형태(`/v1` 유무·후행 슬래시·서브패스) 조립 | PASS |
| 5 | 구성 저장 → `status:1` + state 정직 보고 | PASS |
| 6 | 구성 조회 — 키 미노출(`has_key` 만), provider 카탈로그 | PASS |
| 7 | 시작(연결 확인) → state=running, verified_at 기록 | PASS |
| 8 | 추론(`/test`) — 실 한국어 응답 2.4s | PASS |
| 9 | **평가용 OpenAI shim** — `2 + 2 = 4.` 0.8s | PASS |
| 10 | 데이터셋 일괄 거부 메시지 | PASS |
| 11 | targets read-model — phase/provider/model 정확, 키 없음 | PASS |
| 12 | 상용 provider(ChatGPT) 실도달 → 401 → "인증 실패" | PASS |
| 13 | K8s Secret 생성(개발 인스턴스 워크스페이스 네임스페이스) / DB 행엔 `secret_ref` 만 | PASS |
| 14 | 삭제 → Secret 소멸 + 타겟 목록 회귀 없음(cluster 4건) | PASS |
| 15 | FE `yarn build` 그린, 신규 페이지 번들 포함 | PASS |

미검증 1건: **유효한 상용 API 키로의 실제 생성** — 키 미보유. 12번이 401 까지 도달을
입증하므로 남은 것은 키뿐이다.

## 16. 운영 함정 — NFS 마운트에서 stale 바이트코드

dev 는 소스가 NFS 마운트라 `rollout restart` 만으로 반영되지만(§2), **`__pycache__` 가
남아 있으면 옛 `.pyc` 가 그대로 실행된다**(실측: 트레이스백이 주석 줄을 가리키고
수정 전 로직이 동작). NFS mtime 때문에 Python 의 무효화 검사가 통과해 버린다.
→ 소스 수정 후에는 `__pycache__` 디렉터리를 지운 뒤 `rollout restart` 할 것.
