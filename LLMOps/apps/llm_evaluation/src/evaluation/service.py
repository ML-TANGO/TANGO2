"""llm_evaluation — 평가 오케스트레이션 service (P1b, 벤치마크).

벤치마크 런을 job_type=evaluate 외부 컨테이너(P1a mock evaluate-benchmark-mock / 정식)에
위임. llm_model.evaluate_model 과 동형 — fb_external_container 런치 + eval_result lazy
영속화(fb_utils.llm_db)를 재사용(코드 중복 0). 대상=학습완료 모델, reserved
_base_model→/model, _dataset→/dataset/<name>. 멀티 데이터셋 이름은 params.datasets 로 전달
(mock 은 이름으로 채점). metrics.json 은 jobs/<job_id>/output/ 에 떨어지고 get_eval_result
가 lazy 로 eval_result 를 마감.
"""
from __future__ import annotations

import asyncio
import base64
import csv
import glob
import io
import ipaddress
import json
import os
import re
import socket
import traceback
import uuid
from typing import List, Optional
from urllib.parse import urlparse

import httpx

from utils import PATH, gpu_pool, settings
from utils.llm_db import db_model, db_playground
from utils.redis import get_redis_client

from external.proxy import ExternalContainerClient, ExternalContainerError
from evaluation.constants import (
    BENCHMARK_EVAL_TYPE,
    BENCHMARK_EVAL_TYPES,
    BENCHMARK_IDS,
    BENCHMARK_RECOMMENDED_METRIC,
    DATASET_FREE_BENCHMARK_IDS,
    DEFAULT_BENCHMARK_IDS,
    JUDGE_BENCHMARK_IDS,
    REFERENCE_BENCHMARK_IDS,
    REAL_BENCHMARK_MANIFEST_KEY,
    FORMAT_TRAIN_MANIFEST_KEYS,
    LOCAL_WEIGHTS_MANIFEST_KEYS,
    LMEVAL_EST_DEFAULT_SECONDS,
    LMEVAL_EST_SECONDS,
    LMEVAL_RUN_TIMEOUT_SECONDS,
    LMEVAL_STARTUP_SECONDS,
    LMEVAL_WORST_SLOWDOWN,
    BENCHMARK_SAMPLE_LIMIT_MAX,
    BENCHMARK_SAMPLE_LIMIT_MIN,
    EVAL_DEPLOY_MAX_POLLS,
    EVAL_INFER_RUN_SECONDS,
    EVAL_PROJECT_DESCRIPTION_MAX,
    EVAL_TYPES,
    MAX_BENCHMARK_DATASETS,
    MAX_BENCHMARK_ITEMS,
    MAX_EVAL_SAMPLES,
    PROJECT_STATUS_COMPLETED,
    PROJECT_STATUS_CREATED,
    PROJECT_STATUS_RUNNING,
    EXPERT_CSV_FILENAME,
    EXPERT_IMAGE_FILENAME,
    EXPERT_OUTPUT_GLOB,
    EXPERT_PROMPT_DEFAULT,
    EXPERT_PROMPT_SDS,
    EXPERT_REFERENCE_FILENAME,
    EXPERT_SCORE_JSON_MAX_LEN,
    EXPERT_SCORE_MAX,
    EXPERT_SCORE_MIN,
    EXPERT_VERDICT_PASS_THRESHOLD,
    LOGICKOR_JUDGE_MAX_OUTPUT_MAX,
    LOGICKOR_JUDGE_MAX_OUTPUT_MIN,
    LOGICKOR_DEFAULT_JUDGE_ID,
    LOGICKOR_JUDGE_HF_ID,
    LOGICKOR_JUDGE_MODELS,
    LOGICKOR_MODEL_LEN_MAX,
    LOGICKOR_MODEL_LEN_MIN,
    LOGICKOR_STRATEGIES,
    MAX_COMPARE_MODELS,
    MAX_COMPARE_RUNS,
    EXPERT_SAMPLE_SET_COUNT,
    EXPERT_SAMPLE_SET_SIZE,
    MAX_EXPERT_SAMPLES,
    SDS_GEN_SYSTEM_PROMPT,
    SDS_SAMPLE_DIR_GLOB,
    MAX_RECONCILE_PER_VIEW,
    MAX_PROGRESS_PER_VIEW,
    EVAL_FINALIZE_BATCH,
    EVAL_FINALIZE_INTERVAL_SECONDS,
    RECONCILE_TIMEOUT_SECONDS,
    STALE_RUNNING_MAX_HOURS,
)

# pod subPath 단일 segment(/dataset/<name>, models/<name>)에 들어가므로 조작문자 거부.
_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


async def run_benchmark(project_id: int, model_id: int, dataset_ids: List[int],
                        benchmarks: Optional[List] = None,
                        inference_playground_id: Optional[int] = None,
                        judge_playground_id: Optional[int] = None,
                        format_train: Optional[bool] = None,
                        run_options: Optional[dict] = None,
                        pinned_checkpoint: Optional[str] = None) -> dict:
    """벤치마크 평가 런 — 이 런이 고른 model/dataset 으로 evaluate 컨테이너 런치.

    pinned_checkpoint 는 **내부 전용**(묶음 실행 run_benchmark_batch)이다 — 묶음이 한 번 푼
    체크포인트를 lm-eval 런마다 그대로 쓴다. 라우트는 받지 않는다(요청이 가중치를 고르면
    "고른 체크포인트"와 "배포가 서빙 중인 가중치"가 어긋날 수 있다 — commit_id 폐기 사유).
    dataset_ids 는 비어도 된다 — 고른 벤치마크가 전부 런 데이터셋을 읽지 않을 때
    (DATASET_FREE_BENCHMARK_IDS) 마운트 없이 시작한다.
    model_id·dataset_ids 는 **요청이 준다**(2026-08-24 — 프로젝트 잠금 해제). 둘 다
    프로젝트의 워크스페이스에 속하는지 여기서 검증한다(생성 시점에서 옮겨온 검증).
    benchmarks = 채점할 벤치마크 id 목록(생략 시 기본 집합). **메트릭은 요청이 고르지
    않는다** — 채점기가 한 벤치마크의 지표를 늘 함께 계산하므로 고를 것은 대표 스칼라
    축뿐이고, 그건 BENCHMARK_RECOMMENDED_METRIC 으로 서버가 고정한다.

    생성(누가 답을 만드는가)은 **하나뿐이다**: inference_playground_id — 실행 중인 배포에
    위임한다(필수). 2026-08-27 이전에는 세 갈래였는데, 평가 유형마다 출력 획득 정책이
    달라 "이 점수를 무엇이 냈나"가 화면마다 다르게 읽혔다 → 배포로 통일했다.

    ⚠️ inference_playground_id 는 params.generate_base_url(배포의 OpenAI shim base)로
    컨테이너에 넘어가고 **생성은 컨테이너 안에서 그 배포를 호출해 일어난다**. 예전에는 이
    서비스가 인라인으로 미리 생성해 params.samples 로 넘겼는데, 어느 채점기도 그 키를
    읽지 않아 생성이 두 번(BE 가 배포로 한 번, 컨테이너가 체크포인트로 또 한 번) 일어나
    GPU 절약이 0 이었다. 게다가 벤치마크 프롬프트 조립은 컨테이너 소유다 — LogicKor 은
    42문항 × 2턴이고 2턴 질문이 1턴 답변에 의존하며 채팅 템플릿·토큰 예산 절삭이 전부
    generate.py 안에 있고, MixATIS 의 UGEN 프롬프트 형식도 컨테이너 것이다. 그 조립을
    BE 의 단일턴 루프(_generate_samples)로 재현할 수 없다 → 위임으로 바꿨다. 인라인
    생성이 사라지면서 240초 예산과 Kong 60초 타임아웃 경쟁도 함께 사라졌다.

    ⚠️ 없어진 두 경로. **commit_id(체크포인트)** 는 컨테이너가 그 가중치를 자기 GPU 에
    올려 생성하는 별도 정책이었고, **inference_job_id(러너 생성물)** 는 params.samples 를
    실어 보내지만 evaluate_* 어느 컨테이너도 그 키를 읽지 않는 죽은 계약이었다(grep 실측)
    — 준 사람은 재사용됐다고 믿는데 컨테이너는 자기 경로로 다시 생성했다. 둘을 남긴 채
    배포를 필수로 만들면 오히려 더 나빠진다: 러너 job_id 를 함께 주면 옛 분기가 먼저 걸려
    generate_base_url 이 실리지 않고, 체크포인트도 없으니 채점기가 생성할 대상을 잃는다.
    ⚠️ 컨테이너 계약은 그대로다 — 매니페스트/이미지는 여전히 checkpoint_name·samples 를
    받는다. 우리가 보내지 않을 뿐이라 되돌리기는 이 함수의 분기 복원으로 끝난다.
    (judge/expert 의 inference_job_id 는 채점이 이 서비스 안에서 일어나 실제로 동작한다.)

    format_train=True 는 **그 하나뿐인 생성 경로를 되돌린다** — 채점기가 체크포인트를 자기
    GPU 에 올려 출력 규약을 LoRA 로 학습한 뒤 그대로 생성·채점한다(train+evaluate 한 잡).
    되돌리는 것이 아니라 되살리는 것인 이유: UGEN 처럼 고정 형식을 생성해야 채점되는
    벤치마크는 형식을 배우지 않은 가중치로 재면 **구조적으로 0 점**이고(MixATIS 실측
    joint_acc 0.0), 그 학습은 로컬 모델에 얹는 LoRA 라 원격 배포에는 붙일 통로가 없다.
    컨테이너도 generate_base_url 이 있으면 학습을 스스로 건너뛴다 → 두 경로는 **배타**다.
    체크포인트 이름은 요청이 아니라 **고른 배포가 서빙 중인 커밋**에서 푼다
    (_resolve_deployment_checkpoint) — commit_id 를 요청 필드로 되살리면 "고른 체크포인트"와
    "실제로 점수를 낸 가중치"가 다시 어긋날 수 있고, 그것이 그 필드를 폐기한 이유다.
    이 경로의 런은 결과 화면에서 `source_mode='checkpoint'` 로 읽힌다(fb_utils
    `_eval_run_source` 가 metrics.checkpoint.name 을 그대로 쓴다 — 추가 배선 없음).

    judge_playground_id 를 주면 LogicKor 심판을 컨테이너 안 vLLM 대신 이미 떠 있는 배포에
    위임한다(params.judge_base_url). run_options 는 실채점 컨테이너 실행 옵션(컨텍스트
    길이·전략·심판 모델). run 생성 시 프로젝트를 'running' 으로 전이.

    ⚠️ 이 함수는 **reference(정답 대조)와 judge(LLM 심사) 두 프로젝트 유형이 공유한다**
    (2026-08-27 유형 3분할). 런치 경로가 같고 다른 것은 "누가 점수를 매기는가"뿐이라
    함수를 나누지 않았다 — 대신 프로젝트 유형만으로는 무엇을 채점하는지가 정해지지
    않으므로, 고른 벤치마크의 축(BENCHMARK_EVAL_TYPE)이 프로젝트 유형과 같은지 아래에서
    대조한다. 대조하지 않으면 정답 대조 프로젝트에 심판 점수가 섞여 들어가는데, 결과
    화면에서는 둘 다 그냥 숫자라 사후에 구분할 방법이 없다."""
    # 출력은 **실행 중인 배포에서** 가져온다 — 벤치마크의 유일한 생성 경로다. 파드를
    # 띄우기 전에(그리고 DB 를 두드리기 전에) 사유와 함께 막는다.
    if not inference_playground_id:
        raise Exception(
            "벤치마크 출력은 실행 중인 배포에서 가져옵니다 — 평가할 모델을 서빙하는 "
            "배포를 먼저 시작한 뒤 지정하세요(inference_playground_id)")
    # 벤치마크 런을 시작할 수 있는 유형은 둘(reference/judge)이다. 어느 쪽인지는 아래에서
    # 벤치마크 목록과 대조해 좁힌다 — 여기서는 expert 프로젝트의 진입만 막는다.
    project = await _load_project_for_run(project_id, BENCHMARK_EVAL_TYPES)
    project_type = str(project.get("eval_type") or "")
    model_id = int(model_id)
    # 빈 목록은 "데이터셋을 쓰지 않는 런" — 허용 여부는 벤치마크를 정규화한 뒤 판정한다.
    dataset_ids = _run_dataset_ids(dataset_ids) if dataset_ids else []
    model_info, workspace_id = await _resolve_run_model(project, model_id)
    model_name = model_info["name"]
    if not _SAFE_SEGMENT_RE.match(model_name):
        raise Exception("model name has unsafe characters for container mount")

    datasets = []
    for did in dataset_ids:
        d = await db_model.get_dataset_model(dataset_id=did)
        if not d:
            raise Exception(f"dataset {did} not found")
        if int(d["workspace_id"]) != workspace_id:
            raise Exception("dataset and model belong to different workspaces")
        ds_name = str(d["name"])
        if not _SAFE_SEGMENT_RE.match(ds_name):
            raise Exception("dataset name has unsafe characters for container mount")
        if ".." in str(d.get("access") or ""):
            raise Exception("dataset access path is unsafe")
        datasets.append(d)

    # 벤치마크 정규화. 생략/빈값 → 기본 집합(mock 채점 벤치마크).
    # 전체(BENCHMARK_IDS)로 폴백하지 않는 이유: 실채점 벤치마크는 각자 전용 컨테이너로
    # 가야 하는데 한 런은 컨테이너 하나이므로 "전체 한 번에"가 성립하지 않는다.
    # unknown id 는 무시(dto 에서 이미 422 검증하지만 방어), 벤치마크 중복은 첫 지정 유지.
    #
    # 메트릭은 요청에서 받지 않는다. 채점기는 한 벤치마크의 지표를 언제나 한꺼번에
    # 계산하므로(evaluate_intent scoring.aggregate, LogicKor 심판 점수 전체/1턴/2턴)
    # 고를 수 있었던 것은 결과 화면의 대표 스칼라 축뿐이었고, 그 선택은 "고른 메트릭으로
    # 채점된다"는 오해만 만들었다 → 권장 축으로 고정한다. 컨테이너에 넘기는 계약
    # (benchmarks/metric_map)과 결과 shape 은 그대로다.
    pairs = []
    seen = set()
    for item in (benchmarks or []):
        # 서비스 직접 호출자(테스트·내부)가 옛 dict shape 를 넘겨도 받는다 — metric 키가
        # 실려 있어도 읽지 않는다.
        b = (item if isinstance(item, str)
             else str((item or {}).get("benchmark", "")))
        b = str(b).strip()
        if b not in BENCHMARK_IDS or b in seen:
            continue
        seen.add(b)
        pairs.append({"benchmark": b, "metric": BENCHMARK_RECOMMENDED_METRIC[b]})
    if not pairs:
        # 기본 집합(DEFAULT_BENCHMARK_IDS)은 전부 reference 축이다. judge 프로젝트가
        # 벤치마크를 생략했을 때 이걸 그대로 채우면 사용자가 고른 적 없는 축을 채점하고
        # 그 점수가 judge 프로젝트의 이력으로 남는다 → 명시를 요구한다.
        if project_type != "reference":
            raise Exception(
                f"{project_type} 프로젝트는 채점할 벤치마크를 명시해야 합니다 — "
                f"기본 집합은 정답 대조(reference) 벤치마크뿐입니다"
                f"(지정 가능: {', '.join(JUDGE_BENCHMARK_IDS)})")
        pairs = [{"benchmark": b, "metric": BENCHMARK_RECOMMENDED_METRIC[b]}
                 for b in DEFAULT_BENCHMARK_IDS]
    # 상한은 **자르지 않고 거절한다**. 순서가 중요하다 — 예전에는 여기서 조용히 잘랐고
    # 그 절단이 아래 유형 게이트보다 **먼저**였다: 상한을 넘겨 잘려나간 벤치마크는
    # (1) 사용자가 명시적으로 골랐는데 아무 신호 없이 사라지고(축이 새는 게 아니라 조용한
    # 누락이다), (2) 잘린 것이 프로젝트 유형과 다른 축이었다면 거절됐어야 할 요청이 통과한다.
    # 오늘은 벤치마크가 11종뿐(BENCHMARK_IDS)이라 20 에 닿지 않지만, 벤치마크를 추가하는
    # 쪽에서 이 순서를 다시 볼 일이 없도록 절단 자체를 없앤다.
    # 이 가드에 실제로 닿는 것은 **서비스 직접 호출자(테스트·내부)** 뿐이다 — 공개 라우트는
    # dto(BenchmarkRunBody.benchmarks 의 max_length=MAX_BENCHMARK_ITEMS)가 이미 422 로 막는다.
    if len(pairs) > MAX_BENCHMARK_ITEMS:
        raise Exception(
            f"한 런에 채점할 수 있는 벤치마크는 최대 {MAX_BENCHMARK_ITEMS}개입니다"
            f"(요청 {len(pairs)}개) — 나눠서 실행하세요")

    # 유형 게이트(벤치마크 축) — 채점기 혼재 거부(아래)와 같은 취지지만 막는 것이 다르다.
    # 저쪽은 "한 런에 두 컨테이너를 못 쓴다"는 실행 제약이고, 이쪽은 "이 프로젝트가 무엇을
    # 재는 곳인가"라는 의미의 경계다 — reference 와 judge 는 같은 컨테이너로 갈 수도 있지만
    # (둘 다 real 채점기) 점수의 의미가 다르므로 한 프로젝트에 섞이면 안 된다.
    wrong = [p["benchmark"] for p in pairs
             if BENCHMARK_EVAL_TYPE.get(p["benchmark"]) != project_type]
    if wrong:
        allowed = (JUDGE_BENCHMARK_IDS if project_type == "judge"
                   else REFERENCE_BENCHMARK_IDS)
        detail = ", ".join(
            f"{b}={BENCHMARK_EVAL_TYPE.get(b) or 'unknown'}" for b in wrong)
        raise Exception(
            f"{project_type} 프로젝트에는 {project_type} 유형 벤치마크만 채점할 수 "
            f"있습니다 — {detail} (지정 가능: {', '.join(allowed)})")

    # 데이터셋 없이 가도 되는 건 문항이 이미지에 있는 벤치마크뿐이다. 데이터셋을 읽는 채점기를
    # 데이터셋 없이 띄우면 GPU 를 잡은 뒤에야 죽는다(custom) — 런치 전에 사유와 함께 막는다.
    if not datasets:
        needs = [p["benchmark"] for p in pairs
                 if p["benchmark"] not in DATASET_FREE_BENCHMARK_IDS]
        if needs:
            raise Exception(
                f"{', '.join(needs)} 는 평가 데이터셋이 필요합니다 — 데이터셋을 고르세요")

    # 채점 컨테이너 라우팅 — 벤치마크마다 필요한 런타임이 달라(LogicKor 는 심판 LLM +
    # transformers 5.5.4 핀) 한 이미지가 전부 채점할 수 없다. 한 런 = 컨테이너 하나이므로
    # 서로 다른 채점기의 벤치마크를 섞으면 조용히 일부만 채점된다(mock 은 모르는 id 를
    # 필터링해 버리고 9개 해시 점수를 낸다) → 명시적으로 거부하고 나눠 돌리게 한다.
    manifest_keys = {
        REAL_BENCHMARK_MANIFEST_KEY.get(p["benchmark"], "BENCHMARK") for p in pairs}
    if len(manifest_keys) > 1:
        raise Exception(
            "benchmarks with different scorers cannot run together: "
            f"{sorted(p['benchmark'] for p in pairs)} — run them as separate runs")
    manifest_key = manifest_keys.pop()
    manifest_name = getattr(settings, f"{manifest_key}_MANIFEST_NAME")
    manifest_version = getattr(settings, f"{manifest_key}_MANIFEST_VERSION")
    benchmark_set = [p["benchmark"] for p in pairs]
    metric_map = {p["benchmark"]: p["metric"] for p in pairs}
    # ⚠️ 체크포인트가 **필수**인 채점기(MIXATIS)의 가드는 위임 경로에서는 사라졌다 — 생성이
    # 배포 위임이면 컨테이너는 마운트할 체크포인트가 필요 없다(evaluate_intent 0.2.4 /
    # evaluate-logickor-judge 0.2.5 부터 `generate_base_url` 이 있으면 _resolve_checkpoint
    # 를 우회한다). ⚠️ 그 이전 이미지 태그로 되돌리면 이 런들이 파드를 띄운 뒤 죽는다 →
    # settings 의 MANIFEST_VERSION 을 되돌릴 때는 체크포인트 경로도 함께 복원해야 한다.
    # 포맷 학습(아래)을 켜면 그 가드가 되살아난다 — 학습할 가중치가 없으면 성립하지 않는다.

    # ── 포맷 학습 게이트 — 배포 위임과 배타 ─────────────────────────────────────
    # 지원 채점기 밖에서 켜면 **조용히 무시하지 않고 거절한다**. 무시하면 사용자는 "형식을
    # 학습하고 잰 점수"라고 믿는데 실제로는 zero-shot 점수가 이력에 남고, 그 차이는 결과
    # 화면 어디에도 드러나지 않는다(심판 배타 검증·채점기 혼재 거부와 같은 취지).
    format_train_on = bool(format_train)
    if format_train_on and manifest_key not in FORMAT_TRAIN_MANIFEST_KEYS:
        raise Exception(
            "포맷 학습은 출력 형식을 학습해야 채점되는 벤치마크에서만 쓸 수 있습니다 — "
            f"{', '.join(benchmark_set)} 에는 학습 단계가 없습니다")

    # eval_result.metric_set(VARCHAR 255) = "benchmark:metric" CSV — 런 설정 요약 + 재개 소스
    # (기존 flat metric CSV 대체). 전체 결과(점수)는 metrics JSON 에 별도 영속.
    # 넘치면 **토큰 단위로** 자른다 — 글자 수로 자르면 "truthfulqa_ge" 처럼 없는 벤치마크 id 가
    # 남는다. 한 런이 담은 전체 목록은 묶음 기록(eval_run_batch_member.benchmarks)과 결과
    # metrics 에 있다(런 하나가 여러 벤치마크를 담는 묶음 실행, 설계 §14).
    metric_csv = ""
    for p in pairs:
        token = f"{p['benchmark']}:{p['metric']}"
        joined = f"{metric_csv},{token}" if metric_csv else token
        if len(joined) > 255:
            break
        metric_csv = joined
    ds_names = [str(d["name"]) for d in datasets]
    # eval_result.dataset_name 은 VARCHAR(255). 멀티 데이터셋 CSV 가 넘으면 요약형으로
    # 저장(런 자체는 진행 — 전체 목록은 반환 dict 의 datasets 로 보존). dataset_ids 상한
    # (MAX_BENCHMARK_DATASETS)은 dto 에서 강제.
    # 데이터셋 없는 런은 NULL — 빈 문자열을 남기면 목록이 '데이터셋 ""' 을 이름처럼 다룬다.
    dataset_name_csv = ",".join(ds_names) or None
    if dataset_name_csv and len(dataset_name_csv) > 255:
        dataset_name_csv = f"{ds_names[0]} +{len(ds_names) - 1} more"[:255]

    params = {
        "_base_model": {"name": model_name},
        "datasets": ds_names,
        "benchmarks": pairs,
        "benchmark_set": benchmark_set,
        "metric_map": metric_map,
    }
    # reserved _dataset = 첫 데이터셋(마운트). 전체 이름은 params.datasets. 없으면 싣지 않는다 —
    # BFF 는 빈 값으로 두고 차트는 이름이 있을 때만 /dataset 을 마운트한다(pod.yaml).
    if datasets:
        primary = datasets[0]
        params["_dataset"] = {"name": primary["name"], "access": primary["access"]}

    # 실행 옵션은 **LogicKor 채점기 전용**이다 — 전략·심판 모델·심판 컨텍스트는 그 컨테이너의
    # 계약이고, 다른 실채점 벤치마크(MixATIS 는 심판 LLM 자체가 없다)에는 대응물이 없다.
    # 그래서 '실채점이면'이 아니라 'LOGICKOR 이면'으로 좁힌다. 위에서 채점기 혼재는 이미
    # 거부됐으므로 이 런의 manifest_key 는 하나로 확정돼 있다.
    # dto 가 이미 검증하지만 서비스를 직접 호출하는 경로(테스트·내부 호출)를 위해 알려진
    # 키만 통과시키고 타입을 다시 좁힌다 — 모델·데이터셋 이름 재검증과 같은 취지의 방어다.
    if run_options and manifest_key == "LOGICKOR":
        for key, low, high in (
            ("generate_model_len", LOGICKOR_MODEL_LEN_MIN, LOGICKOR_MODEL_LEN_MAX),
            ("judge_model_len", LOGICKOR_MODEL_LEN_MIN, LOGICKOR_MODEL_LEN_MAX),
            ("judge_max_output_tokens",
             LOGICKOR_JUDGE_MAX_OUTPUT_MIN, LOGICKOR_JUDGE_MAX_OUTPUT_MAX),
        ):
            raw = run_options.get(key)
            if raw is None:
                continue
            try:
                val = int(raw)
            except (TypeError, ValueError):
                raise Exception(f"{key} must be an integer")
            if not low <= val <= high:
                raise Exception(f"{key} must be between {low} and {high}")
            params[key] = val
        strategy = run_options.get("strategy")
        if strategy is not None:
            if strategy not in LOGICKOR_STRATEGIES:
                raise Exception(f"unknown strategy: {strategy}")
            params["strategy"] = strategy
        judge_model = run_options.get("judge_model")
        if judge_model is not None:
            # 화이트리스트 id 만 받는다 — 자유 입력이면 캐시에 없는 모델이 통과해
            # 컨테이너가 GPU 를 잡은 뒤에야 죽는다(HF_HUB_OFFLINE=1, /hf-cache RO).
            if judge_model not in LOGICKOR_JUDGE_HF_ID:
                raise Exception(f"unknown judge_model: {judge_model}")
            # 컨테이너에는 id 가 아니라 HF repo id 를 넘긴다 — resolve_judge_model 이
            # 모르는 값을 그대로 통과시키므로, 컨테이너 프리셋 표에 없는 심판도 로드된다
            # (심판 추가에 이미지 재빌드가 필요 없는 이유).
            params["judge_model"] = LOGICKOR_JUDGE_HF_ID[judge_model]

    # 태스크당 문항 상한 — lm-eval 채점기 전용 옵션. 다른 채점기에 오면 조용히 버리지 않고
    # 거절한다(버리면 "빠르게 쟀다"고 믿는 전체 측정 런이 된다 — 심판 배타 검증과 같은 취지).
    sample_limit = (run_options or {}).get("sample_limit")
    if sample_limit is not None:
        if manifest_key not in LOCAL_WEIGHTS_MANIFEST_KEYS:
            raise Exception(
                "sample_limit 은 lm-eval 채점 벤치마크 전용입니다 — "
                f"{', '.join(benchmark_set)} 에는 문항 상한 옵션이 없습니다")
        try:
            sample_limit = int(sample_limit)
        except (TypeError, ValueError):
            raise Exception("sample_limit must be an integer")
        if not BENCHMARK_SAMPLE_LIMIT_MIN <= sample_limit <= BENCHMARK_SAMPLE_LIMIT_MAX:
            raise Exception(f"sample_limit must be between {BENCHMARK_SAMPLE_LIMIT_MIN} "
                            f"and {BENCHMARK_SAMPLE_LIMIT_MAX}")
        params["limit"] = sample_limit

    # ── 원격 심판(D) — 심판을 컨테이너 안 vLLM 이 아니라 떠 있는 배포에 위임 ────────
    # 컨테이너에 넘기는 것은 사용자가 준 URL 이 아니라 **배포 id 로 서버가 조립한 URL** 이다
    # (URL 수취는 그대로 SSRF 가 된다 — llm_playground _resolve_proposer_llm_url 과 같은 규약).
    judge_remote = None
    if judge_playground_id:
        # 심판 개념이 있는 채점기는 LogicKor 뿐이다(MixATIS 는 정답이 데이터에 있어 심판이
        # 없다). 조용히 무시하면 "심판을 골랐는데 안 쓰인" 런이 되므로 명시적으로 거부한다.
        if manifest_key != "LOGICKOR":
            raise Exception(
                "judge_playground_id 는 LogicKor 채점기 전용입니다 — "
                f"{', '.join(benchmark_set)} 에는 심판 단계가 없습니다")
        # judge_model 은 "컨테이너가 이 가중치를 올려라", judge_playground_id 는 "이미 떠
        # 있는 저 배포에 물어봐라" 로 서로 배타적인 지시다. 한쪽을 조용히 버리면 사용자가
        # 고르지 않은 심판이 매긴 점수가 나온다 → 채점기 혼재 거부와 같은 취지로 거절한다.
        if params.get("judge_model"):
            raise Exception(
                "judge_playground_id 와 judge_model 은 함께 지정할 수 없습니다 — "
                "원격 심판을 쓰면 컨테이너는 심판 가중치를 올리지 않습니다")
        judge_remote = await _resolve_remote_judge(
            judge_playground_id, model_id=model_id, workspace_id=workspace_id,
            exclude_playground_id=inference_playground_id)
        # 넘기는 것은 base URL 하나뿐이다. 채점기는 이 값의 존재만으로 원격 모드를 판정하고
        # metrics.judge{mode,endpoint,note} 에 스스로 새긴다(0.2.4 실측) — "원격 심판을
        # 썼다"를 별도 파라미터로 또 보내면 같은 사실이 두 곳에서 어긋날 수 있다.
        # 결정성(배포 temperature)은 컨테이너가 알 수 없는 값이라 이 서비스가 경고 로그와
        # 런 생성 응답(judge_remote)으로 남긴다.
        params["judge_base_url"] = judge_remote["base_url"]

    # ── 빌린 배포에 생성 위임 — 벤치마크의 유일한 생성 경로 ─────────────────────
    # 넘기는 것은 배포 id 로 **서버가 조립한** OpenAI shim base 하나뿐이고(URL 수취는
    # 그대로 SSRF 다 — 원격 심판과 같은 규약), 생성은 컨테이너 안에서 그 배포를 호출해
    # 일어난다. 그래서 이 핸들러는 아무것도 붙들고 있지 않는다 — 옛 인라인 생성이
    # Kong 60s 와 경쟁하던 문제가 구조적으로 사라졌다.
    # 왜 BE 가 대신 생성하지 않는가: 프롬프트 조립이 컨테이너 소유다(LogicKor 2턴 의존·
    # 채팅 템플릿·토큰 예산, MixATIS UGEN 형식). 함수 docstring 참고.
    # 단, **포맷 학습을 켜면 위임하지 않는다** — 학습 LoRA 는 채점기가 로컬에 올린 모델에만
    # 얹을 수 있고, generate_base_url 을 함께 실으면 컨테이너가 학습 단계를 조용히 건너뛴다
    # (evaluate_intent app.py:376). 그 조합은 "학습을 켰는데 학습이 안 된" 런이 된다.
    generate_remote = None
    checkpoint_name = None
    # lm-eval 채점기는 위임 자체가 불가능하다(보기별 로그확률이 필요한데 shim 이 logprobs 를
    # 주지 못한다 — constants.LOCAL_WEIGHTS_MANIFEST_KEYS). 포맷 학습과 같은 방식으로 배포가
    # 서빙 중인 커밋을 풀어 컨테이너가 로컬에 올린다.
    local_weights = manifest_key in LOCAL_WEIGHTS_MANIFEST_KEYS
    if format_train_on:
        # 배포는 이 경로에서 **생성을 하지 않는다** — 어느 커밋을 마운트할지만 말해 준다.
        checkpoint_name = await _resolve_deployment_checkpoint(
            inference_playground_id, model_id=model_id, workspace_id=workspace_id,
            purpose="포맷 학습", off_hint="포맷 학습을 끄세요")
        params["checkpoint_name"] = checkpoint_name
        params["train"] = True
    elif local_weights:
        # 묶음 실행이 이미 푼 체크포인트가 있으면 그대로 쓴다 — 한 묶음이 한 가중치를 잰다.
        checkpoint_name = pinned_checkpoint or await _resolve_deployment_checkpoint(
            inference_playground_id, model_id=model_id, workspace_id=workspace_id,
            purpose="lm-eval 벤치마크 채점", off_hint=None)
        params["checkpoint_name"] = checkpoint_name
    else:
        generate_remote = await _resolve_remote_generator(
            inference_playground_id, model_id=model_id, workspace_id=workspace_id)
        params["generate_base_url"] = generate_remote["base_url"]
        if manifest_key in FORMAT_TRAIN_MANIFEST_KEYS:
            # 컨테이너는 위임 경로에서 어차피 학습을 건너뛰지만(기본값이 train=true 라
            # 경고를 찍고 끈다), 끈 주체를 **우리로** 명시해 둔다 — 잡 로그에 남는 경고가
            # 사용자가 고른 적 없는 설정을 되돌린 것처럼 읽히지 않게 한다.
            params["train"] = False

    # ── 완전 위임이면 GPU 를 요청하지 않는다 ────────────────────────────────────
    # 매니페스트의 resources.gpu 는 런타임 파라미터를 모른 채 **최악**(로컬 생성 + 로컬
    # 심판)을 선언한다 — 그건 옳고 그대로 둔다. 그 선언을 좁힐 수 있는 유일한 지점이
    # 실제 파라미터를 아는 이 호출부다. 컨테이너가 로컬에 아무 모델도 올리지 않는
    # 조합에서만 0 을 넘긴다:
    #   LogicKor : 생성·심판이 **둘 다** 원격이어야 한다 — 하나라도 로컬이면 vLLM 이 뜬다.
    #   MixATIS  : 심판 단계 자체가 없으므로 생성만 원격이면 된다(그 경로는 학습도 건너뛴다).
    # 판정이 틀리면 GPU 없이 뜬 파드가 vLLM 초기화에서 죽으므로 보수적으로 본다 —
    # 확신이 없으면 None 을 넘겨 매니페스트 기본값을 그대로 쓴다.
    # 부수 효과가 아니라 목적 중 하나다: 위임 런이 쓰지도 않을 GPU 를 예약하던 것을 없앤다.
    #   포맷 학습  : 켜져 있으면 로컬에 모델을 올려 학습·생성한다 → 위임이 아니다.
    fully_delegated = (not format_train_on) and (not local_weights) and (
        judge_remote is not None if manifest_key == "LOGICKOR" else True)
    gpu_count = 0 if fully_delegated else None

    try:
        async with httpx.AsyncClient(timeout=60.0) as http:
            client = ExternalContainerClient(
                base_url=settings.FB_EXTERNAL_CONTAINER_URL, client=http)
            raw = await client.start_job(
                manifest_name=manifest_name,
                manifest_version=manifest_version,
                workspace_id=workspace_id, params=params,
                gpu_count=gpu_count)
    except ExternalContainerError as e:
        raise Exception(f"benchmark job launch failed ({e.status_code}): {e}") from e

    job_id = raw.get("job_id") or (raw.get("result") or {}).get("job_id")
    if not job_id:
        # job_id 없으면 launch 실패로 간주(FE /jobs/null 무한 폴링 방지). raw(내부 URL 가능)
        # 는 API 누출 없이 서버 로그로만.
        print(f"benchmark launch: no job_id in response: {raw!r}")
        raise Exception("benchmark job launched but no job_id in response")

    # 멀티 데이터셋 → dataset_id 단일 컬럼엔 첫 id, dataset_name 엔 CSV. DB 실패가
    # launch 를 막지 않도록 guard(llm_model.evaluate_model 동형).
    try:
        await db_model.insert_eval_result(
            source_model_id=model_id, workspace_id=workspace_id,
            job_str_id=job_id, dataset_id=dataset_ids[0] if dataset_ids else None,
            dataset_name=dataset_name_csv, metric_set=metric_csv,
            eval_project_id=project_id)
        await db_model.update_eval_project_status(project_id, PROJECT_STATUS_RUNNING)
    except Exception:
        traceback.print_exc()

    return {
        "project_id": project_id,
        "model_id": model_id, "model_name": model_name, "workspace_id": workspace_id,
        "dataset_ids": dataset_ids, "datasets": ds_names,
        "benchmarks": pairs, "benchmark_set": benchmark_set, "metric_map": metric_map,
        "manifest_name": manifest_name,
        "manifest_version": manifest_version,
        "job_id": job_id, "mode": "benchmark",
        # 생성이 배포에서 일어났나. 포맷 학습 런은 채점기가 로컬에서 생성하므로 False 다 —
        # 그 런에서 배포는 '어느 커밋인가'만 말해 준 것이고, 그 사실을 True 로 남기면
        # 나중에 출처를 되짚을 때 배포가 답을 만든 것으로 읽힌다.
        "used_deployment": not (format_train_on or local_weights),
        # 포맷 학습 런에서도 남긴다 — 체크포인트를 어느 배포에서 풀었는지의 기록이다.
        "inference_playground_id": inference_playground_id,
        # 포맷 학습을 돌렸나 + 무엇을 학습했나. 실제 레시피(예제 수·에폭·스텝)는 컨테이너가
        # metrics.train 에 새기고, 여기에는 런 생성 시점에 우리가 정한 것만 싣는다.
        "format_train": format_train_on,
        "checkpoint": checkpoint_name,
        # 인라인 생성이 사라져 **항상 None** 이다(생성은 컨테이너 안에서 일어나므로 건수·
        # 빈 출력은 런 결과 metrics.generate 에 컨테이너가 새긴다). 키 자체는 남긴다 —
        # 소비하는 화면이 있고, 없어지면 undefined 접근이 된다.
        "generated": None,
        # 위임한 배포 정보(배포 id·이름·temperature·결정성). judge_remote 와 같은 규약이다.
        "generate_remote": generate_remote,
        # 원격 심판 정보(배포 id·이름·temperature·결정성). metrics.json 은 컨테이너가
        # 통째로 쓰므로 배포 생성 파라미터를 플랫폼이 남길 수 있는 자리는 여기와 서버 로그뿐.
        "judge_remote": judge_remote,
    }


