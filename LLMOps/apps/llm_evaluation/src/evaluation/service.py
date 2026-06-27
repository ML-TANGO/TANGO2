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
import hashlib
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
    JUDGE_CRITERIA,
    JUDGE_DEFAULT_MODEL,
    JUDGE_PROVIDER_HOSTS,
    MAX_EXPERT_SAMPLES,
    MAX_JUDGE_RUN_SECONDS,
    MAX_JUDGE_SAMPLES,
)

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
    rows = await db_model.list_eval_results(source_model_id=model_id)
    return {"model_id": model_id, **db_model.build_eval_comparison(rows)}


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


def _build_judge_samples(model_name: str, ds_names: List[str]) -> list:
    """채점 대상 샘플. P2(A: mock 스캐폴딩) — 실 모델 출력 생성/데이터셋 파일 읽기는 후속.
    데이터셋당 고정 샘플 수의 placeholder(실 provider 어댑터가 받을 input/output 골격)."""
    n = min(MAX_JUDGE_SAMPLES, max(1, len(ds_names) * 5))
    base = ds_names[0] if ds_names else "dataset"
    return [
        {"id": f"{model_name}-{base}-{i}",
         "input": f"[{base}] sample {i} prompt",
         "output": f"[{model_name}] response {i}",
         "reference": ""}
        for i in range(n)
    ]


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


async def _run_judge_task(model_id, job_id, model_name, ds_names, provider, judge_model,
                          api_key, base_url, criteria, custom_prompt) -> None:
    """백그라운드 judge 루프 — 샘플별 심판 호출 → 기준별 평균(0~100) → eval_result 마감.
    ⚠️ api_key 는 이 함수 인자로만 존재(in-memory). 절대 로그/DB 기록 금지.
    전역 wall-clock 상한(MAX_JUDGE_RUN_SECONDS) 초과(hung provider 등) 시 failed 처리."""
    try:
        async def _score_all():
            samples = _build_judge_samples(model_name, ds_names)
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


async def run_judge(model_id: int, dataset_ids: List[int], provider: str,
                    criteria: List[str], judge_model: Optional[str] = None,
                    api_key: Optional[str] = None, base_url: Optional[str] = None,
                    custom_prompt: Optional[str] = None) -> dict:
    """LLM-as-a-Judge 런 생성(직접호출 비동기). 키/URL = transient. 즉시 job_id 반환 후
    백그라운드 채점 → eval_result.metrics(judge_*) 마감. FE 는 get_judge_result 폴링."""
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

    job_id = f"judge-{model_id}-{uuid.uuid4().hex[:16]}"
    await db_model.insert_eval_result(
        source_model_id=model_id, workspace_id=workspace_id, job_str_id=job_id,
        dataset_id=dataset_ids[0], dataset_name=dataset_name_csv,
        metric_set=f"judge:{provider}")

    task = asyncio.create_task(_run_judge_task(
        model_id, job_id, model_name, ds_names, provider, judge_model,
        api_key, base_url, crit, custom_prompt))
    _judge_tasks.add(task)
    task.add_done_callback(_judge_tasks.discard)

    return {"model_id": model_id, "job_id": job_id, "provider": provider,
            "mode": "judge", "criteria": crit, "datasets": ds_names,
            "mock": _judge_mock_enabled()}


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
    return {"job_id": job_id, "metrics": metrics,
            "ready": status == "completed", "status": status}


# ── 전문가 평가 (P3) ──────────────────────────────────────────────────────────
# 사람이 샘플(입력/출력/참조)을 O/X + 코멘트로 채점 → eval_expert_rating 영속 → 합격률 집계.
# 세션 = eval_result row(metric_set='expert'). 전부 채점 시 합격률을 eval_result.metrics
# (expert_pass_rate)로 마감 → 모델 이력 비교표 합류. 샘플=결정적 생성(idx 기반, 재로드 안정).
# P2(A)와 동일 mock 스캐폴딩 — 실 모델출력 생성은 후속.

def _build_expert_samples(model_name: str, ds_names: List[str]) -> list:
    n = min(MAX_EXPERT_SAMPLES, max(1, len(ds_names) * 5))
    base = ds_names[0] if ds_names else "dataset"
    return [
        {"idx": i,
         "dataset": ds_names[i % len(ds_names)] if ds_names else base,
         "input": f"[{base}] sample {i} 입력 프롬프트",
         "output": f"[{model_name}] 응답 {i}",
         "reference": f"참조 답변 {i}"}
        for i in range(n)
    ]


