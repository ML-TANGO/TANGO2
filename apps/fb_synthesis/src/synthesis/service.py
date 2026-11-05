"""데이터 합성 프레임워크 — service (P1, WBS 3.3 / SP-7).

P1 = 단일 generate 외부 컨테이너 직접 호출(파이프라인 미경유). 합성 프로젝트 CRUD +
실행(launch) + 상태 폴링 + 결과 요약. 3-모듈 체이닝·후보 큐레이션·데이터셋 저장은 P2.
"""
import json
import os
import re
import traceback
from datetime import datetime

import aiohttp

from utils import common, kube
from utils.msa_db import db_synthesis

# 단일 generate job 직접 호출 (fb_external_container BFF svc).
EXTERNAL_CONTAINER_SVC = "http://jfb-app-external-container-svc/api/v1"

# 데이터셋 등록은 dataset 도메인(fb_dataset)이 소유 — 내부 register-path 엔드포인트 호출.
DATASET_SVC = "http://jfb-app-dataset-svc/api/datasets"

# generate job 의 /output 은 workspace main PVC 의 jobs/{job_id}/output 에 매핑.
# fb_synthesis 는 동일 NFS 를 마운트해 결과 jsonl 을 직접 읽는다. 경로는 env override 가능.
SYNTHESIS_RESULT_BASE = os.environ.get(
    "SYNTHESIS_RESULT_BASE", "/jf-data/storage-local-nfs/main/workspace/jobs"
)

# job id 는 외부 컨테이너가 발급(uuid/hex 계열). 경로 조작 방지: 형식 검증 + base 이탈 차단.
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _result_jsonl_path(job_str_id: str) -> str:
    if not job_str_id or not _JOB_ID_RE.match(job_str_id):
        raise ValueError(f"invalid job_str_id: {job_str_id!r}")
    path = os.path.join(SYNTHESIS_RESULT_BASE, job_str_id, "output", "result.jsonl")
    base = os.path.realpath(SYNTHESIS_RESULT_BASE)
    if os.path.commonpath([os.path.realpath(path), base]) != base:
        raise ValueError("result path escapes base")
    return path


async def _get_external_job(job_id: str):
    """external generate job 스냅샷 (GET /api/v1/jobs/{id}). 실패 시 None."""
    url = f"{EXTERNAL_CONTAINER_SVC}/jobs/{job_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status >= 400:
                    return None
                return await resp.json()
    except Exception as e:
        print(f"external job fetch failed: {e}")
        return None


def _parse_params(row: dict) -> dict:
    try:
        return json.loads(row.get("params") or "{}")
    except Exception:
        return {}


async def _sync_project_status(proj: dict):
    """running 프로젝트의 라이브 상태를 external generate job 으로 동기화.
    터미널(completed/failed/cancelled)이면 DB 갱신 + proj 갱신(in-place). progress 반환.
    목록/상세 조회가 /status 폴링 없이도 실행 종료를 반영하게 하는 핵심. (P2 fix)"""
    if proj.get("status") != "running" or not proj.get("job_str_id"):
        return None
    ext = await _get_external_job(proj["job_str_id"])
    result = (ext or {}).get("result") or {}
    live = result.get("status")
    progress = result.get("progress")
    if live in ("completed", "failed", "cancelled"):
        rec = (result.get("result") or {}).get("records") if isinstance(result.get("result"), dict) else None
        await db_synthesis.update_synthesis_status(project_id=proj["id"], status=live, result_count=rec)
        proj["status"] = live
        if rec is not None:
            proj["result_count"] = rec
    elif live:
        proj["status"] = live
    return progress


async def list_manifests():
    # 합성 모듈(generate 외부 컨테이너) 선택 드롭다운용.
    return await db_synthesis.list_generate_manifests()


async def get_synthesis_projects(workspace_id: int):
    rows = await db_synthesis.get_synthesis_projects(workspace_id=workspace_id)
    for r in rows:
        r["params"] = _parse_params(r)
        await _sync_project_status(r)  # 실행 중이면 라이브 상태 동기화(종료 반영)
    return rows