async def _gpu_free_count(workspace_id: int) -> Optional[int]:
    """지금 잡을 수 있는 GPU 장수 — 클러스터 풀과 워크스페이스 몫 중 빡빡한 쪽. 모르면 None.

    화면(BenchmarkRunConfig)이 쓰는 것과 같은 계산(utils.gpu_pool.snapshot)이다 — 둘이 다르게
    세면 화면은 되는데 서버가 거절하거나 그 반대가 된다. 조회 실패는 '모름'이라 막지 않는다
    (확신 없이 막으면 멀쩡한 클러스터가 봉쇄된다 — 최종 판정은 스케줄러의 원자적 claim).
    Redis 클라이언트가 동기라 **클라이언트 획득까지** 스레드로 돌린다 — get_redis_client() 는
    ping 실패 시 time.sleep 으로 재시도하므로(fb_utils/redis.py) 루프 위에서 부르면 그동안 워커의
    다른 요청이 전부 멈춘다."""
    try:
        snap = await asyncio.to_thread(
            lambda: gpu_pool.snapshot(get_redis_client(), workspace_id))
    except Exception:
        traceback.print_exc()
        return None
    counts = [snap.get("free"), (snap.get("workspace") or {}).get("free")]
    counts = [int(c) for c in counts if isinstance(c, int) and not isinstance(c, bool)]
    return min(counts) if counts else None


def _est_seconds(benchmark: str) -> int:
    return LMEVAL_EST_SECONDS.get(benchmark, LMEVAL_EST_DEFAULT_SECONDS)


def plan_benchmark_runs(ids: List[str], gpu_count: int) -> List[List[str]]:
    """묶음 실행의 분배 — 벤치마크 목록을 GPU 수(= 런 수, 런마다 GPU 1장)만큼의 런으로 나눈다.

    한 런은 GPU 한 장에서 벤치마크를 **직렬로** 채점한다(모델은 한 번만 올린다). 다른 것과 한 런에
    못 싣는 것이 둘 있다:
      - 코드 실행 벤치마크(HumanEval) — 격리 매니페스트(BENCHMARK_CODE)라 다른 채점기와 한 잡이
        될 수 없다(run_benchmark 의 채점기 혼재 거절).
      - 런 데이터셋을 읽는 벤치마크(custom) — 데이터셋은 그것을 읽는 런에만 싣는다. ARC 와 한 런에
        담으면 그 런의 결과가 "ARC 를 그 데이터셋으로 쟀다"고 말한다.
    나머지(문항이 이미지에 구워진 lm-eval 벤치마크)는 남은 GPU 수만큼의 런에 **예상 시간 기준으로
    고르게** 나눈다(LPT — 무거운 것부터 지금 가장 가벼운 런에). 개수로 나누면 KMMLU(65분)와
    MMLU(31분)가 한 런에 몰려 벽시계가 그 런 하나로 늘어난다. 런 안의 순서는 요청 순서다.

    GPU 수가 벤치마크 수보다 많으면 벤치마크마다 런 하나가 된다(남는 GPU 는 쓰지 않는다)."""
    code = [b for b in ids if REAL_BENCHMARK_MANIFEST_KEY.get(b) == "BENCHMARK_CODE"]
    reads_dataset = [b for b in ids
                     if b not in code and b not in DATASET_FREE_BENCHMARK_IDS]
    plain = [b for b in ids if b not in code and b not in reads_dataset]
    fixed = [group for group in (code, reads_dataset) if group]
    need = len(fixed) + (1 if plain else 0)
    if gpu_count < need:
        raise Exception(
            f"GPU {gpu_count}장으로는 나눌 수 없습니다 — HumanEval(코드 실행)·사용자 데이터셋 평가는 "
            f"다른 벤치마크와 한 런에 담을 수 없어 GPU 가 최소 {need}장 필요합니다")
    n_plain = min(gpu_count - len(fixed), len(plain))
    bins: List[List[str]] = [[] for _ in range(n_plain)]
    loads = [0] * n_plain
    # sorted 는 안정 정렬 — 예상 시간이 같으면 요청 순서대로 배치된다(같은 요청 = 같은 분배).
    for b in sorted(plain, key=lambda x: -_est_seconds(x)):
        k = loads.index(min(loads))
        bins[k].append(b)
        loads[k] += _est_seconds(b)
    order = {b: i for i, b in enumerate(ids)}
    runs = [sorted(group, key=order.__getitem__) for group in bins + fixed]
    runs.sort(key=lambda group: order[group[0]])
    # 한 런이 파드 타임아웃을 넘으면 도중에 죽고 남은 벤치마크는 채점되지 않는다. 추정은 3B 기준이라
    # 최악 배수(8B)를 곱해 본다 — 모델 크기를 모르므로 보수적으로 막는다.
    for group in runs:
        worst = (LMEVAL_STARTUP_SECONDS + sum(_est_seconds(b) for b in group)) \
            * LMEVAL_WORST_SLOWDOWN
        if worst > LMEVAL_RUN_TIMEOUT_SECONDS:
            raise Exception(
                f"GPU {gpu_count}장에 나누면 한 런({', '.join(group)})이 큰 모델에서 "
                f"약 {worst / 3600:.1f}시간 걸려 런 제한 시간({LMEVAL_RUN_TIMEOUT_SECONDS // 3600}"
                f"시간)을 넘을 수 있습니다 — GPU 수를 늘리세요")
    return runs


async def run_benchmark_batch(project_id: int, model_id: int, benchmarks: List[str],
                              inference_playground_id: Optional[int],
                              dataset_ids: Optional[List[int]] = None,
                              run_options: Optional[dict] = None,
                              gpu_count: Optional[int] = None) -> dict:
    """여러 벤치마크를 한 번에 — **GPU 수만큼의 런**으로 나눠 띄운다(설계 §14).

    gpu_count = 이 실행이 쓸 GPU 장수 = 런 수(런마다 GPU 1장, 그 안에서 벤치마크를 직렬 채점).
    분배는 plan_benchmark_runs. 생략하면 벤치마크마다 런 하나(§12.2 의 종전 동작)다.
    왜 나누는가: 벤치마크마다 런이면 20개를 고른 실행이 빈 GPU 20장을 요구해 거절된다 — 외부 잡은
    대기열이 없다. 한 런에 여러 벤치마크를 담아도 **한 벤치마크의 실패가 런을 버리지 않는다** —
    채점기(evaluate-lmeval 0.1.1)가 벤치마크 단위로 실패를 격리하고 끝난 점수를 progress.json 에
    남긴다(파드가 도중에 죽어도 그때까지의 점수가 보인다).

    받는 것은 로컬 가중치 채점기(lm-eval)뿐이다 — 위임 채점기(MixATIS·LogicKor)는 포맷 학습·
    심판 설정이 벤치마크마다 따로라 묶음의 공통 설정으로 표현할 수 없다.

    체크포인트는 **여기서 한 번만** 푼다 — 런마다 풀면 묶음 도중 배포가 커밋을 바꿨을 때 한 묶음
    안에서 서로 다른 가중치를 재고, 화면은 그걸 한 줄로 요약한다.

    런치 전에 막는 것(부분 실행을 남기지 않기 위해): 모르는 id, 위임 채점기, 데이터셋 누락,
    프로젝트 유형, 분배 불가(GPU 수 부족·런 제한 시간 초과), **가용 GPU 부족** — 외부 잡은 빈 GPU 가
    없으면 대기하지 않고 즉시 실패한다(fb_scheduler external_run `GpuAllocationError`). 런치 도중
    실패(경합으로 GPU 를 뺏김 등)는 거기서 멈추지 않고 런별 error 로 돌려준다 — 이미 뜬 런을 되돌릴
    방법이 없으므로 무엇이 떴고 무엇이 안 떴는지를 정확히 알리는 편이 낫다."""
    if not inference_playground_id:
        raise Exception(
            "벤치마크 출력은 실행 중인 배포에서 가져옵니다 — 평가할 모델을 서빙하는 "
            "배포를 먼저 시작한 뒤 지정하세요(inference_playground_id)")
    ids = []
    for raw in benchmarks or []:
        b = str(raw or "").strip()
        if b not in BENCHMARK_IDS:
            raise Exception(f"unknown benchmark: {b!r}")
        if b not in ids:
            ids.append(b)
    if not ids:
        raise Exception("실행할 벤치마크를 하나 이상 고르세요")
    if len(ids) > MAX_BENCHMARK_ITEMS:
        raise Exception(f"한 번에 실행할 수 있는 벤치마크는 최대 {MAX_BENCHMARK_ITEMS}개입니다"
                        f"(요청 {len(ids)}개)")
    delegated = [b for b in ids
                 if REAL_BENCHMARK_MANIFEST_KEY.get(b, "BENCHMARK")
                 not in LOCAL_WEIGHTS_MANIFEST_KEYS]
    if delegated:
        raise Exception(
            "여러 벤치마크 한 번에 실행은 lm-eval 채점 벤치마크만 됩니다 — "
            f"{', '.join(delegated)} 는 따로 실행하세요")
    if not dataset_ids:
        needs = [b for b in ids if b not in DATASET_FREE_BENCHMARK_IDS]
        if needs:
            raise Exception(
                f"{', '.join(needs)} 는 평가 데이터셋이 필요합니다 — 데이터셋을 고르세요")
    plan = plan_benchmark_runs(ids, int(gpu_count) if gpu_count else len(ids))

    project = await _load_project_for_run(project_id, BENCHMARK_EVAL_TYPES)
    project_type = str(project.get("eval_type") or "")
    wrong = [b for b in ids if BENCHMARK_EVAL_TYPE.get(b) != project_type]
    if wrong:
        raise Exception(
            f"{project_type} 프로젝트에는 {project_type} 유형 벤치마크만 채점할 수 "
            f"있습니다 — {', '.join(wrong)}")
    model_id = int(model_id)
    _, workspace_id = await _resolve_run_model(project, model_id)

    free = await _gpu_free_count(workspace_id)
    if free is not None and free < len(plan):
        raise Exception(
            f"런 {len(plan)}개를 동시에 띄우려면 GPU {len(plan)}장이 필요합니다 — "
            f"지금 잡을 수 있는 GPU 는 {free}장입니다. GPU 수를 줄이거나 실행 중인 작업이 "
            f"끝난 뒤 다시 시도하세요")

    checkpoint = await _resolve_deployment_checkpoint(
        inference_playground_id, model_id=model_id, workspace_id=workspace_id,
        purpose="lm-eval 벤치마크 채점", off_hint=None)

    runs = []
    for group in plan:
        try:
            # 데이터셋은 그것을 읽는 런에만 싣는다 — 분배가 데이터셋을 읽는 벤치마크를 따로 떼어
            # 두므로(plan_benchmark_runs) ARC 런에 custom 의 데이터셋이 남지 않는다.
            reads = any(b not in DATASET_FREE_BENCHMARK_IDS for b in group)
            res = await run_benchmark(
                project_id=project_id, model_id=model_id,
                dataset_ids=list(dataset_ids or []) if reads else [],
                benchmarks=group,
                inference_playground_id=inference_playground_id,
                run_options=run_options, pinned_checkpoint=checkpoint)
            runs.append({"benchmarks": group, "job_id": res["job_id"],
                         "manifest_name": res["manifest_name"]})
        except Exception as e:
            traceback.print_exc()
            runs.append({"benchmarks": group, "error": str(e)})
    launched = [r for r in runs if r.get("job_id")]
    # 실행(묶음) 기록 — 결과 카드 1장. 뜬 런만 멤버가 되고, 런마다 담은 벤치마크를 함께 남긴다 —
    # eval_result.metric_set(VARCHAR 255)은 17개를 담으면 잘려(272자) 화면이 목록을 거기서 읽을 수
    # 없다. 기록 실패가 런치를 무르지 않는다(이미 뜬 런은 되돌릴 수 없다) — 그때 런들은 화면에서
    # 카드 한 장씩으로 보인다(insert_eval_result 의 DB 가드와 같은 취지).
    # 런치에 실패한 런의 벤치마크도 벤치마크마다 남긴다 — 빼면 요청한 12개 중 9개만 뜬 실행이
    # 나중에 "9/9 완료"로 읽힌다. 메시지는 짧게 자른다(화면 표시용 — 전체는 서버 로그에 있다).
    launch_failures = [{"benchmark": b, "error": str(r["error"])[:300]}
                       for r in runs if r.get("error") for b in r["benchmarks"]]
    batch_id = None
    if launched:
        try:
            batch_id = await db_model.insert_eval_run_batch(
                eval_project_id=project_id, workspace_id=workspace_id,
                source_model_id=model_id, checkpoint=checkpoint,
                sample_limit=(run_options or {}).get("sample_limit"),
                job_ids=[r["job_id"] for r in launched],
                job_benchmarks={r["job_id"]: r["benchmarks"] for r in launched},
                launch_failures=launch_failures)
        except Exception:
            traceback.print_exc()
    return {"project_id": project_id, "model_id": model_id, "checkpoint": checkpoint,
            "inference_playground_id": inference_playground_id, "batch_id": batch_id,
            "runs": runs, "launched": len(launched), "failed": len(runs) - len(launched)}


async def _eval_jobs_base(model_id: int) -> str:
    """모델의 워크스페이스 jobs 디렉토리(realpath). 여러 런을 한 번에 볼 때 모델당 한 번만 푼다."""
    model_info = await db_model.get_model(model_id=model_id)
    if not model_info:
        raise Exception(f"model {model_id} not found")
    ws = await db_model.get_workspace_model(workspace_id=int(model_info["workspace_id"]))
    if not ws:
        raise Exception(f"workspace for model {model_id} not found")
    main_root = PATH.JF_MAIN_STORAGE_PATH.format(
        STORAGE_NAME=ws["main_storage_name"], WORKSPACE_NAME=ws["name"],
    )
    return os.path.realpath(os.path.join(main_root, "jobs"))


async def _eval_output_dir(model_id: int, job_id: str, jobs_base: Optional[str] = None) -> str:
    """evaluate job 결과 디렉토리(jobs/<job_id>/output) 안전 해석(llm_model 동형).
    jobs_base 를 주면(_eval_jobs_base 로 미리 푼 값) DB 를 다시 조회하지 않는다."""
    if not job_id or not _JOB_ID_RE.match(job_id):
        raise ValueError(f"invalid job_id: {job_id!r}")
    jobs_base = jobs_base or await _eval_jobs_base(model_id)
    output_dir = os.path.join(jobs_base, job_id, "output")
    if os.path.commonpath([os.path.realpath(output_dir), jobs_base]) != jobs_base:
        raise ValueError("output path escapes jobs base")
    return output_dir


# 컨테이너가 보고하는 종료 상태 → eval_result 상태. 여기 없는 값(running/pending/
# completed…)은 아직 진행 중이거나 정상 마감 경로라 손대지 않는다.
_TERMINAL_JOB_STATUS = {
    "failed": "failed",
    "error": "failed",
    "cancelled": "cancelled",
    "canceled": "cancelled",
}


async def _reconcile_running_eval(model_id: int, job_id: str) -> str:
    """DB 가 running 인 런에 대해 컨테이너 잡이 이미 끝났는지 확인해 상태를 맞춘다.

    왜 필요한가. 벤치마크 완료는 **lazy** 다 — `metrics.json` 이 생겨야 completed 로
    마감된다. 그래서 파드가 중간에 죽어 helm 이 uninstall 되면 metrics.json 이 영영
    생기지 않고, DB 는 running 에 고착돼 화면이 '진행중'을 계속 보여준다(사용자가 중지
    버튼을 눌러야만 풀렸다). 나이 기반 스윕(fail_stale_eval_results)은 6시간 경과 +
    모델 이력 화면 진입이라는 두 조건이 겹쳐야 돌아서 이 창을 막지 못한다.

    ⚠️ **조회 실패(404 포함)는 절대 실패 근거로 쓰지 않는다.** fb_external_container 는
    기동 시 in-memory 레지스트리로 즉시 서빙하고 DB 를 백그라운드로 재시도하는데,
    재시도가 끝내 실패하면 재시작 전까지 그대로 남는다(main.py 의
    "staying on in-memory registry"). 그 구간에는 **GPU 에서 정상적으로 도는 잡도 404**
    가 된다. 404 를 실패로 확정하면 그 런은 되돌릴 수 없다 — update_eval_result_status
    와 complete_eval_result 가 둘 다 `WHERE status='running'` 가드라, 나중에
    metrics.json 이 생겨도 completed 로 갈 수 없고 FE 는 이미 폴링을 멈춘 뒤다.
    트래커 스스로도 `404 는 "이런 job 은 존재한 적 없다"에만 쓴다`(job_router)고 규정하고,
    get_persisted 는 "성급한 실패 확정 방지"를 위해 미복구 active row 를 running 으로
    답한다. 그 설계를 거스르지 않는다 — 진짜 고아는 6시간 스윕이 걷어간다.

    전부 best-effort: 무엇이 실패하든 running 을 돌려주어 폴링을 깨뜨리지 않는다.
    반환값은 화면에 그대로 실릴 상태 문자열이다.
    """
    if not job_id or not _JOB_ID_RE.match(job_id):
        return "running"
    try:
        async with httpx.AsyncClient(timeout=RECONCILE_TIMEOUT_SECONDS) as http:
            client = ExternalContainerClient(
                base_url=settings.FB_EXTERNAL_CONTAINER_URL, client=http)
            detail = await client.get_job(job_id)
    except ExternalContainerError:
        # 404(트래커가 모름) 포함. 위 주석 참조 — 조회 실패는 실패의 증거가 아니다.
        return "running"
    except Exception:
        traceback.print_exc()
        return "running"

    # 응답 해석은 try 밖에서 하되 방어적으로 — 파트너가 result 를 dict 가 아닌 형태로
    # 주면 .get() 이 터진다. 여기서 예외가 새면 폴링 한 사이클이 API 오류로 끝난다.
    result = (detail or {}).get("result")
    if not isinstance(result, dict):
        return "running"
    raw = str(result.get("status") or "").lower()
    mapped = _TERMINAL_JOB_STATUS.get(raw)
    if not mapped:
        return "running"

    err = result.get("error")
    reason = err.get("message") if isinstance(err, dict) else None
    reason = reason or f"external job reported {raw}"
    try:
        await db_model.update_eval_result_status(
            job_str_id=job_id, status=mapped, source_model_id=model_id)
    except Exception:
        traceback.print_exc()
        return "running"
    print(f"[eval] run {job_id} reconciled running -> {mapped}: {reason}", flush=True)
    return mapped


