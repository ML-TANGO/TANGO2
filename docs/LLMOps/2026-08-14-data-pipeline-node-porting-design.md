# 데이터 파이프라인 노드 이식 설계

작성 2026-08-14 · 대상 브랜치 `Acryl-LLMOps-dev` · 개발 인스턴스

프로토타입 정본: 별도 프로토타입 저장소 `data_pipeline` (Python 2,620줄 · 테스트 144건 그린 · 실모델 E2E 완주)
선행 설계: [`2026-08-14-llm-data-pipeline-design.md`](2026-08-14-llm-data-pipeline-design.md) — FE 12화면 + BE 스캐폴드(커밋 `eadec874c`/`074c7d3b6`/`91740fbf8`)

---

## 1. 요구사항 재정의

프로토타입의 노드(전처리 · 필터 · 생성 · 심사)를 플랫폼에 **각각 독립 잡으로** 이식해 순서대로 실행하고,
그 산출물이 사람 검수를 거쳐 학습용 버전으로 릴리스되기까지를 하나로 잇는다.

완료 기준: 범용(generic) 파이프라인이 소스 데이터셋에서 시작해 릴리스까지 완주하고,
프로토타입 실측치(SDS 8씬 = 7/8 통과, 탈락 1건 `image_grounding` 0.30)를 재현한다.

**범위**: 범용 파이프라인 우선. SDS(해양 COLREG)는 노드 2개(`join`·`calc`) 추가로 후속.
**일정**: 공인시험(8/31) 비대상. 반복 고도화 전제.

---

## 2. 프로토타입 분석 결과

### 2.1 구성 — 셋으로 나뉘어 있다

| 산출물 | 성격 | 상태 |
|---|---|---|
| `vdf_proto/` | 범용 VLM 데이터 팩토리 — 큐레이션 → 합성 → 4축 게이트 | 실모델 완주 |
| `sds_pipeline/` | 해양 COLREG — 영상+AIS → 조인 → 결정론 계산 → 생성 → 게이트 → LLaVA | 실모델 완주(100씬) |
| `backend/` `frontend/` | FastAPI + React 스켈레톤 | **전부 stub — 이식 대상 아님** |

`backend/app/routes/datasets.py`의 13개 라우트가 전부 `return []` / `{"status":"queued"}`.
프로토타입의 웹 계층에는 이식할 로직이 없다. 대상은 두 파이썬 패키지뿐이다.

### 2.2 노드 인벤토리 — GPU 노드는 4개뿐

| 노드 | 구현 | GPU |
|---|---|---|
| normalize | `curation/normalize.py` | ✕ |
| documents (PDF→페이지) | `curation/documents.py` | ✕ · **유일한 1→N 확장** |
| quality | `curation/quality.py` | ✕ |
| dedup | `curation/dedup.py` | △ CLIP |
| synth | `synth.py` + `prompts.py` | ○ |
| gate | `gate.py` | ○ · **레코드당 3콜** |
| sample / frame_refine / preprocess (SDS) | `ingest/*.py` | ✕ |
| ais_clean / read_ais_log (SDS) | `ingest/ais*.py` | ✕ |
| **join** (SDS) | `join.py` | ✕ |
| **classify COLREG** (SDS) | `colreg.py` | ✕ · 순수 기하, VLM 무관 |
| generate_action / score_action (SDS) | `generate.py` `judge.py` | ○ |
| assemble | `assemble.py` | ✕ |

### 2.3 반드시 보존할 설계 자산 7가지

프로토타입의 값어치는 배관이 아니라 아래 판단들이다. 하나라도 빠지면 게이트가 장식이 된다.

