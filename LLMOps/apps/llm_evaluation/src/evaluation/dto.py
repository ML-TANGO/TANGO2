"""llm_evaluation request DTO (벤치마크 런 — reference/judge, 전문가 평가, 추론 러너)."""
from typing import List, Optional, Union

from pydantic import BaseModel, Field, field_validator

from evaluation.constants import (
    BENCHMARK_IDS,
    EVAL_PROJECT_DESCRIPTION_MAX,
    EVAL_TYPES,
    EXPERT_SAMPLE_SET_COUNT,
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
    MAX_EXPERT_SAMPLES,
)


class EvalProjectCreateBody(BaseModel):
    """평가 프로젝트 생성 — **유형·이름만** 고정한다(2026-08-24). 모델·데이터셋은 런이
    고르므로(RunModelSelection) 여기서 받지 않는다. 그 결과 워크스페이스를 모델에서
    파생할 수 없게 되어 바디가 직접 받는다(프로젝트의 경계 = 이후 런이 고를 수 있는
    모델·데이터셋의 범위). creator 는 라우트가 jf-User 헤더로 받아 주입한다."""

    name: str = Field(..., min_length=1, max_length=255, description="프로젝트 이름(사용자 입력)")
    workspace_id: int = Field(..., ge=1, description="프로젝트가 속할 워크스페이스 id")
    eval_type: str = Field(
        ..., description="평가 유형: reference(정답 대조)|judge(LLM 심사)|expert(전문가)")
    # 선택 입력 — 목록 카드 본문에 실린다(모델·배포 카드와 같은 자리). max_length 는
    # eval_project.description 의 VARCHAR(5000) 과 **같은 값**이어야 한다: 크게 두면
    # 초과분이 422 가 아니라 DB 에서 조용히 잘려 사용자가 쓴 글이 사라진다.
    description: Optional[str] = Field(
        default=None, max_length=EVAL_PROJECT_DESCRIPTION_MAX,
        description="프로젝트 설명(선택 — 목록 카드 본문)")

    @field_validator("eval_type")
    @classmethod
    def _validate_eval_type(cls, v: str) -> str:
        # 옛 값 tombstone(2026-08-27) — 'benchmark' 는 채점 주체 기준으로 reference/judge
        # 로 쪼개졌다. 일반 unknown 메시지로 떨어뜨리면 옛 화면이 무엇을 골라야 하는지
        # 알 수 없으므로 사유와 대안을 함께 준다(commit_id tombstone 과 같은 규약).
        if v == "benchmark":
            raise ValueError(
                "eval_type 'benchmark' 는 'reference'(정답 대조 — arc·mmlu…)와 "
                "'judge'(LLM 심사 — logickor)로 나뉘었습니다 — 둘 중 하나를 지정하세요")
        if v not in EVAL_TYPES:
            raise ValueError(f"unknown eval_type: {v}")
        return v


class EvalProjectUpdateBody(BaseModel):
    """평가 프로젝트 수정 — **설명만** 고친다.

    이름·유형·워크스페이스는 넣지 않았다: 그 셋은 프로젝트의 정체성이고 이미 쌓인 런들이
    그 위에 서 있다(유형은 run-start 게이트가 대조하고, 워크스페이스는 모델·배포 경계
    검증의 기준이다). 설명은 그 무엇도 바꾸지 않는 자유 문구라 사후 편집이 안전하다.

    빈 문자열은 '설명 지우기'다 — service 가 NULL 로 정규화한다. 그래서 min_length 를
    두지 않는다(0 자를 422 로 막으면 한번 쓴 설명을 지울 방법이 없어진다)."""

    description: Optional[str] = Field(
        default=None, max_length=EVAL_PROJECT_DESCRIPTION_MAX,
        description="프로젝트 설명(빈 문자열/null 이면 설명 삭제)")


