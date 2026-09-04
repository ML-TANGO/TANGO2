"""Domain BFF endpoints for external partner containers.

Mounted under llm_model's `/api` prefix, so user-facing paths become:

- ``POST /api/external/jobs`` — start a partner job
- ``GET  /api/external/jobs/{job_id}`` — full job detail (passthrough)
- ``POST /api/external/jobs/{job_id}/cancel`` — request cancellation
- ``GET  /api/external/jobs/{job_id}/sse`` — generic SSE relay
- ``GET  /api/external/jobs/{job_id}/sse-status`` — fine_tuning_status shape SSE
- ``GET  /api/external/jobs/{job_id}/sse-time``   — percent/remaining_time SSE
- ``GET  /api/external/jobs/{job_id}/sse-graph``  — TensorBoard scalars SSE
- ``GET  /api/external/jobs/{job_id}/system-log`` — raw log REST (1s polling)

The sse-status / sse-time / sse-graph payloads match the format used by the
platform's internal LLM fine-tuning SSE (``/api/fine-tuning/sse-{status,
time,graph}/{model_id}``), so the same React hooks
(``useSSEStatus``, ``useSSEFinetuningTime``, ``useSSEGraph``) can drive
external jobs without any frontend code changes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from utils import settings
from utils import errors_catalog
from utils.resource import response as _envelope
from utils.msa_db import db_dataset

from .proxy import ExternalContainerClient, ExternalContainerError

logger = logging.getLogger(__name__)
external = APIRouter(prefix="/external", tags=["external"])


# ── DTO (mirrors fb_external_container response shapes) ──────────────────


class StartJobBody(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    manifest_name: str = Field(min_length=1)
    manifest_version: str = Field(min_length=1)
    workspace_id: int = Field(ge=1)
    namespace: str = Field(default=settings.SYSTEM_NAMESPACE, min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    # Optional GPU/instance override — frontend FINETUNING_SETTING 모달이 제공.
    # 누락 시 manifest 의 spec.resources default 가 그대로 사용된다.
    instance_id: Optional[int] = None
    instance_count: Optional[int] = None
    gpu_count: Optional[int] = None
    # Auto commit hook 활성화 — frontend ExternalFineTuningView 가 학습 시작
    # 시 model_id + params.output_checkpoint_name 을 같이 보내면 fb_external_container
    # 의 terminal=COMPLETED hook 이 자동으로 /external-commit 호출.
    platform_model_id: Optional[int] = None
    output_subdir: Optional[str] = None
    # I6 (SP-3): manifest.secrets.required 로 선언된 자격증명 값(예: HF_TOKEN).
    # params/env_overrides 와 분리 — fb_external_container 가 redacted 경로로 pod env 주입.
    secrets: Optional[dict[str, str]] = None

    @field_validator("output_subdir")
    @classmethod
    def _output_subdir_shape(cls, v: Optional[str]) -> Optional[str]:
        # /output/<여기>/ 단일 경로 세그먼트 — traversal 차단(첫 글자 영숫자로
        # leading-dot 거부, `/`·`\` 불허) + 길이 cap. 기존 partner naming(대문자/
        # 점)을 깨지 않게 phase.id slug 보다 permissive. security L5 defense-in-depth.
        if v is not None and not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$", v):
            raise ValueError(
                f"output_subdir must be path-safe [A-Za-z0-9._-], no slashes; got {v!r}"
            )
        return v


# ── Client helpers ───────────────────────────────────────────────────────

# Lazy-initialized httpx client + lock. main.py registers `close_external_client`
# as a shutdown handler so the pool releases cleanly.
_http_client: Optional[httpx.AsyncClient] = None
_client_lock: Optional[asyncio.Lock] = None


async def _get_client() -> ExternalContainerClient:
    global _http_client, _client_lock
    if _client_lock is None:
        _client_lock = asyncio.Lock()
    async with _client_lock:
        if _http_client is None or _http_client.is_closed:
            _http_client = httpx.AsyncClient(timeout=300.0)
    return ExternalContainerClient(
        base_url=settings.FB_EXTERNAL_CONTAINER_URL,
        client=_http_client,
    )


async def close_external_client() -> None:
    """Release the shared httpx client. Called from main.py shutdown hook."""
    global _http_client
    client = _http_client
    _http_client = None
    if client is not None and not client.is_closed:
        try:
            await client.aclose()
        except Exception:
            logger.exception("close_external_client failed; sockets may be leaked")


def _translate_error(exc: ExternalContainerError) -> HTTPException:
    if exc.status_code == 0:
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=exc.status_code, detail=str(exc))


# ── Internal-LLM-compatible payload builders ─────────────────────────────

# fb_external_container's ExternalContainerStatus → frontend's
# fine_tuning_status.status. Frontend recognises:
#   pending / installing / running / done / stop / error
_FT_STATUS_MAP = {
    "pending":   "pending",
    "running":   "running",
    "completed": "done",
    "failed":    "error",
    "cancelled": "stop",
}


def _platform_format(dt: datetime) -> str:
    """Match TYPE.TIME_DATE_FORMAT used by internal LLM SSE producer."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _parse_started_at(raw: Any) -> Optional[datetime]:
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _extract_etri_scalars(detail: dict) -> dict:
    """Pull ETRI-specific scalars from result.result (current_step, ...).

    ETRIAdapter._build_result merges raw ETRI fields into ExternalJobResult.result
    so we can use them here without re-calling the partner pod.
    """
    inner = (detail.get("result") or {}).get("result") or {}
    return inner if isinstance(inner, dict) else {}


# Reserved status field — a container surfaces its experiment-tracking run URL
# (Weights & Biases, or any tracker) under result.{wandb_url|wandb_run_url|
# tracking_url}. Generic adapters pass result.* through verbatim; the ETRI
# adapter merges the same top-level keys (see etri_vlm._build_result). The BFF
# only forwards it to the FE as an href, so we hard-restrict to http/https and
# cap length — never trust the partner string enough to emit javascript:/data:
# (stored-XSS via the link) or an unbounded value (SSE/FE DoS).
_TRACKING_URL_KEYS = ("wandb_url", "wandb_run_url", "tracking_url")
_MAX_TRACKING_URL = 2048


def _extract_tracking_url(detail: Optional[dict]) -> Optional[str]:
    if not detail:
        return None
    inner = (detail.get("result") or {}).get("result") or {}
    if not isinstance(inner, dict):
        return None
    for key in _TRACKING_URL_KEYS:
        val = inner.get(key)
        if not isinstance(val, str):
            continue
        val = val.strip()
        if not val or len(val) > _MAX_TRACKING_URL:
            continue
        # 제어문자/백슬래시 사전 거부: urlparse 와 브라우저 new URL() 의 정규화가
        # 갈려(backslash→'/', CRLF 처리) 오픈리다이렉트(`https://host\@evil`) /
        # SSE 라인주입 우회 여지. 정상 http(s) run URL 엔 없는 문자라 차단.
        if any(c in val for c in ("\\", "\r", "\n", "\x00")):
            continue
        parsed = urlparse(val)  # CPython urlparse 는 str 입력에 raise 안 함
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return val
    return None