1. **Generator ≠ Judge 하드 실패** — `assert_distinct`가 같은 모델이면 예외로 런을 죽인다. 자기 출력을 자기가 채점하면 게이트가 무의미해진다.
2. **`imgdep`는 평점이 아니라 실제 어블레이션** — 저지에게 "이미지 의존도 몇 점?"을 묻지 않고, **이미지를 빼고 답을 시킨 뒤 정답과 대조**해 `1 − 정확도`로 계산한다(`gate.py:114`). "이미지 없이도 답되는 질문"이 판단이 아니라 **데이터에 대한 사실**이 되는 이유.
3. **`colreg_correctness`는 결정론 앵커 대조** — rubric 점수를 받은 뒤 계산된 조우유형/조항과 불일치하면 **0으로 강등**(`judge.py:73`). LLM 점수를 코드가 덮어쓴다.
4. **통과율 40–85% 밴드** — 낮으면 생성 품질 문제, **높아도 경고**(게이트가 헐거움). 양방향 신호.
5. **per-item 격리 + JSONL 스트리밍** — 한 건 실패가 배치를 안 죽이고, 중간 크래시에도 이미 만든 레코드가 디스크에 남는다.
6. **`VLMClient` Protocol 이음새** — `name` + `chat` 두 개짜리 프로토콜에 transformers · vLLM HTTP · Fake 3구현이 물려 있다. **이식의 통로.**
7. **funnel `{stage, in, out, dropped}`** — 단계마다 몇 개가 왜 빠졌는지가 1급 산출물.

### 2.4 실측 증거

| 항목 | 값 |
|---|---|
| SDS 8씬 | 8건 생성 / **7건 통과(87.5%)**, 탈락 1건 = `image_grounding` 0.30 |
| SDS 100씬 풀런 | 100건 / **57건 통과(57%)** |
| 범용 chain | 8 큐레이션 → 16 레코드 → **7/16 = 44%** |
| transformers ↔ vLLM | **판정 100% 일치**(5케이스 프로브) — 백엔드 교체가 결과를 안 바꿈 |
| 게이트 콜 5→3 병합 | 5건 중 4건 동일, 1건은 align 1.0 vs 0.8 → **게이트 판정 불변** |
| 테스트 | `tests/` 스코프 144건 그린 / 6.9초 |

### 2.5 알려진 결함 — 그대로 옮기면 안 되는 것

🔴 **임계값이 도메인마다 틀린다. 최대 리스크.**
- 블러 임계 100은 해양 프레임(실측 Laplacian 2–10)에 부적합 → SDS는 `_HARD_REASONS`에서 blur를 빼는 것으로 **우회**했다(`preprocess.py:6`). 코드에 박힌 우회지 해결이 아니다.
- 노출 임계도 문서 페이지를 전량 오드롭했다가 `EXPO_STD_MIN=25` 조건 추가로 고쳤다.
- → **임계값이 노드 파라미터로 노출되지 않으면 도메인이 늘 때마다 코드를 고치게 된다.**

🟡 미해결
- CLIP이 **3° 회전 세만틱 중복을 못 잡음**. 문서 경로는 텍스트 Jaccard로 우회했으나 이미지 경로는 그대로.
- **head_on 분류기 GT 일치율 45%** — 임계각 튜닝 미완.
- **`unique` 축이 discriminative하지 않다** — 의도적으로 모호한 질문("What is shown here?")에 1콜/3콜 양쪽 다 1.0을 줬다.
- 다국어 + `--dump-stages` 동시 실행 시 `stages_dir` 언어 간 덮어쓰기.

⚪ README가 코드보다 뒤처져 있다 — "dedup→quality 순서", "ValueError만 격리"는 현재 코드와 다르다(실제: quality→dedup, `except Exception`).

---

## 3. 확정된 설계 결정

### D1. 실행 경로 = **내부 빌트인 잡** (외부컨테이너 계약 미사용)

`prepro_job` 경로의 실제 계약:

```
helm install <name> prepro_job/ --set spec.containers.image=<lean base>
                                --set spec.containers.command="python3 -u /built_in/<script>.py <params>"
```

`/built_in`은 **jf-bin NFS 마운트**라 스크립트가 이미지에 구워지지 않는다.
등록 지점은 `fb_utils/TYPE_BUILT_IN.py:137` `PREPROCESSING_TFS_SCRIPT` 딕셔너리 한 줄이고,
**이미 20종 넘는 빌트인이 이 방식으로 돈다.** 우리 노드는 21번째부터.