def _strip_internal_paths(metrics: dict) -> None:
    """채점기가 metrics.json 에 새긴 컨테이너 내부 경로를 응답/영속 전에 지운다(in-place).

    플랫폼 규약은 체크포인트를 **이름으로만** 노출하는 것이다 — 경로를 받지 않는 것도
    같은 이유다(params 로 마운트 밖을 열지 못하게). 그런데 채점기는 진단 편의로
    `checkpoint.path` 를 함께 실어 보내고, 이 값이 그대로 API 응답과 DB 에 남으면
    화면에 안 그린다는 FE 관례만으로는 막히지 않는다(devtools 로 그대로 보인다).
    서버 경계에서 지워 규약을 코드로 강제한다. `name` 은 어느 체크포인트로 낸 점수인지
    말해주는 값이라 남긴다.
    """
    if not isinstance(metrics, dict):
        return
    ckpt = metrics.get("checkpoint")
    if isinstance(ckpt, dict):
        ckpt.pop("path", None)
    train = metrics.get("train")
    if isinstance(train, dict):
        train.pop("adapter_dir", None)
    # 채점기가 벤치마크별 실패 사유로 남긴 예외 문자열(evaluate-lmeval 0.1.1 failed_benchmarks)에도
    # 컨테이너 경로가 섞인다(가중치 병합·데이터셋 로드 예외) — 같은 규약으로 가린다(보안 리뷰 LOW).
    for failure in metrics.get("failed_benchmarks") or []:
        if isinstance(failure, dict) and failure.get("error"):
            failure["error"] = _redact_paths(str(failure["error"]))


# 절대 경로(/models/…, /tmp/lmeval-merged …) — 앞이 글자·숫자·점이면 경로가 아니다("N/A", "1/3").
_ABS_PATH_RE = re.compile(r"(?<![\w.])/(?:[\w.\-]+/)*[\w.\-]+")


def _redact_paths(text: str) -> str:
    return _ABS_PATH_RE.sub("<path>", text)


_PROGRESS_STATUSES = ("pending", "running", "done", "failed")


def _read_progress(output_dir: str) -> Optional[dict]:
    """채점기가 남긴 벤치마크별 진행(progress.json, evaluate-lmeval 0.1.1+) → 화면용 요약.

    한 런이 여러 벤치마크를 직렬로 채점하므로 런 상태 하나로는 "무엇이 끝났나"를 말할 수 없다.
    끝난 벤치마크의 점수(partial)도 여기 있다 — 파드가 도중에 죽거나 취소돼 metrics.json 이
    없는 런에서도 그때까지 낸 점수를 보여 줄 수 있다. 런 마감(completed)은 여전히 metrics.json
    으로만 한다(partial 은 영속하지 않는다 — 비교·Best 는 끝까지 채점한 런만 쓴다).
    없거나 읽을 수 없으면 None(0.1.0 이하 채점기·위임 채점기는 이 파일을 쓰지 않는다)."""
    out_real = os.path.realpath(output_dir)
    path = os.path.join(output_dir, "progress.json")
    try:
        if os.path.commonpath([os.path.realpath(path), out_real]) != out_real:
            return None
        if not os.path.isfile(path) or os.path.getsize(path) > 1 * 1024 * 1024:
            return None
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return None
    rows = raw.get("benchmarks") if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        return None
    benchmarks = []
    for row in rows:
        if not isinstance(row, dict) or row.get("status") not in _PROGRESS_STATUSES:
            continue
        score = row.get("score")
        benchmarks.append({
            "benchmark": str(row.get("benchmark") or ""),
            "status": row["status"],
            "score": score if isinstance(score, (int, float))
            and not isinstance(score, bool) else None,
            "elapsed_sec": row.get("elapsed_sec"),
            "error": _redact_paths(str(row["error"])[:500]) if row.get("error") else None,
        })
    partial = raw.get("partial")
    if isinstance(partial, dict):
        _strip_internal_paths(partial)
    else:
        partial = None
    return {"benchmarks": benchmarks, "partial_metrics": partial}


async def get_eval_result(model_id: int, job_id: str) -> dict:
    """평가 job metrics.json 읽기 + 완료 시 eval_result lazy 마감(idempotent).
    metrics.json 이 아직 없으면 채점기의 벤치마크별 진행(progress, 있을 때만)을 함께 싣는다."""
    output_dir = await _eval_output_dir(model_id, job_id)
    out_real = os.path.realpath(output_dir)
    metrics_path = os.path.join(output_dir, "metrics.json")
    if os.path.commonpath([os.path.realpath(metrics_path), out_real]) != out_real:
        raise ValueError("metrics path escapes output dir")
    if not os.path.isfile(metrics_path):
        # 파일 아직 없음 → DB 상태로 failed/cancelled 조기 surface(컨테이너 실패 시 FE 가
        # POLL_MAX 까지 헛폴링하지 않도록). 정상 진행 중이면 running.
        try:
            row = await db_model.get_eval_result_by_job(
                job_str_id=job_id, source_model_id=model_id)
            db_status = (row or {}).get("status") or "running"
        except Exception:
            row, db_status = None, "running"
        # running 이면 컨테이너에 되물어 '죽은 잡'을 즉시 표면화한다. FE 는 이미
        # status==failed/cancelled 를 받으면 폴링을 멈추므로, 신호만 만들어 주면 된다.
        if db_status == "running":
            db_status = await _reconcile_running_eval(model_id, job_id)
        return {"job_id": job_id, "metrics": None, "ready": False, "status": db_status,
                "progress": _read_progress(output_dir)}
    try:
        if os.path.getsize(metrics_path) > 1 * 1024 * 1024:
            raise ValueError(f"metrics.json too large for job {job_id}")
    except OSError:
        return {"job_id": job_id, "metrics": None, "ready": False}
    try:
        with open(metrics_path, encoding="utf-8") as f:
            metrics = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"job_id": job_id, "metrics": None, "ready": False}
    _strip_internal_paths(metrics)
    # 위임 런의 출처를 **여기서 한 번** 굳힌다(아래 함수 주석 참고). 실패해도 마감은 진행한다.
    await _freeze_run_source(metrics, model_id=model_id, job_id=job_id)
    try:
        await db_model.complete_eval_result(
            job_str_id=job_id, metrics_json=json.dumps(metrics), source_model_id=model_id)
    except Exception:
        traceback.print_exc()
    return {"job_id": job_id, "metrics": metrics, "ready": True}


async def mark_eval_status(model_id: int, job_id: str, status: str) -> dict:
    """평가 실패/취소 반영(완료는 get_eval_result 가 lazy 마감). 화이트리스트 +
    source_model_id 바인딩(다른 모델 job 마킹 차단). cancelled 면 컨테이너도 실제 취소."""
    if status not in ("failed", "cancelled"):
        raise ValueError(f"invalid eval status: {status!r}")
    if not job_id or not _JOB_ID_RE.match(job_id):
        raise ValueError(f"invalid job_id: {job_id!r}")
    # cancelled: DB만 표시하고 컨테이너가 계속 도는 상황 방지 — fb_external_container 에
    # cancel 전달(best-effort, 실패해도 DB 마킹은 진행).
    if status == "cancelled":
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                client = ExternalContainerClient(
                    base_url=settings.FB_EXTERNAL_CONTAINER_URL, client=http)
                await client.cancel_job(job_id)
        except Exception:
            traceback.print_exc()
    await db_model.update_eval_result_status(
        job_str_id=job_id, status=status, source_model_id=model_id)
    return {"job_id": job_id, "status": status}


async def list_eval_results(model_id: int) -> dict:
    """모델의 평가 이력 + 메트릭별 best 마킹(비교표, §14.12). 벤치마크 nested metrics 는
    averages 로 평탄화돼 self-metric(SP-5)·judge(후속) 런과 동일 flat 비교 shape 에 누적.
    공용 빌더(db_model.build_eval_comparison)로 llm_model 과 동일 shape 보장.
    ⚠️ authZ: 호출자 워크스페이스 ownership 미검증(IDOR) — 단, 플랫폼 authZ posture 가
    전 서비스 비활성(workspace_access_check 주석)이라 단일앱 분기 패치 안 함. 플랫폼 차원
    (SP-13) 일괄 해소 대상(레퍼런스 llm_model 동일). 모델별 eval 이력 열람 한정이라 영향 제한."""
    # 방치된 running 런을 조회 직전 정리(expert 제외). 벤치마크 완료는 lazy(폴링 시 metrics.json
    # 마감)라 'running' 이 곧 '고착'을 뜻하진 않는다 — 성공했으나 폴링 전 창을 닫으면 running 에
    # 남는다. 그래서 fail 전에 각 후보에 get_eval_result(재확인) 를 한 번 태워, metrics.json 이
    # 있으면 completed 로 마감하고(오분류 방지), 그 뒤에도 running 인 진짜 미완만 failed 로 넘긴다.
    # 전부 best-effort: 실패해도 이력 조회는 진행.
    try:
        stale = await db_model.list_stale_running_eval_results(
            source_model_id=model_id, max_age_hours=STALE_RUNNING_MAX_HOURS)
        for r in stale:
            try:
                await get_eval_result(model_id=model_id, job_id=r["job_str_id"])
            except Exception:
                traceback.print_exc()
        await db_model.fail_stale_eval_results(
            source_model_id=model_id, max_age_hours=STALE_RUNNING_MAX_HOURS)
    except Exception:
        traceback.print_exc()
    rows = await db_model.list_eval_results(source_model_id=model_id)
    return {"model_id": model_id, **db_model.build_eval_comparison(rows)}


async def delete_eval_run(model_id: int, job_id: str) -> dict:
    """평가 런 1건 삭제(이력 관리). 존재확인 후 삭제 — source_model_id 바인딩으로 다른 모델의
    런은 삭제 불가(없으면 not-found). expert 세션이면 FK ON DELETE CASCADE 로 채점/이력
    자식행도 함께 정리된다. authZ: list_eval_results 와 동일 IDOR posture(플랫폼 SP-13 일괄),
    단 source_model_id 바인딩으로 모델 경계 밖 삭제는 차단."""
    if not job_id or not _JOB_ID_RE.match(job_id):
        raise ValueError(f"invalid job_id: {job_id!r}")
    row = await db_model.get_eval_result_by_job(job_str_id=job_id, source_model_id=model_id)
    if not row:
        return {"job_id": job_id, "deleted": False, "reason": "not-found"}
    await db_model.delete_eval_result(job_str_id=job_id, source_model_id=model_id)
    return {"job_id": job_id, "deleted": True}


# 배포 위임 런의 shim endpoint → 배포(playground) id. metrics.generate.endpoint 는 컨테이너가
# 받은 generate_base_url 그대로(= _playground_shim_base_url 이 조립한 값)라 그 경로 규칙의 역이다.
# metrics.judge.endpoint(원격 심판)도 같은 조립기를 거치므로 같은 정규식이 그대로 맞는다.
_GENERATE_PLAYGROUND_RE = re.compile(r"/api/playgrounds/(\d+)/openai/v1")
# 배포 조회 동시 실행 상한(커넥션 풀이 없어 호출마다 새 커넥션이 열린다).
_DEPLOYMENT_LOOKUP_CONCURRENCY = 8


def _playground_json_field(value) -> Optional[str]:
    """playground.model JSON 값 정규화 — FE 가 빈 값을 문자열 'null' 로 넣는 필드가 있어
    (실측: model_allm_id='null') 없음과 같이 취급한다. 숫자로 저장된 id 도 문자열로 돌려준다."""
    if value is None:
        return None
    text = str(value).strip()
    return text if text and text.lower() not in ("null", "none") else None


async def _deployment_source(playground_id: int) -> Optional[dict]:
    """배포 1건 → 표시용 {name, model}. model 은 그 배포가 서빙하는 사람이 읽는 모델명 —
    playground.model JSON 에서 고른다: HF 직접 배포는 model_huggingface_id('Qwen/Qwen3-8B'),
    플랫폼 커밋 배포는 커밋 → 모델명(llm_playground 상세 조회와 같은 해석).
    실패/미상은 None — 호출자가 빌더 값을 그대로 둔다.

    workspace_id 를 함께 돌려주는 이유: 이 조회의 입력(배포 id)은 **외부 컨테이너가
    metrics.generate.endpoint 에 써 넣은 문자열**에서 나오므로 플랫폼이 검증한 값이 아니다.
    호출자가 런의 워크스페이스와 대조해 남의 배포 이름이 새어나가지 않게 막는다."""
    try:
        row = await db_playground.get_playground(int(playground_id))
        if not row:
            return None
        model = row.get("model")
        if isinstance(model, str):
            try:
                model = json.loads(model)
            except (TypeError, json.JSONDecodeError):
                model = None
        model = model if isinstance(model, dict) else {}
        served = _playground_json_field(model.get("model_huggingface_id"))
        # 가중치 식별자 — HF 직접 배포는 HF id 가 곧 가중치이고, 플랫폼 커밋 배포는 커밋 이름이다.
        # 비교표가 위임 런을 "배포 × 그때 서빙하던 커밋" 으로 가르는 근거(배포는 나중에 다른
        # 커밋으로 다시 올라갈 수 있다).
        weights = served
        if not served:
            commit_id = _playground_json_field(model.get("model_allm_commit_id"))
            if commit_id and commit_id.isdigit():
                commit = await db_model.get_commit_model(commit_id=int(commit_id))
                served = _playground_json_field((commit or {}).get("model_name"))
                weights = _playground_json_field((commit or {}).get("name"))
        return {"name": row.get("name"), "model": served, "commit": weights or None,
                "workspace_id": row.get("workspace_id")}
    except Exception:
        traceback.print_exc()
        return None


async def _frozen_deployment(section, run_ws) -> Optional[dict]:
    """metrics 의 한 섹션(generate | judge)이 가리키는 배포 → 표시용 {deployment, model}.

    생성 위임과 원격 심판은 **같은 shim URL 규칙**을 쓰므로(_playground_shim_base_url)
    해석도 하나로 둔다. 특히 워크스페이스 대조를 여기 한 곳에만 두려는 것이 목적이다 —
    두 벌로 복제하면 한쪽만 고쳐지는 순간 그쪽이 그대로 구멍이 된다.

    ⚠️ 배포 id 의 출처는 **컨테이너가 endpoint 에 써 넣은 문자열**이라 플랫폼이 검증한
    값이 아니다. 런의 워크스페이스와 같을 때만 돌려준다 — 대조 없이 조회하면 조작된
    endpoint 로 남의 배포 이름을 훑는 열거 오라클이 된다(_attach_run_sources 와 같은 규칙).
    믿을 수 없으면 **비운다**: 틀린 라벨보다 '-' 가 낫다.
    원격 위임이 아니거나(mode != 'remote') 해석 실패면 None — 호출자가 아무것도 새기지 않는다."""
    if not isinstance(section, dict) or section.get("mode") != "remote":
        return None
    endpoint = section.get("endpoint")
    found = (_GENERATE_PLAYGROUND_RE.search(endpoint)
             if isinstance(endpoint, str) else None)
    if not found or run_ws is None:
        return None
    source = await _deployment_source(int(found.group(1)))
    if not source:
        return None
    try:
        if int(source.get("workspace_id")) != int(run_ws):
            return None
    except (TypeError, ValueError):
        return None
    return {k: v for k, v in (("deployment", source.get("name")),
                              ("model", source.get("model")),
                              ("commit", source.get("commit"))) if v} or None


async def _freeze_run_source(metrics: dict, model_id: int, job_id: str) -> None:
    """위임 런의 출처 라벨을 metrics 에 **한 번** 새긴다(완료 마감 직전).
    생성 배포 → `_platform_source`, 원격 심판 배포 → `_platform_judge`.

    왜 굳히나 — 표시할 때마다 배포 행을 조회하던 옛 방식은 세 가지가 걸렸다:
      1) **배포를 지우면 라벨이 사라진다**(사용자 신고). 점수는 남는데 누가 냈는지가 없어진다.
      2) 목록 렌더마다 배포 테이블을 팬아웃 조회한다(커넥션 풀이 없어 비용이 그대로 붙는다).
      3) 워크스페이스 검증을 매번 다시 해야 한다.
    완료 시점에 한 번 해석해 박아 두면 셋 다 사라진다. 키를 `_` 로 시작시키는 이유는
    `_flatten_eval_metrics` 가 `_` 접두를 지표에서 걸러내기 때문 — 지표 목록을 오염시키지 않는다.
    심판 라벨(`_platform_judge`)도 같은 이유로 같은 자리에서 같은 규약으로 새긴다:
    LLM 심사 런의 '심판 배포' 컬럼이 심판 배포를 내린 뒤 사라지면 안 된다.

    ⚠️ 심판은 **표시 시점 폴백을 두지 않는다**. `_attach_run_sources` 의 live 조회는
    굳히기 기능이 생기기 전에 끝난 옛 생성 런을 위한 것이고, 심판 라벨에는 그런 과거가
    없다(이 기능과 함께 태어난다) → 폴백을 만들면 없앨 이유가 없는 표시 시점 조회를
    새로 들이는 셈이다. 굳히기에 실패한 런은 '-' 로 남는 것이 맞다.

    전부 best-effort — 여기서 실패해도 마감(complete_eval_result)은 그대로 진행한다."""
    try:
        if not isinstance(metrics, dict):
            return
        generate, judge = metrics.get("generate"), metrics.get("judge")
        # 어느 쪽도 원격 위임이 아니면 DB 를 두드릴 이유가 없다(정답 대조 런은 심판 섹션
        # 자체가 없고, 컨테이너 안 vLLM 심판은 배포가 아니라 굳힐 배포 id 가 없다).
        if not any(isinstance(sec, dict) and sec.get("mode") == "remote"
                   for sec in (generate, judge)):
            return
        row = await db_model.get_eval_result_by_job(
            job_str_id=job_id, source_model_id=model_id)
        run_ws = (row or {}).get("workspace_id")
        frozen_source = await _frozen_deployment(generate, run_ws)
        if frozen_source:
            metrics["_platform_source"] = frozen_source
        frozen_judge = await _frozen_deployment(judge, run_ws)
        if frozen_judge:
            metrics["_platform_judge"] = frozen_judge
    except Exception:
        traceback.print_exc()


async def _attach_run_sources(comparison: dict, rows: list) -> dict:
    """비교표 runs 중 **배포 위임** 런에 배포 이름·서빙 모델명을 채운다(빌더가 못 채우는 부분).

    공용 빌더(build_eval_comparison)는 원본 metrics 만 보므로 source_mode 까지만 판정한다 —
    metrics.generate.model 은 'playground-<id>' shim 식별자라 모델명이 아니고, 사람이 읽는
    이름은 배포 행에만 있다. 여기서 endpoint 의 배포 id 로 그 행을 읽어 채운다.
    같은 배포가 여러 런에 나오므로 **고유 id 만 한 번씩**(N+1 방지), 서로 독립이라 동시에
    조회한다. 전부 best-effort: 배포가 지워졌거나 조회가 실패하면 그 행은 빌더 값 그대로 두고
    목록 조회는 진행한다(읽기 전용 비교표가 배포 조회 하나로 죽으면 안 된다)."""
    # 완료 시점에 굳혀진 런(_platform_source)은 빌더가 이미 채워 왔으므로 조회 대상이 아니다 —
    # 굳히기 이전에 끝난 옛 런만 live 조회로 폴백한다. 새 런이 쌓일수록 조회는 0 으로 수렴한다.
    targets = [run for run in (comparison.get("runs") or [])
               if run.get("source_mode") == "deployment"
               and not (run.get("source_deployment") or run.get("source_model"))]
    if not targets:
        return comparison
    # run.id → 배포 id. 빌더가 원본 metrics 를 버리므로 endpoint 는 rows 에서 다시 읽는다.
    # ws_by_run 은 그 런이 속한 워크스페이스 — 아래에서 배포의 워크스페이스와 대조한다.
    by_run: dict = {}
    ws_by_run: dict = {}
    for row in rows:
        metrics = row.get("metrics")
        if isinstance(metrics, str):
            try:
                metrics = json.loads(metrics)
            except (TypeError, json.JSONDecodeError):
                continue
        if not isinstance(metrics, dict):
            continue
        generate = metrics.get("generate")
        endpoint = generate.get("endpoint") if isinstance(generate, dict) else None
        found = (_GENERATE_PLAYGROUND_RE.search(endpoint)
                 if isinstance(endpoint, str) else None)
        if found:
            by_run[row.get("id")] = int(found.group(1))
            ws_by_run[row.get("id")] = row.get("workspace_id")
    playground_ids = sorted(set(by_run.values()))
    if not playground_ids:
        return comparison
    # select_query 는 호출마다 새 커넥션을 연다(풀 없음) — 배포 id 가 늘어난 만큼 커넥션이
    # 동시에 열리지 않도록 상한을 둔다. 값은 llm_playground 의 running 배포 조회와 같은 8.
    sem = asyncio.Semaphore(_DEPLOYMENT_LOOKUP_CONCURRENCY)

    async def _guarded(pid):
        async with sem:
            return await _deployment_source(pid)

    resolved = dict(zip(playground_ids, await asyncio.gather(
        *(_guarded(pid) for pid in playground_ids))))
    for run in targets:
        run_id = run.get("id")
        source = resolved.get(by_run.get(run_id))
        if not source:
            continue
        # ⚠️ 배포 id 의 출처는 **컨테이너가 쓴 metrics.generate.endpoint** 다. 런 생성 때는
        # _resolve_remote_generator 가 워크스페이스를 대조해 남의 배포를 '없음'으로 접지만
        # (열거 오라클 차단), 표시 경로에는 그 검증이 없어 조작된 endpoint 로 임의 배포의
        # 이름·모델명을 훑을 수 있었다. 런의 워크스페이스와 같을 때만 채워 그 구멍을 막는다.
        run_ws, dep_ws = ws_by_run.get(run_id), source.get("workspace_id")
        try:
            same_ws = run_ws is not None and int(dep_ws) == int(run_ws)
        except (TypeError, ValueError):
            same_ws = False
        if not same_ws:
            continue
        if source.get("name"):
            run["source_deployment"] = source["name"]
        if source.get("model"):
            run["source_model"] = source["model"]
    return comparison


async def compare_models(model_ids: List[int]) -> dict:
    """교차모델 비교 경량 뷰(④, §14.12). 여러 모델의 평가 이력을 한 표에 합쳐
    메트릭별 best 를 **전역**(모델 무관) 으로 산출. 공용 빌더(build_eval_comparison)를
    그대로 재사용하되, 행마다 model_name 을 주입해 어느 모델 런인지 라벨링한다.

    단일모델 list_eval_results 와 달리 best 가 모델 경계를 넘어 계산되는 게 핵심
    (서로 다른 모델의 같은 메트릭을 직접 비교). 알 수 없는/접근불가 model_id 는 조용히
    건너뛰고(부분 성공) models 목록에 빠진다 — 비교는 best-effort 읽기 전용이라 단건 실패로
    전체를 막지 않는다.
    ⚠️ authZ: list_eval_results 와 동일하게 워크스페이스 ownership 미검증(IDOR) — 플랫폼
    posture 일괄(SP-13). 모델 eval 이력 열람 한정.
    """
    # 중복 제거(순서 보존) + 상한. 0개면 빈 비교표.
    seen: set = set()
    ordered: List[int] = []
    for mid in model_ids:
        if mid not in seen:
            seen.add(mid)
            ordered.append(mid)
    if len(ordered) > MAX_COMPARE_MODELS:
        raise ValueError(
            f"too many models to compare (max {MAX_COMPARE_MODELS})")

    # 모델별 (이름, rows) 를 동시 조회 — select_query 가 호출마다 새 커넥션을 열어(풀 X)
    # 직렬이면 모델당 connect 비용이 누적되므로 gather 로 병렬화. gather 는 입력 순서를
    # 보존하므로 ordered 순서가 그대로 유지된다.
    async def _fetch(mid: int):
        model_info = await db_model.get_model(model_id=mid)
        if not model_info:
            return None    # 알 수 없는 모델 — 건너뜀(부분 성공)
        model_name = model_info.get("name") or str(mid)
        rows = await db_model.list_eval_results(source_model_id=mid)
        # 공용 빌더가 run.model_name 으로 패스스루하도록 행에 라벨 주입(불변 — 새 dict).
        return {"id": mid, "name": model_name,
                "rows": [{**r, "model_name": model_name} for r in rows]}

    fetched = await asyncio.gather(*[_fetch(mid) for mid in ordered])
    models: list = []
    all_rows: list = []
    for item in fetched:
        if item is None:
            continue
        models.append({"id": item["id"], "name": item["name"]})
        all_rows.extend(item["rows"])
    comparison = await _attach_run_sources(
        db_model.build_eval_comparison(all_rows), all_rows)
    return {"models": models, **comparison}


# ── 런 단위 비교 (모델 축 → 런 축, P1) ──────────────────────────────────────────
# compare_models 는 모델을 받아 **모델별 최고 런**을 자동으로 뽑아 비교한다. 그래서 "모델 A의
# ckpt3 vs 모델 B의 ckpt1" 처럼 런을 지목할 수 없다. 아래 두 함수가 축을 런으로 바꾼다 —
# 피커 후보(list_comparable_runs)와 선택 런 비교(compare_runs).
# authZ: 이 축은 사용자에게서 **런 id 를 직접** 받으므로 compare_models 의 posture 를 물려받지
# 않는다. workspace_id 를 필수로 받아 DB 계층(list_eval_results_by_ids)의 쿼리에서 함께
# 필터한다 — 여기 서비스에서 사후에 거르지 않는다.

def _label_runs(comparison: dict, rows: list, projects_by_id: dict) -> dict:
    """비교표 runs 에 소속 프로젝트(id·이름)를 덧댄다. 공용 빌더는 eval_result 의 컬럼 중
    비교표 shape 에 정의된 것만 통과시키므로 eval_project_id 는 원본 rows 에서 되읽는다.
    프로젝트가 지워졌거나 프로젝트 없이 만들어진 옛 런은 이름 None(화면이 '-' 를 그린다)."""
    project_by_run = {r.get("id"): r.get("eval_project_id") for r in rows}
    for run in (comparison.get("runs") or []):
        project_id = project_by_run.get(run.get("id"))
        run["eval_project_id"] = project_id
        run["project_name"] = projects_by_id.get(project_id)
    return comparison


