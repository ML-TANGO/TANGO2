"""llm_evaluation request DTO (P1b — benchmark, P2 — judge)."""
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from evaluation.constants import (
    BENCHMARK_IDS,
    EVAL_TYPES,
    EXPERT_SCORE_MAX,
    EXPERT_SCORE_MIN,
    LOGICKOR_JUDGE_MAX_OUTPUT_MAX,
    LOGICKOR_JUDGE_MAX_OUTPUT_MIN,
    LOGICKOR_JUDGE_MODEL_IDS,
    LOGICKOR_MODEL_LEN_MAX,
    LOGICKOR_MODEL_LEN_MIN,
    LOGICKOR_STRATEGIES,
    MAX_BENCHMARK_DATASETS,
    MAX_BENCHMARK_ITEMS,
    METRIC_IDS,
    JUDGE_CRITERIA,
    JUDGE_PROVIDERS,
)


class EvalProjectCreateBody(BaseModel):
    """평가 프로젝트 생성 — 모델·데이터셋·유형·이름 잠금(P3, 이후 불변). creator 는
    라우트가 jf-User 헤더로 받아 주입하므로 바디에서 수취하지 않는다."""
    # model_id 가 'model_' 보호 네임스페이스 경고 안 나게(pydantic v2).
    model_config = {"protected_namespaces": ()}

    name: str = Field(..., min_length=1, max_length=255, description="프로젝트 이름(사용자 입력)")
    model_id: int = Field(..., ge=1, description="평가 대상(학습 완료) 모델 id — 잠금")
    # 단일 강제(2026-07-19): 전 평가유형 데이터셋 1개만 허용. 다중은 비활성(코드/상수 보존).
    # 근거: 정식 evaluate-selfmetric 컨테이너가 단일 데이터셋(JF_DATASET_NAME)만 채점 →
    # 프로젝트 다중 선택은 실 채점과 불일치. benchmark 정식 plugin 이 다중 계약을 확정하면
    # max_length=MAX_BENCHMARK_DATASETS 로 복원(다운스트림 다중 처리는 그대로 보존됨).
    dataset_ids: List[int] = Field(
        ..., min_length=1, max_length=1,
        description="대상 데이터셋 id — 단일 잠금(다중 상한 %d 은 비활성)" % MAX_BENCHMARK_DATASETS)
    eval_type: str = Field(..., description="평가 유형: benchmark|judge|expert")

    @field_validator("eval_type")
    @classmethod
    def _validate_eval_type(cls, v: str) -> str:
        if v not in EVAL_TYPES:
            raise ValueError(f"unknown eval_type: {v}")
        return v


class EvalProjectListItem(BaseModel):
    """프로젝트 목록 응답의 additive 계약. 기존 키는 extra 로 그대로 보존하고, 최근 run
    활동 시각(없으면 프로젝트 생성 시각)인 update_datetime 존재만 경계에서 검증한다."""

    model_config = {"extra": "allow", "protected_namespaces": ()}

    update_datetime: Optional[str] = Field(
        ..., description="최근 평가 run 생성 시각, run이 없으면 프로젝트 생성 시각")


class EvalProjectListResult(BaseModel):
    """평가 프로젝트 목록 응답."""

    workspace_id: int
    projects: List[EvalProjectListItem]


class BenchmarkMetricPair(BaseModel):
    """벤치마크 1개 + 그 벤치마크에 쓸 메트릭 1개. 벤치마크(ARC·MMLU…)와 메트릭(Accuracy·F1…)을
    분리 — 기존의 섞인 flat metric_set 을 폐기하고 '벤치마크→메트릭' 매핑으로 대체."""

    benchmark: str = Field(..., description="벤치마크 id(BENCHMARK_IDS)")
    metric: str = Field(..., description="점수 메트릭 id(METRIC_IDS)")

    @field_validator("benchmark")
    @classmethod
    def _validate_benchmark(cls, v: str) -> str:
        if v not in BENCHMARK_IDS:
            raise ValueError(f"unknown benchmark: {v}")
        return v

    @field_validator("metric")
    @classmethod
    def _validate_metric(cls, v: str) -> str:
        if v not in METRIC_IDS:
            raise ValueError(f"unknown metric: {v}")
        return v