def _build_fine_tuning_status(detail: Optional[dict]) -> dict:
    """Shape matches /api/models/fine-tuning/sse-status/{id}.

    detail=None (tracker cleanup 후) 면 status='done' 으로 표시 — commit_models
    있는 상태라 학습 완료된 것으로 간주. frontend 가 graph 도 같이 보여줌.
    """
    if not detail:
        return {
            "fine_tuning_status": {"status": "done", "reason": None},
            "commit_status": {"status": None, "type": None, "reason": None},
        }
    result = detail.get("result") or {}
    raw_status = result.get("status") or "pending"
    err = result.get("error")
    reason: Optional[str] = None
    error_detail: Optional[dict] = None
    if isinstance(err, dict):
        reason = err.get("message")
        # I (SP-3): 컨테이너 발행 code 를 errors.yaml 4-튜플(problem/cause/fix)로
        # 변환해 UI 친화 메시지 제공. err 가 dict 면 code 유무와 무관하게 enrich
        # (무코드/미등록 → generic fallback). 항상 error_detail 채움.
        error_detail = errors_catalog.enrich(err.get("code"), reason)
    elif isinstance(err, str):
        reason = err
        error_detail = errors_catalog.enrich(None, err)
    return {
        "fine_tuning_status": {
            "status": _FT_STATUS_MAP.get(raw_status, raw_status),
            "reason": reason,
            # 4-튜플(없으면 None) — FE 가 problem/cause/fix 표시(추가 필드, 하위호환).
            "error_detail": error_detail,
            # 컨테이너가 보고한 W&B run URL(없으면 None) — FE 가 학습 중/후 링크 노출.
            # http/https 만 통과(추가 필드, 하위호환).
            "wandb_url": _extract_tracking_url(detail),
        },
        # External jobs don't drive the platform's commit_model flow yet.
        "commit_status": {"status": None, "type": None, "reason": None},
    }


async def _extract_events_summary(job_id: str, detail: Optional[dict]) -> dict:
    """TensorBoard events 파일에서 last step / training completion / elapsed 추출.

    ETRI partner `/train/status` 의 current_step·total_steps 가 null/0 응답을
    내는 경우의 보강 source. events 파일은 학습 진행 중 + 종료 후 모두 NFS 에 살아
    있으므로 graph endpoint 와 동일한 fallback path 로 read.
    """
    import os
    runs = await _resolve_events_runs_dirs(job_id, detail)
    if not runs:
        return {}
    log_dir = runs[0]
    try:
        from tensorboard.backend.event_processing import event_accumulator
        import asyncio as _aio
        from model import service as _model_svc

        # NFS 부하 완화: graph 파서와 동일한 events 파일 서명 캐시 공유 —
        # 파일이 안 바뀌었으면 재파싱 없이 캐시 반환(sse-time 3s 루프 × 클라이언트).
        sig = await _aio.to_thread(_model_svc.tfevents_signature, log_dir)
        if sig is None:
            return {}
        memo_key = ("evsummary", log_dir)
        cached = _model_svc.tfevents_memo_get(memo_key, sig)
        if cached is not None:
            return cached

        def _read():
            ea = event_accumulator.EventAccumulator(log_dir)
            ea.Reload()
            tags = set(ea.Tags()["scalars"])
            latest_step = 0
            train_runtime = None
            train_samples_per_sec = None
            for t in tags:
                try:
                    evs = ea.Scalars(t)
                except Exception:
                    continue
                if not evs:
                    continue
                if t == "train/loss":
                    latest_step = max(latest_step, evs[-1].step)
                elif t == "train/train_runtime":
                    train_runtime = evs[-1].value
                elif t == "train/train_samples_per_second":
                    train_samples_per_sec = evs[-1].value
            return {
                "latest_step": latest_step,
                "train_runtime": train_runtime,
                "train_samples_per_second": train_samples_per_sec,
                "completed": train_runtime is not None,
            }

        summary = await _aio.to_thread(_read)
        _model_svc.tfevents_memo_put(memo_key, sig, summary)
        return summary
    except Exception:
        logger.exception("_extract_events_summary failed for %s", log_dir)
        return {}


async def _build_time_payload(
    detail: Optional[dict],
    job_id: str,
    last_time_per_step: Optional[float],
) -> tuple[dict, Optional[float]]:
    """Shape matches /api/models/fine-tuning/sse-time/{id}.

    Source priority:
      1) ETRI `/train/status` 의 current_step + total_steps (있으면 정확)
      2) TensorBoard events 의 last `train/loss` step (partner /train/status 가
         null/0 일 때 fallback). ETRI 1.0.0~1.1.0 의 train_manager 가 step/loss
         추적 못 하는 이슈 단기 우회.
      3) `train/train_runtime` scalar 가 있으면 학습 종료 → percent=100, remaining=0.

    total_steps 모르면 percent / remaining_time = null (frontend 가 null 처리).
    progress_epoch 에는 latest_step 노출 (raw step 번호).
    """
    detail_safe = detail or {}
    scalars = _extract_etri_scalars(detail_safe)
    # detail.params 는 fb_external_container 가 record.params(reserved key 제외한
    # 사용자 params)를 **평면** dict 로 반환한다(job_router.ExternalJobDetail). launch
    # 요청 봉투(`{manifest_name, params:{...}}`)와 레벨이 달라, 예전엔 params.params
    # 를 읽어 total_epoch 이 항상 0 → FE Epoch 이 '—' 로 비었다. 평면 우선 + 봉투째
    # 넘기는 어댑터가 생겨도 깨지지 않게 중첩은 폴백으로 관용.
    raw_params = detail_safe.get("params")
    raw_params = raw_params if isinstance(raw_params, dict) else {}
    nested = raw_params.get("params")
    src_params = nested if isinstance(nested, dict) else raw_params
    # num_epochs 는 사용자 입력(recipe params) — 문자열/실수로 와도 아래 산술
    # (max(total_epoch, 1), total_steps / total_epoch)이 깨지지 않게 int 강제.
    try:
        total_epoch = int(src_params.get("num_epochs", 0) or 0)
    except (TypeError, ValueError):
        total_epoch = 0

    started_at = _parse_started_at(detail_safe.get("started_at"))
    start_dt_str = _platform_format(started_at) if started_at else None

    # partner /train/status scalar (정확하지 않은 경우 많음)
    partner_step = scalars.get("current_step") or 0
    total_steps = scalars.get("total_steps") or 0

    # events 파일 fallback — graph 와 동일한 path
    events_info = await _extract_events_summary(job_id, detail)
    events_step = events_info.get("latest_step") or 0
    train_runtime = events_info.get("train_runtime")
    completed = events_info.get("completed", False)

    # current_step: events 가 partner 보다 신뢰성 ↑
    current_step = max(int(partner_step), int(events_step))

    # partner total_steps 는 전 epoch 합산(HF Trainer max_steps)이라 epoch 당
    # 스텝은 total_epoch 로 나눈 값. FE 차트의 "1 Epoch = N steps" 표시와 아래
    # progress_epoch 분모가 같은 수라 여기서 한 번만 구한다. 모르면 0 → FE 가 숨김.
    steps_per_epoch = (
        int(total_steps / total_epoch) if total_steps > 0 and total_epoch > 0 else 0
    )

    progress_epoch = current_step  # raw step 번호 노출
    percent: Optional[float] = None
    remaining_time: Optional[float] = None
    new_last = last_time_per_step

    if completed:
        percent = 100.0
        remaining_time = 0.0
    elif total_steps and total_steps > 0 and current_step > 0:
        # partner 가 total_steps 정확히 주는 정상 path
        percent = round((current_step / total_steps) * 100, 2)
        progress_epoch = current_step // steps_per_epoch if steps_per_epoch else 0
        if started_at and current_step < total_steps:
            elapsed_unix = (datetime.now(timezone.utc) - started_at).total_seconds()
            tps = elapsed_unix / current_step
            if last_time_per_step is not None:
                tps = 0.9 * last_time_per_step + 0.1 * tps
            new_last = tps
            remaining_time = (total_steps - current_step) * tps
    # else: total_steps 모름 — percent / remaining_time null 그대로

    return {
        "total_epoch": total_epoch,
        "start_datetime": start_dt_str,
        "progress_epoch": progress_epoch,
        "percent": percent,
        "remaining_time": remaining_time,
        # 추가 필드(하위호환) — FE 차트 "1 Epoch = N steps". 내부 학습 경로는
        # get_model_fine_tuning 의 steps_per_epoch 를 쓰고, external 은 total_steps
        # 를 아는 이 SSE 가 유일한 출처라 여기에 싣는다.
        "steps_per_epoch": steps_per_epoch,
    }, new_last