async def create_synthesis_project(body) -> int:
    now = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    project_id = await db_synthesis.create_synthesis_project(
        workspace_id=body.workspace_id,
        name=body.name,
        field=body.field,
        description=body.description,
        owner_id=body.owner_id,
        owner_name=body.owner_name,
        mode=body.mode,
        manifest_name=body.manifest_name,
        manifest_version=body.manifest_version,
        params=json.dumps(body.params or {}),
        gpu_count=body.gpu_count,
        dataset_id=body.dataset_id,
        status="created",
        create_datetime=now,
        update_datetime=now,
    )
    return project_id


async def get_synthesis_project_detail(project_id: int):
    proj = await db_synthesis.get_synthesis_project(project_id=project_id)
    if not proj:
        return None
    proj["params"] = _parse_params(proj)
    # 실행 중이면 라이브 상태 동기화 → proj["status"]/progress 반영(종료 반영)
    proj["progress"] = await _sync_project_status(proj)
    return proj


async def delete_synthesis_project(project_id: int):
    return await db_synthesis.delete_synthesis_project(project_id=project_id)


async def update_synthesis_project(project_id: int, body) -> int:
    # 설정/수정 모달 (P2) — 부분 업데이트. params 는 JSON 직렬화.
    fields = {}
    for key in ("name", "field", "description", "mode", "manifest_name", "manifest_version", "gpu_count", "dataset_id"):
        val = getattr(body, key, None)
        if val is not None:
            fields[key] = val
    if body.params is not None:
        fields["params"] = json.dumps(body.params)
    if not fields:
        return 0
    return await db_synthesis.update_synthesis_project(project_id, **fields)


async def run_synthesis(project_id: int) -> str:
    proj = await db_synthesis.get_synthesis_project(project_id=project_id)
    if not proj:
        raise Exception("Error: not exist synthesis project")
    # 중복 실행 가드 — 이미 running 이면 새 job launch 금지(job_str_id 덮어쓰기/고아 job 방지).
    if proj.get("status") == "running":
        raise Exception("Error: synthesis job already running")
    params = _parse_params(proj)
    output_subdir = f"synthesis/project-{project_id}"
    body = {
        "manifest_name": proj["manifest_name"],
        "manifest_version": proj["manifest_version"],
        "workspace_id": proj["workspace_id"],
        "params": params,
        "output_subdir": output_subdir,
    }
    if proj.get("gpu_count"):
        body["gpu_count"] = proj["gpu_count"]
    res = await common.post_request(f"{EXTERNAL_CONTAINER_SVC}/jobs", body)
    if not res or not res.get("job_id"):
        raise Exception("Error: external generate job launch failed")
    job_id = res["job_id"]
    await db_synthesis.update_synthesis_run(
        project_id=project_id, job_str_id=job_id, output_subdir=output_subdir, status="running"
    )
    return job_id


async def get_synthesis_status(project_id: int) -> dict:
    proj = await db_synthesis.get_synthesis_project(project_id=project_id)
    if not proj:
        raise Exception("Error: not exist synthesis project")
    if not proj.get("job_str_id"):
        return {"status": proj.get("status", "created"), "progress": None}
    ext = await _get_external_job(proj["job_str_id"])
    result = (ext or {}).get("result") or {}
    status = result.get("status")
    progress = result.get("progress")
    # 터미널 상태 DB 동기화
    if status in ("completed", "failed", "cancelled") and proj.get("status") != status:
        rec = (result.get("result") or {}).get("records") if isinstance(result.get("result"), dict) else None
        await db_synthesis.update_synthesis_status(project_id=project_id, status=status, result_count=rec)
    return {"status": status or proj.get("status"), "progress": progress}