class BenchmarkRunBody(BaseModel):
    """benchmark 런 — model/dataset 는 프로젝트에서 상속(project_id). 유형별 설정 =
    benchmarks(벤치마크→메트릭 매핑). 생략 시 BE 가 전체 벤치마크를 권장 메트릭으로 채점."""

    project_id: int = Field(..., ge=1, description="평가 프로젝트 id(model/dataset 상속·불변)")
    benchmarks: Optional[List[BenchmarkMetricPair]] = Field(
        default=None, max_length=MAX_BENCHMARK_ITEMS,
        description="벤치마크→메트릭 매핑(생략 시 전체 벤치마크·권장 메트릭)")
    # 생성·채점 분리(D2-b) — 러너 inference 런 job_id 를 주면 그 런이 생성한 output 을
    # 스코어러에 넘겨 채점(재추론 회피). 생략 시 현행(컨테이너 자체 생성). job_str_id 문자셋.
    inference_job_id: Optional[str] = Field(
        default=None, max_length=128, pattern=r"^[A-Za-z0-9_-]+$",
        description="러너 generate 런 job_id(주면 생성 output 을 채점, 없으면 컨테이너 자체 생성)")
    # 체크포인트 선택(LogicKor 등 실채점 컨테이너) — 주면 스코어러가 그 커밋 가중치로
    # 생성부터 수행한다. 같은 모델의 체크포인트 간 비교가 이 필드의 존재 이유다.
    # 미지정이면 컨테이너 규약대로 동작(LogicKor 는 데이터셋의 미채점 생성물을 채점).
    commit_id: Optional[int] = Field(
        default=None, ge=1, description="생성에 쓸 커밋 체크포인트 id(선택)")
    # ── 실채점 컨테이너 실행 옵션(전부 선택 — 미지정이면 컨테이너 기본값) ──────────
    # 자유형식 dict passthrough 로 두지 않는 이유: 이 값들은 그대로 vLLM 기동 인자와
    # 모델 식별자가 되므로, 어떤 키가 컨테이너에 도달할 수 있는지를 서버가 알고 있어야
    # 한다. 필드로 열거해 Pydantic 이 타입·범위·문자셋까지 강제한다.
    generate_model_len: Optional[int] = Field(
        default=None, ge=LOGICKOR_MODEL_LEN_MIN, le=LOGICKOR_MODEL_LEN_MAX,
        description="생성 컨텍스트 길이(미지정 시 컨테이너 기본 4096)")
    strategy: Optional[str] = Field(
        default=None, description=f"프롬프트 전략 {list(LOGICKOR_STRATEGIES)}")
    judge_model: Optional[str] = Field(
        default=None,
        description=f"심판 모델 id — 화이트리스트 {list(LOGICKOR_JUDGE_MODEL_IDS)}")
    judge_model_len: Optional[int] = Field(
        default=None, ge=LOGICKOR_MODEL_LEN_MIN, le=LOGICKOR_MODEL_LEN_MAX,
        description="심판 컨텍스트 길이(미지정 시 컨테이너 기본 8192)")
    judge_max_output_tokens: Optional[int] = Field(
        default=None, ge=LOGICKOR_JUDGE_MAX_OUTPUT_MIN, le=LOGICKOR_JUDGE_MAX_OUTPUT_MAX,
        description="심판 1회 출력 상한 토큰(미지정 시 컨테이너 기본 1024)")

    @field_validator("judge_model")
    @classmethod
    def _validate_judge_model(cls, v):
        # 자유 입력 금지 — 캐시에 없는 모델은 컨테이너가 GPU 를 잡고서야 죽는다.
        if v is not None and v not in LOGICKOR_JUDGE_MODEL_IDS:
            raise ValueError(f"unknown judge_model: {v}")
        return v

    @field_validator("strategy")
    @classmethod
    def _validate_strategy(cls, v):
        if v is not None and v not in LOGICKOR_STRATEGIES:
            raise ValueError(f"unknown strategy: {v}")
        return v

    @field_validator("benchmarks")
    @classmethod
    def _dedup_benchmarks(cls, v):
        # 같은 벤치마크 중복 지정 거부(런당 벤치마크 1행 — 결과 averages 키/메트릭 매핑 충돌 방지).
        if v is None:
            return v
        seen = set()
        for pair in v:
            if pair.benchmark in seen:
                raise ValueError(f"duplicate benchmark: {pair.benchmark}")
            seen.add(pair.benchmark)
        return v