def _contained_path(base: str, *parts: str) -> Optional[str]:
    """``base`` 아래로 ``parts`` 를 join 하되, 최종 realpath 가 ``base`` 밖이면 None.

    output_subdir(/run launch 시 사용자 입력) · job_id(URL path) 등 사용자 영향
    값이 path 에 들어가므로 ``..`` traversal 로 main_root 밖(예: /etc) 파일을
    읽는 것을 차단한다. 탈출 시도·NUL·비정상 경로는 None → 호출부가 건너뛴다.
    """
    import os
    try:
        base_real = os.path.realpath(base)
        full = os.path.realpath(os.path.join(base, *parts))
    except (OSError, ValueError):
        return None
    return full if full == base_real or full.startswith(base_real + os.sep) else None


async def _resolve_events_runs_dirs(job_id: str, detail: Optional[dict]) -> list[str]:
    """Return candidate `runs/` directories with TensorBoard events.

    Search order — 학습 진행 중일 때 jobs path, 학습 종료 후엔 commit_models path
    fallback. 두 곳 다 검색해서 가장 최근 mtime 의 runs/ 사용. detail 이 None 이면
    (tracker cleanup 후) DB lookup 으로 model 찾음.

    Returns list of run directories sorted by mtime descending.
    """
    import os
    from utils.llm_db import db_model as _dbm
    from utils import PATH

    candidate_bases: list[str] = []

    # 1. detail 있으면 (tracker active) jobs path 우선
    if detail:
        output_subdir = detail.get("output_subdir")
        workspace_id = detail.get("workspace_id")
        if output_subdir and workspace_id:
            try:
                ws = await _dbm.get_workspace_model(workspace_id=int(workspace_id))
                if ws:
                    main_root = PATH.JF_MAIN_STORAGE_PATH.format(
                        STORAGE_NAME=ws["main_storage_name"], WORKSPACE_NAME=ws["name"],
                    )
                    cand = _contained_path(
                        main_root, "jobs", job_id, "output", output_subdir, "runs")
                    if cand:
                        candidate_bases.append(cand)
            except Exception:
                logger.exception("sse-graph: ws lookup (active) failed for %s", workspace_id)

    # 2. commit_models fallback — model 의 latest_commit_id 가 가장 최근 학습 결과
    try:
        from utils.llm_db.db_base_async import select_query
        rows = await select_query(
            "SELECT id, workspace_id, name, latest_commit_id "
            "FROM model WHERE external_job_id = %s LIMIT 1",
            params=(job_id,),
        )
        if rows:
            m = rows[0]
            if m.get("latest_commit_id"):
                commit_row = await _dbm.get_commit_model(commit_id=m["latest_commit_id"])
                ws = await _dbm.get_workspace_model(workspace_id=int(m["workspace_id"]))
                if commit_row and ws:
                    main_root = PATH.JF_MAIN_STORAGE_PATH.format(
                        STORAGE_NAME=ws["main_storage_name"], WORKSPACE_NAME=ws["name"],
                    )
                    cand = _contained_path(
                        main_root, "models", m["name"], "commit_models",
                        commit_row["name"], "runs")
                    if cand:
                        candidate_bases.append(cand)
    except Exception:
        logger.exception("sse-graph: commit_models fallback lookup failed for %s", job_id)

    # 두 후보 base 에서 runs/ 디렉토리 수집
    all_run_dirs: list[str] = []
    for base in candidate_bases:
        if not os.path.exists(base):
            continue
        try:
            all_run_dirs.extend(os.path.join(base, d) for d in os.listdir(base))
        except Exception:
            continue
    if not all_run_dirs:
        return []
    all_run_dirs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return all_run_dirs


async def _build_graph_payload(detail: Optional[dict], job_id: Optional[str] = None) -> dict:
    """Shape matches /api/models/fine-tuning/sse-graph/{id}.

    1. detail (tracker active) 가 있으면 jobs/<job_id>/output/<subdir>/runs 사용
    2. tracker 에서 cleanup 후엔 commit_models/<latest_commit>/runs fallback
    3. event 파일 아직 없으면 빈 graph 반환

    fork v3+ 또는 ETRI 정식 release 가 `report_to=['tensorboard']` 적용된 image
    사용 시 자동 동작. ETRI 1.1.0 도 동일한 events 파일 layout 사용.
    """
    from model import service as _model_svc

    effective_job_id = (detail or {}).get("job_id") or job_id
    if not effective_job_id:
        return {"graph": {}}

    run_dirs = await _resolve_events_runs_dirs(effective_job_id, detail)
    if not run_dirs:
        return {"graph": {}}

    log_dir = run_dirs[0]
    try:
        parsed, latest_step = await _model_svc.parse_tensorboard_scalars_async(log_dir, max_steps=50)
    except Exception:
        logger.exception("sse-graph: parse failed for %s", log_dir)
        return {"graph": {}}
    # ⑩ 체크포인트 점 마킹 — runs/ 의 부모(output_subdir / commit_models/<name>)에
    # checkpoint-<step> 디렉토리가 있으면 스캔(파트너가 HF 관례 사용 시). save_steps
    # 를 모르는 외부 잡은 추정 안 함 → 디렉토리 없으면 빈 목록(가짜 점 방지).
    import os
    ckpt_root = os.path.dirname(os.path.dirname(log_dir)) if log_dir else None
    try:
        ckpt_steps = await _model_svc._resolve_checkpoint_steps(ckpt_root, None, latest_step)
    except Exception:
        ckpt_steps = []
    return {"graph": parsed or {}, "checkpoints": ckpt_steps}


# ── Phase 단위 그래프 (SDS 레시피) ───────────────────────────────────────────
# /jobs/{job_id}/sse-graph 는 "모델에 바인딩된 활성 job" 하나만 본다. 4-phase 레시피
# 에서는 phase 가 조회 단위라, 활성 job 이 phase 3 이어도 사용자가 phase 1 을 고르면
# phase 1 의 곡선이 나와야 한다. 게다가 job 기준 해석은 잡 경로에 events 가 없을 때
# `commit_models/<latest_commit>` 으로 폴백해 **직전 phase 곡선을 현재 phase 인 양**
# 흘렸다(학습 종료 후 차트 유지 목적의 폴백이 실행 중에도 발동). 아래 해석은 phase 를
# 경로에 못박아 그 누출을 구조적으로 차단한다.