class RunModelSelection(BaseModel):
    """런 시작 3종(벤치마크 — reference/judge, 전문가, 추론 러너)이 공통으로 싣는
    "무엇을 평가하는가".

    2026-08-24 이전에는 프로젝트가 model/dataset 을 잠그고 런이 상속했는데, 그 잠금이
    한 프로젝트 안에서 모델을 바꿔 가며 비교하는 실제 사용을 막았다 → 선택을 런으로
    내렸다. eval_result 는 이미 런 단위로 source_model_id/dataset_id 를 갖고 있어
    신규 컬럼 없이 성립한다. 워크스페이스 경계 검증(모델·데이터셋이 프로젝트의
    워크스페이스에 속하는가)은 프로젝트 생성 시점에서 **런 시작 시점으로 옮겨졌다**
    (service 가 거절한다).
    """
    # model_id 가 'model_' 보호 네임스페이스 경고 안 나게(pydantic v2).
    model_config = {"protected_namespaces": ()}

    model_id: int = Field(..., ge=1, description="이 런이 평가할 모델 id")
    # 단일 강제(2026-07-19): 전 평가유형 데이터셋 1개만 허용. 다중은 비활성(코드/상수 보존).
    # 근거: 정식 evaluate-selfmetric 컨테이너가 단일 데이터셋(JF_DATASET_NAME)만 채점 →
    # 다중 선택은 실 채점과 불일치. benchmark 정식 plugin 이 다중 계약을 확정하면
    # max_length=MAX_BENCHMARK_DATASETS 로 복원(다운스트림 다중 처리는 그대로 보존됨).
    dataset_ids: List[int] = Field(
        ..., min_length=1, max_length=1,
        description="이 런이 평가할 데이터셋 id — 단일(다중 상한 %d 은 비활성)"
                    % MAX_BENCHMARK_DATASETS)


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


class BenchmarkSelection(BaseModel):
    """채점할 벤치마크 1개. 메트릭은 **더 이상 요청이 고르지 않는다**.

    채점 컨테이너는 한 벤치마크의 지표를 언제나 한꺼번에 계산한다(evaluate_intent
    scoring.aggregate "네 지표를 한 번에 계산한다", LogicKor 심판 점수도 전체/1턴/2턴이
    항상 함께 나온다). 그래서 메트릭 선택은 채점 방식을 바꾸는 노브가 아니라
    `averages[benchmark]` 에 실릴 **대표 스칼라를 어느 축으로 잡느냐**일 뿐이었다.
    고르게 두면 "F1 을 골랐는데 accuracy 로 채점된 것 같다" 류의 오해만 만든다 →
    서버가 BENCHMARK_RECOMMENDED_METRIC 을 고정 적용한다.

    metric 필드는 **하위호환용으로 받기만 하고 버린다**(아래 BenchmarkRunBody 주석 참조).
    """

    # 옛 요청이 실어 보내는 metric 을 422 로 튕기지 않도록 extra 도 허용한다.
    model_config = {"extra": "allow"}

    benchmark: str = Field(..., description="벤치마크 id(BENCHMARK_IDS)")
    metric: Optional[str] = Field(
        default=None,
        description="(폐기) 받기만 하고 무시한다 — 대표 메트릭은 서버가 권장값으로 고정한다")

    @field_validator("benchmark")
    @classmethod
    def _validate_benchmark(cls, v: str) -> str:
        if v not in BENCHMARK_IDS:
            raise ValueError(f"unknown benchmark: {v}")
        return v


