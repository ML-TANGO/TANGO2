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
import csv
import glob
import hashlib
import io
import ipaddress
import json
import os
import re
import socket
import traceback
import uuid
from typing import List, Optional
from urllib.parse import quote, urlparse

import httpx

from utils import PATH, settings
from utils.llm_db import db_model

from external.proxy import ExternalContainerClient, ExternalContainerError
from evaluation.constants import (
    BENCHMARK_METRICS,
    EVAL_TYPES,
    MAX_BENCHMARK_DATASETS,
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
    JUDGE_CRITERIA,
    JUDGE_DEFAULT_MODEL,
    JUDGE_PROVIDER_HOSTS,
    MAX_COMPARE_MODELS,
    MAX_EXPERT_SAMPLES,
    MAX_JUDGE_RUN_SECONDS,
    MAX_JUDGE_SAMPLES,
    SDS_SAMPLE_DIR_GLOB,
    STALE_RUNNING_MAX_HOURS,
)

# pod subPath 단일 segment(/dataset/<name>, models/<name>)에 들어가므로 조작문자 거부.
_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


async def run_benchmark(project_id: int,
                        metric_set: Optional[List[str]] = None) -> dict:
    """벤치마크 평가 런 — 프로젝트에서 model/dataset(잠금) 상속 → evaluate 컨테이너 런치.
    model_id·dataset_ids 는 프로젝트에서 주입(요청 바디 미수취 → 불변 강제, P3). 유형별
    설정(metric_set)만 body 에서 받는다. run 생성 시 프로젝트를 'running' 으로 전이."""
    project, dataset_ids = await _load_project_for_run(project_id, "benchmark")
    model_id = int(project["model_id"])
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
            dataset_name=dataset_name_csv, metric_set=metric_csv,
            eval_project_id=project_id)
        await db_model.update_eval_project_status(project_id, PROJECT_STATUS_RUNNING)
    except Exception:
        traceback.print_exc()

    return {
        "project_id": project_id,
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
        # 파일 아직 없음 → DB 상태로 failed/cancelled 조기 surface(컨테이너 실패 시 FE 가
        # POLL_MAX 까지 헛폴링하지 않도록). 정상 진행 중이면 running.
        try:
            row = await db_model.get_eval_result_by_job(
                job_str_id=job_id, source_model_id=model_id)
            db_status = (row or {}).get("status") or "running"
        except Exception:
            db_status = "running"
        return {"job_id": job_id, "metrics": None, "ready": False, "status": db_status}
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
    return {"models": models, **db_model.build_eval_comparison(all_rows)}


# ── 평가 프로젝트 관리 (2026-07-07) ──────────────────────────────────────────
# 관리 단위 = 프로젝트(모델·데이터셋·유형·이름 잠금, P3). 생성=대기(created·run 0개, P5),
# run-start(benchmark/judge/expert)는 프로젝트에서 잠긴 model/dataset 를 주입해 불변 강제.
# authZ: 워크스페이스 ownership 미검증(IDOR) — 플랫폼 posture 일괄(SP-13), 기존 eval
# 엔드포인트와 동일하게 단일앱 분기 패치 안 함.

def _parse_dataset_ids(raw) -> List[int]:
    """eval_project.dataset_ids(JSON 컬럼)를 int 리스트로 정규화. 드라이버가 문자열/리스트
    어느 쪽으로 주든 방어(비정수 토큰은 조용히 스킵)."""
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


async def _load_project_for_run(project_id: int, eval_type: str):
    """run-start 공통 — 프로젝트 로드 + 잠긴 dataset_ids 반환. 프로젝트 유형과 다른 run
    생성은 거부(benchmark 프로젝트에 judge run 등 교차유형 차단)."""
    project = await db_model.get_eval_project(project_id=project_id)
    if not project:
        raise Exception(f"eval project {project_id} not found")
    if project.get("eval_type") != eval_type:
        raise Exception(
            f"project eval_type is {project.get('eval_type')!r}, not {eval_type!r}")
    dataset_ids = _parse_dataset_ids(project.get("dataset_ids"))
    if not dataset_ids:
        raise Exception("eval project has no dataset_ids")
    return project, dataset_ids


async def create_project(name: str, model_id: int, dataset_ids: List[int],
                         eval_type: str, creator: Optional[str] = None) -> dict:
    """평가 프로젝트 생성(대기 상태 created, run 0개, P5). 모델의 워크스페이스를 상속하고
    데이터셋(들)이 모두 그 워크스페이스에 속하는지 검증(잠금 전 1회 — run 마다 재검증도 유지).
    이후 model/dataset/type/name 불변(P3). creator 는 라우트가 jf-User 헤더로 주입."""
    if eval_type not in EVAL_TYPES:
        raise ValueError(f"unknown eval_type: {eval_type}")
    if not name or not name.strip():
        raise ValueError("project name required")
    if len(name) > 255:
        raise ValueError("project name too long")
    if not dataset_ids:
        raise ValueError("at least one dataset required")
    if len(dataset_ids) > MAX_BENCHMARK_DATASETS:
        raise ValueError(f"too many datasets (max {MAX_BENCHMARK_DATASETS})")
    model_info = await db_model.get_model(model_id=model_id)
    if not model_info:
        raise Exception(f"model {model_id} not found")
    workspace_id = int(model_info["workspace_id"])
    # 중복 제거(순서 보존) + 워크스페이스 경계 검증(잠금 전 1회).
    seen: set = set()
    locked: List[int] = []
    for did in dataset_ids:
        if did in seen:
            continue
        seen.add(did)
        d = await db_model.get_dataset_model(dataset_id=did)
        if not d:
            raise Exception(f"dataset {did} not found")
        if int(d["workspace_id"]) != workspace_id:
            raise Exception("dataset and model belong to different workspaces")
        locked.append(did)
    project_id = await db_model.create_eval_project(
        workspace_id=workspace_id, name=name.strip(), model_id=model_id,
        dataset_ids_json=json.dumps(locked), eval_type=eval_type, creator=creator)
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
    집계로 읽어 프로젝트별로 파생한다(집계에 없는 프로젝트=run 0개→created)."""
    projects = await db_model.list_eval_projects(workspace_id=workspace_id)
    project_ids = [int(p["id"]) for p in projects if p.get("id") is not None]
    status_rows = await db_model.count_run_statuses_by_projects(project_ids)
    by_project: dict = {}
    for row in status_rows:
        by_project.setdefault(int(row["eval_project_id"]), []).append(row.get("status"))
    out = [{**p, "dataset_ids": _parse_dataset_ids(p.get("dataset_ids")),
            "status": _derive_project_status(by_project.get(int(p["id"]), []))}
           for p in projects]
    return {"workspace_id": workspace_id, "projects": out}


async def get_project(project_id: int) -> dict:
    """프로젝트 단건(불변 헤더) + 자식 run 목록(프로젝트 내 비교표 shape). dataset_ids 는
    JSON → 리스트. runs 는 build_eval_comparison 재사용(run.id 키 best)."""
    project = await db_model.get_eval_project(project_id=project_id)
    if not project:
        raise Exception(f"eval project {project_id} not found")
    rows = await db_model.list_eval_results_by_project(eval_project_id=project_id)
    # 표시 상태는 자식 run 상태에서 파생(§5) — DB 의 raw status 를 오버라이드.
    derived_status = _derive_project_status([r.get("status") for r in rows])
    return {"project": {**project, "dataset_ids": _parse_dataset_ids(project.get("dataset_ids")),
                        "status": derived_status},
            "runs": db_model.build_eval_comparison(rows)}


async def delete_project(project_id: int) -> dict:
    """프로젝트 삭제 — FK ON DELETE CASCADE 로 자식 run + expert rating/history 전 체인 정리.
    존재확인 후 삭제(없으면 not-found)."""
    project = await db_model.get_eval_project(project_id=project_id)
    if not project:
        return {"project_id": project_id, "deleted": False, "reason": "not-found"}
    await db_model.delete_eval_project(project_id=project_id)
    return {"project_id": project_id, "deleted": True}


async def compare_project_runs(project_id: int) -> dict:
    """프로젝트 내 run 비교(same model+dataset = apples-to-apples). run 단위 비교표
    (build_eval_comparison 재사용 — best 를 run.id 에 키)."""
    project = await db_model.get_eval_project(project_id=project_id)
    if not project:
        raise Exception(f"eval project {project_id} not found")
    rows = await db_model.list_eval_results_by_project(eval_project_id=project_id)
    return {"project_id": project_id, **db_model.build_eval_comparison(rows)}


# ── LLM-as-a-Judge (P2) ──────────────────────────────────────────────────────
# 직접호출 오케스트레이션(컨테이너 X) — API 키가 transient·영속/로그 금지라 컨테이너 params/
# pod env 로 넘기면 누출됨 → BE 백그라운드 태스크가 in-memory 로만 키 사용. 결과(per-criterion
# 점수)는 eval_result.metrics 에 직접 기록(NFS 미경유). 벤치마크 metrics 와 충돌 방지로
# 'judge_' 접두. JUDGE_MOCK=true(기본) 면 실 provider 호출 없이 결정적 mock 점수(키 불필요).

_judge_tasks = set()  # fire-and-forget 태스크 GC 방지용 강참조


def _judge_mock_enabled() -> bool:
    val = getattr(settings, "JUDGE_MOCK", None)
    if val is None:
        val = os.environ.get("JUDGE_MOCK", "true")
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def _validate_local_url(base_url: Optional[str]) -> tuple:
    """Local LLM endpoint SSRF 가드. 반환: (연결용 검증 IP, Host 헤더값).

    DNS rebinding TOCTOU 차단: 여기서 resolve 한 IP 를 _judge_local 이 그대로 connect 에
    사용(httpx 재resolve 회피). 모든 resolve 결과를 검사(라운드로빈/멀티레코드 우회 방지).
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


async def list_judges() -> dict:
    """가용 심판 — 상용 3종(키=사용자입력) + Local(URL=사용자입력) + 기준 목록.
    실제 키/URL 은 런 실행 시점에만 전달(플랫폼 Secret/env 보관 X)."""
    commercial = [
        {"id": pid, "label": label, "model": JUDGE_DEFAULT_MODEL[pid], "needs_key": True}
        for pid, label in (("chatgpt", "ChatGPT"), ("claude", "Claude"), ("gemini", "Gemini"))
    ]
    return {
        "commercial": commercial,
        "local": {"id": "local", "label": "Local LLM", "needs_url": True},
        "criteria": list(JUDGE_CRITERIA),
        "mock": _judge_mock_enabled(),
    }


# ── A4 실 모델출력 배선 (실 데이터셋 읽기 + 배포모델 추론, mock 폴백) ──────────────
# input/reference 컬럼 자동 감지(여러 데이터셋 스키마 수용). Alpaca 류 단일 text 필드는
# "### Response:" 로 분리. 비수치 데이터셋은 첫 prompt 류 키를 input 으로.
_PROMPT_KEYS = ("prompt", "input", "question", "instruction", "query", "text")
_REFERENCE_KEYS = ("reference", "answer", "output", "completion", "response", "label",
                   "target", "caption")
_MAX_FIELD_LEN = 2000          # 샘플 필드 길이 cap(프롬프트/출력/참조)
_INFER_TIMEOUT = 60.0          # 추론 1건 타임아웃(초)
_DATA_EXTS = (".jsonl", ".json", ".csv")
_MAX_DATA_FILE_BYTES = 50 * 1024 * 1024  # .json 전체 로드 상한(메모리 보호; jsonl/csv 는 스트리밍)
_EXPERT_INFER_BUDGET = 90      # start_expert 인라인 추론 전체 예산(초) — HTTP 핸들러 점유 cap

# 멀티모달(VLM) 전문가 평가 — 데이터셋 row 의 이미지 컬럼을 surface 해 사람이 이미지를 보고
# 채점. 강한 이미지 컬럼명은 값 그대로, 약한(범용) 컬럼명은 이미지 확장자일 때만 채택(오탐 방지).
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


async def _read_dataset_samples(dataset_ids: List[int], limit: int) -> list:
    """워크스페이스 NFS 데이터셋에서 (input, reference) 샘플을 limit 개까지 읽는다.
    eval pod 가 /jf-data 를 마운트(get_eval_result 의 metrics.json 읽기와 동일 마운트).
    파일 없음/포맷 불일치(arrow 등) → 빈 리스트 → 호출자가 mock 으로 폴백."""
    samples = []
    for did in dataset_ids:
        if len(samples) >= limit:
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
            sds = _read_sds_samples(ddir_real, str(ds["name"]), limit - len(samples))
            if sds is not None:
                samples.extend(sds)
                continue
            files = sorted(
                os.path.join(r, fn)
                for r, _dirs, fns in os.walk(ddir_real)
                for fn in fns if fn.lower().endswith(_DATA_EXTS))
            for fp in files:
                if len(samples) >= limit:
                    break
                # 경로 봉쇄(심링크 이탈 방지) — 다른 워크스페이스 파일 읽기 차단.
                if os.path.commonpath([os.path.realpath(fp), ddir_real]) != ddir_real:
                    continue
                for rec in _read_data_file(fp, limit - len(samples)):
                    sample = {
                        "input": rec["input"][:_MAX_FIELD_LEN],
                        "reference": (rec.get("reference") or "")[:_MAX_FIELD_LEN],
                        "dataset": str(ds["name"]),
                    }
                    if rec.get("image"):
                        _attach_image(sample, rec["image"], fp, ddir_real)
                    samples.append(sample)
                    if len(samples) >= limit:
                        break
        except Exception:
            traceback.print_exc()
            continue
    return samples


async def _resolve_inference_url(playground_id: Optional[int]) -> Optional[str]:
    """배포(running) 모델의 추론 test_url 을 playground s2s(get_test_options)로 해석.
    playground_id 미지정/해석 실패 → None(호출자가 mock output 폴백). 모델→배포 매핑은
    배포 목록을 가진 FE 가 inference_playground_id 로 전달(명시 계약·magic 탐색 회피)."""
    if not playground_id:
        return None
    try:
        url = (f"http://{settings.LLM_PLAYGROUND_DNS}"
               f"/api/playgrounds/test/options?playground_id={int(playground_id)}")
        async with httpx.AsyncClient(timeout=10.0) as http:
            r = await http.get(url)
        if r.status_code != 200:
            # 실 추론이 mock 으로 조용히 폴백된 원인을 운영에서 추적 가능하게(키 노출 없음).
            print(f"_resolve_inference_url: playground {playground_id} HTTP {r.status_code}",
                  flush=True)
            return None
        data = r.json()
        if data.get("status") == 1:
            return (data.get("result") or {}).get("test_url")
        print(f"_resolve_inference_url: playground {playground_id} envelope status="
              f"{data.get('status')}", flush=True)
    except Exception:
        traceback.print_exc()
    return None


async def _infer_output(test_url: str, prompt: str, session_id: str) -> Optional[str]:
    """배포 모델 추론 1건 — test_url 로 {input_type:question, input, session_id} POST.
    응답에서 출력 텍스트 추출(여러 키 수용). 실패/타임아웃 → None(mock 폴백)."""
    try:
        async with httpx.AsyncClient(timeout=_INFER_TIMEOUT) as http:
            r = await http.post(test_url, json={
                "input_type": "question", "input": prompt, "session_id": session_id})
        try:
            data = r.json()
        except ValueError:
            return (r.text or "").strip()[:_MAX_FIELD_LEN] or None
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


async def _build_judge_samples(model_id: int, model_name: str, dataset_ids: List[int],
                               ds_names: List[str], inference_url: Optional[str]) -> list:
    """채점 대상 샘플(A4) — 실 데이터셋(input/reference) + 배포모델 추론 output.
    데이터셋을 못 읽으면 합성 input 으로, 추론 URL 없으면 mock output 으로 폴백."""
    n = min(MAX_JUDGE_SAMPLES, max(1, len(ds_names) * 5))
    rows = await _read_dataset_samples(dataset_ids, n)
    base = ds_names[0] if ds_names else "dataset"
    if not rows:    # 실 데이터셋 못 읽음 → 합성 input 폴백(기존 스캐폴딩 동등)
        rows = [{"input": f"[{base}] sample {i} prompt", "reference": "",
                 "dataset": base} for i in range(n)]
    samples = []
    for i, row in enumerate(rows):
        out = None
        if inference_url and row["input"]:    # image-only(빈 input)는 텍스트 추론 스킵
            out = await _infer_output(inference_url, row["input"], f"judge-{model_id}-{i}")
        if not out:
            out = f"[{model_name}] response {i}"    # 추론 불가 → mock output
        samples.append({"id": f"{model_name}-{row.get('dataset', base)}-{i}",
                        "input": row["input"], "output": out,
                        "reference": row.get("reference", "")})
    return samples


def _build_judge_prompt(criteria: List[str], custom_prompt: Optional[str], sample: dict) -> str:
    crit_lines = "\n".join(f"- {c}" for c in criteria)
    base = custom_prompt or "주어진 입력에 대한 모델 출력을 아래 기준으로 1~5점 평가하세요."
    return (
        f"{base}\n\n[입력]\n{sample.get('input', '')}\n\n[모델 출력]\n{sample.get('output', '')}\n\n"
        f"[기준]\n{crit_lines}\n\n"
        "각 기준에 대해 1~5 정수 점수를 JSON 으로만 응답하세요. "
        '예: {"accuracy": 4, "relevance": 5}. 기준 키만 포함.'
    )


def _parse_judge_scores(text: str, criteria: List[str]) -> dict:
    """심판 응답(JSON)에서 기준별 1~5 점수 → 0~100. 범위(1~5) 밖 값(예: {"accuracy":999})은
    무음 만점 변환을 막기 위해 스킵(클램프 X)."""
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        raise ValueError("judge response has no JSON object")
    data = json.loads(m.group(0))
    out = {}
    for c in criteria:
        if c in data:
            try:
                raw = float(data[c])
            except (TypeError, ValueError):
                continue
            if 1.0 <= raw <= 5.0:
                out[c] = round(raw * 20.0, 2)
    return out


def _judge_mock(provider: str, criteria: List[str], sample: dict) -> dict:
    """결정적 mock 점수(55~95) — 키/네트워크 불필요. (provider, criterion, sample) 시드."""
    out = {}
    for c in criteria:
        h = int(hashlib.sha256(f"{provider}:{c}:{sample['id']}".encode()).hexdigest(), 16)
        out[c] = round(55.0 + (h % 4001) / 100.0, 2)
    return out


async def _judge_openai(api_key, model, criteria, custom_prompt, sample) -> dict:
    prompt = _build_judge_prompt(criteria, custom_prompt, sample)
    async with httpx.AsyncClient(timeout=60.0) as http:
        r = await http.post(
            f"https://{JUDGE_PROVIDER_HOSTS['chatgpt']}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model or JUDGE_DEFAULT_MODEL["chatgpt"],
                  "messages": [{"role": "user", "content": prompt}], "temperature": 0})
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
    return _parse_judge_scores(text, criteria)