| | 외부컨테이너 계약 | **내부 빌트인 잡** |
|---|---|---|
| 노드 추가 | 이미지 빌드→push→manifest→등록 승인 | **NFS에 `.py` 1개 + 딕셔너리 1줄 + DB 시드** |
| 이미지 재빌드 | 노드마다 | **0회** (의존성이 base에 있으면) |
| securityContext | `runAsNonRoot`·`readOnlyRootFS` 제약 | 1차년도 패턴, 제약 없음 |
| GPU | manifest resources | 차트가 이미 지원(`device.type=GPU` → `NVIDIA_VISIBLE_DEVICES`) |
| **코드 수정 반영** | 재빌드 | **NFS 파일 교체만** |

마지막 줄이 결정적이다. 반복 고도화 전제에서 **노드 로직을 고칠 때마다 이미지를 굽지 않아도 된다.**

부수 이득: 잡이 `preprocessing_job`으로 등록되므로 `fb_dataset/service.py:195-201`의
`get_dataset_used_preprocessing_jobs_list` **"사용 중" 추적에 자동 편입**된다(§7.2 참조).

### D2. 노드 = 스크립트 1개, 분할 단위는 **노드 종류(kind)**

기능(step)까지 잡으로 나누지 않는다. 이유는 NFS 왕복이다 — 기능마다 잡을 띄우면
중간 이미지를 기능 수만큼 NFS에 읽고 쓴다. 노드 안에서 순차 실행하면 이미지는 메모리에
있고 디스크는 1번만 쓴다. 이 클러스터는 NFS 과부하로 학습 잡이 죽은 이력이 있다.

| 스크립트 | kind | 안에서 순차 실행할 기능 | 여러 개 배치 |
|---|---|---|---|
| `dp_prep.py` | `prep` | 정제 · 구조추출 · 리사이즈 · 크롭 · 회전 · 좌우반전 · 좌표보정 | ✅ |
| `dp_filter.py` | `filter` | 중복제거(pHash·텍스트) · 저품질 · 민감콘텐츠 | ✅ |
| `dp_generate.py` | `synth` | 프롬프트 칩 조립 → VLM 서빙 HTTP 호출 | ✅ |
| `dp_judge.py` | `gate` | 4축(rubric 1콜 + 어블레이션 2콜) | ✅ |
| `dp_assemble.py` | `out` | 학습 포맷 조립 | ✅ |

데이터 노드는 마운트 선언이라 잡이 없다. 노드가 여러 개인 것은 `llm_dp_node.node_index`가
이미 표현하며, 같은 스크립트가 잡으로 여러 번 뜨면서 각자 다른 `steps`/`config`를 받는다.

**기동 비용 실측** (분할이 싼 근거):

| 항목 | 측정값 |
|---|---|
| 경량 스택 import (PIL·numpy·imagehash·pymupdf) | **0.32s** |
| 무거운 스택 import (torch·transformers) | 3.14s ← **서빙 분리로 불필요** |
| normalize 100장 | 2.98s |
| quality 100장 | 8.27s |

서빙을 분리하면 생성·심사 노드가 HTTP 클라이언트가 되어 torch가 필요 없다
(`vllm_client.py`는 stdlib만 씀). 다섯 노드가 **같은 lean base**를 쓴다.

**베이스 이미지 1회 확장 필요** — 현재 `genai-platform-builtin-preprocess:tango_v2.1.0`은
pandas+pyarrow뿐. PIL·numpy·imagehash·pymupdf를 얹는다. 그 뒤로는 전부 스크립트 작업.

CLIP 세만틱 중복제거만 예외(151M). 프로토타입에서 실제 문서 페이지 **11% 오탐** 이력이 있어
pHash + 텍스트 Jaccard로 먼저 가고 CLIP은 후순위로 미룬다.

### D3. 모델 서빙 = playground 자체 서빙을 **VLM으로 확장**

현재 playground 서빙은 **채팅 LLM 전용이고 이미지가 통과하지 못한다.** 3중 확인:

- `llm_playground/service.py:3236` `_messages_to_prompt` — content가 문자열이 아니면 `continue`로 **조용히 버린다**. `image_url` 배열은 사라지고, 이미지만 보내면 "no textual content in messages"로 실패.
- 서빙 래퍼가 role 분리도 안 받고 `test_question` **단일 문자열**만 받는다.
- 백엔드가 Triton+vLLM인데 tokenizer `chat_template`으로 프롬프트를 **평탄화**하는 구조.

확장 대상 4곳:

| 파일 | 변경 |
|---|---|
| `fb_scheduler/helm_chart/deployment_llm/src/llm/playground.py` | `LLM_ENGINE.generate(prompt_string, …)` → vLLM `multi_modal_data` 지원. `post_llm`이 이미지 입력 수용 |
| `llm_playground/src/playground/service.py:3236` | `_messages_to_prompt`가 non-string content를 버리는 것 → 이미지 보존 |
| `fb_utils/settings.py` | VLM 서빙 이미지 태그 |
| 모델 등록 | Qwen3-VL-8B / InternVL3-8B (HF 캐시에 이미 있음) |

vLLM 자체는 VLM을 지원하므로 엔진 교체는 없다. **입력 경로가 문자열로 좁혀져 있는 걸 넓히는 작업.**
생성용·심사용 **2개 인스턴스**를 띄우면 `assert_distinct`가 자연히 지켜진다.
플랫폼이 GPU 개수를 골라 launch(`model_gpu_count`)한다.

### D4. 축 스키마를 프리셋별로 분리

현재 `constants.py`의 `GATE_AXES`·`DEFAULT_THRESHOLDS`는 범용 4축 하드코딩이고
`db.count_gate_failed()`도 그 축을 전제한다. SDS는 축 이름·임계가 전부 다르다.

```
GATE_AXES → PRESET_AXES = {
  generic:    align .75 / imgdep .80 / answer .80 / unique .70
  sds_colreg: situation_accuracy .75 / colreg_correctness .80
              / image_grounding .70 / actionability .75
}
```

`llm_dp_record.scores`는 JSON이라 스키마 변경 없이 담긴다.
고칠 곳은 `constants.py` · `service.get_effective_thresholds` · `db.count_gate_failed` 세 곳.

---

## 4. 스토리지 설계

### 4.1 실측한 저장 구조

```
PVC jf-data (워크스페이스 단위)
└─ data/{workspace}/          ← PVC 루트
   ├─ 0/                      ← access=0
   └─ 1/                      ← access=1
      ├─ sds/  llamarine/  cc3m/  test/    ← 데이터셋들
```

`prepro_job`은 `jf-data`를 subPath `{access}/{name}`으로 `/dataset`에 마운트 — **데이터셋 딱 하나**.

### 4.2 `access`의 의미 — 무엇이 아니라 **누가**

`access_check.py`. 접근 레벨 1=root, 2=워크스페이스 관리자, 3=생성자, 4=워크스페이스 사용자, 기본 허용선 3.

| 동작 | 허용선 | `access` 영향 |
|---|---|---|
| 폴더 생성·수정·삭제 | 4 | **`access=='0'`이면 3으로 낮춤** |
| 다운로드·미리보기 | 5 → 4로 낮춤 | **없음** |

**`access`는 "수정 권한을 워크스페이스 전체에 열 것인가"** 다 — `0`=생성자·관리자만 수정, `1`=워크스페이스 사용자도 수정.
**읽기는 둘 다 워크스페이스 사용자에게 열려 있다.**

→ 파이프라인 잡이 워크스페이스 사용자 자격으로 도는 이상 **그 워크스페이스의 모든 데이터셋을 읽는 것은 이미 허용된 행위**다.
PVC 루트를 RO로 마운트해도 새로 열리는 것이 없다. access 0·1 혼용도 문제없다.

### 4.3 마운트 — 입력은 다중, 출력은 작업 데이터셋 하나

