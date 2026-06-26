"""llm_evaluation — 평가 오케스트레이션 service (P1b, 벤치마크).

벤치마크 런을 job_type=evaluate 외부 컨테이너(P1a mock evaluate-benchmark-mock / 정식)에
위임. llm_model.evaluate_model 과 동형 — fb_external_container 런치 + eval_result lazy
영속화(fb_utils.llm_db)를 재사용(코드 중복 0). 대상=학습완료 모델, reserved
_base_model→/model, _dataset→/dataset/<name>. 멀티 데이터셋 이름은 params.datasets 로 전달
(mock 은 이름으로 채점). metrics.json 은 jobs/<job_id>/output/ 에 떨어지고 get_eval_result
가 lazy 로 eval_result 를 마감.
"""
from __future__ import annotations

import json
import os
import re
import traceback
from typing import List, Optional

import httpx

from utils import PATH, settings
from utils.llm_db import db_model

from external.proxy import ExternalContainerClient, ExternalContainerError
from evaluation.constants import BENCHMARK_METRICS

# pod subPath 단일 segment(/dataset/<name>, models/<name>)에 들어가므로 조작문자 거부.
_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


async def run_benchmark(model_id: int, dataset_ids: List[int],
                        metric_set: Optional[List[str]] = None) -> dict:
    """벤치마크 평가 런 — 대상 모델 × 데이터셋(다중) × 메트릭 → evaluate 컨테이너 런치."""
    model_info = await db_model.get_model(model_id=model_id)
    if not model_info:
        raise Exception(f"model {model_id} not found")
    model_name = model_info["name"]
    workspace_id = int(model_info["workspace_id"])
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

    metrics = [m for m in (metric_set or list(BENCHMARK_METRICS))
               if m in BENCHMARK_METRICS] or list(BENCHMARK_METRICS)
    metric_csv = ",".join(metrics)
    ds_names = [str(d["name"]) for d in datasets]
    # eval_result.dataset_name 은 VARCHAR(255). 멀티 데이터셋 CSV 가 넘으면 요약형으로
    # 저장(런 자체는 진행 — 전체 목록은 반환 dict 의 datasets 로 보존). dataset_ids 상한
    # (MAX_BENCHMARK_DATASETS)은 dto 에서 강제.
    dataset_name_csv = ",".join(ds_names)
    if len(dataset_name_csv) > 255:
        dataset_name_csv = f"{ds_names[0]} +{len(ds_names) - 1} more"[:255]

    # reserved _dataset = 첫 데이터셋(마운트·validator 충족). 전체 이름은 params.datasets.
    primary = datasets[0]
    params = {
        "_base_model": {"name": model_name},
        "_dataset": {"name": primary["name"], "access": primary["access"]},
        "datasets": ds_names,
        "metric_set": metrics,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as http:
            client = ExternalContainerClient(
                base_url=settings.FB_EXTERNAL_CONTAINER_URL, client=http)
            raw = await client.start_job(
                manifest_name=settings.BENCHMARK_MANIFEST_NAME,
                manifest_version=settings.BENCHMARK_MANIFEST_VERSION,
                workspace_id=workspace_id, params=params)
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
            job_str_id=job_id, dataset_id=dataset_ids[0],
            dataset_name=dataset_name_csv, metric_set=metric_csv)
    except Exception:
        traceback.print_exc()

    return {
        "model_id": model_id, "model_name": model_name, "workspace_id": workspace_id,
        "dataset_ids": dataset_ids, "datasets": ds_names, "metric_set": metrics,
        "manifest_name": settings.BENCHMARK_MANIFEST_NAME,
        "manifest_version": settings.BENCHMARK_MANIFEST_VERSION,
        "job_id": job_id, "mode": "benchmark",
    }


async def _eval_output_dir(model_id: int, job_id: str) -> str:
    """evaluate job 결과 디렉토리(jobs/<job_id>/output) 안전 해석(llm_model 동형)."""
    if not job_id or not _JOB_ID_RE.match(job_id):
        raise ValueError(f"invalid job_id: {job_id!r}")
    model_info = await db_model.get_model(model_id=model_id)
    if not model_info:
        raise Exception(f"model {model_id} not found")
    ws = await db_model.get_workspace_model(workspace_id=int(model_info["workspace_id"]))
    if not ws:
        raise Exception(f"workspace for model {model_id} not found")
    main_root = PATH.JF_MAIN_STORAGE_PATH.format(
        STORAGE_NAME=ws["main_storage_name"], WORKSPACE_NAME=ws["name"],
    )
    jobs_base = os.path.realpath(os.path.join(main_root, "jobs"))
    output_dir = os.path.join(jobs_base, job_id, "output")
    if os.path.commonpath([os.path.realpath(output_dir), jobs_base]) != jobs_base:
        raise ValueError("output path escapes jobs base")
    return output_dir


async def get_eval_result(model_id: int, job_id: str) -> dict:
    """평가 job metrics.json 읽기 + 완료 시 eval_result lazy 마감(idempotent)."""
    output_dir = await _eval_output_dir(model_id, job_id)
    out_real = os.path.realpath(output_dir)
    metrics_path = os.path.join(output_dir, "metrics.json")
    if os.path.commonpath([os.path.realpath(metrics_path), out_real]) != out_real:
        raise ValueError("metrics path escapes output dir")
    if not os.path.isfile(metrics_path):
        return {"job_id": job_id, "metrics": None, "ready": False}
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
    """모델의 평가 이력(최신순). 비교표/best 마킹은 P1c FE 배선 시 보강.
    ⚠️ authZ: 호출자 워크스페이스 ownership 미검증(IDOR) — 단, 플랫폼 authZ posture 가
    전 서비스 비활성(workspace_access_check 주석)이라 단일앱 분기 패치 안 함. 플랫폼 차원
    (SP-13) 일괄 해소 대상(레퍼런스 llm_model 동일). 모델별 eval 이력 열람 한정이라 영향 제한."""
    rows = await db_model.list_eval_results(source_model_id=model_id)
    return {"model_id": model_id, "results": rows}