class BenchmarkRunBody(RunModelSelection):
    """벤치마크 런 — model/dataset 는 이 런이 고른다(RunModelSelection). 유형별 설정 =
    benchmarks(채점할 벤치마크 목록). 생략 시 BE 가 기본 집합을 채점하고, 대표 메트릭은
    어느 경우에도 서버가 BENCHMARK_RECOMMENDED_METRIC 으로 고정한다.

    ⚠️ 이 바디는 **reference 와 judge 두 프로젝트 유형이 공유한다**(2026-08-27). 런치
    경로가 같고 다른 것은 채점 주체뿐이라 엔드포인트를 나누지 않았다 — 대신 service 가
    고른 벤치마크가 프로젝트 유형과 같은 축인지 대조해 거절한다(BENCHMARK_EVAL_TYPE).
    여기서 막지 않는 이유는 프로젝트 유형이 바디에 없고 DB 조회로만 알 수 있어서다."""

    project_id: int = Field(..., ge=1, description="평가 프로젝트 id(유형 게이트·run 묶음)")
    # 두 shape 를 다 받는다: ["logickor"] 와 [{"benchmark": "logickor"}].
    # 이유는 하위호환이 아니라 **배포 순서 분리**다 — 화면(FE)과 서버가 서로 다른 시점에
    # 나가도 어느 쪽이 먼저든 런이 깨지지 않아야 한다. 옛 요청의 metric 키는 조용히 버린다:
    # 버려도 채점 결과가 달라지지 않고(컨테이너는 전 지표를 계산한다) 대표 축만 권장값으로
    # 정해지므로, 422 로 거절해 런을 못 돌게 만드는 편이 오히려 손해다.
    benchmarks: Optional[List[Union[str, BenchmarkSelection]]] = Field(
        default=None, max_length=MAX_BENCHMARK_ITEMS,
        description="채점할 벤치마크 목록(생략 시 기본 집합). 메트릭은 서버 고정.")
    # 체크포인트 경로 폐기(2026-08-27) — 벤치마크 출력은 **실행 중 배포에서만** 온다.
    # 필드를 조용히 지우면 옛 화면이 보낸 commit_id 가 extra=ignore 로 버려져, 사용자가
    # 고른 체크포인트가 아니라 배포로 낸 점수를 "그 커밋의 점수"로 읽게 된다 — 아래 배타
    # 규칙이 막고 있던 바로 그 거짓이다. 그래서 이름만 남겨 사유와 함께 거절한다(422).
    # ⚠️ 컨테이너 계약은 그대로다 — 매니페스트/이미지는 여전히 checkpoint_name 을 받는다.
    #    우리가 보내지 않을 뿐이라 되돌리기는 이 필드와 service 분기 복원으로 끝난다.
    commit_id: Optional[int] = Field(
        default=None,
        description="(폐기) 지정 불가 — 출력은 실행 중 배포에서 가져온다")
    # 빌린 배포에 생성 위임(A) — 컨테이너가 대상 모델을 자기 GPU 에 올리는 대신 이미 떠
    # 있는 running 배포에 생성을 요청한다. 서버는 배포를 검증하고 OpenAI 호환 base URL 을
    # 조립해 params.generate_base_url 로 넘긴다(URL 직접 수취 금지 — SSRF).
    #   ⚠️ 프롬프트 조립은 컨테이너 소유다(LogicKor 2턴 의존·MixATIS UGEN 형식) → 생성은
    #      BE 가 아니라 컨테이너 안에서 일어난다.
    #   ⚠️ 배포가 **이 런의 모델을 서빙**해야 한다(service 가 검증·거절). 아니면 다른
    #      모델의 점수가 이 런의 eval_result 로 기록된다.
    #   ⚠️ **사실상 필수**다(유일한 생성 경로). 그래도 타입을 Optional 로 두는 이유는
    #      누락을 pydantic 의 'Field required' 422 가 아니라 service 가 사유와 함께
    #      거절하게 하기 위해서다 — 이 런의 다른 경계(모델 불일치·심판 배타)도 전부
    #      service 가 잡고, 화면은 envelope 의 message 를 그대로 세운다.
    inference_playground_id: Optional[int] = Field(
        default=None, ge=1,
        description="생성을 위임할 running 배포 id(필수 — 컨테이너가 그 배포로 생성)")
    # 원격 심판(D) — LogicKor 심판을 컨테이너가 vLLM 으로 올리는 대신 이미 떠 있는 배포에
    # 위임한다. 서버가 배포를 검증하고 OpenAI 호환 base URL 을 조립해 넘긴다(URL 직접
    # 수취 금지 — SSRF).
    judge_playground_id: Optional[int] = Field(
        default=None, ge=1,
        description="심판으로 쓸 running 배포 id(LogicKor 전용 — 주면 원격 채점)")
    # 포맷 학습(train+evaluate) — 채점기가 체크포인트를 로컬에 올려 출력 규약을 LoRA 로
    # 짧게 학습한 뒤 평가한다. UGEN 처럼 고정 형식을 생성해야 채점되는 벤치마크(MixATIS)는
    # 형식을 배우지 않은 가중치로 재면 내용을 알아도 0 점이 나오기 때문이다.
    #   ⚠️ **배포 위임과 배타**다 — 학습 LoRA 를 원격 배포에 얹을 통로가 없어 컨테이너도
    #      generate_base_url 이 있으면 학습을 건너뛴다. 켜면 service 가 generate_base_url
    #      대신 checkpoint_name 을 싣는다(그 이름은 고른 배포가 서빙 중인 커밋에서 푼다 —
    #      commit_id 는 요청 필드로 폐기됐다, 위 _reject_commit_id 참고).
    #   ⚠️ 그래서 이 런은 GPU 를 실제로 쓴다(위임 런의 gpu_count=0 최적화가 적용되지 않는다).
    #   지원하지 않는 채점기에 켜면 service 가 사유와 함께 거절한다(조용히 무시하면
    #   "학습하고 쟀다"고 믿는 점수가 남는다).
    format_train: Optional[bool] = Field(
        default=None,
        description="평가 전 형식(출력 규약) 학습 수행 — MixATIS 전용, 배포 위임과 배타")
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

    @field_validator("commit_id")
    @classmethod
    def _reject_commit_id(cls, v):
        # 조용히 무시하면 "고른 체크포인트로 채점됐다"는 오해가 남는다 — 명시적으로 거절.
        if v is not None:
            raise ValueError(
                "commit_id 는 더 이상 지원하지 않습니다 — 벤치마크 출력은 실행 중인 "
                "배포에서 가져옵니다(inference_playground_id)")
        return v

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
        # 같은 벤치마크 중복 지정 거부(런당 벤치마크 1행 — 결과 averages 키 충돌 방지).
        # str/객체 두 shape 를 모두 받으므로 여기서 id 를 뽑아 비교한다.
        if v is None:
            return v
        seen = set()
        for item in v:
            bid = item if isinstance(item, str) else item.benchmark
            if bid not in BENCHMARK_IDS:
                raise ValueError(f"unknown benchmark: {bid}")
            if bid in seen:
                raise ValueError(f"duplicate benchmark: {bid}")
            seen.add(bid)
        return v