```
/datasets   RO   ← jf-data 루트.  /datasets/{access}/{name}/{folder}
                   데이터 노드가 어느 데이터셋·폴더든 가리킬 수 있다. 개수 무제한.

/dataset    RW   ← 이 파이프라인의 작업 데이터셋 (기존 단일 마운트 그대로)
```

**차트 변경은 마운트 한 줄 추가뿐이다.** 기존 `/dataset`은 손대지 않으므로 현재 돌고 있는 빌트인 4종에 회귀가 없다.
여러 데이터셋을 위해 마운트를 여러 개 만들 필요가 없다 — 한 워크스페이스의 모든 데이터셋이 이미 같은 PVC 안에 있으므로
subPath를 한 단계 올리면 하나의 마운트로 전부 보인다. helm 배열 `--set`의 콤마 이스케이프 함정도 회피된다.

### 4.4 작업 데이터셋 — 선례와 그 선례를 따르지 않는 지점

`synthesis_project`가 데이터 도메인의 기존 관행이다.

```
dataset_id      COMMENT '입력 데이터셋'
output_subdir   COMMENT '생성 결과(result.jsonl) 하위 경로'
```
`fb_synthesis/route.py:140` — "생성 결과 result.jsonl 을 플랫폼 데이터셋으로 등록".

즉 **프로젝트 → 입력 데이터셋 참조 → 하위 경로에 산출 → 데이터셋으로 등록**이 관행이다.
우리는 이 관행을 따르되 **한 가지는 따르지 않는다**: 합성은 `output_subdir`를 **입력 데이터셋 안**에 쓴다.
원본을 오염시키고, 남이 그 데이터셋을 지우면 산출물까지 함께 날아간다.

**파이프라인 생성 시 빈 작업 데이터셋 1개를 새로 만들어 거기에 쓴다.**
처음부터 자기 데이터셋 안에 쌓이므로 합성처럼 끝에 별도 등록 단계도 필요 없다.

### 4.5 작업 데이터셋 내부 구조

```
/dataset/
  _preview/{node_index}/{preview_id}/    ← 표본 실행. GPU 미사용. 최근 K개만 보존, 이력에 안 남음
  _runs/{run_id}/{node_index}/           ← 정식 실행. 전량. 이력에 남음
      config.json                        ← 이 실행에 쓴 기능 목록·순서·파라미터
      records.jsonl                      ← 산출 레코드 (다음 노드의 입력)
      drops.jsonl                        ← 제외 항목: 원본 경로 + 사유
      funnel.json                        ← {stage, in, out, dropped{사유:건수}}
      samples/                           ← 샘플 썸네일 N장
      reused_from.json                   ← (부분 재실행 시) 재사용한 이전 산출물 경로
  releases/{version}/                    ← write-once
      records.jsonl                      ← 릴리스 시점 내용 그대로 고정
      manifest.json
```

| 항목 | 결정 | 이유 |
|---|---|---|
| 작업 데이터셋 `access` | **0** (생성자만 수정) | 정책을 바꾸지 않고 오삭제 가능성을 줄이는 유일한 수단 |
| 원본 데이터셋 | **RO 마운트, 절대 쓰지 않음** | 합성의 오염 패턴을 따르지 않음 |
| 원본을 읽는 노드 | **전처리 하나만** | 그 뒤로는 작업 데이터셋만 봄 → 원본 삭제 노출 창 최소화 |
| 제외 항목 이미지 | **복사하지 않음** | 원본이 RO로 살아 있으니 경로+사유만 기록, 썸네일은 원본에서 생성 |
| 작업 데이터셋 단위 | **파이프라인당 하나** | run은 폴더로 격리. run마다 나누면 버전 비교·이력이 쪼개짐(§5.1) |
| 중간물 확인 | 파일브라우저 | 작업 데이터셋이라 `get_filebrowser_url` 기존 기능이 그대로 붙음 |
| 용량 | 워크스페이스 쿼터에 잡힘 | 보이는 것이 맞음. 릴리스 안 된 `_runs/` 정리 정책은 Phase 5 |

---

## 5. run · version · 미리보기

### 5.1 run과 version은 직교한다

