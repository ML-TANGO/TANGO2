"""llm_evaluation request DTO (P1b — benchmark, P2 — judge)."""
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from evaluation.constants import (
    BENCHMARK_METRICS,
    MAX_BENCHMARK_DATASETS,
    JUDGE_CRITERIA,
    JUDGE_PROVIDERS,
)


class BenchmarkRunBody(BaseModel):
    # model_id 가 'model_' 보호 네임스페이스 경고 안 나게(pydantic v2).
    model_config = {"protected_namespaces": ()}

    model_id: int = Field(..., ge=1, description="평가 대상(학습 완료) 모델 id")
    dataset_ids: List[int] = Field(
        ..., min_length=1, max_length=MAX_BENCHMARK_DATASETS,
        description="벤치마크 데이터셋 id(다중, 최대 %d)" % MAX_BENCHMARK_DATASETS)
    metric_set: Optional[List[str]] = Field(
        default=None, description="17 메트릭 중 부분집합(생략 시 전체)")

    @field_validator("metric_set")
    @classmethod
    def _validate_metrics(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        # unknown 메트릭이 조용히 전체 17개로 확장되지 않도록 입력단에서 거부(422).
        if v is None:
            return v
        unknown = [m for m in v if m not in BENCHMARK_METRICS]
        if unknown:
            raise ValueError(f"unknown metric(s): {unknown}")
        return v


class JudgeRunBody(BaseModel):
    """LLM-as-a-Judge 런 (P2). api_key/base_url = 사용자 입력·transient(영속/로그 금지).
    검증 실패 메시지에 키 값이 절대 echo 되지 않도록 api_key/base_url 엔 값-노출 validator 미부여."""
    model_config = {"protected_namespaces": ()}

    model_id: int = Field(..., ge=1, description="평가 대상(학습 완료) 모델 id")
    dataset_ids: List[int] = Field(
        ..., min_length=1, max_length=MAX_BENCHMARK_DATASETS,
        description="대상 데이터셋 id(다중, 최대 %d)" % MAX_BENCHMARK_DATASETS)
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
    """P3 전문가 평가 세션 시작 — 대상 모델 + 데이터셋(다중)."""
    model_config = {"protected_namespaces": ()}

    model_id: int = Field(..., ge=1, description="평가 대상(학습 완료) 모델 id")
    dataset_ids: List[int] = Field(
        ..., min_length=1, max_length=MAX_BENCHMARK_DATASETS,
        description="대상 데이터셋 id(다중, 최대 %d)" % MAX_BENCHMARK_DATASETS)
    inference_playground_id: Optional[int] = Field(
        default=None, ge=1,
        description="대상 모델의 배포(running) playground id — 주면 실 출력 추론, "
                    "없으면 mock output(A4)")


class ExpertRatingBody(BaseModel):
    """전문가 채점 1건(O/X + 코멘트)."""
    sample_idx: int = Field(..., ge=0, description="채점 대상 샘플 인덱스")
    verdict: str = Field(..., pattern="^(O|X)$", description="합격(O)/불합격(X)")
    comment: Optional[str] = Field(default=None, max_length=2000)


class EvalStatusBody(BaseModel):
    status: str = Field(..., pattern="^(failed|cancelled)$")