# phase.id 는 launch 시 output_subdir 로 그대로 쓰이므로 동일 제약(job_router 의
# _OUTPUT_SUBDIR_RE)을 적용한다 — path 세그먼트로 들어가니 traversal 차단이 필수.
_PHASE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _phase_commit_dirs_sync(commit_root: str, phase_id: str) -> list[str]:
    """`{phase_id}-{YYYYMMDD-HHMMSS}` 커밋 이름을 최신순으로.

    커밋명 = `{output_subdir}-{ts}` (service.py 의 external commit) 이고 레시피는
    output_subdir=phase.id 로 실행한다. 프론트 derivePhaseCommitMap 과 같은 anchored
    규칙 — prefix 매칭이면 `lora` 가 `lora_marine-...` 을 오매칭할 수 있다.
    ts 가 고정폭이라 사전순 정렬 = 시간순.
    """
    import os
    pattern = re.compile(r"^" + re.escape(phase_id) + r"-\d{8}-\d{6}$")
    try:
        names = [n for n in os.listdir(commit_root) if pattern.match(n)]
    except OSError:
        return []
    names.sort(reverse=True)
    return names


def _run_dirs_by_mtime_sync(runs_dir: str) -> list[str]:
    """runs/ 하위 실행 디렉토리를 mtime 내림차순으로(없으면 빈 목록)."""
    import os
    try:
        entries = [os.path.join(runs_dir, d) for d in os.listdir(runs_dir)]
    except OSError:
        return []

    def _mtime(path: str) -> float:
        try:
            return os.path.getmtime(path)
        except OSError:
            return -1.0

    entries.sort(key=_mtime, reverse=True)
    return entries


async def _resolve_phase_output_dir(model_id: int, phase_id: str) -> Optional[str]:
    """해당 phase 자신의 산출물 디렉토리(runs/ 와 checkpoint-*/ 의 부모).

    1) 모델에 바인딩된 활성 job 이 이 phase 면 jobs/<job>/output/<phase_id> (학습 중 라이브)
    2) 아니면 commit_models/{phase_id}-{ts} 최신 (완료분)
    다른 phase 디렉토리로는 폴백하지 않는다 — 없으면 None(빈 그래프)이 정답.
    """
    import os
    from utils.llm_db import db_model as _dbm
    from utils.llm_db.db_base_async import select_query
    from utils import PATH

    try:
        rows = await select_query(
            "SELECT id, workspace_id, name, external_job_id FROM model WHERE id = %s LIMIT 1",
            params=(model_id,),
        )
    except Exception:
        logger.exception("phase sse-graph: model lookup failed for %s", model_id)
        return None
    if not rows:
        return None
    model_row = rows[0]

    try:
        ws = await _dbm.get_workspace_model(workspace_id=int(model_row["workspace_id"]))
    except Exception:
        logger.exception("phase sse-graph: ws lookup failed for %s", model_row.get("workspace_id"))
        return None
    if not ws:
        return None
    main_root = PATH.JF_MAIN_STORAGE_PATH.format(
        STORAGE_NAME=ws["main_storage_name"], WORKSPACE_NAME=ws["name"],
    )

    job_id = model_row.get("external_job_id")
    if job_id:
        cand = _contained_path(main_root, "jobs", job_id, "output", phase_id)
        if cand and await asyncio.to_thread(os.path.isdir, cand):
            return cand

    commit_root = _contained_path(main_root, "models", model_row["name"], "commit_models")
    if not commit_root:
        return None
    for name in await asyncio.to_thread(_phase_commit_dirs_sync, commit_root, phase_id):
        cand = _contained_path(commit_root, name)
        if cand:
            return cand
    return None


async def _build_phase_graph_payload(model_id: int, phase_id: str) -> dict:
    """phase 단위 그래프 — /jobs/{id}/sse-graph 와 같은 payload shape.

    events 가 없으면 trainer_state.json 으로 폴백한다. 파트너 스크립트가 TensorBoard
    를 켜지 않는 경우가 실재하기 때문(eva-vlm 의 `lora_marine` 전용 train_text_lora.py).
    """
    import os
    from model import service as _model_svc

    base = await _resolve_phase_output_dir(model_id, phase_id)
    if not base:
        return {"graph": {}}

    parsed: dict = {}
    latest_step = 0
    run_dirs = await asyncio.to_thread(_run_dirs_by_mtime_sync, os.path.join(base, "runs"))
    if run_dirs:
        try:
            parsed, latest_step = await _model_svc.parse_tensorboard_scalars_async(
                run_dirs[0], max_steps=50)
        except Exception:
            logger.exception("phase sse-graph: events parse failed for %s", run_dirs[0])
    if not parsed:
        try:
            parsed, latest_step = await _model_svc.parse_trainer_state_scalars_async(
                base, max_steps=50)
        except Exception:
            logger.exception("phase sse-graph: trainer_state parse failed for %s", base)
    if not parsed:
        return {"graph": {}}

    try:
        ckpt_steps = await _model_svc._resolve_checkpoint_steps(base, None, latest_step)
    except Exception:
        ckpt_steps = []
    return {"graph": parsed, "checkpoints": ckpt_steps}


# ── Manifest listings (BFF surface for frontend) ─────────────────────────

# Contract (frontend 와 합의됨 — 변경 금지):
#   GET /api/external/manifests           → envelope { status, result: [...], message, error }
#   GET /api/external/manifests/{name}    → envelope { status, result: {manifest_name, versions:[...]}, ... }
# 각 entry 필드: manifest_name, manifest_version, service_family,
#                contract_version, description, default_params, is_active.
# fb_external_container 의 응답 (ManifestStored) 을 위 contract 형태로 normalize.

_EMPTY_STR = ""


def _normalize_manifest_entry(raw: dict[str, Any]) -> dict[str, Any]:
    """fb_external_container ManifestStored → frontend contract entry."""
    return {
        "manifest_name": raw.get("name") or _EMPTY_STR,
        "manifest_version": raw.get("version") or _EMPTY_STR,
        "service_family": raw.get("service_family") or _EMPTY_STR,
        "contract_version": raw.get("contract_version") or _EMPTY_STR,
        "description": raw.get("description"),
        "default_params": raw.get("default_params") or {},
        "is_active": bool(raw.get("is_active", True)),
    }


@external.get("/manifests")
async def list_external_manifests() -> dict[str, Any]:
    """전체 등록 manifest 목록. platform envelope (status=1) 로 반환 — frontend
    callApi 가 data.status===1 만 STATUS_SUCCESS 로 인식한다."""
    client = await _get_client()
    try:
        rows = await client.list_manifests()
    except ExternalContainerError as exc:
        raise _translate_error(exc) from exc
    return _envelope(status=1, result=[_normalize_manifest_entry(r) for r in rows])


