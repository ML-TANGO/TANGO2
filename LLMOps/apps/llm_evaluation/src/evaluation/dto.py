"""llm_evaluation request DTO (P1b — benchmark)."""
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from evaluation.constants import BENCHMARK_METRICS, MAX_BENCHMARK_DATASETS


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


class EvalStatusBody(BaseModel):
    status: str = Field(..., pattern="^(failed|cancelled)$")