`llm_dp_version`은 **검수를 마친 레코드 풀의 스냅샷**이고 `UNIQUE (dataset_id, version)`이다.

- **1 run → N version**: 같은 레코드 풀에서 구성(mix)만 바꿔 여러 버전을 뽑는다.
- **N run → 1 version**: 1차 1,000건 + 2차 500건을 합쳐 v1.0을 낸다.

run마다 데이터셋을 나누면 두 경우 다 표현이 안 되고, **이력 화면이 한 데이터셋의 버전 목록**을
보여주는 구조라 v0.1과 v0.2가 서로 다른 데이터셋에 흩어져 비교가 불가능해진다.

**계보 보강 2건** (현재 `llm_dp_version`은 `gen_model`·`judge_model`·`prompt_name`·`thresholds`만 남기고
어느 실행의 레코드인지가 없다):

| 위치 | 추가 | 비고 |
|---|---|---|
| `llm_dp_record.lineage` | `run_id` | **JSON이라 스키마 변경 0** |
| `llm_dp_version` | `source_runs` JSON | 이 버전에 담긴 레코드들의 run_id 집합 |

이것으로 버전 → run → 노드 설정 → 소스 데이터셋까지 역추적된다.

**불변성은 파일로 보장한다.** 통계(`record_count`·`pass_rate`·counts)는 릴리스 시점에 확정 저장되지만
레코드 내용 자체는 재검수로 바뀔 수 있다. `releases/{version}/records.jsonl`을 물리적으로 써서 고정한다.

### 5.2 미리보기와 실행을 나눈다

사용자가 기능을 토글할 때마다 정식 run을 만들면 이력이 쓰레기로 찬다.
그리고 **전처리·필터 효과는 GPU 없이 표본만으로 다 보인다** — 프로토타입도 `run.py curate`가
체인을 안 태우고 큐레이션만 돌리는 별도 커맨드다.

| | 경로 | 범위 | GPU | 이력 |
|---|---|---|---|---|
| 미리보기 | `_preview/{node_index}/{preview_id}/` | 표본 N장 | 미사용 | 안 남음(최근 K개 LRU) |
| 실행 | `_runs/{run_id}/{node_index}/` | 전량 | 노드에 따라 | 남음 |

`dto.StageRunBody(dry_run, sample_size)`가 **이미 정의돼 있다** — 실행 라우트를 2차로 비워둔 자리를 채운다.

### 5.3 부분 재실행 — 덮어쓰지 않는다

노드 N 설정을 바꾸면 N부터 끝까지만 돌리고 앞 노드 산출물은 재사용한다.
같은 `run_id` 폴더를 덮어쓰면 이전 결과가 사라져 비교가 다시 불가능해지므로,
**run_id는 항상 새로 발급**하고 재사용 노드는 복사 대신 경로만 적는다.

```
_runs/{new_run}/2/reused_from.json   → {"run_id": "...", "node_index": 2}
```

디스크는 안 늘고, 모든 run이 완전한 계보를 갖고, 아무것도 덮이지 않는다.

### 5.4 비교 — 노드 종류에 따라 지표가 다르다

프로토타입 `report.render_comparison`(축별 before/after + Δ, 상승·하락 색)이 사양이다.

| 노드 | 비교 지표 |
|---|---|
| 전처리 · 필터 | funnel — `in/out` + 사유별 제외 건수 + 샘플 이미지 나란히 |
| 생성 · 심사 | 4축 평균 + Δ + 통과율 |

### 5.5 노드 전후 열람 UI

`curation/report.py`가 이미 만들던 화면이 사양이다 — **funnel 표** + **제외 항목을 사유별로 묶은 썸네일 그리드**.

| | 내용 |
|---|---|
| 노드 산출 | `funnel.json` + `drops.jsonl` + `samples/` |
| BE | `GET .../runs/{run_id}/nodes/{idx}/preview` → `{in, out, dropped{}, samples[]}` |
| FE | 노드 드로어에 **입력 / 통과 / 제외** 3열 + 사유별 썸네일 |

---

## 6. 노드 간 계약