async def _judge_anthropic(api_key, model, criteria, custom_prompt, sample) -> dict:
    prompt = _build_judge_prompt(criteria, custom_prompt, sample)
    async with httpx.AsyncClient(timeout=60.0) as http:
        r = await http.post(
            f"https://{JUDGE_PROVIDER_HOSTS['claude']}/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            json={"model": model or JUDGE_DEFAULT_MODEL["claude"], "max_tokens": 512,
                  "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json().get("content", []))
    return _parse_judge_scores(text, criteria)


async def _judge_gemini(api_key, model, criteria, custom_prompt, sample) -> dict:
    prompt = _build_judge_prompt(criteria, custom_prompt, sample)
    # dto 패턴(영숫자/._-)으로 이미 경로조작 차단 + URL 보간 방어로 segment 인코딩(이중방어).
    mdl = quote(model or JUDGE_DEFAULT_MODEL["gemini"], safe="")
    async with httpx.AsyncClient(timeout=60.0) as http:
        # 키는 헤더로만(x-goog-api-key) — URL 쿼리에 넣으면 httpx 예외/액세스로그의 URL 에
        # 키가 노출됨. 다른 어댑터(Authorization/x-api-key)와 동일하게 헤더 전달.
        r = await http.post(
            f"https://{JUDGE_PROVIDER_HOSTS['gemini']}/v1beta/models/{mdl}:generateContent",
            headers={"x-goog-api-key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]})
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return _parse_judge_scores(text, criteria)


async def _judge_local(base_url, model, criteria, custom_prompt, sample) -> dict:
    # 매 호출 resolve+검증 후 그 IP 로 직접 connect(TOCTOU 차단). https+hostname 은 cert
    # 불일치로 fail-closed(내부 local LLM 은 보통 http). IPv6 는 대괄호.
    safe_ip, host_header = _validate_local_url(base_url)
    p = urlparse(base_url)
    ip_host = f"[{safe_ip}]" if ":" in safe_ip else safe_ip
    port_seg = f":{p.port}" if p.port else ""
    path = (p.path or "").rstrip("/") + "/chat/completions"  # OpenAI 호환 가정
    url = f"{p.scheme}://{ip_host}{port_seg}{path}"
    prompt = _build_judge_prompt(criteria, custom_prompt, sample)
    async with httpx.AsyncClient(timeout=60.0) as http:
        r = await http.post(url, headers={"Host": host_header}, json={
            "model": model or "local",
            "messages": [{"role": "user", "content": prompt}], "temperature": 0})
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
    return _parse_judge_scores(text, criteria)


async def _judge_score(provider, judge_model, api_key, base_url,
                       criteria, custom_prompt, sample) -> dict:
    if _judge_mock_enabled():
        return _judge_mock(provider, criteria, sample)
    if provider == "local":
        return await _judge_local(base_url, judge_model, criteria, custom_prompt, sample)
    if provider == "chatgpt":
        return await _judge_openai(api_key, judge_model, criteria, custom_prompt, sample)
    if provider == "claude":
        return await _judge_anthropic(api_key, judge_model, criteria, custom_prompt, sample)
    if provider == "gemini":
        return await _judge_gemini(api_key, judge_model, criteria, custom_prompt, sample)
    raise Exception(f"unsupported provider: {provider}")


async def _run_judge_task(model_id, job_id, model_name, dataset_ids, ds_names, provider,
                          judge_model, api_key, base_url, criteria, custom_prompt,
                          inference_url=None) -> None:
    """백그라운드 judge 루프 — 샘플별 심판 호출 → 기준별 평균(0~100) → eval_result 마감.
    ⚠️ api_key 는 이 함수 인자로만 존재(in-memory). 절대 로그/DB 기록 금지.
    전역 wall-clock 상한(MAX_JUDGE_RUN_SECONDS) 초과(hung provider 등) 시 failed 처리.
    inference_url 있으면 대상 모델 실 추론으로 output 생성, 없으면 mock(A4)."""
    try:
        async def _score_all():
            samples = await _build_judge_samples(
                model_id, model_name, dataset_ids, ds_names, inference_url)
            agg = {c: [] for c in criteria}
            for s in samples:
                scores = await _judge_score(provider, judge_model, api_key, base_url,
                                            criteria, custom_prompt, s)
                for c in criteria:
                    if c in scores:
                        agg[c].append(scores[c])
            return samples, agg

        samples, agg = await asyncio.wait_for(
            _score_all(), timeout=MAX_JUDGE_RUN_SECONDS)
        metrics = {}
        for c in criteria:
            if agg[c]:
                metrics[f"judge_{c}"] = round(sum(agg[c]) / len(agg[c]), 2)
        if not metrics:
            raise Exception("judge produced no scores")
        # 내부 메타(_접두 → 비교표 metric_keys 에서 제외).
        metrics["_mode"] = "judge"
        metrics["_provider"] = provider
        metrics["_samples"] = len(samples)
        await db_model.complete_eval_result(
            job_str_id=job_id, metrics_json=json.dumps(metrics), source_model_id=model_id)
    except Exception:
        # 트레이스백에 api_key 노출 없음 — 키는 헤더로만 전달, 예외 메시지는 URL/상태뿐.
        traceback.print_exc()
        try:
            await db_model.update_eval_result_status(
                job_str_id=job_id, status="failed", source_model_id=model_id)
        except Exception:
            traceback.print_exc()


async def run_judge(project_id: int, provider: str,
                    criteria: List[str], judge_model: Optional[str] = None,
                    api_key: Optional[str] = None, base_url: Optional[str] = None,
                    custom_prompt: Optional[str] = None,
                    inference_playground_id: Optional[int] = None) -> dict:
    """LLM-as-a-Judge 런 생성(직접호출 비동기). model/dataset 는 프로젝트에서 상속(불변, P3),
    유형별 설정(provider/criteria/judge_model/api_key/base_url/custom_prompt)만 body.
    키/URL = transient. 즉시 job_id 반환 후 백그라운드 채점 → eval_result.metrics(judge_*)
    마감. FE 는 get_judge_result 폴링. inference_playground_id(배포 모델) 주면 대상 모델 실
    출력으로 채점, 없으면 mock(A4)."""
    project, dataset_ids = await _load_project_for_run(project_id, "judge")
    model_id = int(project["model_id"])
    model_info = await db_model.get_model(model_id=model_id)
    if not model_info:
        raise Exception(f"model {model_id} not found")
    model_name = model_info["name"]
    workspace_id = int(model_info["workspace_id"])

    ds_names = []
    for did in dataset_ids:
        d = await db_model.get_dataset_model(dataset_id=did)
        if not d:
            raise Exception(f"dataset {did} not found")
        if int(d["workspace_id"]) != workspace_id:
            raise Exception("dataset and model belong to different workspaces")
        ds_names.append(str(d["name"]))

    crit = [c for c in criteria if c in JUDGE_CRITERIA] or list(JUDGE_CRITERIA)

    if provider == "local":
        _validate_local_url(base_url)
    elif provider in JUDGE_PROVIDER_HOSTS:
        if not _judge_mock_enabled() and not (api_key and api_key.strip()):
            raise Exception("API key required for commercial judge")
    else:
        raise Exception(f"unsupported provider: {provider}")

    dataset_name_csv = ",".join(ds_names)
    if len(dataset_name_csv) > 255:
        dataset_name_csv = f"{ds_names[0]} +{len(ds_names) - 1} more"[:255]

    # 배포 모델 추론 URL 해석(실패/미지정 → None → mock output 폴백).
    inference_url = await _resolve_inference_url(inference_playground_id)

    job_id = f"judge-{model_id}-{uuid.uuid4().hex[:16]}"
    await db_model.insert_eval_result(
        source_model_id=model_id, workspace_id=workspace_id, job_str_id=job_id,
        dataset_id=dataset_ids[0], dataset_name=dataset_name_csv,
        metric_set=f"judge:{provider}", eval_project_id=project_id)
    try:
        await db_model.update_eval_project_status(project_id, PROJECT_STATUS_RUNNING)
    except Exception:
        traceback.print_exc()

    task = asyncio.create_task(_run_judge_task(
        model_id, job_id, model_name, dataset_ids, ds_names, provider, judge_model,
        api_key, base_url, crit, custom_prompt, inference_url))
    _judge_tasks.add(task)
    task.add_done_callback(_judge_tasks.discard)

    return {"project_id": project_id, "model_id": model_id, "job_id": job_id,
            "provider": provider, "mode": "judge", "criteria": crit,
            "datasets": ds_names, "mock": _judge_mock_enabled(),
            "real_output": bool(inference_url)}


async def get_judge_result(model_id: int, job_id: str) -> dict:
    """judge 런 결과 폴링 — eval_result row 직접 조회(컨테이너/NFS 미경유)."""
    if not job_id or not _JOB_ID_RE.match(job_id):
        raise ValueError(f"invalid job_id: {job_id!r}")
    row = await db_model.get_eval_result_by_job(job_str_id=job_id, source_model_id=model_id)
    if not row:
        return {"job_id": job_id, "metrics": None, "ready": False, "status": "pending"}
    status = row.get("status")
    metrics = row.get("metrics")
    if isinstance(metrics, str):
        try:
            metrics = json.loads(metrics)
        except (TypeError, json.JSONDecodeError):
            metrics = None
    # 내부키 제거 — judge-result 가 metric_set 게이트 없이 raw metrics 를 반환하므로, expert
    # job_id 로 호출되면 metrics._samples 의 서버 전용 _image_abs(NFS 절대경로)가 누출될 수
    # 있다. _ 접두 top-level 키(_samples/_mode/_rated/_total)는 FE 가 안 쓰므로 제거.
    if isinstance(metrics, dict):
        metrics = {k: v for k, v in metrics.items() if not str(k).startswith("_")}
    return {"job_id": job_id, "metrics": metrics,
            "ready": status == "completed", "status": status}


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


async def _build_expert_samples(model_id: int, model_name: str, dataset_ids: List[int],
                                ds_names: List[str], inference_url: Optional[str]) -> list:
    """전문가 채점 샘플(A4) — 실 데이터셋(input/reference/이미지) + 배포모델 추론 output.
    데이터셋 못 읽으면 합성(레거시 동등·결정적), 추론 URL 없으면 mock output 폴백."""
    # 데이터셋 전량 로드(ceiling 까지). 구 `len(ds_names)*5` 휴리스틱 제거 — 전문가는 전 샘플 리뷰.
    n = MAX_EXPERT_SAMPLES
    rows = await _read_dataset_samples(dataset_ids, n)
    base = ds_names[0] if ds_names else "dataset"
    if not rows:    # 실 데이터셋 못 읽음 → 합성 폴백(구 스캐폴딩과 동일 문자열 = 레거시 안정)
        rows = [{"input": f"[{base}] sample {i} 입력 프롬프트", "reference": f"참조 답변 {i}",
                 "dataset": ds_names[i % len(ds_names)] if ds_names else base}
                for i in range(n)]
    # mock output baseline 먼저 — 항상 출력 보장. start_expert 가 HTTP 핸들러를 잡고 있으므로
    # 실 추론은 전체 예산(_EXPERT_INFER_BUDGET) 내에서만 업그레이드(초과분은 mock 유지).
    samples = []
    for i, row in enumerate(rows):
        s = {"idx": i, "dataset": row.get("dataset", base), "input": row["input"],
             "output": f"[{model_name}] 응답 {i}", "reference": row.get("reference", "")}
        for k in ("image", "image_url", "image_served", "_image_abs", "_image_dir",
                  "csv_rows", "csv_text"):
            if k in row:
                s[k] = row[k]
        samples.append(s)
    if inference_url:
        async def _upgrade():
            for s in samples:
                if not s["input"]:
                    continue    # image-only(VLM) 샘플 — 텍스트 추론은 이미지 미전달이라
                    #             무의미. mock output 유지(실 VLM 추론은 A4 GPU 후속).
                real = await _infer_output(
                    inference_url, s["input"], f"expert-{model_id}-{s['idx']}")
                if real:
                    s["output"] = real
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


async def start_expert(project_id: int,
                       inference_playground_id: Optional[int] = None) -> dict:
    """전문가 평가 세션 시작 — model/dataset 는 프로젝트에서 상속(불변, P3). 채점 샘플 생성
    + 세션 행. inference_playground_id(배포 모델) 주면 실 출력으로, 없으면 mock(A4). 생성
    샘플은 metrics._samples 로 영속 → 재로드 안정(실 추론 비결정성/배포 종료에도 표시 고정)."""
    project, dataset_ids = await _load_project_for_run(project_id, "expert")
    model_id = int(project["model_id"])
    model_info = await db_model.get_model(model_id=model_id)
    if not model_info:
        raise Exception(f"model {model_id} not found")
    model_name = model_info["name"]
    workspace_id = int(model_info["workspace_id"])

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

    inference_url = await _resolve_inference_url(inference_playground_id)
    samples = await _build_expert_samples(
        model_id, model_name, dataset_ids, ds_names, inference_url)
    dataset_name_csv = ",".join(ds_names)
    if len(dataset_name_csv) > 255:
        dataset_name_csv = f"{ds_names[0]} +{len(ds_names) - 1} more"[:255]

    # 시나리오 결속 고정 프롬프트(D3) — 샘플 shape(SDS=csv_rows)로 판별해 세션에 동결.
    expert_prompt = _expert_prompt(samples)
    job_id = f"expert-{model_id}-{uuid.uuid4().hex[:16]}"
    await db_model.insert_eval_result(
        source_model_id=model_id, workspace_id=workspace_id, job_str_id=job_id,
        dataset_id=dataset_ids[0], dataset_name=dataset_name_csv, metric_set="expert",
        eval_project_id=project_id)
    # 샘플 + 고정 프롬프트 영속(running 유지) — get_expert_samples/submit 가 재생성 대신 이걸 읽는다.
    await db_model.set_eval_result_metrics(
        job_str_id=job_id, source_model_id=model_id,
        metrics_json=json.dumps({"_mode": "expert", "_samples": samples,
                                 "_expert_prompt": expert_prompt}))
    try:
        await db_model.update_eval_project_status(project_id, PROJECT_STATUS_RUNNING)
    except Exception:
        traceback.print_exc()

    return {"project_id": project_id, "model_id": model_id, "job_id": job_id,
            "mode": "expert", "datasets": ds_names,
            "samples": [_public_sample(s) for s in samples],
            "total": len(samples), "real_output": bool(inference_url),
            "expert_prompt": expert_prompt}


async def get_expert_samples(model_id: int, job_id: str) -> dict:
    """세션 샘플 + 기존 채점 + 채점 이력(재개·감사추적용)."""
    row, samples = await _expert_session(model_id, job_id)
    ratings = await db_model.list_expert_ratings(job_str_id=job_id, source_model_id=model_id)
    history = await db_model.list_expert_rating_history(
        job_str_id=job_id, source_model_id=model_id)
    return {"job_id": job_id, "status": row.get("status"),
            "samples": [_public_sample(s) for s in samples],
            "total": len(samples), "ratings": ratings, "history": history,
            "expert_prompt": _session_prompt(row, samples)}


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
        # expert_avg_score(1~5) = 신규 기본 metric(_flatten 자동 노출·방향 max). _distribution 은
        # _ 접두라 비교표 미노출(서버측). expert_pass_rate 는 backward-compat 병기.
        # _samples/_expert_prompt 보존 — 완료 후 get_expert_samples 가 표시 출력·프롬프트 유지.
        metrics = {"expert_avg_score": avg_score, "expert_pass_rate": pass_rate,
                   "_distribution": distribution, "_mode": "expert",
                   "_rated": rated, "_total": total, "_samples": samples,
                   "_expert_prompt": _session_prompt(row, samples)}
        await db_model.complete_eval_result(
            job_str_id=job_id, metrics_json=json.dumps(metrics), source_model_id=model_id)
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