@external.get("/manifests/{manifest_name}")
async def get_external_manifest_by_name(manifest_name: str) -> dict[str, Any]:
    """지정한 manifest 이름의 모든 version + 각 version 의 default_params."""
    client = await _get_client()
    try:
        rows = await client.get_manifest_by_name(manifest_name)
    except ExternalContainerError as exc:
        raise _translate_error(exc) from exc

    versions = [
        {
            "manifest_version": (r.get("version") or _EMPTY_STR),
            "default_params": r.get("default_params") or {},
            # 다단계 학습 레시피(SP-10 도메인 카드/프리셋) — 없으면 None.
            # FE 가 phase 카드 파이프라인 렌더 + phase 별 params 실행에 사용.
            "recipe": r.get("recipe"),
            "service_family": r.get("service_family") or _EMPTY_STR,
            "contract_version": r.get("contract_version") or _EMPTY_STR,
            "description": r.get("description"),
            "is_active": bool(r.get("is_active", True)),
        }
        for r in rows
    ]
    return _envelope(
        status=1,
        result={"manifest_name": manifest_name, "versions": versions},
    )


# ── Dynamic dataset binding ────────────────────────────────────────────────

# 데이터셋 이름은 NFS subPath segment + DB 조회에 쓰이므로 allowlist 검증.
# datasets.name 은 VARCHAR(100) — 첫 글자 영숫자(leading-dot 거부) + ._- 허용.
_DATASET_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


async def _resolve_dataset_binding(params: dict[str, Any], workspace_id: int) -> None:
    """params['_dataset'].access 를 워크스페이스 데이터셋 레코드에서 동적 해석.

    recipe 는 `_dataset: {name}` 만 선언한다 — access(0=RO/1=RW) 는 DB 의 데이터셋
    속성이지 manifest 가 하드코딩할 값이 아니다. 여기서 launch 워크스페이스 안에서
    이름으로 조회해(워크스페이스 스코프 쿼리가 곧 same-workspace ACL) 실제 access
    플래그를 주입한다 — evaluate 런처(model/service.py)와 동일 패턴. `_dataset` 이
    없거나 name 이 없으면 no-op(데이터셋을 마운트하지 않는 단일 launch 는 무영향).

    ``params['_dataset']`` 를 새 dict 로 교체. 이름이 유효하지 않거나 워크스페이스에
    등록되지 않은 데이터셋이면 HTTPException.
    """
    ref = params.get("_dataset")
    if not isinstance(ref, dict):
        return
    name = ref.get("name")
    if not name:
        return
    name = str(name)
    if not _DATASET_NAME_RE.match(name):
        raise HTTPException(
            status_code=422, detail=f"invalid dataset name for binding: {name!r}"
        )
    record = await db_dataset.get_dataset_async(
        dataset_name=name, workspace_id=workspace_id
    )
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"dataset {name!r} not found in workspace {workspace_id}",
        )
    # DB access 플래그(INT 0=RO / 1=RW)가 /dataset 마운트의 subPath 버킷
    # ({access}/{name}) 로도 쓰인다. recipe 가 실었던 하드코딩 값은 override.
    params["_dataset"] = {"name": name, "access": str(record["access"])}


# ── Routes ───────────────────────────────────────────────────────────────


@external.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def start_external_job(body: StartJobBody) -> dict[str, Any]:
    client = await _get_client()
    # 동적 데이터셋 바인딩 — recipe 의 _dataset.name 을 워크스페이스 데이터셋
    # 레코드로 해석해 실제 access(RW/RO) 주입. _dataset 없으면 no-op(단일 launch).
    await _resolve_dataset_binding(body.params, body.workspace_id)
    try:
        raw = await client.start_job(
            manifest_name=body.manifest_name,
            manifest_version=body.manifest_version,
            workspace_id=body.workspace_id,
            params=body.params,
            namespace=body.namespace,
            instance_id=body.instance_id,
            instance_count=body.instance_count,
            gpu_count=body.gpu_count,
            platform_model_id=body.platform_model_id,
            output_subdir=body.output_subdir,
            secrets=body.secrets,
        )
        return _envelope(status=1, result=raw)
    except ExternalContainerError as exc:
        raise _translate_error(exc) from exc


@external.get("/jobs/{job_id}")
async def get_external_job(job_id: str) -> dict[str, Any]:
    client = await _get_client()
    try:
        raw = await client.get_job(job_id)
        return _envelope(status=1, result=raw)
    except ExternalContainerError as exc:
        raise _translate_error(exc) from exc


@external.post("/jobs/{job_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_external_job(job_id: str) -> dict[str, Any]:
    client = await _get_client()
    try:
        raw = await client.cancel_job(job_id)
        return _envelope(status=1, result=raw)
    except ExternalContainerError as exc:
        raise _translate_error(exc) from exc


# ── Deploy (hybrid pair — train → infer reload) ──────────────────────────


class DeployBody(BaseModel):
    """Hybrid pair deploy — train manifest 학습 완료 후 paired infer pod 의
    /deploy 호출. 사용자가 명시적 trigger (자동 chain 은 별도 SP).
    """
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    manifest_name: str = Field(min_length=1)
    manifest_version: str = Field(min_length=1)
    workspace_id: int = Field(ge=1)
    namespace: str = Field(default=settings.SYSTEM_NAMESPACE, min_length=1)
    # infer pod 의 job_id (lifecycle 의 platform job_id). 없으면 service_family
    # 기준 자동 매칭. 둘 다 없으면 fb_external_container 가 404.
    infer_job_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)


@external.post("/deploy")
async def deploy_external_pair(body: DeployBody) -> dict[str, Any]:
    """Hybrid pair deploy — paired infer pod 의 /deploy 호출."""
    client = await _get_client()
    try:
        raw = await client.deploy(
            manifest_name=body.manifest_name,
            manifest_version=body.manifest_version,
            workspace_id=body.workspace_id,
            namespace=body.namespace,
            infer_job_id=body.infer_job_id,
            payload=body.payload,
        )
        return _envelope(status=1, result=raw)
    except ExternalContainerError as exc:
        raise _translate_error(exc) from exc


# ── Inference proxy (sync long-running infer pod) ────────────────────────


class InferenceBody(BaseModel):
    """Sync infer pod 의 endpoints.run 호출 — 이미 startup 시 load 된 모델로
    즉시 추론. reload 없음. params 는 partner-specific (예: ETRI 의
    image_base64 + ais_rows + output_type).
    """
    model_config = ConfigDict(extra="forbid", protected_namespaces=())
    params: dict[str, Any] = Field(default_factory=dict)


@external.post("/jobs/{job_id}/run")
async def run_inference(job_id: str, body: InferenceBody) -> dict[str, Any]:
    """Proxy infer request to a running sync infer pod."""
    client = await _get_client()
    try:
        raw = await client.run_inference(job_id=job_id, params=body.params)
        return _envelope(status=1, result=raw)
    except ExternalContainerError as exc:
        raise _translate_error(exc) from exc


# ── SSE — generic stream (raw passthrough) ───────────────────────────────