async def _build_run_comparison(rows: list, workspace_id: int) -> dict:
    """rows → 비교표. compare_models 와 **같은 조립 순서**(모델명 주입 → 공용 빌더 →
    배포 출처 보강)를 따르되, 라벨 소스가 모델 축이 아니라 워크스페이스 축이다.
    모델명·프로젝트명은 각각 목록조회 **한 번**으로 매핑한다 — 런 목록은 한 워크스페이스의
    전 런이라 행마다 조회하면 그대로 N+1 이 된다. 두 조회는 서로 독립이라 동시에 던진다."""
    models, projects = await asyncio.gather(
        db_model.get_models(workspace_id=workspace_id),
        db_model.list_eval_projects(workspace_id=workspace_id))
    names_by_model = {int(m["id"]): m.get("name")
                      for m in (models or []) if m.get("id") is not None}
    names_by_project = {int(p["id"]): p.get("name")
                        for p in (projects or []) if p.get("id") is not None}
    # 공용 빌더가 run.model_name 으로 패스스루하도록 행에 라벨 주입(불변 — 새 dict).
    labeled = []
    for r in rows:
        model_id = r.get("source_model_id")
        try:
            model_name = names_by_model.get(int(model_id))
        except (TypeError, ValueError):
            model_name = None
        labeled.append({**r, "model_name": model_name})
    comparison = await _attach_run_sources(
        db_model.build_eval_comparison(labeled), rows)
    return _label_runs(comparison, rows, names_by_project)


async def list_comparable_runs(workspace_id: int) -> dict:
    """비교 후보 런 목록(피커 소스). 워크스페이스의 채점 런 전부를 최신순으로, 점수와 함께
    "무엇이 이 점수를 냈나"(checkpoint/source_mode/source_model/source_deployment)를 실어
    돌려준다 — 같은 모델의 런이 여러 개일 때 점수만으로는 런을 고를 수 없기 때문이다.
    출처 4필드는 공용 빌더 + _attach_run_sources 재사용(로직 복제 X)."""
    rows = await db_model.list_eval_results_by_workspace(workspace_id=workspace_id)
    comparison = await _build_run_comparison(rows, workspace_id=workspace_id)
    return {"workspace_id": workspace_id, "runs": comparison.get("runs") or []}


async def compare_runs(workspace_id: int, run_ids: List[int]) -> dict:
    """선택한 런들만 모은 비교표. shape 은 compare_models(/compare)와 호환 — metric_keys /
    best / runs 는 그대로이고 best 만 **선택된 런 사이**에서 산출된다.

    datasets/dataset_consistent 가 이 축에서 새로 필요해진 부분이다. 지금까지 비교 가능성은
    "프로젝트가 데이터셋을 잠근다"가 보장했는데(같은 프로젝트 내 런은 같은 데이터셋), 비교가
    프로젝트를 가로지르면 그 보장이 사라진다. 서로 다른 데이터셋에서 나온 점수를 한 표에서
    비교하면 무의미하지만 **여기서 막지는 않는다** — 어느 데이터셋들이 섞였는지 사실만 싣고
    경고는 화면이 한다(읽기 전용 비교표가 사용자의 탐색을 차단하지 않는 기존 태도와 같다).

    알 수 없는/워크스페이스 밖 run_id 는 조용히 빠진다(부분 성공) — 존재/미존재를 구분해
    알려주면 그 자체가 열거 오라클이 된다."""
    # 중복 제거(순서 보존) + 상한. 0개면 빈 비교표.
    seen: set = set()
    ordered: List[int] = []
    for rid in run_ids:
        if rid not in seen:
            seen.add(rid)
            ordered.append(rid)
    if len(ordered) > MAX_COMPARE_RUNS:
        raise ValueError(f"too many runs to compare (max {MAX_COMPARE_RUNS})")

    # ⚠️ workspace_id 를 DB 계층에 그대로 넘긴다 — 필터는 쿼리 안에 있다(여기서 거르지 않음).
    rows = await db_model.list_eval_results_by_ids(
        result_ids=ordered, workspace_id=workspace_id)
    comparison = await _build_run_comparison(rows, workspace_id=workspace_id)
    # 선택 런들이 걸친 데이터셋(중복 제거, 최신 런 순). dataset_id 가 없는 옛 런은 이름만으로
    # 구분되지 않으므로 집계에서 뺀다 — 없는 값을 '1종'으로 세면 판정이 거짓 안전이 된다.
    datasets: list = []
    seen_datasets: set = set()
    for r in rows:
        dataset_id = r.get("dataset_id")
        if dataset_id is None or dataset_id in seen_datasets:
            continue
        seen_datasets.add(dataset_id)
        datasets.append({"dataset_id": dataset_id, "dataset_name": r.get("dataset_name")})
    return {**comparison, "datasets": datasets,
            "dataset_consistent": len(datasets) <= 1}


# ── 평가 프로젝트 관리 (2026-07-07) ──────────────────────────────────────────
# 관리 단위 = 프로젝트(유형·이름·워크스페이스). 생성=대기(created·run 0개, P5).
# 2026-08-24: 모델·데이터셋 잠금 해제 — run-start(benchmark/judge/expert/inference)가
# model_id/dataset_ids 를 **요청에서 받아** 쓴다. 프로젝트가 강제하는 것은 유형 게이트와
# 워크스페이스 경계 두 가지뿐이다(eval_result 가 이미 런 단위로 source_model_id/dataset_id
# 를 갖고 있어 신규 컬럼 없이 성립한다).
# authZ: 워크스페이스 ownership 미검증(IDOR) — 플랫폼 posture 일괄(SP-13), 기존 eval
# 엔드포인트와 동일하게 단일앱 분기 패치 안 함.