async def get_synthesis_result(project_id: int, limit: int = 20) -> dict:
    """P2: 생성 결과 — job 요약 + result.jsonl 실데이터 미리보기(상위 limit) + 총 건수.
    result.jsonl 은 generate job 의 /output(jf-main jobs/{job_id}/output) NFS 에서 읽음."""
    proj = await db_synthesis.get_synthesis_project(project_id=project_id)
    if not proj:
        raise Exception("Error: not exist synthesis project")
    summary = {
        "project_id": project_id,
        "status": proj.get("status"),
        "output_subdir": proj.get("output_subdir"),
        "result_count": proj.get("result_count", 0),
        "job_result": None,
        "records": [],
        "total": 0,
    }
    if proj.get("job_str_id"):
        ext = await _get_external_job(proj["job_str_id"])
        summary["job_result"] = (ext or {}).get("result", {}).get("result")
        # result.jsonl 실데이터 미리보기 (job_str_id 검증 실패는 로깅 후 summary 만 반환)
        try:
            path = _result_jsonl_path(proj["job_str_id"])
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    for i, line in enumerate(f):
                        line = line.strip()
                        if not line:
                            continue
                        summary["total"] += 1
                        if len(summary["records"]) < limit:
                            try:
                                summary["records"].append(json.loads(line))
                            except Exception:
                                summary["records"].append({"raw": line})
        except Exception as e:
            print(f"result.jsonl read failed: {e}")
            traceback.print_exc()
    return summary


async def get_synthesis_log(project_id: int) -> dict:
    """생성 실행 실시간 로그 — generate pod stdout(JSONL 이벤트) tail.
    결과는 NFS(result.jsonl), 로그는 pod stdout. pod GC(완료) 후엔 결과 탭 안내.
    FE 는 running 동안 1~2초 폴링."""
    proj = await db_synthesis.get_synthesis_project(project_id=project_id)
    if not proj:
        raise Exception("Error: not exist synthesis project")
    if not proj.get("job_str_id"):
        return {"log": "", "running": False, "status": proj.get("status")}
    ext = await _get_external_job(proj["job_str_id"])
    if not ext:
        return {"log": "", "running": False, "status": proj.get("status")}
    status = (ext.get("result") or {}).get("status")
    pod_name = ext.get("pod_name")
    namespace = ext.get("namespace")
    log = kube.get_pod_log(namespace, pod_name, tail_lines=300) if (pod_name and namespace) else None
    if log is None:
        log = (f"[platform] 실시간 로그 없음 (job status={status or 'pending'}). "
               "완료된 결과는 '생성 결과' 표/다운로드에서 확인하세요.")
    return {"log": log, "running": status == "running", "status": status}


async def get_synthesis_result_file(project_id: int):
    """결과 result.jsonl 의 실제 파일 경로 반환(다운로드용). 없으면 None."""
    proj = await db_synthesis.get_synthesis_project(project_id=project_id)
    if not proj or not proj.get("job_str_id"):
        return None
    try:
        path = _result_jsonl_path(proj["job_str_id"])
    except ValueError:
        return None
    return path if os.path.exists(path) else None


async def save_to_dataset(project_id: int, dataset_name: str, access: str = "0",
                          create_user_id: int = None) -> dict:
    """생성 result.jsonl 을 플랫폼 데이터셋으로 등록(학습/전처리에 투입 가능).
    데이터셋 생성은 fb_dataset 의 내부 register-path 엔드포인트가 수행.
    create_user_id = 저장 실행 세션 사용자(없으면 프로젝트 owner fallback) — orphan 데이터셋 방지."""
    proj = await db_synthesis.get_synthesis_project(project_id=project_id)
    if not proj:
        raise Exception("Error: not exist synthesis project")
    if not proj.get("job_str_id"):
        raise Exception("Error: no generated result to save")
    path = _result_jsonl_path(proj["job_str_id"])
    if not os.path.exists(path):
        raise Exception("Error: result file not found")
    body = {
        "workspace_id": proj["workspace_id"],
        "dataset_name": dataset_name,
        "job_str_id": proj["job_str_id"],
        "access": access or "0",
        "description": f"합성 데이터 (synthesis project {project_id})",
        "create_user_id": create_user_id if create_user_id is not None else proj.get("owner_id"),
    }
    res = await common.post_request(f"{DATASET_SVC}/register-path", body)
    if not res or res.get("status") != 1:
        raise Exception((res or {}).get("message") or "dataset register failed")
    return res.get("result") or {}