@external.get("/jobs/{job_id}/sse")
async def stream_external_job(job_id: str, request: Request) -> StreamingResponse:
    """Generic SSE relay — emits the full ExternalJobDetail payload."""

    async def _iterate() -> AsyncIterator[bytes]:
        client = await _get_client()
        terminal = {"completed", "failed", "cancelled"}
        last_signature: Optional[tuple] = None
        poll_interval = 0.5
        max_seconds = 6 * 60 * 60
        elapsed = 0.0

        while elapsed < max_seconds:
            if await request.is_disconnected():
                return
            try:
                detail = await client.get_job(job_id)
            except ExternalContainerError as exc:
                err = json.dumps({
                    "code": "E_UPSTREAM_FAILURE",
                    "status_code": exc.status_code,
                    "message": str(exc),
                })
                yield f"event: error\ndata: {err}\n\n".encode()
                return

            result = detail.get("result") or {}
            raw_status = result.get("status")
            sig = (
                raw_status,
                result.get("progress"),
                (result.get("error") or {}).get("code") if isinstance(result.get("error"), dict) else None,
            )
            if sig != last_signature:
                yield f"event: status\ndata: {json.dumps(detail)}\n\n".encode()
                last_signature = sig

            if raw_status in terminal:
                yield f"event: terminal\ndata: {json.dumps({'status': raw_status})}\n\n".encode()
                return

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        timeout_event = json.dumps({"reason": "stream_timeout", "max_seconds": max_seconds})
        yield f"event: error\ndata: {timeout_event}\n\n".encode()

    return StreamingResponse(_iterate(), media_type="text/event-stream")


# ── SSE — internal-LLM-compatible variants ──────────────────────────────


@external.get("/jobs/{job_id}/sse-status")
async def stream_fine_tuning_status(job_id: str, request: Request) -> StreamingResponse:
    """Drop-in replacement for /api/models/fine-tuning/sse-status/{id}."""

    async def _iterate() -> AsyncIterator[bytes]:
        client = await _get_client()
        last_payload: Optional[dict] = None
        last_emit = datetime.now(timezone.utc)

        while True:
            if await request.is_disconnected():
                return
            detail: Optional[dict]
            try:
                detail = await client.get_job(job_id)
            except ExternalContainerError as exc:
                if exc.status_code == 404:
                    # tracker cleanup 후 학습 완료 (done) 으로 처리.
                    detail = None
                else:
                    err = json.dumps({"code": "E_UPSTREAM_FAILURE", "message": str(exc)})
                    yield f"event: error\ndata: {err}\n\n".encode()
                    return

            payload = _build_fine_tuning_status(detail)
            now = datetime.now(timezone.utc)
            if payload != last_payload:
                yield f"data: {json.dumps(payload)}\n\n".encode()
                last_payload = payload
                last_emit = now
            elif (now - last_emit).total_seconds() >= 30:
                yield f"data: {json.dumps(payload)}\n\n".encode()
                last_emit = now

            # Same terminal short-circuit as the internal SSE: keep streaming
            # for as long as the client holds the connection.
            await asyncio.sleep(3)

    return StreamingResponse(_iterate(), media_type="text/event-stream")


@external.get("/jobs/{job_id}/sse-time")
async def stream_fine_tuning_time(job_id: str, request: Request) -> StreamingResponse:
    """Drop-in replacement for /api/models/fine-tuning/sse-time/{id}."""

    async def _iterate() -> AsyncIterator[bytes]:
        client = await _get_client()
        last_payload: Optional[dict] = None
        last_emit = datetime.now(timezone.utc)
        last_time_per_step: Optional[float] = None

        while True:
            if await request.is_disconnected():
                return
            detail: Optional[dict]
            try:
                detail = await client.get_job(job_id)
            except ExternalContainerError as exc:
                if exc.status_code == 404:
                    # tracker cleanup 후 — commit_models path 로 fallback
                    detail = None
                else:
                    err = json.dumps({"code": "E_UPSTREAM_FAILURE", "message": str(exc)})
                    yield f"event: error\ndata: {err}\n\n".encode()
                    return

            payload, last_time_per_step = await _build_time_payload(
                detail, job_id, last_time_per_step,
            )
            now = datetime.now(timezone.utc)
            if payload != last_payload:
                yield f"data: {json.dumps(payload)}\n\n".encode()
                last_payload = payload
                last_emit = now
            elif (now - last_emit).total_seconds() >= 30:
                yield f"data: {json.dumps(payload)}\n\n".encode()
                last_emit = now

            await asyncio.sleep(3)

    return StreamingResponse(_iterate(), media_type="text/event-stream")


@external.get("/jobs/{job_id}/sse-graph")
async def stream_fine_tuning_graph(job_id: str, request: Request) -> StreamingResponse:
    """Drop-in replacement for /api/models/fine-tuning/sse-graph/{id}.

    ETRI v1.0.0 does not emit TensorBoard scalars, so this returns
    `{graph: {}}` and the existing frontend chart renders its empty state.
    ETRI v1.0.1 with TensorBoard activated will populate the graph via
    `parse_tensorboard_scalars_async` against the partner pod's NFS log dir.
    """

    async def _iterate() -> AsyncIterator[bytes]:
        client = await _get_client()
        last_payload: Optional[dict] = None
        last_emit = datetime.now(timezone.utc)

        while True:
            if await request.is_disconnected():
                return
            # tracker active 면 detail 받고, cleanup 됐으면 None 으로 fallback.
            # commit_models path 로 graph 보존 (학습 종료 후에도 같은 chart 유지).
            detail: Optional[dict]
            try:
                detail = await client.get_job(job_id)
            except ExternalContainerError as exc:
                if exc.status_code == 404:
                    detail = None
                else:
                    err = json.dumps({"code": "E_UPSTREAM_FAILURE", "message": str(exc)})
                    yield f"event: error\ndata: {err}\n\n".encode()
                    return

            payload = await _build_graph_payload(detail, job_id=job_id)
            now = datetime.now(timezone.utc)
            if payload != last_payload:
                yield f"data: {json.dumps(payload)}\n\n".encode()
                last_payload = payload
                last_emit = now
            elif (now - last_emit).total_seconds() >= 30:
                yield f"data: {json.dumps(payload)}\n\n".encode()
                last_emit = now

            await asyncio.sleep(3)

    return StreamingResponse(_iterate(), media_type="text/event-stream")


@external.get("/models/{model_id}/phases/{phase_id}/sse-graph")
async def stream_phase_fine_tuning_graph(
    model_id: int, phase_id: str, request: Request,
) -> StreamingResponse:
    """레시피 phase 단위 학습 그래프 SSE.

    payload shape 은 /jobs/{job_id}/sse-graph 와 동일(`{graph, checkpoints}`)해서
    프론트 차트(FineTuningGraph/SDSMonitorSummary)가 그대로 소비한다. 활성 job 유무와
    무관하게 조회되므로 이미 끝난 phase 도 자기 곡선을 돌려준다.
    """
    if not _PHASE_ID_RE.match(phase_id or ""):
        raise HTTPException(status_code=400, detail="invalid phase_id")

    async def _iterate() -> AsyncIterator[bytes]:
        last_payload: Optional[dict] = None
        last_emit = datetime.now(timezone.utc)

        while True:
            if await request.is_disconnected():
                return
            payload = await _build_phase_graph_payload(model_id, phase_id)
            now = datetime.now(timezone.utc)
            if payload != last_payload:
                yield f"data: {json.dumps(payload)}\n\n".encode()
                last_payload = payload
                last_emit = now
            elif (now - last_emit).total_seconds() >= 30:
                yield f"data: {json.dumps(payload)}\n\n".encode()
                last_emit = now

            await asyncio.sleep(3)

    return StreamingResponse(_iterate(), media_type="text/event-stream")


# ── REST — raw log (1s polling on the frontend side) ────────────────────