class ExpertStartBody(RunModelSelection):
    """P3 전문가 평가 세션 시작 — model/dataset 는 이 세션이 고른다(RunModelSelection)."""

    project_id: int = Field(..., ge=1, description="평가 프로젝트 id(유형 게이트·run 묶음)")
    # 출력 획득원 — **둘 중 하나는 필수**다(2026-08-27, mock 폴백 제거). 누락 거절은
    # service 가 사유와 함께 한다(BenchmarkRunBody.inference_playground_id 와 같은 이유).
    # ⚠️ 샘플 단위 mock 폴백(이미지 전용 VLM·추론 실패분)은 그대로다 — 없어진 것은
    #    "출력원 없이 세션을 연다"는 진입 경로뿐이다.
    inference_playground_id: Optional[int] = Field(
        default=None, ge=1,
        description="대상 모델의 배포(running) playground id — 이 배포로 실 출력 추론")
    # P2-b2 — 러너 inference 런 job_id. 주면 그 런이 생성한 _samples 를 채점 대상으로 사용
    # (재추론 회피, 이미지/CSV 필드 포함). 우선순위: inference_job_id > inference_playground_id.
    inference_job_id: Optional[str] = Field(
        default=None, max_length=128, pattern=r"^[A-Za-z0-9_-]+$",
        description="러너 generate 런 job_id(주면 생성 샘플을 채점, 없으면 배포 추론)")
    # 채점할 샘플 수 상한. 비우면 종전대로 데이터셋 전량(MAX_EXPERT_SAMPLES 천장까지).
    # **앞에서부터** 자른다 — 무작위로 뽑으면 런마다 다른 문항이 걸려 런 간 비교가 깨진다
    # (프로젝트가 여러 런을 나란히 놓고 보는 구조다). 표본 편향이 문제가 되면 씨앗을
    # 런에 영속하는 고정 무작위가 다음 단계다.
    sample_limit: Optional[int] = Field(
        default=None, ge=1, le=MAX_EXPERT_SAMPLES,
        description="채점 샘플 수(앞에서부터). 비우면 데이터셋 전량")
    # 평가 세트(1..EXPERT_SAMPLE_SET_COUNT) — 주면 sample_limit 대신 이게 구간을 정한다
    # (offset=(N-1)*SIZE, limit=SIZE). 평가자가 여러 명일 때 카드마다 다른 구간을 맡기 위한 것이라
    # 프로젝트 안에서 같은 데이터셋의 같은 세트를 두 카드가 쓰지 못한다(서비스에서 거절).
    sample_set: Optional[int] = Field(
        default=None, ge=1, le=EXPERT_SAMPLE_SET_COUNT,
        description=f"평가 세트 번호(1~{EXPERT_SAMPLE_SET_COUNT}). 주면 그 100개 구간만 채점")
    # 세션 생성 시 사용자 입력(표시 전용·세션 동결). eval_result 에 name 컬럼이 없어 제목은
    # metrics._run_name 으로 영속한다(llm_db 마이그레이션 러너 없음 → DDL 회피).
    run_name: Optional[str] = Field(
        default=None, max_length=100,
        description="채점 세션 제목(표시 전용). 없으면 목록에서 데이터셋명으로 표시")
    expert_prompt: Optional[str] = Field(
        default=None, max_length=2000,
        description="평가 지침(사람이 볼 채점 기준). 없으면 시나리오 기본 지침(SDS/일반)")