async def _expert_session(model_id: int, job_id: str):
    """세션 행 + (model_name, ds_names, samples) 재구성(결정적). 없으면 예외."""
    if not job_id or not _JOB_ID_RE.match(job_id):
        raise ValueError(f"invalid job_id: {job_id!r}")
    row = await db_model.get_eval_result_by_job(job_str_id=job_id, source_model_id=model_id)
    # metric_set 검증 — 벤치마크/judge job_id 를 expert 로 다뤄 그 metrics 를
    # complete_eval_result 로 덮어쓰는 교차모드 오염 차단.
    if not row or row.get("metric_set") != "expert":
        raise Exception("expert session not found")
    model_info = await db_model.get_model(model_id=model_id)
    model_name = (model_info or {}).get("name", "model")
    ds_names = [s for s in str(row.get("dataset_name") or "").split(",") if s]
    samples = _build_expert_samples(model_name, ds_names)
    return row, samples


async def start_expert(model_id: int, dataset_ids: List[int]) -> dict:
    """전문가 평가 세션 시작 — 대상 모델 × 데이터셋 → 채점 샘플 생성 + 세션 행."""
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
        # 샘플을 dataset_name(CSV)에서 재구성하므로 이름에 콤마/공백이 있으면 왕복이 깨짐.
        # run_benchmark 와 동일 가드 → CSV 가 손실 없는 정본이 되도록 안전 문자만 허용.
        if not _SAFE_SEGMENT_RE.match(ds_name):
            raise Exception("dataset name has unsafe characters")
        ds_names.append(ds_name)

    samples = _build_expert_samples(model_name, ds_names)
    dataset_name_csv = ",".join(ds_names)
    if len(dataset_name_csv) > 255:
        # 전문가 평가는 dataset_name 으로 샘플을 결정적 재구성 → 요약 저장 시 재구성 불일치.
        # (벤치마크는 재구성 안 해 요약 OK) 손실 방지로 거부.
        raise Exception(
            "dataset names too long to store; reduce dataset count or shorten names")

    job_id = f"expert-{model_id}-{uuid.uuid4().hex[:16]}"
    await db_model.insert_eval_result(
        source_model_id=model_id, workspace_id=workspace_id, job_str_id=job_id,
        dataset_id=dataset_ids[0], dataset_name=dataset_name_csv, metric_set="expert")

    return {"model_id": model_id, "job_id": job_id, "mode": "expert",
            "datasets": ds_names, "samples": samples, "total": len(samples)}


async def get_expert_samples(model_id: int, job_id: str) -> dict:
    """세션 샘플 + 기존 채점(재개용)."""
    row, samples = await _expert_session(model_id, job_id)
    ratings = await db_model.list_expert_ratings(job_str_id=job_id, source_model_id=model_id)
    return {"job_id": job_id, "status": row.get("status"), "samples": samples,
            "total": len(samples), "ratings": ratings}


async def submit_expert_rating(model_id: int, job_id: str, sample_idx: int,
                               verdict: str, comment: str = None,
                               rater_user: str = None) -> dict:
    """채점 1건 upsert → 합격률 재계산 → 전부 채점 시 세션 완료(eval_result 마감)."""
    if verdict not in ("O", "X"):
        raise ValueError(f"invalid verdict: {verdict!r}")
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
        verdict=verdict, input=s.get("input"), output=s.get("output"),
        reference=s.get("reference"), rater_user=rater_user, comment=comment)

    ratings = await db_model.list_expert_ratings(job_str_id=job_id, source_model_id=model_id)
    rated = len(ratings)
    passed = sum(1 for r in ratings if r.get("verdict") == "O")
    pass_rate = round(passed / rated * 100.0, 2) if rated else 0.0

    completed = False
    if rated >= total:  # 전부 채점 → 합격률 영속 + 완료(비교표 합류)
        metrics = {"expert_pass_rate": pass_rate, "_mode": "expert",
                   "_rated": rated, "_total": total}
        await db_model.complete_eval_result(
            job_str_id=job_id, metrics_json=json.dumps(metrics), source_model_id=model_id)
        completed = True

    return {"job_id": job_id, "rated": rated, "total": total,
            "pass_rate": pass_rate, "completed": completed}


async def get_expert_result(model_id: int, job_id: str) -> dict:
    """세션 진행/결과 — 상태 + 채점 목록 + 합격률."""
    if not job_id or not _JOB_ID_RE.match(job_id):
        raise ValueError(f"invalid job_id: {job_id!r}")
    row = await db_model.get_eval_result_by_job(job_str_id=job_id, source_model_id=model_id)
    if not row or row.get("metric_set") != "expert":
        return {"job_id": job_id, "status": "pending", "ratings": [], "pass_rate": None}
    ratings = await db_model.list_expert_ratings(job_str_id=job_id, source_model_id=model_id)
    rated = len(ratings)
    passed = sum(1 for r in ratings if r.get("verdict") == "O")
    pass_rate = round(passed / rated * 100.0, 2) if rated else None
    return {"job_id": job_id, "status": row.get("status"), "ratings": ratings,
            "rated": rated, "pass_rate": pass_rate}