```
/input/params.json  (스케줄러가 --set 으로 넘긴 인자 → 스크립트 argv)
  {
    "run_id": "...", "node_index": 2, "preset": "generic",
    "sources": [{"dataset_id":.., "access":.., "name":.., "folder":".."}, ...],
    "prev": "_runs/{run_id}/1",
    "steps": [["리사이즈", {"longEdge":1024}], ["크롭", {"cropPct":90}]],
    "dry_run": false, "sample_size": 10
  }
```

- 노드 N의 `/dataset/_runs/{run_id}/{N}/`이 노드 N+1의 입력.
- `funnel.json`은 그대로 `llm_dp_node`에 적재 → 파이프라인 화면의 노드 카운트가 된다.
- 심사 노드가 끝나면 레코드를 `llm_dp_record`에 INSERT → **검수 화면이 바로 붙는다**(이미 구현됨).
- helm 릴리스명 = `dp-{dataset_id}-n{node_index}-{run_id}` — 실패 릴리스 이름 재사용 차단을 회피.

---

## 7. 선결 수정 (Phase 0)

### 7.1 🔴 `prepro_job/_command.tpl` 종료코드 결함

```
( cd $JF_HOME
  {{ .Values.spec.containers.command }}
  sleep 10 )
```

**서브셸 종료코드가 `sleep 10`의 0으로 덮여서 스크립트가 실패해도 잡이 성공으로 보고된다.**
전처리 전역 결함이고 포맷 변환 때도 관측됐다.

단발 전처리에서는 "결과가 안 나왔네" 정도지만 **파이프라인에서는 치명적**이다 —
전처리 노드가 조용히 실패해도 파이프라인은 다음 노드로 진행하고, 필터는 없는 입력을 읽고,
최종적으로 빈 데이터셋이 "정상 완료"로 릴리스된다.

### 7.2 데이터셋 삭제 노출 (플랫폼 정책 — 우리가 고치지 않음)

`fb_dataset/service.py remove_dataset`:

```python
if dataset_db.delete_dataset(id_str):
    shutil.rmtree(dataset_dir)          # 즉시·비가역
```

- **사용 중 검사가 없다.** 잡이 마운트한 채 돌고 있어도 지운다.
- `route.py:295`의 `@dataset_access_check(allow_max_level=4)`가 **주석 처리**돼 있다(권한 검사 비활성).
- 목록 API(`service.py:195-204`)에 `dataset_used_pods` 검사가 있으나 바로 아래 `except`가 삼켜서 **동작하지 않는다.**

실제 결과: NFS 마운트는 남고 파일만 사라져 읽기가 ENOENT로 실패 → §7.1 결함과 겹쳐 **성공으로 보고**된다.

**정책을 바꾸지 않고 파이프라인 쪽에서 줄이는 방법 3가지** (모두 설계에 반영됨):

1. **원본을 읽는 노드를 전처리 하나로 제한** → 노출 창이 첫 노드 실행 시간으로 줄어든다.
2. **런 시작 시 소스 스냅샷**(`source_manifest.json`: 파일 수·총 용량·상위 경로) 기록 후 노드 시작 시 대조 → 원본이 사라지면 **명확한 에러로 죽는다.**
3. **잡을 `preprocessing_job`으로 등록** → 플랫폼의 "사용 중" 추적에 자동 편입. 나중에 플랫폼이 검사를 고칠 때 함께 보호된다.

### 7.3 플랫폼 팀에 넘길 사실 (판단은 팀에서)

- `fb_dataset/route.py:295` — 삭제 라우트의 권한 데코레이터 주석 처리
- `fb_dataset/service.py remove_dataset` — 사용 중 검사 없이 `shutil.rmtree`
- `prepro_job/_command.tpl` — 서브셸 종료코드가 `sleep 10`에 덮임 (**명백한 버그, 우리가 고쳐도 무방**)

---

## 8. Phase 계획

