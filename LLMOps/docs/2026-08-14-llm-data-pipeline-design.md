# LLM · VLM 학습 특화 데이터 파이프라인 설계

작성 2026-08-14 · 대상 브랜치 `Acryl-LLMOps-dev` · 개발 인스턴스

목업 정본: `LLMOps/vlm-data-factory-app/` (Vite + React18 + Tailwind + react-router v6, 48파일 ~2,600줄)

---

## 1. 요구사항 재정의

학습 데이터 구축(업로드 → 전처리 → 필터 → 생성 → VLM 심사 → 사람 검수 → 분포 분석 → 구성·분할 → 버전 릴리스)을
LLM 도메인 안의 단일 표면으로 세운다. 프론트는 `front/src/pages/llm/dataset/`, 백엔드는 신규 MSA `apps/llm_data_pipeline`.

## 2. 활성 토폴로지 (실측 2026-08-14)

| 항목 | 실측 |
|---|---|
| 개발 네임스페이스 | 개발 인스턴스(`${JF_NAMESPACE}`, 이 worktree 소속) — 작업 대상 |
| 서빙 네임스페이스 | `jonathan-system` (얼림) — 건드리지 않음 |
| 기존 LLM 앱 | `jfb-llm-model` · `jfb-llm-playground` · `jfb-llm-evaluation` → 신규가 4번째 |
| front | 모노레포 단일 repo (별도 repo 아님). Vite + Redux + SCSS 모듈 786개, **Tailwind 없음**, **react-router v5** |

## 3. 결정 사항 (사용자 확정)

1. **스타일** — Tailwind 도입하지 않고 **SCSS 모듈로 전면 변환**. front `styles/color.scss` 토큰 재사용.
2. **앱 이름** — `llm_data_pipeline` (스네이크케이스, 기존 LLM 앱 규약 일치). Kong prefix `/api/(data-pipelines)`.
3. **기존 표면 관계** — flightbase 데이터 표면(**전처리 · 분석 · 합성**)을 신규 파이프라인이 **대체**.
   - ⚠️ **예외: `fb_pipeline` 은 보존.** `task_type` 이 `finetuning / quantize / llm_deploy / prompt_gen / data_gen / algo_call` 로
     데이터 파이프라인이 아니라 **GenAI 통합 파이프라인(학습·양자화·배포 DAG)** 이다. 제거 시 파인튜닝·양자화·배포가 깨진다.
4. **1차 범위** — 13화면 전부 + BE 스캐폴드.

## 4. 토큰 매핑 (목업 Tailwind → front SCSS)

front `styles/color.scss` 가 이미 같은 조나단 팔레트를 갖고 있어 대부분 1:1.

| 목업 | front | 값 |
|---|---|---|
| `blue-104` | `$blue104` | `#2d76f8` |
| `blue-106` | `$blue105` | `#164abe` |
| `blue-102` | 신규 로컬 토큰 | `#eaf1fe` — front `$blue102` 는 `#c8dbfd` 로 다름 |
| `mono-200…207` | `$mono200…207` | 동일 |
| `green-601 / 603 / 604` | `$lime601 / 603 / 604` | `#e3fcee / #00c775 / #439f6e` 정확히 일치 |
| `red-501 / 502 / 503` | `$red501 / 502 / 503` | 동일 |
| `orange-401` | `$orange401` | `#fff0e4` |
| `orange-404` | 신규 로컬 토큰 | `#b35500` |

목업 고유 토큰(radius `ctl 7 / ctl2 8 / ctl3 9 / card 12 / tile 16`, shadow `card / tile / ring / node / drawer`,
easing `cubic-bezier(.4,0,.2,1)`, duration `120/180/240`)은 `pages/llm/dataset/styles/_tokens.scss` 에 모은다.

## 5. 프론트 구조

```
front/src/pages/llm/dataset/
  index.js
  styles/_tokens.scss              목업 고유 토큰 + front color.scss 매핑
  lib/format.js                    fmt · allocate · tokenTotals · gateState
  lib/frames.js                    플레이스홀더 SVG (SHOTS · seaFrame)
  mock/                            datasets · assets · records · coverage · versions · chain · sds
  components/                      목업 ds/ + features/ + layout/ 포팅 (SCSS 모듈)
    Btn · Badge · Field(Textfield·Textarea·Select·SearchField·Checkbox·RadioBtn·Slider)
    Display(ProgressBar·MetricCard·Pagination·SectionHead)
    GateRibbon · NodeCanvas · NodeDrawer · Funnel · DataTable
    DatasetPageHeader · DatasetTabBar · DatasetTabs
  DatasetListPage/ UploadPage/ PipelinePage/ PreprocessPage/ FilterPage/ GeneratePage/
  GatePage/ SdsNodePage/ ReviewPage/ AnalysisPage/ ComposePage/ HistoryPage/ RecordPage/
```