def _parse_dataset_ids(raw) -> List[int]:
    """eval_project.dataset_ids(JSON 컬럼)를 int 리스트로 정규화. 드라이버가 문자열/리스트
    어느 쪽으로 주든 방어(비정수 토큰은 조용히 스킵). 신규 프로젝트는 NULL → [] 이고,
    값이 남아 있는 것은 잠금 시절(P3)에 만들어진 옛 프로젝트뿐이다."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            raw = None
    if not isinstance(raw, list):
        return []
    out: List[int] = []
    for v in raw:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            continue
    return out


def _derive_project_status(statuses) -> str:
    """자식 run 상태에서 프로젝트 표시 상태를 파생(설계 §5). run 0개→created,
    running/pending 하나라도 있으면→running, run 이 있고 전부 종료면→completed.
    DB 의 status 컬럼은 run-start 시 'running' write 만 남는 레거시라, 표시는 읽기 시점
    파생이 정본(그래야 완료 프로젝트가 'completed' 에 도달)."""
    norm = [str(s or "").lower() for s in statuses]
    if not norm:
        return PROJECT_STATUS_CREATED
    if any(s in ("running", "pending") for s in norm):
        return PROJECT_STATUS_RUNNING
    return PROJECT_STATUS_COMPLETED


async def _load_project_for_run(project_id: int, eval_type=None):
    """run-start 공통 — 프로젝트 로드 + 유형 게이트. eval_type 지정 시 프로젝트 유형과 다른
    run 생성 거부(expert 프로젝트에 벤치마크 run 등 교차유형 차단). eval_type=None 이면
    게이트 생략(추론 러너 generate 는 type-agnostic — 유형 무관 output 생성).

    eval_type 은 단일 유형 문자열 또는 **허용 유형 집합**이다. 벤치마크 런은 reference 와
    judge 가 한 함수를 공유하므로(run_benchmark) 여기서는 둘 다 통과시키고, 어느 쪽인지는
    호출부가 고른 벤치마크와 대조해 좁힌다 — 이 함수는 벤치마크 목록을 모른다.

    ⚠️ 2026-08-24 부터 **데이터셋을 프로젝트에서 꺼내지 않는다** — 모델·데이터셋은 런이
    고르고(_resolve_run_model/_run_dataset_ids) 프로젝트는 유형·이름·워크스페이스만 고정한다."""
    project = await db_model.get_eval_project(project_id=project_id)
    if not project:
        raise Exception(f"eval project {project_id} not found")
    if eval_type is not None:
        accepted = (eval_type,) if isinstance(eval_type, str) else tuple(eval_type)
        if project.get("eval_type") not in accepted:
            want = " | ".join(repr(t) for t in accepted)
            raise Exception(
                f"project eval_type is {project.get('eval_type')!r}, not {want}")
    return project


async def _resolve_run_model(project: dict, model_id: int):
    """런이 고른 모델 해석 + 워크스페이스 경계 검증 → (model_info, workspace_id).

    프로젝트가 모델에 잠겨 있던 동안에는 workspace_id 를 모델에서 파생했기 때문에 이
    경계가 자동으로 성립했다. 이제 프로젝트가 워크스페이스를 소유하고 모델은 런이
    고르므로, 여기서 막지 않으면 다른 워크스페이스 모델의 점수가 이 프로젝트의
    eval_result 로 기록된다(생성 시점에 있던 검증을 런 시작으로 옮긴 것)."""
    workspace_id = int(project["workspace_id"])
    model_info = await db_model.get_model(model_id=model_id)
    if not model_info:
        raise Exception(f"model {model_id} not found")
    if int(model_info["workspace_id"]) != workspace_id:
        raise Exception("model and eval project belong to different workspaces")
    return model_info, workspace_id


def _run_dataset_ids(dataset_ids: List[int]) -> List[int]:
    """런이 고른 데이터셋 정규화 — 중복 제거(순서 보존) + 상한. 프로젝트 생성이 잠금 전에
    하던 정규화를 런 시작으로 옮긴 것이다. 존재·워크스페이스 경계 검증은 각 런 경로의
    기존 데이터셋 루프가 그대로 수행한다(그 루프가 이름·access 안전성까지 함께 본다)."""
    if not dataset_ids:
        raise ValueError("at least one dataset required")
    seen: set = set()
    out: List[int] = []
    for did in dataset_ids:
        did = int(did)
        if did in seen:
            continue
        seen.add(did)
        out.append(did)
    if len(out) > MAX_BENCHMARK_DATASETS:
        raise ValueError(f"too many datasets (max {MAX_BENCHMARK_DATASETS})")
    return out


def _normalize_project_description(description: Optional[str]) -> Optional[str]:
    """설명 입력 → 저장값. 공백만 남는 입력과 빈 문자열은 '설명 없음'(NULL)으로 접는다 —
    화면은 값이 없을 때 플레이스홀더를 세우는데, ' ' 가 저장되면 플레이스홀더도 설명도
    아닌 빈 칸이 남는다. 길이는 dto 가 경계에서 이미 막지만 여기서도 본다: service 는
    라우트 밖(다른 앱·스크립트)에서도 불릴 수 있고, 초과분은 거절하지 않으면 DB 에서
    조용히 잘린다."""
    if description is None:
        return None
    text = description.strip()
    if not text:
        return None
    if len(text) > EVAL_PROJECT_DESCRIPTION_MAX:
        raise ValueError(f"project description too long (max {EVAL_PROJECT_DESCRIPTION_MAX})")
    return text


async def create_project(name: str, eval_type: str, workspace_id: int,
                         creator: Optional[str] = None,
                         description: Optional[str] = None) -> dict:
    """평가 프로젝트 생성(대기 상태 created, run 0개, P5) — **유형·이름만** 고정한다.

    2026-08-24: 모델·데이터셋 잠금 해제. 무엇을 평가하는지는 런이 고르고(eval_result 가
    이미 런 단위로 source_model_id/dataset_id 를 갖는다), 프로젝트는 그 런들을 묶는
    관리 단위 + 워크스페이스 경계다. 모델이 빠지면서 워크스페이스를 파생할 원천이
    사라졌으므로 요청이 직접 준다 — 존재 여부는 여기서 검증한다(없는 워크스페이스로
    만들면 그 프로젝트에서는 어떤 모델도 경계 검증을 통과하지 못한다).
    creator 는 라우트가 jf-User 헤더로 주입.

    2026-08-27: description 은 선택 입력 — 목록 카드 본문에 실린다(update_project 로
    사후 수정 가능)."""
    if eval_type not in EVAL_TYPES:
        raise ValueError(f"unknown eval_type: {eval_type}")
    if not name or not name.strip():
        raise ValueError("project name required")
    if len(name) > 255:
        raise ValueError("project name too long")
    description = _normalize_project_description(description)
    workspace = await db_model.get_workspace_model(workspace_id=workspace_id)
    if not workspace:
        raise Exception(f"workspace {workspace_id} not found")
    # model_id/dataset_ids 는 신규 프로젝트에서 NULL 이다 — 잠금이 박혀 있던 옛
    # 프로젝트의 값을 보존하려고 컬럼만 남겼다(_parse_dataset_ids 가 NULL → [] 로 정규화).
    project_id = await db_model.create_eval_project(
        workspace_id=workspace_id, name=name.strip(), description=description,
        eval_type=eval_type, creator=creator)
    if not project_id:
        raise Exception("eval project create failed")
    # Galera service load-balances separate INSERT/SELECT connections. Give a
    # just-created row a short read-after-write window before surfacing not-found.
    for attempt in range(5):
        try:
            return await get_project(project_id=project_id)
        except Exception as e:
            if str(e) != f"eval project {project_id} not found" or attempt == 4:
                raise
            await asyncio.sleep(0.05 * (2 ** attempt))


async def list_projects(workspace_id: int) -> dict:
    """워크스페이스의 평가 프로젝트 목록(최신순). dataset_ids 는 JSON → 리스트로 정규화.
    표시 상태는 자식 run 상태에서 파생(§5) — N+1 회피 위해 run 상태를 한 번의 GROUP BY
    집계로 읽어 프로젝트별로 파생한다(집계에 없는 프로젝트=run 0개→created).
    update_datetime 은 DB 조회가 파생한 최근 run 생성 시각이며, 구버전 공용 DB 모듈과의
    롤링 배포 중에는 create_datetime 으로 안전하게 폴백한다."""
    projects = await db_model.list_eval_projects(workspace_id=workspace_id)
    project_ids = [int(p["id"]) for p in projects if p.get("id") is not None]
    status_rows = await db_model.count_run_statuses_by_projects(project_ids)
    by_project: dict = {}
    for row in status_rows:
        by_project.setdefault(int(row["eval_project_id"]), []).append(row.get("status"))
    out = [{**p, "dataset_ids": _parse_dataset_ids(p.get("dataset_ids")),
            "update_datetime": p.get("update_datetime") or p.get("create_datetime"),
            "status": _derive_project_status(by_project.get(int(p["id"]), []))}
           for p in projects]
    return {"workspace_id": workspace_id, "projects": out}


async def _attach_expert_run_view(runs: list, rows: list) -> None:
    """run 목록 표시 보강(in-place) — ① 세션 제목(run_name) ② 진행중 전문가 세션의 부분 집계.

    비교표(build_eval_comparison)는 `_` 접두 내부키를 버리므로, 사람이 시간에 걸쳐 채점하는
    전문가 세션은 전량 마감 전까지 목록에 점수가 하나도 안 보인다(완료 시에만 metrics 에
    expert_avg_score 가 기록됨). 완료 세션은 그 값이 이미 있으므로, 여기서는 아직 완료되지
    않은 전문가 세션만 채점 테이블에서 read-time 파생한다(GROUP BY 1회 — N+1 회피,
    list_projects 의 count_run_statuses_by_projects 와 동형)."""
    by_job = {r["job_str_id"]: r for r in rows if r.get("job_str_id")}
    pending = []
    for run in runs:
        row = by_job.get(run.get("job_id"))
        if row is None:
            continue
        name = _session_run_name(row)
        if name:
            run["run_name"] = name
        # 평가 세트 — 카드 표시 + 새 카드 생성 시 중복 비활성화의 근거. dataset_id 는 런 비교
        # shape 에 없어 여기서 같이 실어 준다(세트는 데이터셋별로 세므로 짝이 있어야 한다).
        sset = _session_sample_set(row)
        if sset:
            run["sample_set"] = sset
            run["dataset_id"] = row.get("dataset_id")
        if row.get("metric_set") == "expert" and row.get("status") != "completed":
            pending.append(run)
    if not pending:
        return
    agg = await db_model.aggregate_expert_ratings_by_jobs(
        [run["job_id"] for run in pending])
    by_agg = {a.get("job_str_id"): a for a in agg}
    for run in pending:
        samples = _session_metrics(by_job[run["job_id"]]).get("_samples")
        a = by_agg.get(run["job_id"]) or {}
        avg = a.get("avg_score")
        run["expert_progress"] = {
            "rated": int(a.get("rated") or 0),
            "total": len(samples) if isinstance(samples, list) else 0,
            # AVG() 는 Decimal 로 오므로 JSON 직렬화 가능한 float 로 정규화.
            "avg_score": round(float(avg), 2) if avg is not None else None,
        }


async def get_project(project_id: int) -> dict:
    """프로젝트 단건(헤더) + 자식 run 목록(프로젝트 내 비교표 shape). dataset_ids 는
    JSON → 리스트(신규 프로젝트는 []). runs 는 _build_run_comparison 재사용(run.id 키 best).
    ⚠️ 응답의 project.model_id 는 **NULL 일 수 있다** — 잠금 시절 프로젝트만 값이 남는다."""
    project = await db_model.get_eval_project(project_id=project_id)
    if not project:
        raise Exception(f"eval project {project_id} not found")
    rows = await db_model.list_eval_results_by_project(eval_project_id=project_id)
    # running 으로 남은 런은 조회 시점에 정리한다. 목록/헤더는 DB 상태를 그대로 보여주므로,
    # 결과 뷰를 열지 않으면 끝난 런·죽은 런이 '진행중'으로 계속 남는다. 정리는 결과 조회와 **같은
    # 마감**(_settle_running_run → get_eval_result)이다 — metrics.json 이 있으면 completed, 없으면
    # 컨테이너에 되물어 failed/cancelled. 종전엔 되묻기만 해서 컨테이너가 completed 라고 답한 런이
    # 결과 화면을 열기 전까지 '실행 중'으로 남았다(파드는 정리돼 사라져 죽은 것처럼 보였다).
    # 상한(MAX_RECONCILE_PER_VIEW)을 두는 이유는 목록 렌더가 외부 호출 수에 비례해
    # 느려지지 않게 하려는 것. best-effort — 실패해도 목록 조회는 그대로 진행한다.
    targets = [r for r in rows
               if r.get("status") == "running" and r.get("metric_set") != "inference"
               ][:MAX_RECONCILE_PER_VIEW]
    if targets:
        # 순차로 돌면 목록 렌더가 (호출수 x 타임아웃) 만큼 지연돼 게이트웨이 타임아웃을
        # 넘길 수 있다. 서로 독립된 조회라 동시에 던지고 한 번만 기다린다 —
        # 최대 대기가 호출 수와 무관하게 RECONCILE_TIMEOUT_SECONDS 로 고정된다.
        settled = await asyncio.gather(
            *(_settle_running_run(model_id=int(r["source_model_id"]),
                                  job_id=str(r["job_str_id"]))
              for r in targets),
            return_exceptions=True)
        for r, new_status in zip(targets, settled):
            if isinstance(new_status, str) and new_status != "running":
                r["status"] = new_status
    # 표시 상태는 자식 run 상태에서 파생(§5) — 단 러너 inference '생성' 런(metric_set='inference')은
    #   채점이 아니므로 상태 파생에서 제외(생성만 한 프로젝트가 completed 로 오분류 방지, 리뷰 HIGH).
    #   runs 목록엔 포함(FE 가 생성 배너·최신 inference job 추적에 사용, 표시 필터는 FE 담당).
    score_rows = [r for r in rows if r.get("metric_set") != "inference"]
    derived_status = _derive_project_status([r.get("status") for r in score_rows])
    # 런 행에 모델명 라벨 주입 — eval_result 엔 model_name 이 없다. 예전엔 프로젝트가
    # model_id 에 잠겨 있어 조회 한 번으로 전 행이 같은 값이었지만, 이제 런마다 모델이
    # 다를 수 있으므로 **런의 source_model_id 별로** 이름을 붙여야 한다. 워크스페이스
    # 모델 목록 조회 한 번으로 id→이름 맵을 만드는 _build_run_comparison 을 그대로
    # 재사용한다(행마다 조회하면 그대로 N+1). 비교표에 eval_project_id/project_name 이
    # 함께 실리는 것은 additive 이며, 이 뷰에서는 전 행이 이 프로젝트다.
    comparison = await _build_run_comparison(
        rows, workspace_id=int(project["workspace_id"]))
    # 목록 표시 보강(제목·진행중 전문가 부분집계) — 비교표 shape 는 그대로 두고 additive.
    await _attach_expert_run_view(comparison.get("runs") or [], rows)
    await _attach_run_progress(comparison.get("runs") or [])
    return {"project": {**project, "dataset_ids": _parse_dataset_ids(project.get("dataset_ids")),
                        "status": derived_status},
            "runs": comparison,
            # 실행(묶음) — 정답 대조 화면이 "한 번의 실행 = 카드 1장" 으로 런을 묶는 근거.
            # 묶음에 없는 런(단건 실행·묶음 기록 이전의 런)은 화면이 카드 한 장씩으로 세운다.
            "batches": await _project_batches(project_id)}


async def _settle_running_run(model_id: int, job_id: str) -> str:
    """running 런 하나를 결과 조회와 같은 경로로 마감하고 화면에 실을 상태를 돌려준다.
    get_eval_result 가 metrics.json 이 있으면 completed 로 마감하고, 없으면 DB 상태 → 컨테이너
    되묻기(_reconcile_running_eval)로 failed/cancelled 를 반영한다. 조회 실패는 호출부(gather)가 거른다."""
    res = await get_eval_result(model_id=model_id, job_id=job_id)
    if res.get("ready"):
        return "completed"
    return str(res.get("status") or "running")


async def finalize_finished_runs_once() -> int:
    """백그라운드 마감 한 바퀴 — metrics.json 이 생긴 running 런을 completed 로 마감하고 그 수를 돌려준다.

    벤치마크 완료는 lazy(결과 조회 시 metrics.json 을 보고 마감)라, 아무도 결과를 조회하지 않으면 끝난
    런이 running 에 남는다 — 프로젝트 목록의 상태·비교·Best 가 그 동안 틀린다. 이 루프가 조회 없이도
    맞춘다. 파일이 있는 런만 get_eval_result 로 마감한다(컨테이너 호출·실패 판정은 하지 않는다 — 그건
    조회 경로의 되묻기와 나이 기반 스윕 몫이다). 한 런의 실패가 나머지를 막지 않는다."""
    rows = await db_model.list_running_eval_results(limit=EVAL_FINALIZE_BATCH)
    bases = {}          # model_id → jobs 디렉토리(모델당 DB 조회 한 번)
    finalized = 0
    for r in rows:
        try:
            model_id = int(r["source_model_id"])
            job_id = str(r["job_str_id"])
            if model_id not in bases:
                bases[model_id] = await _eval_jobs_base(model_id)
            output_dir = await _eval_output_dir(model_id, job_id, jobs_base=bases[model_id])
            if not os.path.isfile(os.path.join(output_dir, "metrics.json")):
                continue
            res = await get_eval_result(model_id=model_id, job_id=job_id)
            if res.get("ready"):
                finalized += 1
        except Exception:
            traceback.print_exc()
    return finalized


async def finalize_finished_runs_loop() -> None:
    """finalize_finished_runs_once 를 EVAL_FINALIZE_INTERVAL_SECONDS 마다 — 서비스 기동 시 시작(main)."""
    while True:
        try:
            n = await finalize_finished_runs_once()
            if n:
                print(f"[eval] background finalize: {n} finished run(s) → completed", flush=True)
        except Exception:
            traceback.print_exc()
        await asyncio.sleep(EVAL_FINALIZE_INTERVAL_SECONDS)


async def _attach_run_progress(runs: list) -> None:
    """끝나지 않은 벤치마크 런 행에 채점기 진행(벤치마크별 상태·점수)을 싣는다(additive, in-place).

    실행 카드 목록은 결과를 폴링하지 않는다 — 이것이 없으면 도중에 멈춘 런이 카드에서는 "실패"로만
    보이고 끝난 벤치마크의 점수는 요약 화면에서만 보여, 같은 실행을 두 화면이 다르게 말한다.
    점수 요약(benchmarks)만 싣는다 — lm-eval 상세(partial_metrics)는 결과 조회(get_eval_result)가
    준다. 진행 기록이 없는 런(0.1.0 이하·위임 채점기)은 손대지 않는다. 전부 best-effort."""
    targets = [r for r in runs
               if r.get("status") != "completed" and r.get("job_id")
               and r.get("metric_set") not in ("inference", "expert")]
    targets.sort(key=lambda r: str(r.get("create_datetime") or ""), reverse=True)
    bases = {}          # model_id → jobs 디렉토리(모델당 DB 조회 한 번)
    for r in targets[:MAX_PROGRESS_PER_VIEW]:
        try:
            model_id = int(r["model_id"])
            if model_id not in bases:
                bases[model_id] = await _eval_jobs_base(model_id)
            output_dir = await _eval_output_dir(model_id, str(r["job_id"]),
                                                jobs_base=bases[model_id])
        except Exception:
            continue
        progress = _read_progress(output_dir)
        if progress:
            r["progress"] = {"benchmarks": progress["benchmarks"]}


async def _project_batches(project_id: int) -> list:
    """프로젝트의 실행(묶음) 목록. 조회 실패는 빈 목록 — 테이블이 아직 없는 DB(수동 마이그레이션
    전)에서도 프로젝트 화면은 떠야 한다(그때는 런마다 카드 한 장으로 보인다)."""
    try:
        batches = await db_model.list_eval_run_batches(eval_project_id=project_id)
    except Exception:
        traceback.print_exc()
        return []
    return [{"id": b["id"], "create_datetime": b.get("create_datetime"),
             "model_id": b.get("source_model_id"), "checkpoint": b.get("checkpoint"),
             "sample_limit": b.get("sample_limit"), "job_ids": b.get("job_ids") or [],
             # 런마다 담은 벤치마크({job_id: [...]}) — 한 런이 여러 벤치마크를 채점한다(§14).
             # 기록 이전 멤버는 비어 있다(화면이 metric_set 으로 되돌아간다).
             "job_benchmarks": b.get("job_benchmarks") or {},
             "launch_failures": b.get("launch_failures") or []}
            for b in batches]


async def delete_run_batch(project_id: int, batch_id: int) -> dict:
    """실행(묶음) 삭제 — 멤버 런을 지우고 묶음 행을 지운다(카드 한 장 = 실행 한 번이 지워지는 단위).
    다른 프로젝트의 묶음은 not-found 로 돌려준다(프로젝트 경계 — 삭제는 경로의 프로젝트 안에서만).
    멤버 런 삭제는 단건 삭제(delete_eval_run)와 같은 경로를 탄다 — source_model_id 바인딩 포함."""
    batch = await db_model.get_eval_run_batch(int(batch_id))
    if not batch or int(batch.get("eval_project_id") or 0) != int(project_id):
        return {"batch_id": batch_id, "deleted": False, "reason": "not-found"}
    model_id = int(batch["source_model_id"])
    for job_id in batch.get("job_ids") or []:
        # 도는 멤버는 행을 지우기 전에 컨테이너까지 취소한다(mark_eval_status) — 행만 지우면 잡이
        # GPU 를 쥔 채 계속 돈다. 화면은 먼저 취소하지만 API 를 직접 부르는 경로도 같아야 한다.
        # 취소는 best-effort(단건 삭제 화면 흐름과 같다) — 실패해도 삭제는 진행한다.
        row = await db_model.get_eval_result_by_job(job_str_id=job_id,
                                                    source_model_id=model_id)
        if row and row.get("status") == "running":
            try:
                await mark_eval_status(model_id, job_id, "cancelled")
            except Exception:
                traceback.print_exc()
        # 반환값(deleted/not-found)은 보지 않는다 — 한 묶음의 멤버는 전부 같은 모델이고(묶음 실행이
        # 한 model_id 로 띄운다), 따로 지워진 멤버는 FK CASCADE 로 이미 목록에서 빠져 있다.
        await delete_eval_run(model_id, job_id)
    await db_model.delete_eval_run_batch(int(batch_id))
    return {"batch_id": int(batch_id), "deleted": True, "runs": len(batch.get("job_ids") or [])}


async def update_project(project_id: int, description: Optional[str] = None) -> dict:
    """프로젝트 설명 수정. 존재확인 후 갱신하고 저장된 설명을 돌려준다(없으면 not-found
    를 사유와 함께 올린다 — get_project·compare_project_runs 와 같은 규약).

    ⚠️ 워크스페이스 경계: 이 경로는 **project_id 만으로** 동작한다 — 형제인
    delete_project 와 같은 수준이다. 배포 id 를 받는 네 경로에는
    _playground_in_workspace 대조가 있지만 그건 다른 문제를 푼다: 거기서는 요청이
    *두* 개의 경계(런의 워크스페이스와 배포의 워크스페이스)를 엮으므로, 대조하지
    않으면 남의 배포로 낸 출력이 이 워크스페이스의 점수로 기록된다. 여기는 엮을 두
    번째 경계가 없고 "요청자가 이 프로젝트에 접근할 수 있는가"만 남는데, 그 판정은
    이 서비스가 아니라 플랫폼의 workspace_access_check(전역 비활성 — SP-13)가 할 일로
    분류돼 있다. 삭제(더 파괴적인 연산)가 그 수준에 있는데 수정만 더 엄격하게 만들면
    같은 리소스에 두 개의 경계 규칙이 생겨 일관성이 깨지고, 나중에 SP-13 이 authZ 를
    켤 때 어느 쪽이 정본인지 알 수 없게 된다. 플랫폼 차원에서 함께 조인다."""
    project = await db_model.get_eval_project(project_id=project_id)
    if not project:
        raise Exception(f"eval project {project_id} not found")
    description = _normalize_project_description(description)
    await db_model.update_eval_project_description(
        project_id=project_id, description=description)
    # 응답은 형제 delete_project 처럼 가볍게 — 저장된 값(공백 정규화 후)만 돌려준다.
    # get_project 를 돌려주지 않는 이유: 그 경로는 running 런을 컨테이너에 되물어
    # 정리하고(외부 호출 N회 + 타임아웃) 런 비교표까지 조립한다. 설명 한 줄 저장이
    # 그 대가를 치를 이유가 없고, 더 나쁘게는 **텍스트 저장의 부수효과로 런 상태가
    # 바뀐다**. 화면은 이 응답으로 카드의 설명만 갈아 끼우면 된다.
    return {"project_id": project_id, "updated": True, "description": description}


async def delete_project(project_id: int) -> dict:
    """프로젝트 삭제 — FK ON DELETE CASCADE 로 자식 run + expert rating/history 전 체인 정리.
    존재확인 후 삭제(없으면 not-found)."""
    project = await db_model.get_eval_project(project_id=project_id)
    if not project:
        return {"project_id": project_id, "deleted": False, "reason": "not-found"}
    await db_model.delete_eval_project(project_id=project_id)
    return {"project_id": project_id, "deleted": True}


async def compare_project_runs(project_id: int) -> dict:
    """프로젝트 내 run 비교. run 단위 비교표(build_eval_comparison 재사용 — best 를
    run.id 에 키). 2026-08-24 부터 프로젝트가 model/dataset 을 잠그지 않으므로 같은
    프로젝트의 런들이 서로 다른 모델·데이터셋일 수 있다 — 무엇으로 낸 점수인지는 각 run
    행(source_model_id/dataset_name)에 실려 있고, 비교 가능성 경고는 화면이 한다
    (compare_runs 가 워크스페이스 축에서 이미 택한 태도와 같다)."""
    project = await db_model.get_eval_project(project_id=project_id)
    if not project:
        raise Exception(f"eval project {project_id} not found")
    rows = await db_model.list_eval_results_by_project(eval_project_id=project_id)
    # get_project 와 **같은 조립 순서**를 쓴다(모델명 주입 → 공용 빌더 → 출처 보강).
    # 공용 빌더를 직접 부르면 eval_result 에 없는 model_name 이 비고 _attach_run_sources
    # 도 건너뛴다 — 그러면 같은 런이 실행 목록에서는 모델·배포가 보이는데 이 비교 탭에서만
    # '-' 로 뜬다(2026-08-27 리뷰 HIGH). 형제 넷(get_project·compare_models·compare_runs·
    # list_comparable_runs)이 전부 이 순서를 따르므로 여기만 예외를 두지 않는다.
    comparison = await _build_run_comparison(
        rows, workspace_id=int(project["workspace_id"]))
    return {"project_id": project_id, **comparison}


# ── 외부 LLM endpoint SSRF 가드 — 지금은 **호출자가 없다**(휴면 자산) ──────────
# 2026-08-27: 자유 샘플 + 기준 4종 LLM-as-a-Judge(직접호출 오케스트레이션, 상용 API 키
# transient)는 제품에서 없앴다. 'judge' 유형은 이제 표준 심사 벤치마크(LogicKor)를 뜻하고
# 그 심판은 플랫폼 안(채점 컨테이너 또는 우리가 조립한 배포 URL)에서 돈다.
#
# 아래 가드를 남기는 이유는 constants.JUDGE_PROVIDER_HOSTS 를 남기는 이유와 같다 —
# 그쪽이 "상용 호스트는 우리가 고정한다"는 allowlist 라면 이쪽은 "사용자가 URL 을 주는
# 유일한 경우"의 방어 본체다. 예정된 '외부 API 배포' 작업이 같은 입력(사용자 endpoint)을
# 다시 받으므로 그때 이 함수를 배포 표면으로 옮긴다. 지금 지우면 DNS rebinding TOCTOU·
# 멀티레코드 우회·link-local 차단을 처음부터 다시 짜게 된다.
# ⚠️ apps/evaluate_intent/remote.py 와 apps/evaluate_logickor_judge/app.py 의 주석이
#    이 함수를 규약의 정본으로 지목하고 있다(컨테이너 쪽 가드가 이걸 베꼈다).


def _validate_local_url(base_url: Optional[str]) -> tuple:
    """외부 LLM endpoint SSRF 가드. 반환: (연결용 검증 IP, Host 헤더값).

    DNS rebinding TOCTOU 차단: 여기서 resolve 한 IP 를 호출부가 그대로 connect 에
    사용한다(httpx 재resolve 회피). 모든 resolve 결과를 검사(라운드로빈/멀티레코드 우회 방지).
    metadata(link-local 169.254/fe80)·multicast·unspecified 차단. loopback/private 는
    local LLM 특성상 허용(차단 시 기능 불가) — is_reserved 는 IPv6 loopback(::1)까지 잡아
    127.0.0.1 과 비일관이라 사용 안 함. (운영 egress 정책으로 추가 제한 권장.)"""
    if not base_url:
        raise Exception("local judge requires base_url")
    p = urlparse(base_url)
    if p.scheme not in ("http", "https"):
        raise Exception("base_url must be http or https")
    host = p.hostname
    if not host:
        raise Exception("invalid base_url host")
    if ".." in (p.path or ""):
        raise Exception("base_url path must not contain '..'")
    port = p.port or (443 if p.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port)
    except Exception:
        raise Exception("base_url host not resolvable")
    safe_ip = None
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            raise Exception("base_url resolves to a disallowed address")
        if safe_ip is None:
            safe_ip = info[4][0]
    if safe_ip is None:
        raise Exception("base_url host not resolvable")
    host_header = f"{host}:{p.port}" if p.port else host
    return safe_ip, host_header


async def list_benchmark_judge_models() -> dict:
    """LogicKor 심판 후보 — FE 는 이 목록만 렌더한다(하드코딩 금지).

    자유 입력을 주지 않는 이유는 constants.LOGICKOR_JUDGE_MODELS 주석 참조.
    hf_id 는 참고 표시용이며, 런 생성 시 넘기는 값은 id 다(서버가 hf_id 로 환산).
    """
    return {
        "models": [dict(m) for m in LOGICKOR_JUDGE_MODELS],
        "default": LOGICKOR_DEFAULT_JUDGE_ID,
    }


# ── A4 실 모델출력 배선 (실 데이터셋 읽기 + 배포모델 추론, mock 폴백) ──────────────
# input/reference 컬럼 자동 감지(여러 데이터셋 스키마 수용). Alpaca 류 단일 text 필드는
# "### Response:" 로 분리. 비수치 데이터셋은 첫 prompt 류 키를 input 으로.
_PROMPT_KEYS = ("prompt", "input", "question", "instruction", "query", "text")
_REFERENCE_KEYS = ("reference", "answer", "output", "completion", "response", "label",
                   "target", "caption")
_MAX_FIELD_LEN = 2000          # 샘플 필드 길이 cap(프롬프트/출력/참조)
_INFER_TIMEOUT = 60.0          # 추론 1건 타임아웃(초)
_VLM_INFER_TIMEOUT = 300.0     # VLM(external SDS) sync 추론 1건 타임아웃 — GPU 직렬이라 텍스트보다 김
# 이중모델(LLM1→LLM2) 체인 1건 타임아웃 — playground 측 예산 합계(LLM1 재작성 300s + LLM2 응답
#   1800s)에 맞춘다. 단일용 60s 를 그대로 쓰면 서버가 아직 정상 처리 중인데 클라이언트가 먼저
#   끊고, 그 예외가 _infer_output 에서 삼켜져 호출부가 mock 문자열을 채점 대상으로 채운다
#   (= 실제 추론이 아닌 플레이스홀더가 judge/전문가 점수에 들어간다).
_DUAL_INFER_TIMEOUT = 2100.0
_DATA_EXTS = (".jsonl", ".json", ".csv")
_MAX_DATA_FILE_BYTES = 50 * 1024 * 1024  # .json 전체 로드 상한(메모리 보호; jsonl/csv 는 스트리밍)
_EXPERT_INFER_BUDGET = 90      # start_expert 인라인 추론 전체 예산(초) — HTTP 핸들러 점유 cap
# 인라인 업그레이드 동시성. 순차로 돌리면 예산 안에 (배포 1건 지연 × 샘플 수)가 그대로
#   쌓여 느린 배포에서는 앞의 서너 개만 실출력이 되고 나머지는 **영구히** mock 으로 남는다
#   (텍스트 샘플에는 지연 업그레이드가 없다 — infer_expert_sample 은 VLM 전용).
#   상한을 두는 이유: 배포 하나의 추론 큐를 넘기면 개별 요청이 타임아웃으로 되돌아와
#   오히려 커버리지가 줄어든다(원격 심판 fan-out 과 같은 판단).
_EXPERT_INFER_CONCURRENCY = 6

# 멀티모달(VLM) 전문가 평가 — 데이터셋 row 의 이미지 컬럼을 surface 해 사람이 이미지를 보고
# 채점. 강한 이미지 컬럼명은 값 그대로, 약한(범용) 컬럼명은 이미지 확장자일 때만 채택(오탐 방지).
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # VLM 추론 image_base64 원본 상한(payload/메모리 방어)
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")
_IMAGE_KEYS_STRONG = ("image", "image_url", "image_path", "img", "img_url", "img_path",
                      "image_file")
_IMAGE_KEYS_WEAK = ("file_name", "filename", "file", "path", "picture", "photo")
_IMAGE_MEDIA = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}


def _looks_like_image(v: str) -> bool:
    path = urlparse(v).path if "://" in v else v
    return os.path.splitext(path.split("?")[0])[1].lower() in _IMAGE_EXTS


def _pick_image(row: dict) -> Optional[str]:
    """row 에서 이미지 참조(URL 또는 상대경로) 1건. 강한 컬럼명은 값 그대로, 약한 컬럼명은
    이미지 확장자일 때만. 못 찾으면 None(텍스트-only 데이터셋은 영향 없음)."""
    lower = {str(k).lower(): k for k in row.keys()}

    def _val(key):
        actual = lower.get(key)
        v = row.get(actual) if actual is not None else None
        if not isinstance(v, str):
            return None
        v = v.strip()
        return v[:_MAX_FIELD_LEN] if v else None

    for k in _IMAGE_KEYS_STRONG:
        v = _val(k)
        if v:
            return v
    for k in _IMAGE_KEYS_WEAK:
        v = _val(k)
        if v and _looks_like_image(v):
            return v
    return None


def _first_key(row: dict, keys) -> Optional[str]:
    for k in keys:
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return str(v)
    return None


def _split_alpaca(text: str):
    """Alpaca 류 '### Instruction:..\\n### Response:..' → (input, reference). 마커 없으면
    전체를 input 으로(reference 없음)."""
    resp_marker = re.search(r"###\s*Response\s*:\s*", text, re.IGNORECASE)
    if not resp_marker:
        instr = re.sub(r"###\s*Instruction\s*:\s*", "", text, flags=re.IGNORECASE)
        return instr.strip(), ""
    inp = text[:resp_marker.start()]
    inp = re.sub(r"###\s*Instruction\s*:\s*", "", inp, flags=re.IGNORECASE).strip()
    ref = text[resp_marker.end():].strip()
    return inp, ref


def _row_to_sample(row: dict):
    """데이터셋 row(dict) → {"input","reference", "image"?} 또는 None. 명시 prompt/reference
    컬럼 우선, 없고 text 단일 필드면 Alpaca 분리. 이미지 컬럼이 있으면 image 부착 — VLM 은
    이미지가 곧 입력이므로 텍스트 입력이 없어도(image-only) 샘플로 인정."""
    if not isinstance(row, dict):
        return None
    img = _pick_image(row)
    # text 단일 필드(prompt 컬럼 부재) → Alpaca 분리
    has_explicit = any(k in row for k in _PROMPT_KEYS if k != "text")
    if not has_explicit and isinstance(row.get("text"), str):
        inp, alpaca_ref = _split_alpaca(row["text"])
        # 명시 reference 컬럼(output/answer/caption 등)이 있으면 우선 — {"text":q,"output":a}
        # 류에서 Alpaca 마커가 없어도 reference 를 잃지 않도록.
        ref = _first_key(row, _REFERENCE_KEYS) or alpaca_ref
    else:
        inp = _first_key(row, _PROMPT_KEYS) or ""
        ref = _first_key(row, _REFERENCE_KEYS) or ""
    # 텍스트 입력도 이미지도 없으면 샘플 아님.
    if not inp and not img:
        return None
    out = {"input": inp, "reference": ref}
    if img:
        out["image"] = img
    return out


def _read_data_file(path: str, need: int) -> list:
    """jsonl/json/csv 파일에서 (input, reference) 샘플을 need 개까지. 실패 시 빈 리스트."""
    out = []
    try:
        if path.endswith(".jsonl"):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        s = _row_to_sample(json.loads(line))
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if s:
                        out.append(s)
                        if len(out) >= need:
                            break
        elif path.endswith(".json"):
            if os.path.getsize(path) > _MAX_DATA_FILE_BYTES:
                return out    # 과대 .json 전체 로드 회피(jsonl 과 달리 스트리밍 불가)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            rows = data if isinstance(data, list) else data.get("data") if isinstance(data, dict) else None
            for row in (rows or []):
                s = _row_to_sample(row)
                if s:
                    out.append(s)
                    if len(out) >= need:
                        break
        elif path.endswith(".csv"):
            with open(path, encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    s = _row_to_sample(row)
                    if s:
                        out.append(s)
                        if len(out) >= need:
                            break
    except (OSError, ValueError):
        traceback.print_exc()
    return out


def _attach_image(sample: dict, raw: str, data_file_path: str, ddir_real: str) -> None:
    """이미지 참조를 샘플에 부착. http(s) URL 은 image_url 로 그대로(FE 직접 렌더). 상대경로는
    데이터파일 디렉터리(없으면 데이터셋 루트) 기준으로 해석하되 데이터셋 디렉터리 내부로 봉쇄
    (다른 워크스페이스/시스템 파일 노출 차단) 후 절대경로를 _image_abs(서버측 전용, FE 미노출)
    에 보관 — 서빙 엔드포인트가 이 경로만 스트리밍. 해석 실패 시 image(raw)만 남고 텍스트 채점은
    계속(렌더는 FE 가 무시)."""
    low = raw.lower()
    is_url = low.startswith("http://") or low.startswith("https://")
    # 공개 image 필드(FE alt 표시용)는 URL 은 그대로, 로컬 경로는 basename 만 — NFS 절대경로/
    # 디렉터리 구조 누출 차단. 실제 절대경로는 _image_abs(서버 전용)에만.
    sample["image"] = raw if is_url else (os.path.basename(raw) or "image")
    if is_url:
        sample["image_url"] = raw
        return
    try:
        for cand in (os.path.join(os.path.dirname(data_file_path), raw),
                     os.path.join(ddir_real, raw)):
            real = os.path.realpath(cand)
            if (os.path.commonpath([real, ddir_real]) == ddir_real
                    and os.path.isfile(real)
                    and os.path.splitext(real)[1].lower() in _IMAGE_EXTS):
                sample["_image_abs"] = real
                sample["_image_dir"] = ddir_real    # 서빙 시 재봉쇄(심링크 스왑 방어)
                sample["image_served"] = True
                return
    except (ValueError, OSError):
        pass    # commonpath 드라이브 불일치/접근 오류 — 렌더 불가(텍스트 채점 계속)


# ── SDS 샘플당 디렉토리 레이아웃 빌더 (tango_sds-*/ = csv + png + txt) ──────────
# 실측상 SDS 데이터셋은 행/열이 아니라 샘플당 서브디렉토리로 저장돼 기존 파일-워크 빌더가
# 0 샘플 → mock 폴백(미동작)이었다. 여기서 디렉토리 1개=샘플 1개로 CSV 인라인 + 이미지
# blob(_attach_image 재사용) + output_*.txt reference 로 실 샘플을 만든다.
_MAX_CSV_BYTES = 1 * 1024 * 1024   # per-sample input_data.csv 전량 로드 상한(실측 ~수백B)
_MAX_CSV_ROWS = 200                # 표 행 상한(과대 CSV 방어)
_MAX_CSV_COLS = 50                 # 표 열 상한
_MAX_CSV_CELL = 500                # 셀 문자열 길이 상한


def _read_csv_grid(path: str, ddir_real: str):
    """input_data.csv → (rows2d, raw_text). 작은 표라 전량 로드하되 크기/행/열/셀 상한으로
    방어. 선택 파일은 데이터셋 디렉터리 내부로 재봉쇄(심링크 이탈 차단) 후 읽는다.
    실패/부재 시 (None, None) — 호출자가 CSV 없는 샘플로 graceful 처리."""
    try:
        real = os.path.realpath(path)
        if os.path.commonpath([real, ddir_real]) != ddir_real:
            return None, None    # csv 가 데이터셋 디렉터리 밖을 가리키는 심링크 — 스킵
        if not os.path.isfile(real) or os.path.getsize(real) > _MAX_CSV_BYTES:
            return None, None
        with open(real, encoding="utf-8", newline="") as f:
            text = f.read()
        rows = []
        for i, row in enumerate(csv.reader(io.StringIO(text))):
            if i >= _MAX_CSV_ROWS:
                break
            rows.append([str(c)[:_MAX_CSV_CELL] for c in row[:_MAX_CSV_COLS]])
        return (rows or None), text[:_MAX_FIELD_LEN]
    except (OSError, ValueError, csv.Error, UnicodeDecodeError):
        return None, None


def _sds_reference(sd_real: str, ddir_real: str) -> str:
    """SDS 서브디렉토리의 output_*.txt 에서 reference 선택 — advice_kor 우선, 없으면 정렬 첫.
    선택 파일은 데이터셋 디렉터리 내부로 재봉쇄(심링크 이탈 차단) 후 읽는다. 없으면 ''."""
    try:
        cands = sorted(glob.glob(os.path.join(sd_real, EXPERT_OUTPUT_GLOB)))
    except (OSError, ValueError):
        return ""
    if not cands:
        return ""
    preferred = os.path.join(sd_real, EXPERT_REFERENCE_FILENAME)
    path = preferred if preferred in cands else cands[0]
    try:
        real = os.path.realpath(path)
        if os.path.commonpath([real, ddir_real]) != ddir_real:
            return ""    # output 파일이 데이터셋 디렉터리 밖을 가리키는 심링크 — 스킵
        if not os.path.isfile(real) or os.path.getsize(real) > _MAX_DATA_FILE_BYTES:
            return ""
        with open(real, encoding="utf-8") as f:
            return f.read()[:_MAX_FIELD_LEN].strip()
    except (OSError, ValueError, UnicodeDecodeError):
        return ""


def _read_sds_samples(ddir_real: str, ds_name: str, need: int):
    """SDS 레이아웃(tango_sds-*/ 서브디렉토리)이면 디렉토리 1개=샘플 1개 리스트를, 아니면
    None(레이아웃 부재 — 호출자가 기존 파일-워크로 폴백)을 반환. 각 샘플: input_data.csv 인라인
    (csv_rows 2D + csv_text), input_image.png 는 _attach_image 재사용(image_served·commonpath
    봉쇄·_image_abs 서버전용), reference 는 output_*.txt(D4 로 FE 미표시하나 계약 유지)."""
    try:
        subdirs = sorted(
            d for d in glob.glob(os.path.join(ddir_real, SDS_SAMPLE_DIR_GLOB))
            if os.path.isdir(d))
    except (OSError, ValueError):
        return None
    if not subdirs:
        return None    # SDS 레이아웃 아님 → 파일-워크 폴백
    out = []
    for sd in subdirs:
        if len(out) >= need:
            break
        # 서브디렉토리 봉쇄 — ddir 밖을 가리키는 심링크면 스킵(다른 워크스페이스 노출 차단).
        sd_real = os.path.realpath(sd)
        try:
            if os.path.commonpath([sd_real, ddir_real]) != ddir_real:
                continue
        except (ValueError, OSError):
            continue
        csv_path = os.path.join(sd_real, EXPERT_CSV_FILENAME)
        csv_rows, csv_text = _read_csv_grid(csv_path, ddir_real)
        sample = {"input": "", "reference": _sds_reference(sd_real, ddir_real),
                  "dataset": ds_name}
        if csv_rows:
            sample["csv_rows"] = csv_rows
            sample["csv_text"] = csv_text
        img_path = os.path.join(sd_real, EXPERT_IMAGE_FILENAME)
        if os.path.isfile(img_path):
            # raw=basename, data_file_path=csv_path → _attach_image 후보1(csv 디렉터리 기준)
            # 이 sd_real/input_image.png 로 해석·봉쇄. _image_dir=ddir_real 로 서빙 재봉쇄.
            _attach_image(sample, EXPERT_IMAGE_FILENAME, csv_path, ddir_real)
        # csv·이미지 둘 다 없으면 빈 디렉터리 — 샘플로 인정 안 함(mock 오염 방지).
        if not csv_rows and not sample.get("image_served"):
            continue
        out.append(sample)
    # 유효 샘플 0 개면 None 반환 — 호출자가 기존 행/열 파일-워크로 폴백(빈 리스트는 폴백 shadow).
    return out or None


async def _read_dataset_samples(dataset_ids: List[int], limit: int, offset: int = 0) -> list:
    """워크스페이스 NFS 데이터셋에서 (input, reference) 샘플을 limit 개까지 읽는다.
    eval pod 가 /jf-data 를 마운트(get_eval_result 의 metrics.json 읽기와 동일 마운트).
    파일 없음/포맷 불일치(arrow 등) → 빈 리스트 → 호출자가 mock 으로 폴백.

    offset 은 평가 세트(100개씩 10구간)용. 하위 리더(파일워크·SDS 서브디렉토리)는 "앞에서부터
    N개"만 지원하므로 offset+limit 을 읽고 앞을 버린다 — 상한이 MAX_EXPERT_SAMPLES(1000)라
    전량 읽기와 같은 비용이고, 무엇보다 리더마다 offset 을 심는 것보다 어긋날 여지가 없다."""
    need = max(0, int(offset)) + limit
    samples = []
    for did in dataset_ids:
        if len(samples) >= need:
            break
        try:
            ds = await db_model.get_dataset_model(dataset_id=did)
            if not ds:
                continue
            ws = await db_model.get_workspace_model(workspace_id=int(ds["workspace_id"]))
            if not ws or not ws.get("data_storage_name"):
                continue
            # 경로 세그먼트 검증 — access/name/storage 가 DB 값이라도 '..'·'/' 가 섞이면
            # ddir 자체가 NFS 루트를 이탈할 수 있고, 그러면 아래 commonpath 가드(ddir 기준)는
            # 무력해진다. 안전 문자만 허용하고 아니면 스킵(→ mock 폴백). 비안전명 데이터셋은
            # 실 데이터 미독해로 graceful degrade.
            segs = [str(ds.get("access")), str(ds.get("name")),
                    str(ws.get("data_storage_name")), str(ws.get("name"))]
            if not all(_SAFE_SEGMENT_RE.match(s) for s in segs):
                continue
            ddir = PATH.JF_DATA_DATASET_PATH.format(
                STORAGE_NAME=ws["data_storage_name"], WORKSPACE_NAME=ws["name"],
                ACCESS=ds["access"], DATASET_NAME=ds["name"])
            ddir_real = os.path.realpath(ddir)
            if not os.path.isdir(ddir_real):
                continue
            # SDS(샘플당 디렉토리) 레이아웃 우선 — tango_sds-*/ 서브디렉토리가 있으면
            # 디렉토리-워크 빌더(CSV 인라인 + 이미지 blob)로. 레이아웃 부재 시 None → 기존
            # 행/열 파일-워크로 자연 폴백(graceful, 일반 데이터셋 무영향).
            sds = _read_sds_samples(ddir_real, str(ds["name"]), need - len(samples))
            if sds is not None:
                samples.extend(sds)
                continue
            files = sorted(
                os.path.join(r, fn)
                for r, _dirs, fns in os.walk(ddir_real)
                for fn in fns if fn.lower().endswith(_DATA_EXTS))
            for fp in files:
                if len(samples) >= need:
                    break
                # 경로 봉쇄(심링크 이탈 방지) — 다른 워크스페이스 파일 읽기 차단.
                if os.path.commonpath([os.path.realpath(fp), ddir_real]) != ddir_real:
                    continue
                for rec in _read_data_file(fp, need - len(samples)):
                    sample = {
                        "input": rec["input"][:_MAX_FIELD_LEN],
                        "reference": (rec.get("reference") or "")[:_MAX_FIELD_LEN],
                        "dataset": str(ds["name"]),
                    }
                    if rec.get("image"):
                        _attach_image(sample, rec["image"], fp, ddir_real)
                    samples.append(sample)
                    if len(samples) >= need:
                        break
        except Exception:
            traceback.print_exc()
            continue
    # 앞의 offset 개는 다른 세트의 몫 — 여기서 버린다(부족하면 빈 리스트 = 그 세트는 없음).
    return samples[max(0, int(offset)):]


async def _resolve_inference_target(playground_id: Optional[int]) -> Optional[dict]:
    """배포 모델의 추론 대상을 playground s2s(get_test_options) 한 번으로 해석한다.
    단일은 기존 direct URL, 저장 링크가 있는 이중은 /playgrounds/test 합성 경로를 반환한다.

    ⚠️ **소유권을 검증하지 않는다** — 받은 playground_id 를 그대로 믿고 부른다. 워크스페이스
    경계는 호출자가 먼저 대조한다: 지금 두 호출자(run_eval_inference 의 러너 태스크·
    start_expert)가 전부 _playground_in_workspace 로 대조한 id 만 넘긴다(러너의 전용 할당
    경로는 자기가 만든 배포다). 여기서 검증하지 않는 이유: 이 함수는 workspace_id 를 모르고,
    실패를 None 으로 접는 계약이라(호출자가 사유를 정한다) 경계 위반이 '대상 없음'으로
    조용히 섞인다 — 새 호출자를 붙이면 그쪽에서 먼저 대조해야 한다."""
    if not playground_id:
        return None
    try:
        url = (f"http://{settings.LLM_PLAYGROUND_DNS}"
               f"/api/playgrounds/test/options?playground_id={int(playground_id)}")
        async with httpx.AsyncClient(timeout=10.0) as http:
            r = await http.get(url)
        if r.status_code != 200:
            # 실 추론이 mock 으로 조용히 폴백된 원인을 운영에서 추적 가능하게(키 노출 없음).
            print(f"_resolve_inference_target: playground {playground_id} HTTP {r.status_code}",
                  flush=True)
            return None
        data = r.json()
        if data.get("status") == 1:
            result = data.get("result") or {}
            if result.get("prompt_gen_playground_id") is not None:
                # 이중 세션을 LLM2 pod URL로 직접 호출하면 LLM1 최적화가 빠지므로 BFF 체인을 사용한다.
                return {
                    "url": (
                        f"http://{settings.LLM_PLAYGROUND_DNS}"
                        "/api/playgrounds/test"
                    ),
                    "playground_id": int(playground_id),
                }
            test_url = result.get("test_url")
            return {"url": test_url, "playground_id": None} if test_url else None
        print(f"_resolve_inference_target: playground {playground_id} envelope status="
              f"{data.get('status')}", flush=True)
    except Exception:
        traceback.print_exc()
    return None


async def _playground_detail(playground_id: int) -> Optional[dict]:
    """GET /playgrounds/{id} 상세 s2s — envelope 를 벗겨 result 만 돌려준다.
    실패/비정상 envelope → None(호출자가 사유를 정한다)."""
    url = (f"http://{settings.LLM_PLAYGROUND_DNS}"
           f"/api/playgrounds/{int(playground_id)}")
    async with httpx.AsyncClient(timeout=10.0) as http:
        r = await http.get(url)
    if r.status_code != 200:
        return None
    data = r.json()
    if not isinstance(data, dict) or data.get("status") != 1:
        return None
    result = data.get("result")
    return result if isinstance(result, dict) else None


async def _playground_in_workspace(label: str, playground_id: int,
                                   workspace_id: int) -> dict:
    """배포가 이 런의 워크스페이스 것인지 대조하고 상세(detail)를 돌려준다 — 배포 id 를
    요청에서 받는 **네 경로**(생성 위임·원격 심판·추론 러너·전문가 세션)가 공유하는 단일
    규칙이다.

    한 벌로 뽑은 이유: 같은 규칙이 복제돼 있으면 한쪽만 고쳐지는 순간 그쪽이 구멍이 된다.
    실제로 이 검증은 생성·심판 두 곳에만 있었고 러너·전문가 경로는 열려 있었다(2026-08-27).

    실패는 셋 다 **거절**이다 — 못 믿으면 조용한 통과가 아니라 거절이다:
      - 조회 자체 실패 → 사유를 붙여 올린다('없음'으로 접으면 원인이 사라진다)
      - 상세 없음 / 워크스페이스 불일치 → **같은 문구**로 접는다(열거 오라클 방지)
      - workspace_id 를 못 읽으면 or 0 으로 떨어져 불일치가 된다(fail-closed)
    label 은 메시지 접두사("inference"/"judge")로만 쓴다 — 화면이 envelope 의 message 를
    그대로 세우므로 기존 문구를 바꾸지 않는다. detail 을 돌려주는 것은 호출자가 이어서
    보는 값(서빙 모델·temperature)을 위해 왕복을 한 번으로 끝내기 위함이다."""
    pid = int(playground_id)
    try:
        detail = await _playground_detail(pid)
    except Exception as e:
        raise Exception(f"{label} playground {pid} 조회 실패: {e}") from e
    if not detail:
        raise Exception(f"{label} playground {pid} 를 찾을 수 없습니다")
    if int(((detail.get("info") or {}).get("workspace_id")) or 0) != int(workspace_id):
        raise Exception(f"{label} playground {pid} 를 찾을 수 없습니다")
    return detail


async def _playground_status(playground_id: int) -> Optional[str]:
    """배포 집계 상태 1건 s2s(status-sync). 조회 자체가 실패하면 예외를 올린다 —
    호출자가 '못 물어봤다'와 'running 이 아니다'를 구분해야 하기 때문이다."""
    url = (f"http://{settings.LLM_PLAYGROUND_DNS}"
           f"/api/playgrounds/status-sync/{int(playground_id)}")
    async with httpx.AsyncClient(timeout=10.0) as http:
        r = await http.get(url)
    return (r.json().get("result") or {}).get("status")


async def _resolve_deploy_system_prompt(playground_id: Optional[int]) -> Optional[str]:
    """바인드된 배포(playground)의 생성 시스템 프롬프트(prompt.system_message)를 s2s 로 해석.
    러너를 안 쓴 현행 배포-바인드 경로(전문가 SDS 등)에서 헤더 고정 박스에 '실제 생성에 쓰인
    시스템 프롬프트'를 표시하기 위함(표시=실사용 일치, P3). GET /playgrounds/{id} →
    result.prompt.system_message. 미지정/실패/빈값 → None(박스 숨김)."""
    if not playground_id:
        return None
    try:
        detail = await _playground_detail(int(playground_id))
        prompt = (detail or {}).get("prompt") or {}
        msg = prompt.get("system_message")
        if isinstance(msg, str) and msg.strip():
            return msg.strip()[:_MAX_FIELD_LEN]
    except Exception:
        traceback.print_exc()
    return None


def _playground_shim_base_url(playground_id: int) -> str:
    """컨테이너가 호출할 OpenAI 호환 base — llm_playground 의 플랫폼 shim.

    원격 심판(judge_base_url)과 원격 생성(generate_base_url)이 **같은 규칙**을 쓴다 —
    가리키는 대상이 같은 shim 이므로 URL 조립을 두 곳에 두지 않는다.

    ⚠️ **규칙 중복이다.** 정본은 llm_playground service.`_shim_llm_url` 이고 이 문자열은
    그 복제다. s2s 로 받아오지 않은 이유: 그러려면 "이 배포의 shim base 를 알려달라"는
    라우트를 llm_playground 에 새로 내야 하는데, 그 응답은 이 서비스가 이미 갖고 있는
    값(LLM_PLAYGROUND_DNS)과 고정 경로의 결합일 뿐이라 왕복 한 번을 더 사는 값이 없다.
    같은 이유로 이 서비스는 /api/playgrounds/test·status-sync 경로도 직접 조립한다.
    깨질 수 있는 지점이므로 shim 경로가 바뀌면 이 함수도 함께 고쳐야 한다.
    """
    return (f"http://{settings.LLM_PLAYGROUND_DNS}:80"
            f"/api/playgrounds/{int(playground_id)}/openai/v1")


async def _resolve_deployment_checkpoint(inference_playground_id: int, model_id: int,
                                         workspace_id: int, purpose: str,
                                         off_hint: Optional[str]) -> str:
    """로컬 가중치 런(포맷 학습 · lm-eval 채점)이 마운트할 체크포인트 **이름**을 고른 배포에서
    역으로 푼다. purpose 는 오류 문구의 주어, off_hint 는 "이 옵션을 끄면 된다" 안내(없으면 생략).

    왜 요청이 아니라 배포에서 푸나 — `commit_id` 는 요청 필드로 폐기됐다
    (dto.`_reject_commit_id`). 폐기 사유가 "사용자가 고른 체크포인트"와 "실제로 점수를 낸
    가중치"가 어긋나던 것이었으므로, 되살리면 같은 어긋남을 다시 들인다. 배포는 자기가 어떤
    커밋을 올렸는지 이미 알고 있고(playground 상세가 커밋을 조인해 내려준다) 화면은 그 배포를
    이미 고르게 하므로, 여기서 역으로 풀면 두 값이 어긋날 자리 자체가 없어진다.

    _resolve_remote_generator 와 다른 점 둘:
      1) **running 을 보지 않는다.** 이 경로에서 배포는 생성을 하지 않는다 — 학습도 생성도
         채점기가 자기 GPU 에서 한다. 커밋은 배포가 내려가 있어도 그대로이므로, 실행 중을
         요구하면 쓰지도 않을 GPU 한 장을 이유 없이 더 붙들게 한다.
      2) **모델 확인 실패를 통과시키지 않는다.** 저쪽은 식별자를 못 읽으면 경고만 남기고
         진행하는데(정상 배포까지 막지 않으려고), 이쪽은 못 읽으면 **엉뚱한 가중치를 마운트해
         학습까지 시킨다**. 확인 못 하면 거절이 맞다.

    이름만 돌려주는 것은 플랫폼 규약이다 — 경로를 넘기면 params 로 마운트 밖을 열 수 있고
    NFS 실경로가 로그·응답에 샌다(`_strip_internal_paths` 와 같은 취지). 컨테이너는 이름을
    /models/checkpoints/<name> 으로만 해석한다.
    """
    pid = int(inference_playground_id)
    # 워크스페이스 경계(조회 실패·없음·타 워크스페이스 거절)는 공유 규칙 한 곳에 있다.
    detail = await _playground_in_workspace("inference", pid, workspace_id)
    model = detail.get("model") or {}

    # 배포가 이 런의 모델을 서빙하나 — 아니면 다른 모델의 가중치를 학습해 이 프로젝트
    # 모델의 점수로 기록하게 된다. model_allm_id 는 상세가 커밋 행에서 뽑아 준 값이라,
    # 일치하면 아래 커밋도 같은 모델의 것임이 함께 보장된다.
    served_model_id = model.get("model_allm_id")
    try:
        model_matches = int(served_model_id) == int(model_id)
    except (TypeError, ValueError):
        model_matches = False
    if not model_matches:
        raise Exception(
            f"배포 {pid} 가 평가 대상 모델을 서빙하는지 확인하지 못했습니다 — {purpose}은 "
            "그 배포의 체크포인트로 점수를 내므로, 확인되지 않으면 다른 모델의 "
            "가중치를 이 프로젝트 모델의 점수로 기록하게 됩니다. 평가 대상 모델의 "
            "체크포인트를 올린 배포를 고르세요" + (f"(또는 {off_hint})" if off_hint else ""))

    name = str(model.get("model_allm_commit_name") or "").strip()
    if not name:
        # HF 모델을 직접 올린 배포는 플랫폼 커밋이 없다 — 올릴 가중치를 특정할 수 없다.
        raise Exception(
            f"배포 {pid} 에는 {purpose}에 쓸 체크포인트가 없습니다 — 플랫폼 커밋을 올린 "
            "배포에서만 할 수 있습니다(HF 모델을 직접 올린 배포에는 커밋이 없습니다). "
            "체크포인트를 올린 배포를 고르세요" + (f"(또는 {off_hint})" if off_hint else ""))
    if not _SAFE_SEGMENT_RE.match(name):
        # 이 이름은 컨테이너 안에서 마운트 경로 한 조각이 된다 — 경계에서 막는다.
        raise Exception(
            f"체크포인트 이름에 마운트에 쓸 수 없는 문자가 있습니다: {name!r}")
    return name


async def _resolve_remote_generator(inference_playground_id: int, model_id: int,
                                    workspace_id: int) -> dict:
    """생성을 위임할 배포를 검증하고 컨테이너에 넘길 OpenAI 호환 base 를 조립한다.

    _resolve_remote_judge 와 같은 검증을 쓰되 모델 판정의 **방향이 반대**다:
      - 심판은 평가 대상과 같은 모델이면 거부한다(self-preference).
      - 생성은 평가 대상 **그 모델이어야** 하고, 다르면 거부한다. 이 프로젝트는
        model_id 에 잠겨 있고 결과는 그 모델의 eval_result 로 영속되므로, 다른 모델의
        배포로 생성하면 **B 의 점수가 A 의 점수로 기록된다**(런 산출물만 봐서는 추적
        불가). 로컬 경로가 `commit.model_id != model_id` 를 거부하는 것과 같은 이유다.
    대상 배포가 심판 배포와 같은지는 여기서 안 본다 — 그 배타 검증은 심판 쪽
    (`_resolve_remote_judge(exclude_playground_id=...)`)이 이미 한다.
    실행 중이 아니면 여기서 막는다: 컨테이너가 뜬 뒤 전량 연결 실패로 죽는 것보다
    파드를 띄우기 전에 사유를 주는 게 낫다(원격 심판과 같은 취지).
    """
    pid = int(inference_playground_id)
    # 워크스페이스 경계(조회 실패·없음·타 워크스페이스 거절)는 공유 규칙 한 곳에 있다.
    detail = await _playground_in_workspace("inference", pid, workspace_id)

    # 배포가 서빙하는 모델이 프로젝트 모델과 같은지 — 위 docstring 의 핵심 검증이다.
    served_model_id = (detail.get("model") or {}).get("model_allm_id")
    model_verified = False
    if served_model_id is not None:
        try:
            model_verified = int(served_model_id) == int(model_id)
        except (TypeError, ValueError):
            model_verified = False
        if not model_verified:
            raise Exception(
                f"inference playground {pid} 는 평가 대상과 다른 모델을 서빙합니다 — "
                "그 배포로 생성하면 다른 모델의 점수가 이 프로젝트 모델의 점수로 "
                "기록됩니다. 평가 대상 모델의 배포를 고르세요")
    else:
        # 모델 식별자를 못 읽었다 = 같은지 다른지 **확인하지 못했다**. 거절하지 않는 이유:
        # 배포 행의 model JSON 이 비어 있는 조합이 있고, 거절로 두면 정상 배포까지 막힌다.
        # 대신 확인 실패를 로그와 런 생성 응답(model_verified=False)에 남겨 추적 가능하게 한다.
        print(f"[eval] WARN generation playground {pid}: 서빙 모델 식별자를 읽지 못해 "
              f"평가 대상(model_id={model_id})과 같은 모델인지 확인하지 못했습니다 — "
              f"런 결과의 출처를 배포 설정으로 직접 확인하세요.", flush=True)

    try:
        status = await _playground_status(pid)
    except Exception as e:
        raise Exception(f"inference playground {pid} 상태 조회 실패: {e}") from e
    if status != "running":
        raise Exception(
            f"inference playground {pid} 가 실행 중이 아닙니다(status={status}) — "
            "먼저 배포를 시작한 뒤 실행하세요")

    # ⚠️ 결정성 — 벤치마크 생성은 greedy(temperature 0)여야 같은 체크포인트에 같은 점수가
    # 나온다. 그런데 shim(openai_chat_completions)은 요청 body 의 temperature·max_tokens 를
    # **무시**하고 배포 시점 설정을 따른다. 즉 컨테이너가 temperature=0 을 보내도 배포가
    # 0.7 이면 0.7 로 생성된다. 우리가 할 수 있는 것은 배포 설정을 읽어 알리는 것까지다.
    # 거절하지 않는 이유는 원격 심판과 같다 — 플랫폼 기본 배포가 0.7 이라 거절로 두면
    # 기능이 사실상 못 쓰이게 된다.
    temperature = (detail.get("model_parameter") or {}).get("temperature")
    try:
        deterministic = temperature is not None and float(temperature) == 0.0
    except (TypeError, ValueError):
        deterministic = False
    if not deterministic:
        print(f"[eval] WARN generation playground {pid}: temperature={temperature!r} "
              f"(≠0) — 벤치마크 점수가 런마다 달라질 수 있습니다. 배포의 생성 파라미터를 "
              f"temperature=0 으로 저장한 뒤 재배포하면 재현됩니다.", flush=True)
    # ⚠️ 이 경로에서는 chat template 도 배포 쪽 서빙 엔진이 정한다(임베드 vLLM 은 아무도
    # 안 붙이고 llama.cpp/TGI 는 엔진이 붙인다). 컨테이너가 템플릿을 적용하면 후자에서
    # 이중 적용이 되므로 적용하지 않는다 → 컨테이너의 로컬 생성 경로 점수와 직접 비교할 수
    # 없다. 이 사실은 컨테이너가 metrics.generate.note 에 새긴다.
    return {
        "playground_id": pid,
        "name": (detail.get("info") or {}).get("name"),
        "base_url": _playground_shim_base_url(pid),
        "temperature": temperature,
        "deterministic": deterministic,
        # 배포가 프로젝트 모델을 서빙함을 **확인했는지**. False = 식별자를 못 읽어
        # 확인하지 못한 것이지, 다르다는 뜻이 아니다(다르면 위에서 이미 거부했다).
        "model_verified": model_verified,
    }


async def _resolve_remote_judge(judge_playground_id: int, model_id: int,
                                workspace_id: int,
                                exclude_playground_id: Optional[int] = None) -> dict:
    """심판 배포를 검증하고 컨테이너에 넘길 OpenAI 호환 base 를 조립한다.

    검증 순서는 '거절이 싼 것부터'가 아니라 '오해를 부르는 것부터'다:
      1) 대상 배포와 동일 — 자기 답을 자기가 채점(self-preference)
      2) 워크스페이스 밖 — 남의 배포를 심판으로 끌어오는 경로 차단
      3) 평가 대상과 같은 모델 — 배포가 달라도 self-preference 는 그대로다
      4) 실행 중이 아님 — 컨테이너가 GPU 를 잡고서야 연결 실패로 죽는 것을 앞당겨 막는다
    """
    pid = int(judge_playground_id)
    if exclude_playground_id and int(exclude_playground_id) == pid:
        raise Exception(
            "심판 배포가 생성에 쓰는 배포와 같습니다 — 자기 답을 자기가 채점하면 "
            "점수가 self-preference 로 부풀어 비교가 무의미해집니다")

    # 2) 워크스페이스 밖 — 조회 실패·없음·타 워크스페이스 거절은 공유 규칙 한 곳에 있다.
    detail = await _playground_in_workspace("judge", pid, workspace_id)

    # 3) 평가 대상과 같은 모델인가. 식별자를 못 읽거나(HF 직접 배포 등 model JSON 이 빈
    #    조합) 비교할 수 없으면 **확인하지 못한 것**이지 다르다는 뜻이 아니다 — 조용히
    #    넘기면 self-preference 로 부푼 점수가 검증된 점수와 구분되지 않는다.
    #    거절하지 않는 이유는 _resolve_remote_generator 와 같다(정상 배포까지 막힌다).
    #    대신 사실을 로그와 런 생성 응답(distinct_model_verified=False)에 남긴다.
    judge_model_id = (detail.get("model") or {}).get("model_allm_id")
    same_model = None                      # None = 비교 불가(확인 못 함)
    if judge_model_id is not None:
        try:
            same_model = int(judge_model_id) == int(model_id)
        except (TypeError, ValueError):
            same_model = None
        if same_model:
            raise Exception(
                "심판 배포가 평가 대상과 같은 모델입니다 — 다른 모델의 배포를 고르세요")
    # 생성 쪽 model_verified 와 뜻이 반대라(그쪽은 '같은 모델임을 확인') 이름을 달리 둔다.
    distinct_model_verified = same_model is False
    if not distinct_model_verified:
        print(f"[eval] WARN judge playground {pid}: 서빙 모델 식별자를 읽지 못해"
              f"(model_allm_id={judge_model_id!r}) 평가 대상(model_id={model_id})과 "
              f"다른 모델인지 확인하지 못했습니다 — 자기 답을 자기가 채점하는 "
              f"self-preference 일 수 있으니 심판 배포 설정을 직접 확인하세요.", flush=True)

    try:
        status = await _playground_status(pid)
    except Exception as e:
        raise Exception(f"judge playground {pid} 상태 조회 실패: {e}") from e
    if status != "running":
        raise Exception(
            f"judge playground {pid} 가 실행 중이 아닙니다(status={status}) — "
            "먼저 배포를 시작한 뒤 실행하세요")

    # ⚠️ 결정성 — LogicKor 심판은 greedy(temperature 0)여야 같은 답에 같은 점수가 나온다.
    # 그런데 shim(openai_chat_completions)은 요청 body 의 temperature·max_tokens 를 **무시**
    # 하고 배포 시점 설정을 따른다. 즉 채점기가 temperature=0 을 보내도 배포가 0.7 이면
    # 0.7 로 채점된다. 우리가 할 수 있는 것은 배포 설정을 읽어 알리는 것까지다.
    # 거절하지 않는 이유: 플랫폼 기본 배포가 temperature 0.7 이라(pipeline_deploy) 거절로
    # 두면 기능이 사실상 못 쓰이게 된다. 대신 사실을 응답과 로그에 남긴다.
    temperature = (detail.get("model_parameter") or {}).get("temperature")
    try:
        deterministic = temperature is not None and float(temperature) == 0.0
    except (TypeError, ValueError):
        deterministic = False
    if not deterministic:
        print(f"[eval] WARN remote judge playground {pid}: temperature={temperature!r} "
              f"(≠0) — LogicKor 점수가 런마다 달라질 수 있습니다. 심판 배포의 생성 "
              f"파라미터를 temperature=0 으로 저장한 뒤 재배포하면 재현됩니다.", flush=True)
    return {
        "playground_id": pid,
        "name": (detail.get("info") or {}).get("name"),
        "base_url": _playground_shim_base_url(pid),
        "temperature": temperature,
        "deterministic": deterministic,
        # 심판이 평가 대상과 **다른** 모델임을 확인했는지. False = 식별자를 못 읽어
        # 확인하지 못한 것이지, 같다는 뜻이 아니다(같으면 위에서 이미 거부했다).
        # 생성 쪽 generate_remote.model_verified 와 뜻이 반대이므로 키 이름이 다르다.
        "distinct_model_verified": distinct_model_verified,
    }


async def _infer_output(inference_target, prompt: str, session_id: str) -> Optional[str]:
    """배포 모델 추론 1건 → scorer가 소비하는 출력 문자열만 반환한다.
    단일 direct 응답과 이중 /playgrounds/test envelope를 여기서 같은 문자열 shape로 정규화한다."""
    try:
        if isinstance(inference_target, str):
            # 내부 레거시 호출자가 URL 문자열을 넘겨도 기존 direct 계약을 유지한다.
            target_url = inference_target
            playground_id = None
        else:
            target_url = (inference_target or {}).get("url")
            playground_id = (inference_target or {}).get("playground_id")
        if not target_url:
            return None

        if playground_id is not None:
            # 저장된 dual 링크는 playground route가 다시 고정 검증하므로 평가 요청이 LLM1을 주입하지 않는다.
            request_body = {
                "playground_id": int(playground_id),
                "test_type": "question",
                "test_question": prompt,
                "session_id": session_id,
            }
        else:
            # ⚠️ 서빙 래퍼(fb_scheduler deployment_llm/src/llm/playground.py post_llm)는
            #    test_type / test_question 만 읽는다 — input_type / input 은 아예 보지
            #    않는다. 옛 키를 보내면 test_question 이 None 이 되어 vLLM 이
            #    "Prompt should be a string" 으로 죽고 [{"input":null,"output":""}] 가 온다
            #    (2026-08-28 실측). 플랫폼 정본(llm_playground playground_test)과 같은 키다.
            request_body = {
                "test_type": "question",
                "test_question": prompt,
                "session_id": session_id,
            }
        # dual 은 BFF 체인(LLM1→LLM2)이라 서버 예산이 단일보다 훨씬 크다.
        _timeout = _DUAL_INFER_TIMEOUT if playground_id is not None else _INFER_TIMEOUT
        async with httpx.AsyncClient(timeout=_timeout) as http:
            r = await http.post(target_url, json=request_body)
        try:
            data = r.json()
        except ValueError:
            return (r.text or "").strip()[:_MAX_FIELD_LEN] or None
        if playground_id is not None:
            if not isinstance(data, dict) or data.get("status") != 1:
                return None
            result = data.get("result")
            if isinstance(result, list) and result and isinstance(result[0], dict):
                output = result[0].get("output")
                if isinstance(output, str) and output.strip():
                    return output.strip()[:_MAX_FIELD_LEN]
            return None
        # 서빙 래퍼는 입력 1건에도 **리스트**로 답한다: [{"input","output","time"}].
        # 첫 원소만 본다(질문 경로는 언제나 1건). 이 정규화가 없으면 키를 고쳐도
        # dict 분기에 걸리지 않아 계속 None 이 된다.
        if isinstance(data, list):
            data = data[0] if data and isinstance(data[0], dict) else None
        if isinstance(data, dict):
            for k in ("output", "response", "answer", "result", "text", "content"):
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()[:_MAX_FIELD_LEN]
        elif isinstance(data, str) and data.strip():
            return data.strip()[:_MAX_FIELD_LEN]
    except Exception:
        traceback.print_exc()
    return None


async def _load_run_samples(model_id: int, project_id: int,
                            inference_job_id: Optional[str] = None) -> tuple:
    """생성·채점 분리(P2-b) — 지정된 러너 inference 런(inference_job_id)의 _samples +
    gen_system_prompt 를 로드해 score phase 가 재사용(재추론 회피). **명시 opt-in 전용**:
    inference_job_id 없으면 (None, None) — judge/expert 가 조용히 라이브추론(inference_playground_id)
    을 오버라이드하지 않도록 benchmark 와 통일(리뷰 HIGH). 프로젝트 바인딩(list_eval_results_by_project
    필터)으로 타 프로젝트 런 유입 차단(같은 model 이라도 — 리뷰 MEDIUM). 완료된
    metric_set=='inference' 만. 서버전용 _image_abs 등 보존(expert VLM 표시용).
    반환 (samples|None, gen_system_prompt|None). gen_system_prompt=P3 헤더 고정 박스 표시원.

    ⚠️ 2026-08-24 부터 model 바인딩도 함께 본다. 프로젝트가 모델을 잠그던 동안에는
    "같은 프로젝트 = 같은 모델"이라 프로젝트 필터만으로 충분했지만, 이제 한 프로젝트에
    서로 다른 모델의 생성 런이 공존한다 — 모델 A 가 만든 output 을 모델 B 의 채점에
    붙이면 A 의 답이 B 의 점수로 기록된다."""
    if not inference_job_id:
        return None, None
    try:
        rows = await db_model.list_eval_results_by_project(
            eval_project_id=project_id) or []
    except Exception:
        traceback.print_exc()
        return None, None
    for r in rows:
        if (not r or r.get("job_str_id") != inference_job_id
                or r.get("metric_set") != "inference" or r.get("status") != "completed"
                or int(r.get("source_model_id") or 0) != int(model_id)):
            continue
        m = r.get("metrics")
        if isinstance(m, str):
            try:
                m = json.loads(m)
            except (TypeError, json.JSONDecodeError):
                m = None
        if not isinstance(m, dict):
            return None, None
        samples = m.get("_samples")
        if isinstance(samples, list) and samples:
            return samples, m.get("_gen_system_prompt")
        return None, None
    return None, None


async def _generate_samples(inference_target, dataset_ids: List[int], limit: int,
                            tag: str, concurrency: int = 1) -> list:
    """데이터셋 문항을 배포에 던져 per-sample output 을 만든다 — 평가의 **유일한 생성 루프**.

    호출자는 러너(POST /evaluations/inference, generate phase 백그라운드) 하나다.
    벤치마크도 이 함수를 공유했었지만(인라인 생성) 지금은 배포에 위임하므로 쓰지 않는다 —
    벤치마크 프롬프트 조립은 컨테이너 소유이고 이 루프는 "문항 하나 → 출력 하나"의
    단일턴이라 LogicKor 2턴·MixATIS UGEN 형식을 재현할 수 없다(run_benchmark docstring).
    concurrency 인자는 그 시절의 잔재다 — 러너는 예산 3600s 라 종전대로 순차(1)를 쓴다.
    이미지/CSV 등 서버전용 필드는 그대로 실어 보낸다 — score phase(전문가 VLM)가
    _samples 를 소비할 때 렌더/추론 컨텍스트가 유지돼야 한다.
    """
    rows = await _read_dataset_samples(dataset_ids, limit)
    sem = asyncio.Semaphore(max(int(concurrency or 1), 1))

    async def _one(i: int, row: dict) -> dict:
        out = None
        if row.get("input"):    # 텍스트 input 만 — image-only(VLM) 전량 batch 는 P4
            async with sem:
                out = await _infer_output(inference_target, row["input"], f"{tag}-{i}")
        sample = {
            "idx": i, "input": row.get("input", ""), "output": out or "",
            "reference": row.get("reference", ""), "dataset": row.get("dataset", "")}
        for k in ("image", "image_url", "image_served", "_image_abs", "_image_dir",
                  "csv_rows", "csv_text"):
            if k in row:
                sample[k] = row[k]
        return sample

    return list(await asyncio.gather(*(_one(i, r) for i, r in enumerate(rows))))


# ── 평가 추론 러너 (generate phase, P1) ──────────────────────────────────────
# 평가가 대상 모델을 골라 인스턴스를 확보(하이브리드: running 배포 재사용 or 전용 할당)하고
# 데이터셋 전량(≤MAX_EVAL_SAMPLES)에 batch 추론 → per-sample output + 런 시스템프롬프트를
# eval_result.metrics 에 영속. 채점(score phase, P2)이 _samples.output 을 소비한다.
# 배포/상태/teardown 은 llm_playground 프리미티브를 s2s 재사용(신규 서빙 로직 없음).
_eval_infer_tasks: set = set()
# 프로젝트 단위 in-process 락 — run_eval_inference 의 idempotency check + 예약 insert 를 원자화
#   (동시 POST 2건이 둘 다 통과해 GPU 중복 할당하는 TOCTOU 차단, 리뷰 HIGH). 단일 레플리카 전제.
_eval_infer_project_locks: dict = {}


def _project_infer_lock(project_id: int) -> asyncio.Lock:
    lock = _eval_infer_project_locks.get(project_id)
    if lock is None:
        lock = asyncio.Lock()
        _eval_infer_project_locks[project_id] = lock
    return lock


async def _deploy_transient_playground(model_id, workspace_id, user_name, instance_id,
                                       instance_count, gpu_count, commit_id,
                                       system_prompt=None) -> int:
    """전용 배포 할당 — llm_playground pipeline-deploy s2s(create+bind+start 원자). pipeline.py
    execute_llm_deploy(cluster) 와 동형 바디. user_name 은 실 플랫폼 유저(pipeline_deploy 가
    db.get_user 검증)라 eval 런 트리거 유저(jf-User)/project.creator 를 넘긴다. playground_id 반환."""
    body = {
        "workspace_id": int(workspace_id),
        "model_id": int(model_id),
        "user_name": user_name,
        "model_instance_id": instance_id,
        "model_instance_count": int(instance_count or 1),
        # gpu_count=0(CPU) 를 1 로 뒤집지 않는다(`or 1` 금지) — DTO 가 ge=0 허용.
        "model_gpu_count": int(gpu_count if gpu_count is not None else 1),
    }
    if commit_id is not None:
        body["model_commit_id"] = commit_id
    if system_prompt:    # 런의 시스템 프롬프트를 배포에 baking(표시=실사용 일치, P2-b)
        body["prompt_system_message"] = system_prompt
    url = f"http://{settings.LLM_PLAYGROUND_DNS}/api/playgrounds/pipeline-deploy"
    async with httpx.AsyncClient(timeout=60.0) as http:
        r = await http.post(url, json=body)
    data = r.json() if r.status_code == 200 else {}
    pid = (data.get("result") or {}).get("playground_id")
    if not pid:
        # response() 는 앱-레벨 실패도 HTTP 200(envelope status=0)로 반환 — 실패 사유(message)를
        #   삼키지 않고 노출(GPU 쿼터·commit 부재·user 미존재 등 진단 가능하게, 리뷰 MEDIUM).
        msg = data.get("message") or f"HTTP {r.status_code}"
        raise Exception(f"pipeline-deploy failed: {msg}")
    return int(pid)


async def _wait_playground_ready(playground_id: int) -> bool:
    """status-sync 폴링 — running 까지(pipeline._wait_for_playground_deploy 동형, ~10분 상한).
    running=True, error/failed 또는 상한 초과/연속 unreachable=False."""
    fails = 0
    for _ in range(EVAL_DEPLOY_MAX_POLLS):
        try:
            status = await _playground_status(playground_id)
            fails = 0
            if status == "running":
                return True
            if status in ("error", "failed"):
                return False
        except Exception:
            fails += 1
            if fails >= 60:
                return False
        await asyncio.sleep(2)
    return False


async def _teardown_playground(playground_id: int) -> None:
    """전용 배포 회수 — DELETE /api/playgrounds/{id}(helm uninstall+GPU 오펀 가드 재사용).
    best-effort(실패해도 예외 전파 X — finally 경로 호출, GPU 오펀만은 로그로 남긴다)."""
    try:
        url = (f"http://{settings.LLM_PLAYGROUND_DNS}"
               f"/api/playgrounds/{int(playground_id)}")
        async with httpx.AsyncClient(timeout=30.0) as http:
            r = await http.delete(url)
        # 무음 실패 방지 — helm uninstall 실패/앱-레벨 오류가 성공처럼 보이지 않게 가시화(GPU 오펀 추적).
        ok = r.status_code < 400 and (r.json().get("status") == 1
                                      if r.headers.get("content-type", "").startswith("application/json")
                                      else True)
        if not ok:
            print(f"_teardown_playground: {playground_id} 회수 실패(HTTP {r.status_code}) — GPU 오펀 가능",
                  flush=True)
    except Exception:
        traceback.print_exc()


async def run_eval_inference(project_id: int, model_id: int, dataset_ids: List[int],
                             system_prompt: Optional[str] = None,
                             inference_playground_id: Optional[int] = None,
                             instance_id=None, instance_count: int = 1,
                             gpu_count: int = 1, commit_id=None,
                             user_name: Optional[str] = None) -> dict:
    """평가 추론 러너(generate phase) — 이 런이 고른 모델/데이터셋으로 인스턴스를 확보해
    데이터셋 전량(≤MAX_EVAL_SAMPLES) batch 추론 → _samples + _gen_system_prompt 를
    eval_result.metrics 에 영속. 하이브리드 인스턴스: inference_playground_id 주면 running
    배포 재사용, 아니면 instance_id 로 전용 할당(완료/실패 시 delete_playground 회수).
    즉시 job_id 반환 후 백그라운드 생성(judge 런과 동형 비동기).
    ⚠️ P1 WIP — review 지적(wall-clock cap/teardown 견고화/idempotency/system_prompt 실사용/
    실패→completed/gpu_count=0/eval_type gate/instance_id ge=1)은 P2 선결.
    ⚠️ '배포 소유권 검증'은 목록에서 빠졌다 — 2026-08-27 해소(재사용 경로의 워크스페이스
    대조, 아래). 전용 할당 경로는 그대로다(배포를 이 함수가 만드니 소유권이 자명하다)."""
    # run-start 공통 로더 재사용(중복 방지). generate 는 type-agnostic 이라 eval_type gate 생략.
    project = await _load_project_for_run(project_id, None)
    model_id = int(model_id)
    dataset_ids = _run_dataset_ids(dataset_ids)
    model_info, workspace_id = await _resolve_run_model(project, model_id)
    model_name = model_info["name"]

    ds_names = []
    for did in dataset_ids:
        d = await db_model.get_dataset_model(dataset_id=did)
        if not d:
            raise Exception(f"dataset {did} not found")
        if int(d["workspace_id"]) != workspace_id:
            raise Exception("dataset and model belong to different workspaces")
        ds_names.append(str(d["name"]))
    dataset_name_csv = ",".join(ds_names)
    if len(dataset_name_csv) > 255:
        dataset_name_csv = f"{ds_names[0]} +{len(ds_names) - 1} more"[:255]

    # 하이브리드: 배포 미지정이면 전용 할당 → instance_id + 실 유저 필수(FE 인스턴스 선택 전달).
    allocate = not inference_playground_id
    deploy_user = user_name or project.get("creator")
    if allocate and not instance_id:
        raise Exception("inference_playground_id or instance_id required")
    if allocate and not deploy_user:
        raise Exception("deploy user_name required for transient allocation")

    # 빌린 배포(재사용 경로)는 **이 런의 워크스페이스 것**이어야 한다 — 규칙은 배포 id 를
    # 받는 네 경로가 공유하는 _playground_in_workspace 한 곳에 있다. 왜 필요한가: 이 id 는
    # 요청이 준 raw 값이고 _resolve_inference_target 은 그것을 그대로 믿고 s2s 를 부른다.
    # 대조하지 않으면 남의 워크스페이스 배포로 생성이 일어나고, 그 출력은 이 프로젝트의
    # eval_result(_samples)로 영속돼 사후에 출처를 구분할 수 없다.
    # 전용 할당 경로(allocate)는 건드리지 않는다: 배포를 이 함수가 만든다.
    if inference_playground_id:
        await _playground_in_workspace(
            "inference", inference_playground_id, workspace_id)

    sysprompt = (system_prompt or "").strip()[:_MAX_FIELD_LEN] or None
    job_id = f"infer-{model_id}-{uuid.uuid4().hex[:16]}"
    # TOCTOU 가드 — idempotency check(프로젝트당 running inference 1개)와 예약 insert 를 프로젝트
    #   단위 in-process 락으로 원자화(동시 POST 2건이 둘 다 통과해 GPU 중복 할당 차단, 리뷰 HIGH).
    #   조회 실패는 가드를 막지 않음(진행). 멀티레플리카면 DB 유니크 제약 필요(P4-deploy).
    async with _project_infer_lock(project_id):
        try:
            _existing = await db_model.list_eval_results_by_project(
                eval_project_id=project_id) or []
        except Exception:
            _existing = []
            traceback.print_exc()
        if any(r.get("metric_set") == "inference" and r.get("status") == "running"
               for r in _existing):
            raise Exception("an inference run is already in progress for this project")
        await db_model.insert_eval_result(
            source_model_id=model_id, workspace_id=workspace_id, job_str_id=job_id,
            dataset_id=dataset_ids[0], dataset_name=dataset_name_csv,
            metric_set="inference", eval_project_id=project_id)
    try:
        await db_model.update_eval_project_status(project_id, PROJECT_STATUS_RUNNING)
    except Exception:
        traceback.print_exc()

    task = asyncio.create_task(_run_eval_inference_task(
        model_id, workspace_id, job_id, model_name, dataset_ids, sysprompt,
        inference_playground_id, allocate, instance_id, instance_count, gpu_count, commit_id,
        deploy_user))
    _eval_infer_tasks.add(task)
    task.add_done_callback(_eval_infer_tasks.discard)

    return {"project_id": project_id, "model_id": model_id, "job_id": job_id,
            "mode": "inference", "datasets": ds_names, "allocated": allocate,
            "system_prompt": sysprompt}


async def _run_eval_inference_task(model_id, workspace_id, job_id, model_name, dataset_ids,
                                   system_prompt, inference_playground_id, allocate,
                                   instance_id, instance_count, gpu_count, commit_id,
                                   deploy_user=None) -> None:
    """백그라운드 generate — 인스턴스 확보 → 전량 batch 추론 → _samples 영속 → (할당형) 회수.
    wall-clock 상한(EVAL_INFER_RUN_SECONDS)으로 hung/느린 배포의 GPU 무한점유 방지, finally 에서
    teardown 강제. 전량 추론 실패 또는 timeout → eval_result=failed('completed' 위장 안 함).
    state['pid'] 에 배포 id 를 담아 timeout 후에도 teardown 되게 한다(단, deploy POST 자체
    timeout 후 서버측 생성된 경우는 pid 미포착 — pipeline.execute_llm_deploy 와 동일 잔여 gap)."""
    state = {"pid": None}

    async def _generate():
        playground_id = inference_playground_id
        if allocate:
            state["pid"] = await _deploy_transient_playground(
                model_id, workspace_id, deploy_user, instance_id, instance_count,
                gpu_count, commit_id, system_prompt)
            if not await _wait_playground_ready(state["pid"]):
                raise Exception(f"transient playground {state['pid']} not ready")
            playground_id = state["pid"]
        inference_target = await _resolve_inference_target(playground_id)
        if not inference_target:
            raise Exception("no inference target (deployment not running?)")
        # 생성 루프(_generate_samples)의 유일한 호출자다. 러너는
        # 백그라운드라 종전대로 순차(concurrency 기본 1) — 배포에 걸리는 부하를 바꾸지 않는다.
        samples = await _generate_samples(
            inference_target, dataset_ids, MAX_EVAL_SAMPLES, f"infer-{model_id}")
        # 데이터셋을 못 읽었거나(0 샘플) 전량 추론 실패(모든 output 공백)면 completed 로 위장하지
        #   않고 실패 처리 — rows=[] 인 dataset-read 실패도 failed(리뷰 CRITICAL: 성공 위장 방지).
        if not samples:
            raise Exception("no samples read from dataset (unreadable/empty/unsupported)")
        if not any(s["output"] for s in samples):
            raise Exception("all inference outputs empty (deployment unreachable?)")
        metrics = {"_mode": "inference", "_gen_system_prompt": system_prompt,
                   "_samples": samples, "_total": len(samples)}
        await db_model.complete_eval_result(
            job_str_id=job_id, metrics_json=json.dumps(metrics), source_model_id=model_id)

    try:
        await asyncio.wait_for(_generate(), timeout=EVAL_INFER_RUN_SECONDS)
    except Exception:
        traceback.print_exc()
        try:
            await db_model.update_eval_result_status(
                job_str_id=job_id, status="failed", source_model_id=model_id)
        except Exception:
            traceback.print_exc()
    finally:
        if state["pid"]:
            await _teardown_playground(state["pid"])


# ── 전문가 평가 (P3) ──────────────────────────────────────────────────────────
# 사람이 샘플(입력/출력/참조)을 O/X + 코멘트로 채점 → eval_expert_rating 영속 → 합격률 집계.
# 세션 = eval_result row(metric_set='expert'). 전부 채점 시 합격률을 eval_result.metrics
# (expert_pass_rate)로 마감 → 모델 이력 비교표 합류. 샘플=결정적 생성(idx 기반, 재로드 안정).
# P2(A)와 동일 mock 스캐폴딩 — 실 모델출력 생성은 후속.

# 이미지 등 서버 내부키(_image_abs)는 FE 로 내보내지 않는다(NFS 절대경로 누출 차단). 공개
# 키만 통과 — image_url(URL 직접 렌더)·image_served(서빙 엔드포인트 사용 플래그)·image(원본 참조).
def _public_sample(s: dict) -> dict:
    return {k: v for k, v in s.items() if not str(k).startswith("_")}


def _expert_prompt(samples: list) -> str:
    """시나리오 결속 고정 프롬프트(D3) — SDS(샘플에 csv_rows) 는 SDS 상수, 그 외 일반 상수.
    빌더가 만든 프리즈 샘플의 shape 로 판별하므로 세션 내내 결정적(고정)."""
    if any(isinstance(s, dict) and s.get("csv_rows") for s in samples):
        return EXPERT_PROMPT_SDS
    return EXPERT_PROMPT_DEFAULT


def _session_prompt(row: dict, samples: list) -> str:
    """세션 고정 프롬프트 — start 시점에 metrics._expert_prompt 로 동결한 값을 우선(진짜 freeze),
    없으면(레거시 세션) 프리즈 샘플에서 재도출. 상수 텍스트가 이후 바뀌어도 기존 세션은 유지."""
    m = row.get("metrics") if isinstance(row, dict) else None
    if isinstance(m, str):
        try:
            m = json.loads(m)
        except (TypeError, json.JSONDecodeError):
            m = None
    if isinstance(m, dict) and isinstance(m.get("_expert_prompt"), str):
        return m["_expert_prompt"]
    return _expert_prompt(samples)


def _aggregate_expert(ratings: list):
    """채점 목록 → (avg_score, distribution, pass_rate). avg_score(1~5, 2dp)가 신규 기본
    집계, distribution 은 1~5 카운트, pass_rate(0~100)는 verdict=="O" 기반 backward-compat."""
    scores = []
    for r in ratings:
        sc = r.get("score")
        if sc is None:
            continue
        try:
            scores.append(int(sc))
        except (TypeError, ValueError):
            continue
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
    distribution = {str(i): 0 for i in range(EXPERT_SCORE_MIN, EXPERT_SCORE_MAX + 1)}
    for sc in scores:
        if EXPERT_SCORE_MIN <= sc <= EXPERT_SCORE_MAX:
            distribution[str(sc)] += 1
    rated = len(ratings)
    passed = sum(1 for r in ratings if r.get("verdict") == "O")
    pass_rate = round(passed / rated * 100.0, 2) if rated else 0.0
    return avg_score, distribution, pass_rate


def _sample_image_b64(sample: dict) -> Optional[str]:
    """VLM 샘플의 서버보관 이미지(_image_abs)를 base64 로 인코딩. get_expert_image 의 봉쇄
    로직 재사용(realpath + _image_dir commonpath 재봉쇄 + isfile + 이미지 확장자 + 크기 상한).
    없거나 검증 실패 → None(→ 실추론 스킵, mock 유지)."""
    abs_path = sample.get("_image_abs")
    if not abs_path:
        return None
    try:
        real = os.path.realpath(abs_path)
        image_dir = sample.get("_image_dir")
        # 서빙 시 재봉쇄(fail-closed) — start 이후 심링크 스왑 차단. _image_dir 이 없으면 봉쇄
        # 불가로 간주해 거부(디폴트 거부 — 미래에 _image_abs 만 있는 샘플이 생겨도 임의 파일 미노출).
        if not image_dir or os.path.commonpath([real, image_dir]) != image_dir:
            return None
        ext = os.path.splitext(real)[1].lower()
        if not os.path.isfile(real) or ext not in _IMAGE_MEDIA:
            return None
        if os.path.getsize(real) > _MAX_IMAGE_BYTES:
            return None
        with open(real, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except (OSError, ValueError):
        return None


def _csv_to_ais_rows(sample: dict) -> list:
    """샘플 csv_rows(2D: 헤더+행)를 ais_rows(dict 리스트)로 변환. Playground external 분기가
    ais_rows 에 my_ship=1 행을 요구 — SDS input_data.csv 가 AIS 표라 헤더/행 zip 이 그대로
    계약이 된다. 헤더/행 부족 시 [](→ Playground 검증 거부 → mock 폴백). 셀 상한은 이미
    _read_csv_grid 에서 적용됨."""
    rows = sample.get("csv_rows")
    if not isinstance(rows, list) or len(rows) < 2:
        return []
    header = [str(c) for c in rows[0]]
    out = []
    for r in rows[1:_MAX_CSV_ROWS + 1]:
        if not isinstance(r, list):
            continue
        out.append({header[i]: r[i] for i in range(min(len(header), len(r)))})
    return out


async def _infer_vlm_output(playground_id: int, image_b64: str, ais_rows: list,
                            session_id: str, prompt: Optional[str] = None) -> Optional[str]:
    """배포 SDS(external) 모델 VLM 추론 1건 — Playground /test 의 external 분기 재사용(내부
    vLLM 텍스트 경로와 달리 external 배포는 test_url 이 없어 이 경유가 유일). s2s POST
    {playground_id, test_type:'question', external_payload:{image_base64, ais_rows}}.
    envelope status==1 → result[0].output. 실패/타임아웃/검증거부 → None(mock 유지).
    ⚠️ test_type=='question' 은 Playground 에서 dual-prompt-gen 체크를 타지만 SDS 단일
    배포는 dual 링크가 없어 None → external 분기로 통과한다."""
    try:
        url = f"http://{settings.LLM_PLAYGROUND_DNS}/api/playgrounds/test"
        # 생성 시스템 프롬프트를 external_payload 에 실으면 playground_test 가 그대로 params 로
        # eva-vlm /run 에 포워딩. eva-vlm 은 params.custom_prompt 로 받아 question 을 오버라이드
        # (실측: yvvyee/eva-vlm-backend:1.1.0 schemas.py:94 RunParams.custom_prompt /
        # model_manager.py:333 `question = custom_prompt or PROMPT_MAP[output_type]`). 미전달 시
        # PROMPT_MAP[output_type] 기본 프롬프트 사용. (표시=실사용 일치, P4.)
        # SDS 전문가 평가는 '항해조력메시지'를 채점(묘사 아님) → output_type 을 조력메시지로 지정
        # (eva-vlm 기본값이 '영문 해상상황묘사'라 미지정 시 묘사를 생성해 채점대상과 어긋남).
        # sds-lora-ko 체크포인트 + reference=output_advice_kor.txt(한글 조력)라 '한글 항해조력메시지'.
        # custom_prompt 전달 시 그게 question 을 오버라이드(output_type 은 AIS 텍스트 lang=ko 에 계속 작용).
        ext = {"image_base64": image_b64, "ais_rows": ais_rows,
               "output_type": "한글 항해조력메시지"}
        if prompt:
            ext["custom_prompt"] = prompt
        body = {"playground_id": int(playground_id), "test_type": "question",
                "external_payload": ext}
        async with httpx.AsyncClient(timeout=_VLM_INFER_TIMEOUT) as http:
            r = await http.post(url, json=body)
        if r.status_code != 200:
            print(f"_infer_vlm_output: playground {playground_id} HTTP {r.status_code}",
                  flush=True)
            return None
        data = r.json()
        if data.get("status") != 1:
            # external 검증 거부(image/ais_rows) 등 — 원인 추적용(비밀 없음).
            print(f"_infer_vlm_output: playground {playground_id} envelope status="
                  f"{data.get('status')} msg={data.get('message')}", flush=True)
            return None
        result = data.get("result")
        if isinstance(result, list) and result and isinstance(result[0], dict):
            out = result[0].get("output")
            if isinstance(out, str) and out.strip():
                return out.strip()[:_MAX_FIELD_LEN]
    except Exception:
        traceback.print_exc()
    return None


async def _build_expert_samples(model_id: int, model_name: str, dataset_ids: List[int],
                                ds_names: List[str], inference_target,
                                run_samples: Optional[list] = None,
                                sample_limit: Optional[int] = None,
                                sample_offset: int = 0) -> list:
    """전문가 채점 샘플(A4) — 실 데이터셋(input/reference/이미지) + 배포모델 추론 output.
    run_samples(러너 생성, P2-b2) 주면 그것을 그대로(이미지/CSV 필드 보존) 채점 대상으로.
    없으면 데이터셋 로드 + 배포 추론, 못 읽으면 합성(레거시 동등), 추론 URL 없으면 mock 폴백."""
    base = ds_names[0] if ds_names else "dataset"
    # 채점 샘플 상한 — 요청값이 있으면 그것, 없으면 종전대로 전량(천장까지).
    # 천장(MAX_EXPERT_SAMPLES)은 런어웨이 방지용이라 요청값이 그보다 커도 넘기지 않는다.
    cap = (MAX_EXPERT_SAMPLES if sample_limit is None
           else max(1, min(int(sample_limit), MAX_EXPERT_SAMPLES)))
    # P2-b2 — 러너 생성 샘플 우선(재생성/재추론 회피). output 있으면 real_output=True.
    if run_samples:
        out = []
        for i, s in enumerate(run_samples[:cap]):
            item = {"idx": i, "dataset": s.get("dataset", base),
                    "input": s.get("input", ""),
                    "output": (s.get("output") or "").strip() or f"[{model_name}] 응답 {i}",
                    "reference": s.get("reference", ""),
                    "real_output": bool((s.get("output") or "").strip())}
            for k in ("image", "image_url", "image_served", "_image_abs", "_image_dir",
                      "csv_rows", "csv_text"):
                if k in s:
                    item[k] = s[k]
            out.append(item)
        return out
    # 기본은 데이터셋 전량(ceiling 까지) — 전문가는 전 샘플 리뷰가 기본 의도다.
    # sample_limit 을 주면 **앞에서부터** 그 개수만(dto 주석에 무작위를 쓰지 않는 이유).
    n = cap
    rows = await _read_dataset_samples(dataset_ids, n, offset=sample_offset)
    if not rows:
        # 세트를 지정한 경우(offset>0)엔 합성 폴백을 쓰지 않는다. 데이터셋이 그 구간까지
        # 없는 것인데 mock 100개를 만들어 주면 평가자는 그게 가짜인 줄 모르고 채점하고,
        # 그 점수가 공인시험 결과로 남는다 — 조용한 폴백이 가장 위험한 지점이다.
        if sample_offset:
            raise Exception(
                f"selected sample set is out of range for this dataset "
                f"(offset={sample_offset})")
        # 실 데이터셋 못 읽음 → 합성 폴백(구 스캐폴딩과 동일 문자열 = 레거시 안정)
        rows = [{"input": f"[{base}] sample {i} 입력 프롬프트", "reference": f"참조 답변 {i}",
                 "dataset": ds_names[i % len(ds_names)] if ds_names else base}
                for i in range(n)]
    # mock output baseline 먼저 — 항상 출력 보장. start_expert 가 HTTP 핸들러를 잡고 있으므로
    # 실 추론은 전체 예산(_EXPERT_INFER_BUDGET) 내에서만 업그레이드(초과분은 mock 유지).
    samples = []
    for i, row in enumerate(rows):
        s = {"idx": i, "dataset": row.get("dataset", base), "input": row["input"],
             "output": f"[{model_name}] 응답 {i}", "reference": row.get("reference", ""),
             # 공개 플래그(비-_ 키라 _public_sample 통과) — 실추론 반영 여부. 텍스트는 아래
             # 예산 업그레이드에서, VLM 은 infer_expert_sample(지연 단위)에서 True 로 승격.
             "real_output": False}
        for k in ("image", "image_url", "image_served", "_image_abs", "_image_dir",
                  "csv_rows", "csv_text"):
            if k in row:
                s[k] = row[k]
        samples.append(s)
    if inference_target:
        # input 이 빈 샘플은 건너뛴다 — image-only(VLM) 샘플은 텍스트 추론에 이미지가 실리지
        # 않아 무의미하다. mock 유지, 실 VLM 추론은 infer_expert_sample(지연 단위).
        targets = [s for s in samples if s["input"]]
        sem = asyncio.Semaphore(_EXPERT_INFER_CONCURRENCY)

        async def _one(s):
            async with sem:
                real = await _infer_output(
                    inference_target, s["input"], f"expert-{model_id}-{s['idx']}")
            if real:
                s["output"] = real
                s["real_output"] = True

        async def _upgrade():
            # 예산 초과로 취소되면 이미 끝난 샘플의 실출력은 그대로 남는다(각 코루틴이
            # 자기 샘플에 직접 쓴다) — 취소 지점까지의 성과를 잃지 않는다.
            await asyncio.gather(*(_one(s) for s in targets), return_exceptions=True)

        try:
            await asyncio.wait_for(_upgrade(), _EXPERT_INFER_BUDGET)
        except asyncio.TimeoutError:
            pass    # 예산 초과 — 업그레이드된 샘플은 실출력, 나머지는 mock 유지
    return samples


async def _expert_session(model_id: int, job_id: str):
    """세션 행 + samples. start 시점 영속된 _samples(metrics)를 우선 사용 — 실 추론 출력은
    비결정적이라 매 조회 재생성하면 사람이 채점한 출력과 표시 출력이 어긋난다(A4). 영속이
    없으면(레거시) dataset_name 기반 결정적 합성으로 폴백."""
    if not job_id or not _JOB_ID_RE.match(job_id):
        raise ValueError(f"invalid job_id: {job_id!r}")
    row = await db_model.get_eval_result_by_job(job_str_id=job_id, source_model_id=model_id)
    # metric_set 검증 — 벤치마크/judge job_id 를 expert 로 다뤄 그 metrics 를
    # complete_eval_result 로 덮어쓰는 교차모드 오염 차단.
    if not row or row.get("metric_set") != "expert":
        raise Exception("expert session not found")
    metrics = row.get("metrics")
    if isinstance(metrics, str):
        try:
            metrics = json.loads(metrics)
        except (TypeError, json.JSONDecodeError):
            metrics = None
    persisted = (metrics or {}).get("_samples") if isinstance(metrics, dict) else None
    if isinstance(persisted, list) and persisted:
        return row, persisted
    # 레거시(영속 전 세션) → 결정적 합성 재구성(추론/데이터셋 없이).
    model_info = await db_model.get_model(model_id=model_id)
    model_name = (model_info or {}).get("name", "model")
    ds_names = [s for s in str(row.get("dataset_name") or "").split(",") if s]
    samples = await _build_expert_samples(model_id, model_name, [], ds_names, None)
    return row, samples


async def start_expert(project_id: int, model_id: int, dataset_ids: List[int],
                       inference_playground_id: Optional[int] = None,
                       inference_job_id: Optional[str] = None,
                       sample_limit: Optional[int] = None,
                       sample_set: Optional[int] = None,
                       run_name: Optional[str] = None,
                       expert_prompt: Optional[str] = None) -> dict:
    """전문가 평가 세션 시작 — model/dataset 는 **이 세션이 고른다**(2026-08-24 —
    프로젝트 워크스페이스 경계 검증은 유지). 빌린 배포(inference_playground_id)도 같은
    경계로 대조한다(2026-08-27). 채점 샘플 생성 + 세션 행.
    inference_job_id(러너 생성) 주면 그 샘플을, 없고 inference_playground_id 주면
    실 출력 추론. 생성 샘플은 metrics._samples 로 영속 → 재로드 안정(실 추론 비결정성/
    배포 종료에도 표시 고정).

    출력원 **둘 중 하나는 필수**다 — "둘 다 없으면 mock" 폴백은 없앴다(2026-08-27).
    사람이 별점을 매기는 화면이라 합성 문자열을 채점하면 그 점수가 곧바로 모델 평가로
    남는다(judge/benchmark 와 같은 규칙).
    ⚠️ **샘플 단위** mock 은 그대로다 — image-only(VLM) 샘플은 텍스트 추론을 건너뛰고
    mock 출력을 baseline 으로 두었다가 infer_expert_sample(지연 단위 VLM)이 승격한다.
    그래서 여기서는 배포가 텍스트 추론 대상으로 해석되는지까지는 요구하지 않는다 —
    SDS 배포 바인딩이 그 경로다."""
    # 출력원이 아예 없으면 사람이 채점할 실 출력이 없다 — 세션 행을 만들기 전에 거절한다.
    if not inference_playground_id and not inference_job_id:
        raise Exception(
            "채점할 출력이 필요합니다 — 평가할 모델을 서빙하는 배포를 먼저 시작해 "
            "지정하거나(inference_playground_id), 완료된 생성 런을 지정하세요"
            "(inference_job_id)")
    project = await _load_project_for_run(project_id, "expert")
    model_id = int(model_id)
    dataset_ids = _run_dataset_ids(dataset_ids)
    model_info, workspace_id = await _resolve_run_model(project, model_id)
    model_name = model_info["name"]

    ds_names = []
    for did in dataset_ids:
        d = await db_model.get_dataset_model(dataset_id=did)
        if not d:
            raise Exception(f"dataset {did} not found")
        if int(d["workspace_id"]) != workspace_id:
            raise Exception("dataset and model belong to different workspaces")
        ds_name = str(d["name"])
        # dataset_name(CSV)은 비교표/표시용. 안전 문자만(run_benchmark 동일 가드).
        if not _SAFE_SEGMENT_RE.match(ds_name):
            raise Exception("dataset name has unsafe characters")
        ds_names.append(ds_name)

    # 빌린 배포는 **이 세션의 워크스페이스 것**이어야 한다 — run_eval_inference 와 같은
    # 규칙·같은 문구(_playground_in_workspace)이고, 대조하는 workspace_id 의 출처도 같다
    # (_resolve_run_model 이 프로젝트에서 얻어 모델까지 이미 대조한 값).
    # ⚠️ inference_job_id 로 러너 샘플이 잡혀 이 세션이 배포를 부르지 않게 되더라도 **먼저**
    # 대조한다 — 이 id 는 metrics._inference_playground_id 로 영속돼 나중에
    # infer_expert_sample(지연 VLM 추론)이 그대로 호출하므로, 여기서 막지 않으면 경계가
    # 뒤로 새기만 한다.
    if inference_playground_id:
        await _playground_in_workspace(
            "inference", inference_playground_id, workspace_id)

    # P2-b2 — 러너 생성 샘플 우선(재추론 회피). 있으면 배포 대상 해석 스킵.
    run_samples, gen_prompt = await _load_run_samples(
        model_id, project_id, inference_job_id)
    # 러너 런만 지정했는데 그 샘플을 못 찾으면(미완료·타 프로젝트·타 모델) 배포 폴백도 없어
    # 전량 mock 이 된다 — 진입 게이트를 통과한 요청이 옛 폴백으로 되돌아가지 않게 막는다.
    if inference_job_id and not run_samples and not inference_playground_id:
        raise Exception(
            "지정한 생성 런(inference_job_id)의 샘플을 찾지 못했습니다 — 이 프로젝트·이 "
            "모델의 완료된 생성 런이어야 합니다")
    inference_target = (
        None
        if run_samples
        else await _resolve_inference_target(inference_playground_id)
    )
    # 생성 시스템 프롬프트(P3 헤더 고정 박스) — 러너 런 우선, 없으면 바인드 배포의 system_message.
    if not gen_prompt and inference_playground_id:
        gen_prompt = await _resolve_deploy_system_prompt(inference_playground_id)
    # 평가 세트 — 공인시험은 평가자가 여러 명이라 카드마다 다른 100문항 구간을 맡는다.
    # 같은 프로젝트 안에서 같은 데이터셋의 같은 세트를 두 카드가 잡으면 두 사람이 같은 문항을
    # 채점하게 되므로(그러라고 나눈 게 아니다) 여기서 거절한다. 범위는 프로젝트 안까지만 —
    # 재시험·다른 모델 평가에서는 같은 세트를 다시 써야 한다.
    sample_offset = 0
    if sample_set is not None:
        sample_set = int(sample_set)
        if not 1 <= sample_set <= EXPERT_SAMPLE_SET_COUNT:
            raise Exception(f"sample_set must be 1..{EXPERT_SAMPLE_SET_COUNT}")
        if (dataset_ids[0], sample_set) in await _expert_sets_in_use(project_id):
            raise Exception(f"sample set {sample_set} is already taken in this project")
        sample_offset = (sample_set - 1) * EXPERT_SAMPLE_SET_SIZE
        sample_limit = EXPERT_SAMPLE_SET_SIZE

    samples = await _build_expert_samples(
        model_id, model_name, dataset_ids, ds_names, inference_target, run_samples,
        sample_limit=sample_limit, sample_offset=sample_offset)
    # external eva-vlm(SDS)은 내부 system_message 가 없어 위 gen_prompt 가 None → 실사용 프롬프트
    #   미러로 폴백(샘플에 csv_rows=선박 계측표 있으면 SDS 시나리오, _expert_prompt 와 동일 판별).
    if not gen_prompt and any(
            isinstance(s, dict) and s.get("csv_rows") for s in samples):
        gen_prompt = SDS_GEN_SYSTEM_PROMPT
    dataset_name_csv = ",".join(ds_names)
    if len(dataset_name_csv) > 255:
        dataset_name_csv = f"{ds_names[0]} +{len(ds_names) - 1} more"[:255]

    # 시나리오 결속 고정 프롬프트(D3) — 샘플 shape(SDS=csv_rows)로 판별해 세션에 동결.
    # 생성 시 사용자가 지침을 직접 준 경우 그것을 우선 동결(표시 = 실제 채점 기준 일치).
    expert_prompt = (expert_prompt or "").strip() or _expert_prompt(samples)
    run_name = (run_name or "").strip() or None
    job_id = f"expert-{model_id}-{uuid.uuid4().hex[:16]}"
    await db_model.insert_eval_result(
        source_model_id=model_id, workspace_id=workspace_id, job_str_id=job_id,
        dataset_id=dataset_ids[0], dataset_name=dataset_name_csv, metric_set="expert",
        eval_project_id=project_id)
    # 샘플 + 고정 프롬프트 영속(running 유지) — get_expert_samples/submit 가 재생성 대신 이걸 읽는다.
    # inference_playground_id(배포 SDS) 는 지연 단위 VLM 추론(infer_expert_sample)이 세션 재로드
    # 후에도 대상 배포를 알 수 있도록 함께 영속(재개 세션 포함).
    metrics_obj = {"_mode": "expert", "_samples": samples, "_expert_prompt": expert_prompt}
    if gen_prompt:    # 생성 시스템 프롬프트 동결(세션 재로드 시 헤더 박스 유지)
        metrics_obj["_gen_system_prompt"] = gen_prompt
    if inference_playground_id:
        metrics_obj["_inference_playground_id"] = int(inference_playground_id)
    if run_name:      # 세션 제목 동결(run 목록·채점 헤더 표시원)
        metrics_obj["_run_name"] = run_name
    if sample_set:    # 평가 세트 동결 — 목록의 중복 판정과 카드 표시가 이 값을 읽는다
        metrics_obj["_sample_set"] = sample_set
    await db_model.set_eval_result_metrics(
        job_str_id=job_id, source_model_id=model_id,
        metrics_json=json.dumps(metrics_obj))
    try:
        await db_model.update_eval_project_status(project_id, PROJECT_STATUS_RUNNING)
    except Exception:
        traceback.print_exc()

    return {"project_id": project_id, "model_id": model_id, "job_id": job_id,
            "mode": "expert", "datasets": ds_names,
            "samples": [_public_sample(s) for s in samples],
            "total": len(samples),
            "real_output": bool(inference_target) or bool(run_samples),
            "used_runner": bool(run_samples),
            "inference_enabled": bool(inference_playground_id),
            "expert_prompt": expert_prompt, "gen_system_prompt": gen_prompt,
            "run_name": run_name}


def _session_inference_enabled(row: dict) -> bool:
    """세션에 배포 SDS(_inference_playground_id)가 바인드됐는지 — FE 가 지연 VLM 추론
    호출 여부를 판별(재개 세션 포함). 영속 metrics 에서 파생."""
    metrics = row.get("metrics") if isinstance(row, dict) else None
    if isinstance(metrics, str):
        try:
            metrics = json.loads(metrics)
        except (TypeError, json.JSONDecodeError):
            metrics = None
    return bool(isinstance(metrics, dict) and metrics.get("_inference_playground_id"))


def _session_gen_prompt(row: dict) -> Optional[str]:
    """세션에 동결된 생성 시스템 프롬프트(_gen_system_prompt) — 헤더 고정 박스 표시원(P3).
    영속 metrics 에서 파생(재개 세션 포함). 없으면 None(박스 숨김)."""
    metrics = row.get("metrics") if isinstance(row, dict) else None
    if isinstance(metrics, str):
        try:
            metrics = json.loads(metrics)
        except (TypeError, json.JSONDecodeError):
            metrics = None
    val = metrics.get("_gen_system_prompt") if isinstance(metrics, dict) else None
    return val if isinstance(val, str) and val else None


# 세션 동결 키 — start 시 metrics 에 동결해 재개·완료 후에도 표시가 유지돼야 하는 값들.
# 완료 시 submit_expert_rating 이 metrics 를 새로 쓰므로 그때 이월하지 않으면 소실된다.
_SESSION_FROZEN_KEYS = ("_run_name", "_gen_system_prompt", "_inference_playground_id",
                        "_sample_set")


def _session_metrics(row: dict) -> dict:
    """세션 행의 metrics(JSON 문자열/딕트) → 딕트. 부재·파싱 실패는 빈 딕트."""
    metrics = row.get("metrics") if isinstance(row, dict) else None
    if isinstance(metrics, str):
        try:
            metrics = json.loads(metrics)
        except (TypeError, json.JSONDecodeError):
            metrics = None
    return metrics if isinstance(metrics, dict) else {}


def _session_run_name(row: dict) -> Optional[str]:
    """세션 제목(_run_name) — 생성 시 사용자 입력을 동결한 값. eval_result 에 name 컬럼이 없어
    metrics 에 싣는다(llm_db 마이그레이션 러너 없음 → DDL 회피). 없으면 None(목록=데이터셋명)."""
    val = _session_metrics(row).get("_run_name")
    return val if isinstance(val, str) and val else None


def _session_sample_set(row: dict) -> Optional[int]:
    """세션이 잡은 평가 세트 번호(_sample_set). 없으면 None — 세트를 안 쓰고 만든 세션이다
    (전량/상위 N개). 중복 판정에서도 제외돼 새 카드가 어떤 세트든 고를 수 있다."""
    val = _session_metrics(row).get("_sample_set")
    return int(val) if isinstance(val, int) and val > 0 else None


async def _expert_sets_in_use(project_id: int) -> set:
    """이 프로젝트에서 이미 잡힌 (dataset_id, 세트번호) 집합. 삭제된 런은 행이 사라지므로
    그 세트는 자동으로 다시 열린다 — 별도 반납 처리가 필요 없다."""
    rows = await db_model.list_eval_results_by_project(eval_project_id=project_id) or []
    out = set()
    for row in rows:
        if row.get("metric_set") != "expert":
            continue
        n = _session_sample_set(row)
        if n and row.get("dataset_id") is not None:
            out.add((int(row["dataset_id"]), n))
    return out


def _session_frozen(row: dict) -> dict:
    """완료 시 metrics 재기록에 이월할 동결값만 추출(_SESSION_FROZEN_KEYS)."""
    m = _session_metrics(row)
    return {k: m[k] for k in _SESSION_FROZEN_KEYS if m.get(k) is not None}


async def get_expert_samples(model_id: int, job_id: str) -> dict:
    """세션 샘플 + 기존 채점 + 채점 이력(재개·감사추적용)."""
    row, samples = await _expert_session(model_id, job_id)
    ratings = await db_model.list_expert_ratings(job_str_id=job_id, source_model_id=model_id)
    history = await db_model.list_expert_rating_history(
        job_str_id=job_id, source_model_id=model_id)
    return {"job_id": job_id, "status": row.get("status"),
            "samples": [_public_sample(s) for s in samples],
            "total": len(samples), "ratings": ratings, "history": history,
            "inference_enabled": _session_inference_enabled(row),
            "expert_prompt": _session_prompt(row, samples),
            "gen_system_prompt": _session_gen_prompt(row),
            "run_name": _session_run_name(row)}


# 지연 단위 VLM 추론의 per-job 락 — 빠른 prev/next 네비로 동시 호출 시 _samples 재영속
# read-modify-write 경쟁(인접 샘플 clobber) 차단. job_id 단위(프로세스 생명주기 내 누적).
_EXPERT_INFER_LOCKS: dict = {}


def _expert_infer_lock(job_id: str) -> asyncio.Lock:
    lock = _EXPERT_INFER_LOCKS.get(job_id)
    if lock is None:
        lock = asyncio.Lock()
        _EXPERT_INFER_LOCKS[job_id] = lock
    return lock


async def infer_expert_sample(model_id: int, job_id: str, sample_idx: int) -> dict:
    """지연 단위 VLM 실추론 — 전문가가 여는 샘플 1개만 바인드된 배포 SDS 모델로 추론해
    output 을 실출력으로 교체·영속(동결). 배포 미바인드/비-VLM 샘플/이미 실출력/이미지 없음
    → no-op(mock 유지). per-job 락 + real_output 멱등으로 재영속 경쟁·중복추론 방지."""
    if not job_id or not _JOB_ID_RE.match(job_id):
        raise ValueError(f"invalid job_id: {job_id!r}")

    # ── 1) 사전 점검(락 밖) — 대상/바인드/이미지 확보 후 실추론 여부 판정 ──────────────
    row, samples = await _expert_session(model_id, job_id)
    if sample_idx < 0 or sample_idx >= len(samples):
        raise ValueError(f"sample_idx out of range: {sample_idx}")
    s = samples[sample_idx]
    if s.get("real_output"):    # 멱등 — 이미 실출력(동결)
        return {"real_output": True, "sample": _public_sample(s)}
    # 완료/취소 세션은 실추론 안 함 — set_eval_result_metrics 가 WHERE status='running' 이라
    # 영속이 no-op 이 되어 real_output 이 DB 에 안 남고, 그러면 재열람마다 실 GPU 추론이
    # 무한 재실행된다(리뷰 HIGH). running 아니면 현재 상태 그대로 반환(no-op).
    if row.get("status") != "running":
        return {"real_output": bool(s.get("real_output")), "sample": _public_sample(s)}
    metrics = row.get("metrics")
    if isinstance(metrics, str):
        try:
            metrics = json.loads(metrics)
        except (TypeError, json.JSONDecodeError):
            metrics = None
    pid = metrics.get("_inference_playground_id") if isinstance(metrics, dict) else None
    # 배포 미바인드 or VLM 샘플 아님(텍스트는 start 예산 경로) → no-op.
    if not pid or not (s.get("csv_rows") or s.get("image_served")):
        return {"real_output": False, "sample": _public_sample(s)}
    image_b64 = _sample_image_b64(s)
    if not image_b64:    # 서빙 이미지 없음/검증 실패 → 추론 불가
        return {"real_output": False, "sample": _public_sample(s)}

    # ── 2) VLM 호출(락 밖) — sync 최대 _VLM_INFER_TIMEOUT 라 락으로 잡으면 채점 완료나 다른
    #        샘플 infer 가 그동안 막힌다. 오래 걸리는 호출은 락 밖에서 수행. ──────────────
    text = await _infer_vlm_output(
        int(pid), image_b64, _csv_to_ais_rows(s), f"expert-{model_id}-{sample_idx}",
        _session_gen_prompt(row))
    if not text:    # 추론 실패/검증 거부/타임아웃 → mock 유지(graceful)
        return {"real_output": False, "sample": _public_sample(s)}

    # ── 3) 재영속(짧은 락 구간) — 쓰기 직전 최신 _samples 재로드 후 이 idx 만 갱신해 동시
    #        infer/완료와의 lost-update 를 막는다. 락 안에서 status 재확인(그 사이 완료됐으면
    #        WHERE status='running' 이 0행이라 영속 안 되므로 mock 로 포기). ──────────────
    async with _expert_infer_lock(job_id):
        fresh_row, fresh_samples = await _expert_session(model_id, job_id)
        if fresh_row.get("status") != "running":
            return {"real_output": False, "sample": _public_sample(s)}
        if sample_idx >= len(fresh_samples):
            return {"real_output": False, "sample": _public_sample(s)}
        fs = fresh_samples[sample_idx]
        if fs.get("real_output"):    # 그 사이 다른 호출이 채움 — 멱등
            return {"real_output": True, "sample": _public_sample(fs)}
        fs["output"] = text
        fs["real_output"] = True
        fresh_metrics = fresh_row.get("metrics")
        if isinstance(fresh_metrics, str):
            try:
                fresh_metrics = json.loads(fresh_metrics)
            except (TypeError, json.JSONDecodeError):
                fresh_metrics = None
        if not isinstance(fresh_metrics, dict):
            fresh_metrics = {"_mode": "expert"}
        fresh_metrics["_samples"] = fresh_samples    # _expert_prompt/_inference_playground_id 보존
        await db_model.set_eval_result_metrics(
            job_str_id=job_id, source_model_id=model_id,
            metrics_json=json.dumps(fresh_metrics))
        return {"real_output": True, "sample": _public_sample(fs)}


async def submit_expert_rating(model_id: int, job_id: str, sample_idx: int,
                               score: int, score_json=None, comment: str = None,
                               rater_user: str = None) -> dict:
    """채점 1건(1~5 별점) upsert → 평균/분포 재계산 → 전부 채점 시 세션 완료(eval_result 마감).
    verdict 는 score 에서 파생 기록(NOT NULL 보존·레거시 pass_rate/verdict 카운팅 유지)."""
    try:
        score = int(score)
    except (TypeError, ValueError):
        raise ValueError(f"invalid score: {score!r}")
    if score < EXPERT_SCORE_MIN or score > EXPERT_SCORE_MAX:
        raise ValueError(
            f"score out of range({EXPERT_SCORE_MIN}~{EXPERT_SCORE_MAX}): {score}")
    # score→verdict 파생 — 임계 이상은 합격(O). ⚠️ 임계값(EXPERT_VERDICT_PASS_THRESHOLD)은 잠정.
    verdict = "O" if score >= EXPERT_VERDICT_PASS_THRESHOLD else "X"
    # 확장 JSON(무스키마) — 직렬화 + 길이 상한(입력 경계 검증). None 이면 그대로 NULL.
    score_json_str = None
    if score_json is not None:
        score_json_str = json.dumps(score_json, ensure_ascii=False)
        if len(score_json_str) > EXPERT_SCORE_JSON_MAX_LEN:
            raise ValueError("score_json too large")
    row, samples = await _expert_session(model_id, job_id)
    # 완료된 세션 재채점 차단 — complete_eval_result 가 running 만 갱신해 metrics 가
    # stale 해지고 completed=True 가 반복 반환되는 문제 방지(재평가는 새 세션).
    if row.get("status") != "running":
        raise Exception("expert session already completed")
    total = len(samples)
    if sample_idx < 0 or sample_idx >= total:
        raise ValueError(f"sample_idx out of range: {sample_idx}")
    s = samples[sample_idx]
    await db_model.insert_expert_rating(
        source_model_id=model_id, job_str_id=job_id, sample_idx=sample_idx,
        verdict=verdict, score=score, score_json=score_json_str,
        input=s.get("input"), output=s.get("output"),
        reference=s.get("reference"), rater_user=rater_user, comment=comment)
    # 감사추적 — 메인 행은 (job_str_id,sample_idx) upsert 라 '현재' 채점만 남지만, 이력
    # 테이블엔 채점 이벤트마다 누적(누가 언제 어떻게 바꿨는지 불변 보존).
    await db_model.insert_expert_rating_history(
        source_model_id=model_id, job_str_id=job_id, sample_idx=sample_idx,
        verdict=verdict, score=score, score_json=score_json_str,
        comment=comment, rater_user=rater_user)

    ratings = await db_model.list_expert_ratings(job_str_id=job_id, source_model_id=model_id)
    rated = len(ratings)
    avg_score, distribution, pass_rate = _aggregate_expert(ratings)
    # 방금 채점의 채점자·시각 + 이 샘플의 누적 채점 횟수(재채점 표면화)를 반환 → FE 즉시 표시.
    this = next((r for r in ratings if r.get("sample_idx") == sample_idx), None)
    history = await db_model.list_expert_rating_history(
        job_str_id=job_id, source_model_id=model_id)
    rate_count = sum(1 for h in history if h.get("sample_idx") == sample_idx)

    completed = False
    if rated >= total:  # 전부 채점 → 집계 영속 + 완료(비교표 합류)
        # 완료 집계 직전 최신 _samples 재로드(infer 와 같은 per-job 락) — 동시 infer_expert_sample
        # 이 올린 실출력을 이 함수 상단(1565)의 stale 스냅샷으로 덮지 않도록(lost-update 방지).
        async with _expert_infer_lock(job_id):
            fresh_row, fresh_samples = await _expert_session(model_id, job_id)
            # expert_avg_score(1~5) = 신규 기본 metric(_flatten 자동 노출·방향 max). _distribution 은
            # _ 접두라 비교표 미노출. expert_pass_rate 는 backward-compat 병기. _samples/_expert_prompt
            # 보존 — 완료 후 get_expert_samples 가 표시 출력(최신 실출력 포함)·프롬프트 유지.
            # 동결값(_run_name·_gen_system_prompt·_inference_playground_id)은 여기서
            # metrics 를 새로 쓰기 때문에 이월하지 않으면 완료 시점에 소실된다(제목/생성
            # 프롬프트 박스가 완료 후 재개에서 사라짐).
            metrics = {**_session_frozen(fresh_row),
                       "expert_avg_score": avg_score, "expert_pass_rate": pass_rate,
                       "_distribution": distribution, "_mode": "expert",
                       "_rated": rated, "_total": total, "_samples": fresh_samples,
                       "_expert_prompt": _session_prompt(fresh_row, fresh_samples)}
            await db_model.complete_eval_result(
                job_str_id=job_id, metrics_json=json.dumps(metrics), source_model_id=model_id)
        # 완료 세션은 이후 infer 가 status 게이트로 no-op 이라 락 불요 → 회수(dict 누수 방지, 리뷰 LOW).
        _EXPERT_INFER_LOCKS.pop(job_id, None)
        completed = True

    return {"job_id": job_id, "rated": rated, "total": total,
            "avg_score": avg_score, "distribution": distribution,
            "pass_rate": pass_rate, "completed": completed,
            "rater_user": (this or {}).get("rater_user", rater_user),
            "rated_at": (this or {}).get("create_datetime"), "rate_count": rate_count}


async def get_expert_result(model_id: int, job_id: str) -> dict:
    """세션 진행/결과 — 상태 + 채점 목록 + 평균점수/분포(+ backward-compat pass_rate)."""
    if not job_id or not _JOB_ID_RE.match(job_id):
        raise ValueError(f"invalid job_id: {job_id!r}")
    row = await db_model.get_eval_result_by_job(job_str_id=job_id, source_model_id=model_id)
    if not row or row.get("metric_set") != "expert":
        return {"job_id": job_id, "status": "pending", "ratings": [],
                "avg_score": None, "distribution": None, "pass_rate": None}
    ratings = await db_model.list_expert_ratings(job_str_id=job_id, source_model_id=model_id)
    history = await db_model.list_expert_rating_history(
        job_str_id=job_id, source_model_id=model_id)
    rated = len(ratings)
    avg_score, distribution, pass_rate = _aggregate_expert(ratings)
    if rated == 0:    # 미채점 세션은 평균·합격률 미정(None) — 레거시 shape 보존.
        avg_score, pass_rate = None, None
    return {"job_id": job_id, "status": row.get("status"), "ratings": ratings,
            "history": history, "rated": rated, "avg_score": avg_score,
            "distribution": distribution, "pass_rate": pass_rate}


async def get_expert_image(model_id: int, job_id: str, sample_idx: int):
    """샘플 이미지 1건의 (절대경로, media_type). NFS 상대경로 이미지(서버 보관 _image_abs)만
    서빙 — URL 이미지는 FE 가 직접 렌더하므로 여기로 오지 않는다. 없거나 검증 실패 시 예외
    (라우트가 404). 경로 봉쇄는 build 시 데이터셋 디렉터리 commonpath 로 완료했고, 영속값이라도
    재검증(파일 존재 + 이미지 확장자)해 방어."""
    row, samples = await _expert_session(model_id, job_id)
    if sample_idx < 0 or sample_idx >= len(samples):
        raise ValueError(f"sample_idx out of range: {sample_idx}")
    abs_path = samples[sample_idx].get("_image_abs")
    if not abs_path:
        raise FileNotFoundError("no served image for sample")
    real = os.path.realpath(abs_path)
    # 서빙 시 데이터셋 디렉터리 재봉쇄 — start 이후 파일이 디렉터리 밖을 가리키는 심링크로
    # 교체돼도(symlink-swap) 이탈 차단(build 시 commonpath 가드의 시점 외 보강).
    image_dir = samples[sample_idx].get("_image_dir")
    if image_dir and os.path.commonpath([real, image_dir]) != image_dir:
        raise FileNotFoundError("image escapes dataset dir")
    ext = os.path.splitext(real)[1].lower()
    if not os.path.isfile(real) or ext not in _IMAGE_MEDIA:
        raise FileNotFoundError("image not available")
    return real, _IMAGE_MEDIA[ext]