def _mock_variants(meta: str) -> list:
    """⚠️ MOCK: 메타프롬프트 변형으로 후보 생성. 고려대 LLM1(OPRO/APE) 수령 시
    이 함수를 LLM1 generate job 호출로 교체(나머지 영속/큐레이션 로직은 그대로)."""
    variants = [
        f"{meta} — 핵심 속성을 단계별로 식별하고 근거와 함께 상세히 기술하라.",
        f"다음 입력에 대해 '{meta}' 작업을 수행하고 결과를 구조화하라.",
        f"{meta} (간결·핵심 위주 버전)",
    ]
    return [{"prompt": v, "score": round(0.92 - i * 0.06, 2)} for i, v in enumerate(variants)]


async def get_prompt_candidates(project_id: int) -> dict:
    """프롬프트 후보(LLM1) — 영속된 후보를 반환. 없으면 mock 생성+영속(lazy init).
    채택/폐기 status 포함. prompt-list 뷰와 최적화 뷰가 공유."""
    proj = await db_synthesis.get_synthesis_project(project_id=project_id)
    if not proj:
        raise Exception("Error: not exist synthesis project")
    params = _parse_params(proj)
    method = params.get("optimize_method", "OPRO")
    rows = await db_synthesis.list_synthesis_candidates(project_id)
    if not rows:
        meta = (params.get("meta_prompt") or "").strip() or "도메인 데이터를 생성하는 프롬프트"
        for c in _mock_variants(meta):
            await db_synthesis.insert_synthesis_candidate(
                project_id=project_id, prompt=c["prompt"], score=c["score"],
                method=method, iteration=1, status="candidate")
        rows = await db_synthesis.list_synthesis_candidates(project_id)
    return {
        "method": method,
        "iteration": max((r.get("iteration", 0) for r in rows), default=1),
        "adopted_prompt": params.get("adopted_prompt"),
        "candidates": rows,
        "mock": True,
    }


async def regenerate_prompt_candidates(project_id: int) -> dict:
    """'최적화 실행' — 미결정(candidate) 후보를 비우고 새 iteration 후보 생성+영속.
    채택/폐기 이력은 보존."""
    proj = await db_synthesis.get_synthesis_project(project_id=project_id)
    if not proj:
        raise Exception("Error: not exist synthesis project")
    params = _parse_params(proj)
    method = params.get("optimize_method", "OPRO")
    meta = (params.get("meta_prompt") or "").strip() or "도메인 데이터를 생성하는 프롬프트"
    await db_synthesis.delete_open_synthesis_candidates(project_id)
    it = (await db_synthesis.max_synthesis_candidate_iteration(project_id)) + 1
    for c in _mock_variants(meta):
        await db_synthesis.insert_synthesis_candidate(
            project_id=project_id, prompt=c["prompt"], score=c["score"],
            method=method, iteration=it, status="candidate")
    return await get_prompt_candidates(project_id)


async def adopt_candidate(project_id: int, candidate_id: int) -> dict:
    cand = await db_synthesis.get_synthesis_candidate(candidate_id)
    if not cand or cand.get("project_id") != project_id:
        raise Exception("Error: candidate not found")
    await db_synthesis.update_synthesis_candidate_status(candidate_id, "adopted")
    proj = await db_synthesis.get_synthesis_project(project_id=project_id)
    params = _parse_params(proj)
    params["adopted_prompt"] = cand["prompt"]
    params["meta_prompt"] = cand["prompt"]
    await db_synthesis.update_synthesis_project(project_id, params=json.dumps(params))
    return {"adopted_prompt": cand["prompt"]}


async def discard_candidate(project_id: int, candidate_id: int) -> dict:
    cand = await db_synthesis.get_synthesis_candidate(candidate_id)
    if not cand or cand.get("project_id") != project_id:
        raise Exception("Error: candidate not found")
    await db_synthesis.update_synthesis_candidate_status(candidate_id, "discarded")
    return {"discarded": candidate_id}