라우트 (react-router **v5**, `UserRouter.jsx` `routeArrAll` 등록):

| 목업 v6 경로 | front v5 경로 |
|---|---|
| `/` | `/user/workspace/:id/datasets/pipeline` |
| `/ds/:dsId/upload` | `/user/workspace/:id/datasets/pipeline/:dsId/upload` |
| `/ds/:dsId/pipeline` | `…/:dsId/flow` |
| `/ds/:dsId/pipeline/preprocess` | `…/:dsId/flow/preprocess` |
| `/ds/:dsId/pipeline/filter` | `…/:dsId/flow/filter` |
| `/ds/:dsId/pipeline/generate` | `…/:dsId/flow/generate` |
| `/ds/:dsId/pipeline/gate` | `…/:dsId/flow/gate` |
| `/ds/:dsId/pipeline/node/:idx` | `…/:dsId/flow/node/:idx` |
| `/ds/:dsId/review` | `…/:dsId/review` |
| `/ds/:dsId/analysis` | `…/:dsId/analysis` |
| `/ds/:dsId/dataset` | `…/:dsId/compose` |
| `/ds/:dsId/dataset/history` | `…/:dsId/compose/history` |
| `/ds/:dsId/record/:rid` | `…/:dsId/record/:rid` |

라우터 API 변환: `useNavigate()` → `useHistory().push`, `useParams()` 유지, `<Routes>/<Route element>` → `routeArrAll` 항목.

**대체로 제거되는 기존 라우트** (전처리 · 분석 · 합성):
`/datasets/process`, `/datasets/process/:did/detail`, `/datasets/analysis`, `/datasets/analysis/:did/detail`,
`/datasets/synthesis` 및 하위 5종(`overview` · `prompt-optimize` · `wizard` · `prompt-list` · `canvas`).
수집(`/datasets/collect`) · 라벨링(`/datasets/labeling`) · 드라이브(`/datasets/management`) 는 유지.

## 6. 백엔드 구조

```
apps/llm_data_pipeline/
  Dockerfile · run.sh · requirements.txt
  src/main.py                      FastAPI 팩토리, app.mount('/api', api), openapi /data-pipelines/openapi.json
  src/data_pipeline/{__init__,route,service,dto,constants}.py
  migrations/001_llm_data_pipeline.sql
devops/llm_data_pipeline/helm/
  Chart.yaml (name: jfb-llm-data-pipeline, commonlib 0.1.0 의존)
  templates/{deployment,service,ingress,rbac,volume_src}.yaml
```

Kong ingress: `path: /api/(data-pipelines)(.*)` · APIRouter `prefix="/data-pipelines"`.

엔드포인트 (목업 `mock/*` 이 계약 초안):

| 메서드 · 경로 | 대응 화면 |
|---|---|
| `GET/POST /datasets` | 데이터셋 목록 · 생성 |
| `POST /datasets/{ds_id}/assets` | 원본 등록(드라이브 참조) |
| `GET /datasets/{ds_id}/records/{record_key}` | 레코드 상세(사람이 읽는 키) |
| `GET /datasets/{ds_id}` | 공통 헤더 |
| `GET /datasets/{ds_id}/assets` | 업로드 (목록 + summary + failures) |
| `GET/PUT /datasets/{ds_id}/flow` | 파이프라인 노드 체인 (preset `generic` \| `sds_colreg`) |
| ~~`POST /datasets/{ds_id}/flow/run`~~ | 파이프라인 실행 — **2차**(외부 컨테이너 디스패치 필요, 미구현) |
| `GET/PUT /datasets/{ds_id}/stages/{stage}` | 단계 설정 (`stage` = preprocess\|filter\|generate\|gate) |
| ~~`POST /datasets/{ds_id}/stages/{stage}/run`~~ | 단계 실행 — **2차**(동일) |
| `GET /datasets/{ds_id}/records` | 검수 큐 (정렬 · 오류유형 필터) |
| `GET /records/{record_id}` | 레코드 상세 |
| `POST /records/{record_id}/review` | 승인 · 수정후승인 · 거절 |
| `GET /datasets/{ds_id}/coverage` | 분포 분석 (유형별 + UMAP 좌표) |
| `GET/POST /datasets/{ds_id}/versions` | 이력 · 버전 생성 |
| `POST /datasets/{ds_id}/verify-format` | 학습 형식 미리 검사 |