| Phase | 내용 | 완료 기준 |
|---|---|---|
| **0** | §7.1 종료코드 수정 · 축 프리셋 분리(D4) · 마운트 한 줄 추가(§4.3) · lean base 확장 · 계보 2건(§5.1) | 실패하는 스크립트가 `failed`로 뜬다 |
| **1** | `dp_prep.py` **한 노드만 끝까지** — 스크립트 → 등록 → 미리보기 → funnel → 노드 드로어 3열 → 비교 | **전처리 기능을 껐다 켜며 두 결과를 화면에서 비교할 수 있다** |
| **2** | `dp_filter.py` · `dp_assemble.py` (모델 불요) | 모델 없이 파이프라인 절반 완주 |
| **3** | VLM 서빙 확장(D3) → 배포 화면에서 Qwen3-VL 기동 | 이미지 포함 추론이 200으로 돌아온다 |
| **4** | `dp_generate.py` · `dp_judge.py` | SDS 8씬 대조: **7/8 통과, 탈락 1건 = `image_grounding` 0.30** 재현 |
| **5** | 순차 오케스트레이션 + 레코드 적재 → 검수 → 릴리스 · `_runs/` 정리 정책 | 전 구간 e2e |
| **후속** | SDS 노드 2종(`join` · `calc`) 추가 | SDS 프리셋 완주 |

Phase 1이 계약 검증이고, 그것이 끝나면 2·4는 같은 틀의 반복 작업이 된다.

---

## 9. 리스크

| | 항목 | 대응 |
|---|---|---|
| 🔴 | `sleep 10` 종료코드 — 실패가 성공으로 보고 | Phase 0 선결. 전처리 전역이 함께 고쳐짐 |
| 🔴 | 도메인별 임계값 코드 하드코딩(해양 프레임이 블러 임계 100에 전량 오드롭) | 전 임계를 `params`로. 스크립트라 재빌드 없이 조정 가능 |
| 🔴 | 데이터셋 삭제 노출(§7.2) | 노출 창 축소 + 소스 스냅샷 대조 + 사용 중 추적 편입. 정책은 팀 판단 |
| 🟡 | helm 릴리스 이름 재사용 차단(failed 릴리스가 남으면 같은 이름 재실행 불가) | 릴리스명에 run_id 포함 |
| 🟡 | 스케줄러 차트 기본 요청 8cpu/80G — 쿼터 충돌 이력 | 노드별 resources를 작게 지정 |
| 🟡 | ws 네임스페이스라 `jfb-settings` envFrom 불가 | 필요한 값은 `--set env.KEY`로 개별 주입 |
| 🟡 | `unique` 축이 discriminative하지 않음 | 원형 이식 후 별도 튜닝 |
| 🟡 | CLIP 세만틱 dedup 11% 오탐 · 3° 회전 미검출 | pHash + 텍스트 Jaccard 우선, CLIP 후순위 |
| ⚪ | `_runs/` 누적으로 워크스페이스 쿼터 잠식 | Phase 5 정리 정책 |

---

## 10. 검증 계획

- **노드별 단위 테스트** — 프로토타입 144건을 스크립트 코드로 이관(Fake VLM 유지)
- **노드별 클러스터 잡 e2e** — 산출물 스키마 + funnel 카운트 + **실패 시 `failed`로 뜨는지**
- **비교 e2e** — 같은 입력에 기능 토글 두 번 → 두 미리보기가 나란히 보이는지
- **전 노드 순차 e2e** — SDS 8씬으로 **프로토타입 결과(7/8, 탈락 1건 `image_grounding` 0.30)와 동일한지 대조**. 이것이 이식 성공의 판정 기준
- **FE 브라우저 QA** — 노드 드로어 3열 → 검수 → 릴리스

---

## 11. 이식 제외

- `sds_pipeline/bootstrap.py` — 100개 씬 디렉터리를 mp4+CSV로 되말아 가짜 raw를 만드는 **개발 도구**. 실운영은 raw가 직접 들어온다. 샘플 데이터 생성 유틸로만 남긴다.
- `backend/` `frontend/` — 전부 stub(§2.1).
- `nemo_demos/` · `scripts/smoke_*` — 탐색용.