class ExpertRatingBody(BaseModel):
    """전문가 채점 1건(1~5 별점 + 선택 확장 JSON + 코멘트, D2). verdict 는 BE 가 score 에서 파생."""
    sample_idx: int = Field(..., ge=0, description="채점 대상 샘플 인덱스")
    score: int = Field(..., ge=EXPERT_SCORE_MIN, le=EXPERT_SCORE_MAX,
                        description="전문가 별점(%d~%d)" % (EXPERT_SCORE_MIN, EXPERT_SCORE_MAX))
    score_json: Optional[dict] = Field(
        default=None, description="확장 피드백(다기준/구조화·플라이휠 선호, 무스키마)")
    comment: Optional[str] = Field(default=None, max_length=2000)


class EvalInferenceRunBody(RunModelSelection):
    """평가 추론 러너(generate phase) 런 — model/dataset 는 이 런이 고른다(RunModelSelection).
    하이브리드 인스턴스: inference_playground_id(running 배포 재사용) 또는 instance_id(전용 할당·완료 후 회수).
    system_prompt = 이 런이 소유하는 생성 시스템 프롬프트(헤더 고정 표시·채점 컨텍스트).
    ⚠️ P1 WIP — instance_id ge=1 등 review 지적은 P2 선결."""

    project_id: int = Field(..., ge=1, description="평가 프로젝트 id(run 묶음 — 유형 게이트는 생략)")
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