async def _resolve_train_log_path(job_id: str, detail: Optional[dict]) -> Optional[str]:
    """NFS 의 train.log 위치 추론.

    Source priority — graph fallback 과 동일 path 패턴:
      1) tracker active → jobs/<job_id>/output/<subdir>/train.log
      1.5) 학습이 아닌 잡(평가·변환 등) → jobs/<job_id>/output/run.log
      2) tracker cleanup 후 → models/<external>/commit_models/<commit>/train.log

    1.5 가 필요한 이유: train.log 는 파인튜닝 컨테이너의 산출물이다. 평가 컨테이너
    (evaluate-intent 등)는 학습 로그가 아니라 실행 로그를 남기므로 파일명이 다르고,
    output_subdir 도 쓰지 않는다. 파드 stdout 을 읽지 않는 이유는 잡이 끝나면 파드가
    사라져 로그를 다시 볼 수 없기 때문이다 — NFS 파일이라야 사후에도 열린다.
    """
    import os
    from utils.llm_db import db_model as _dbm
    from utils import PATH

    # 1. tracker active jobs path
    if detail:
        output_subdir = detail.get("output_subdir")
        workspace_id = detail.get("workspace_id")
        if output_subdir and workspace_id:
            try:
                ws = await _dbm.get_workspace_model(workspace_id=int(workspace_id))
                if ws:
                    main_root = PATH.JF_MAIN_STORAGE_PATH.format(
                        STORAGE_NAME=ws["main_storage_name"], WORKSPACE_NAME=ws["name"],
                    )
                    p = _contained_path(
                        main_root, "jobs", job_id, "output", output_subdir, "train.log")
                    if p and os.path.exists(p):
                        return p
            except Exception:
                logger.exception("system-log: ws lookup (active) failed")

        # 1.5. 학습이 아닌 외부 잡의 실행 로그. output_subdir 이 없는 경우가 대부분이라
        #      위 분기와 조건을 공유하지 않는다(subdir 이 있으면 그 아래도 본다).
        if workspace_id:
            try:
                ws = await _dbm.get_workspace_model(workspace_id=int(workspace_id))
                if ws:
                    main_root = PATH.JF_MAIN_STORAGE_PATH.format(
                        STORAGE_NAME=ws["main_storage_name"], WORKSPACE_NAME=ws["name"],
                    )
                    candidates = [("jobs", job_id, "output", "run.log")]
                    if output_subdir:
                        candidates.insert(
                            0, ("jobs", job_id, "output", output_subdir, "run.log"))
                    for parts in candidates:
                        p = _contained_path(main_root, *parts)
                        if p and os.path.exists(p):
                            return p
            except Exception:
                logger.exception("system-log: run.log lookup failed")

    # 2. commit_models fallback
    try:
        from utils.llm_db.db_base_async import select_query
        rows = await select_query(
            "SELECT id, workspace_id, name, latest_commit_id "
            "FROM model WHERE external_job_id = %s LIMIT 1",
            params=(job_id,),
        )
        if rows:
            m = rows[0]
            if m.get("latest_commit_id"):
                commit_row = await _dbm.get_commit_model(commit_id=m["latest_commit_id"])
                ws = await _dbm.get_workspace_model(workspace_id=int(m["workspace_id"]))
                if commit_row and ws:
                    main_root = PATH.JF_MAIN_STORAGE_PATH.format(
                        STORAGE_NAME=ws["main_storage_name"], WORKSPACE_NAME=ws["name"],
                    )
                    p = _contained_path(
                        main_root, "models", m["name"], "commit_models",
                        commit_row["name"], "train.log")
                    if p and os.path.exists(p):
                        return p
    except Exception:
        logger.exception("system-log: commit fallback failed")
    return None