class JudgeRunBody(BaseModel):
    """LLM-as-a-Judge 런 (P2). model/dataset 는 프로젝트에서 상속(project_id). api_key/
    base_url = 사용자 입력·transient(영속/로그 금지). 검증 실패 메시지에 키 값이 절대
    echo 되지 않도록 api_key/base_url 엔 값-노출 validator 미부여."""

    project_id: int = Field(..., ge=1, description="평가 프로젝트 id(model/dataset 상속·불변)")
    provider: str = Field(..., description="심판 provider: chatgpt|claude|gemini|local")
    judge_model: Optional[str] = Field(
        default=None, max_length=128,
        # gemini 어댑터가 모델명을 URL 경로에 보간 → 경로조작 차단. 실 모델명(gpt-4o,
        # claude-opus-4-8, gemini-2.0-flash, llama3-8b-instruct)은 영숫자/._- 로 충분 →
        # '/'·':' 불허(‘x/../admin’ 류 traversal 거부).
        pattern=r"^[A-Za-z0-9._-]+$",
        description="심판 모델명(생략 시 provider 기본)")
    api_key: Optional[str] = Field(
        default=None, description="상용 provider API 키(사용자 입력·transient — 저장/로그 금지)")
    base_url: Optional[str] = Field(
        default=None, description="Local LLM endpoint URL(사용자 입력·SSRF 가드)")
    criteria: List[str] = Field(
        ..., min_length=1, description="채점 기준(JUDGE_CRITERIA 부분집합)")
    custom_prompt: Optional[str] = Field(
        default=None, max_length=4000, description="심사 프롬프트(선택)")
    inference_playground_id: Optional[int] = Field(
        default=None, ge=1,
        description="대상 모델의 배포(running) playground id — 주면 실 출력 추론, "
                    "없으면 mock output(A4)")
    # P2-b2 — 러너 inference 런 job_id. 주면 그 런이 생성한 _samples.output 을 채점(재추론
    # 회피). 우선순위: inference_job_id(러너) > inference_playground_id(빌린 배포) > mock.
    inference_job_id: Optional[str] = Field(
        default=None, max_length=128, pattern=r"^[A-Za-z0-9_-]+$",
        description="러너 generate 런 job_id(주면 생성 output 을 채점, 없으면 배포 추론/mock)")

    @field_validator("provider")
    @classmethod
    def _validate_provider(cls, v: str) -> str:
        if v not in JUDGE_PROVIDERS:
            raise ValueError(f"unknown provider: {v}")
        return v

    @field_validator("criteria")
    @classmethod
    def _validate_criteria(cls, v: List[str]) -> List[str]:
        unknown = [c for c in v if c not in JUDGE_CRITERIA]
        if unknown:
            raise ValueError(f"unknown criteria: {unknown}")
        return v


class ExpertStartBody(BaseModel):
    """P3 전문가 평가 세션 시작 — model/dataset 는 프로젝트에서 상속(project_id·불변)."""

    project_id: int = Field(..., ge=1, description="평가 프로젝트 id(model/dataset 상속·불변)")
    inference_playground_id: Optional[int] = Field(
        default=None, ge=1,
        description="대상 모델의 배포(running) playground id — 주면 실 출력 추론, "
                    "없으면 mock output(A4)")
    # P2-b2 — 러너 inference 런 job_id. 주면 그 런이 생성한 _samples 를 채점 대상으로 사용
    # (재추론 회피, 이미지/CSV 필드 포함). 우선순위: inference_job_id > inference_playground_id > mock.
    inference_job_id: Optional[str] = Field(
        default=None, max_length=128, pattern=r"^[A-Za-z0-9_-]+$",
        description="러너 generate 런 job_id(주면 생성 샘플을 채점, 없으면 배포 추론/mock)")


class ExpertRatingBody(BaseModel):
    """전문가 채점 1건(1~5 별점 + 선택 확장 JSON + 코멘트, D2). verdict 는 BE 가 score 에서 파생."""
    sample_idx: int = Field(..., ge=0, description="채점 대상 샘플 인덱스")
    score: int = Field(..., ge=EXPERT_SCORE_MIN, le=EXPERT_SCORE_MAX,
                        description="전문가 별점(%d~%d)" % (EXPERT_SCORE_MIN, EXPERT_SCORE_MAX))
    score_json: Optional[dict] = Field(
        default=None, description="확장 피드백(다기준/구조화·플라이휠 선호, 무스키마)")
    comment: Optional[str] = Field(default=None, max_length=2000)


class EvalInferenceRunBody(BaseModel):
    """평가 추론 러너(generate phase) 런 — model/dataset 는 프로젝트 상속(project_id). 하이브리드
    인스턴스: inference_playground_id(running 배포 재사용) 또는 instance_id(전용 할당·완료 후 회수).
    system_prompt = 이 런이 소유하는 생성 시스템 프롬프트(헤더 고정 표시·채점 컨텍스트).
    ⚠️ P1 WIP — instance_id ge=1 등 review 지적은 P2 선결."""
    model_config = {"protected_namespaces": ()}

    project_id: int = Field(..., ge=1, description="평가 프로젝트 id(model/dataset 상속·불변)")
    system_prompt: Optional[str] = Field(
        default=None, max_length=4000, description="생성 시스템 프롬프트(런 소유·표시)")
    inference_playground_id: Optional[int] = Field(
        default=None, ge=1, description="재사용할 running 배포 id(주면 재사용, 없으면 전용 할당)")
    instance_id: Optional[int] = Field(
        default=None, ge=1, description="전용 할당 시 인스턴스 id(할당 경로 필수)")
    instance_count: int = Field(default=1, ge=1, le=8, description="전용 할당 인스턴스 수")
    gpu_count: int = Field(default=1, ge=0, le=8, description="전용 할당 GPU 수")
    commit_id: Optional[int] = Field(
        default=None, ge=1, description="대상 커밋 체크포인트 id(선택)")


class EvalStatusBody(BaseModel):
    status: str = Field(..., pattern="^(failed|cancelled)$")