DB — **신규 테이블만** (ALTER 회피):
`llm_dp_dataset` · `llm_dp_asset` · `llm_dp_node` · `llm_dp_record` · `llm_dp_review` · `llm_dp_version`.

`llm_dp_dataset.flow` 가 노드 간 엣지를 갖는다(노드 행이 아니라 그래프의 속성).
`llm_dp_record.worst_score` 는 기록 시점에 계산해 둔 최저 축 — 검수 큐 정렬이 매 요청마다
JSON 을 평가하지 않게 한다. 생성자는 `create_user` 문자열(jf-User 헤더)이며 `msa_jfb.user` FK 를 걸지 않는다.

## 7. 도메인 규칙 (목업 코드에 박힌 것 — 구현이 보존해야 함)

1. **기하 변형은 심사 점수를 무효화한다.** `크롭 · 회전 · 좌우 반전 · 리사이즈` 가 레코드 단계에 걸리면 재심사 필요.
   그중 `영역 좌표 보정` 이 없으면 bbox 가 깨진다 → 노드 상태 `위험`. `회전 · 좌우 반전` 은 사람 판정까지 무효.
2. **4축 심사 임계값** — 이미지 정합도 0.75 · 이미지 의존도 0.80 · 답변 가능성 0.80 · 정답 유일성 0.70.
3. **생성 모델 = 심사 모델 금지.** 같으면 실행 차단, 같은 계열(`fam`)이면 경고. 자기 결과 자가심사는 맹점이 겹쳐 게이트가 무의미해진다.
4. **정상 통과율 범위 40–85%.** 85% 초과는 게이트가 헐거울 수 있다는 신호 → `범위 밖` 표시.
5. **SDS COLREG 는 결정론 계산이 앵커.** AIS 기하로 조우유형 · 조항(13/14/15/17) · CPA · TCPA 를 먼저 계산하고
   그 사실을 grounding 으로 넣어 생성 → 환각 원천 차단. 이 프리셋은 구성 고정(편집 불가).
6. **분할은 문서 ID 기준이 기본** — 같은 문서의 페이지가 train/test 로 갈리면 누출.

## 8. Cross-surface 계약

- **앱 ↔ 차트 페어** — `apps/llm_data_pipeline` 신설 시 `devops/llm_data_pipeline/helm` 동시 신설 +
  `devops/run_llm.sh` install/uninstall/upgrade **3블록 모두** 등록.
- **FE ↔ API** — `front/src/apis/llm/dataset/index.js` 의 `callApi({url:'data-pipelines/...'})` prefix 가 ingress `path` 와 일치해야 함.
- **라우트 제거 ↔ LNB** — 전처리·분석·합성 라우트를 빼면 `UserRouter.jsx` 의 `isLastGroup` · `excludeChildren` 플래그도
  함께 조정해야 그룹 점등이 깨지지 않는다.
- **마이그레이션** — 러너 부재(기존 이슈)이므로 `migrations/001_*.sql` 은 수동 적용 경로를 명시한다.

## 9. 빌드 · 배포 시퀀스

1. `apps/llm_data_pipeline` 이미지 빌드 → `devops/llm_data_pipeline/helm/values` 태그 정합
2. `devops/run_llm.sh install|upgrade -f values_dev.yaml` (`JF_NAMESPACE=<개발 인스턴스 네임스페이스>`)
3. `migrations/001_llm_data_pipeline.sql` 수동 적용
4. front: `yarn build` → `jfb-app-front` 반영

## 10. 리스크

| 리스크 | 레벨 | 대응 |
|---|---|---|
| 전처리·분석·합성 라우트 제거로 기존 사용자 플로우 단절 | HIGH | 라우트만 제거하고 앱·데이터는 보존. 되돌리기는 라우트 복원으로 충분 |
| `fb_pipeline` 을 데이터 파이프라인으로 오인해 함께 제거 | CRITICAL | §3-3 예외로 명문화. 학습 DAG 는 손대지 않음 |
| Tailwind 임의 클래스(`shadow-[inset_…]`)의 SCSS 변환 누락 | MED | 토큰을 `_tokens.scss` 에 선집계 후 화면 이식 |
| react-router v5/v6 API 차이 | MED | `useNavigate` → `useHistory` 일괄 변환, 중첩 라우트는 평면 `routeArrAll` 로 |
| 13화면 동시 이식 중 회귀 | MED | 화면별 독립 폴더 + 화면 단위 빌드 확인 |