def _read_log_tail_sync(log_path: str, max_bytes: int = 256 * 1024,
                        max_lines: int = 200) -> tuple[str, int, int]:
    """(tail 텍스트, 파일 전체 크기, 실제 줄 수) — 모달 폴링용.
    큰 파일 보호로 끝에서 max_bytes 만 읽는다. job/phase 로그 조회가 공유."""
    import os
    with open(log_path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        read_size = min(size, max_bytes)
        f.seek(size - read_size)
        content = f.read().decode("utf-8", errors="replace")
    lines = content.splitlines()[-max_lines:]
    return "\n".join(lines), size, len(lines)


def _read_log_full_sync(log_path: str) -> tuple[str, int, int]:
    """(내용, 파일 전체 크기, 실제 읽은 bytes) — 다운로드용.
    상한 초과 시 뒤쪽(최근)을 남긴다. job/phase 다운로드가 공유."""
    import os
    with open(log_path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        read_size = min(size, _LOG_DOWNLOAD_MAX_BYTES)
        f.seek(size - read_size)
        content = f.read().decode("utf-8", errors="replace")
    return content, size, read_size


@external.get("/jobs/{job_id}/system-log")
async def get_external_system_log(job_id: str) -> dict[str, Any]:
    """Drop-in replacement for /api/models/fine-tuning/system-log?model_id=.

    NFS 의 로그 파일 직접 read — graph fallback 과 동일한 path 패턴.
    학습 잡은 jobs/.../train.log → commit_models/.../train.log 순으로,
    학습이 아닌 잡(평가·변환 등)은 jobs/<job_id>/output/run.log 를 읽는다.
    partner pod 가 로그 endpoint 를 제공하지 않아도 NFS mount 로 동기 동작하고,
    파드가 사라진 뒤에도 조회된다(파드 stdout 을 읽지 않는 이유).

    Modal 의 폴링 (1초 간격) 에 매번 마지막 200 줄 응답.
    """
    client = await _get_client()
    detail: Optional[dict]
    try:
        detail = await client.get_job(job_id)
    except ExternalContainerError as exc:
        if exc.status_code == 404:
            detail = None
        else:
            raise _translate_error(exc) from exc

    log_path = await _resolve_train_log_path(job_id, detail)
    if log_path:
        try:
            tail, size, n_lines = _read_log_tail_sync(log_path)
            # ⚠️ 소스 **경로**는 싣지 않는다. 이 문자열은 로그 모달에 그대로 렌더되는데,
            #    NFS 실경로는 내부 스토리지/워크스페이스 명명과 잡 디렉터리 구조를 그대로
            #    공개한다(정찰 정보). 플랫폼 규약도 체크포인트를 이름으로만 노출한다.
            #    내부 대응 경로(models/fine-tuning/system-log)도 경로를 싣지 않는다.
            header = (
                f"[platform] external job {job_id}  "
                f"size={size} bytes  showing last {n_lines} lines\n"
                f"{'-' * 80}\n"
            )
            return _envelope(status=1, result=header + tail)
        except Exception:
            logger.exception("system-log: read failed for %s", log_path)
            return _envelope(
                status=1,
                result=f"[platform] failed to read {log_path} — see server logs",
            )

    # 읽을 로그 파일이 없음 — placeholder 응답
    result = (detail or {}).get("result") or {}
    raw_status = result.get("status") or ("unknown" if detail is None else "pending")
    scalars = _extract_etri_scalars(detail or {})
    output_dir = scalars.get("output_dir") or "(unknown)"
    placeholder = (
        f"[platform] external job {job_id}\n"
        f"  status        : {raw_status}\n"
        f"  output_dir    : {output_dir}\n"
        f"\n"
        f"[platform] 이 잡의 로그 파일을 NFS 에서 찾지 못했습니다.\n"
        f"           찾는 위치는 jobs/{job_id}/output/ 아래의 run.log(실행 로그) 와\n"
        f"           train.log(학습 로그) 입니다.\n"
        f"\n"
        f"           흔한 원인:\n"
        f"           - 잡이 방금 시작해 아직 첫 줄을 쓰지 않았다(잠시 후 다시 조회).\n"
        f"           - 로그를 남기지 않는 구버전 컨테이너로 실행된 잡이다.\n"
        f"             (evaluate-intent 는 0.2.1, evaluate-logickor-judge 는 0.2.1\n"
        f"              부터 run.log 를 남긴다 — 그 이전 런은 다시 볼 로그가 없다.)\n"
        f"           - 학습 잡이라면 산출물이 commit 으로 옮겨진 직후일 수 있다.\n"
    )
    err = result.get("error")
    if isinstance(err, dict) and err.get("message"):
        placeholder += f"\n[platform] last partner error: {err.get('message')}\n"
    return _envelope(status=1, result=placeholder)


# 다운로드 상한. 조회(200줄 tail)와 달리 전문을 내려주되, 수백 MB 로그가 그대로
# 메모리에 올라오는 것은 막는다. 넘치면 뒤쪽(최근)을 남긴다 — 실패 진단에 필요한 건
# 대개 마지막 부분이라 앞을 버리는 편이 낫다.
_LOG_DOWNLOAD_MAX_BYTES = 20 * 1024 * 1024


@external.get("/jobs/{job_id}/system-log/download")
async def download_external_system_log(job_id: str):
    """실행 로그 전문 다운로드 — 내부용 /models/fine-tuning/system-log/download 의 external 판.

    조회 endpoint 는 모달 폴링용이라 마지막 200 줄만 준다. 실패를 파고들 때는 전문이
    필요하므로 같은 파일을 통째로 내려준다. 응답 생성은 내부용과 **같은 헬퍼**를 써서
    프런트가 두 경로를 다르게 다루지 않아도 되게 한다.

    로그 파일이 없으면 404 — 프런트는 HTTP status 로 성공을 판정하므로, 여기서
    envelope 200 을 돌려주면 안내 문구가 .log 파일로 저장돼 버린다.
    """
    from utils import common

    client = await _get_client()
    detail: Optional[dict]
    try:
        detail = await client.get_job(job_id)
    except ExternalContainerError as exc:
        if exc.status_code == 404:
            detail = None
        else:
            raise _translate_error(exc) from exc

    log_path = await _resolve_train_log_path(job_id, detail)
    if not log_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no log file for external job {job_id}",
        )

    try:
        content, size, read_size = _read_log_full_sync(log_path)
    except OSError:
        logger.exception("system-log download: read failed for %s", log_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to read log file",
        )

    # 조회 배너와 같은 이유로 소스 경로는 제외한다(다운로드 파일에 남으면 더 오래 돈다).
    header = (
        f"[platform] external job {job_id}\n"
        f"           size={size} bytes"
        + (f" (truncated to last {read_size} bytes)" if read_size < size else "")
        + "\n" + "-" * 80 + "\n"
    )
    return await common.text_response_generator_async(
        data_str=header + content, filename=f"[EXTERNAL]{job_id}.log")


# ── Phase 단위 시스템 로그 (SDS 레시피) ──────────────────────────────────────
# 그래프와 같은 이유로 phase 를 조회 단위로 잡는다. job 기준(`/jobs/{id}/system-log`)
# 은 (a) 활성 job 이 없으면 열 수 없고 (b) 커밋 폴백이 `latest_commit_id` 를 써서
# 끝난 phase 의 로그를 요청해도 **최신 phase 의 로그**가 나온다. 기존 endpoint 는
# 비레시피 external 잡(평가·변환의 run.log 분기 포함)이 계속 쓰므로 그대로 둔다.


async def _resolve_phase_train_log_path(model_id: int, phase_id: str) -> Optional[str]:
    """선택 phase 자신의 로그 파일. 실행 중이면 jobs/, 끝났으면 그 phase 의 커밋에서.

    train.log(학습 컨테이너 산출물) 우선, 없으면 run.log — 기존 job 경로와 같은 관례.
    """
    import os

    base = await _resolve_phase_output_dir(model_id, phase_id)
    if not base:
        return None
    for name in ("train.log", "run.log"):
        path = _contained_path(base, name)
        if path and os.path.exists(path):
            return path
    return None


@external.get("/models/{model_id}/phases/{phase_id}/system-log")
async def get_phase_system_log(model_id: int, phase_id: str) -> dict[str, Any]:
    """레시피 phase 단위 로그 조회 — 모달 폴링용(마지막 200 줄).

    응답은 job 판과 같은 envelope + 같은 'showing last N lines' 헤더 규약이다.
    프런트가 그 문구로 실제 로그/안내문구를 구분하므로 바꾸면 안 된다.
    """
    if not _PHASE_ID_RE.match(phase_id or ""):
        raise HTTPException(status_code=400, detail="invalid phase_id")

    log_path = await _resolve_phase_train_log_path(model_id, phase_id)
    if log_path:
        try:
            tail, size, n_lines = _read_log_tail_sync(log_path)
            # ⚠️ 소스 경로는 싣지 않는다(job 판과 동일 — NFS 실경로 노출 방지).
            header = (
                f"[platform] model {model_id} phase {phase_id}  "
                f"size={size} bytes  showing last {n_lines} lines\n"
                f"{'-' * 80}\n"
            )
            return _envelope(status=1, result=header + tail)
        except Exception:
            logger.exception("phase system-log: read failed for %s", log_path)
            return _envelope(
                status=1,
                result=f"[platform] failed to read log for phase {phase_id} — see server logs",
            )

    placeholder = (
        f"[platform] model {model_id} phase {phase_id}\n"
        f"\n"
        f"[platform] 이 phase 의 로그 파일을 찾지 못했습니다.\n"
        f"\n"
        f"           흔한 원인:\n"
        f"           - 아직 실행하지 않은 phase 다.\n"
        f"           - 방금 시작해 컨테이너가 첫 줄을 쓰지 않았다(잠시 후 다시 조회).\n"
        f"           - 학습 산출물이 commit 으로 옮겨지는 중이다.\n"
    )
    return _envelope(status=1, result=placeholder)


@external.get("/models/{model_id}/phases/{phase_id}/system-log/download")
async def download_phase_system_log(model_id: int, phase_id: str):
    """phase 로그 전문 다운로드. 파일이 없으면 404 — 프런트가 HTTP status 로 성공을
    판정하므로 envelope 200 을 주면 안내 문구가 .log 로 저장된다(job 판과 동일)."""
    from utils import common

    if not _PHASE_ID_RE.match(phase_id or ""):
        raise HTTPException(status_code=400, detail="invalid phase_id")

    log_path = await _resolve_phase_train_log_path(model_id, phase_id)
    if not log_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no log file for model {model_id} phase {phase_id}",
        )

    try:
        content, size, read_size = _read_log_full_sync(log_path)
    except OSError:
        logger.exception("phase system-log download: read failed for %s", log_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to read log file",
        )

    header = (
        f"[platform] model {model_id} phase {phase_id}\n"
        f"           size={size} bytes"
        + (f" (truncated to last {read_size} bytes)" if read_size < size else "")
        + "\n" + "-" * 80 + "\n"
    )
    return await common.text_response_generator_async(
        data_str=header + content, filename=f"[PHASE]{model_id}-{phase_id}.log")
