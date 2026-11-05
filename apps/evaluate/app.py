"""evaluate — 플랫폼 소유 자동평가 컨테이너 (SP-5 / v0.4 3.8).

학습 완료 모델(/model)을 평가 데이터셋(/dataset/<name>)으로 채점한다. 외부 SaaS
judge(gpt-4.1 등)에 의존하지 않는 **자체 메트릭**(BLEU / ROUGE-1/2/L / perplexity)을
순수 파이썬 + torch 로 계산한다 (PROGRESS 7/15 SaaS 비의존 결정). 동시에 ⑪ 고려대
평가 plugin 슬롯의 **참조 구현** 역할 — 같은 job_type=evaluate 계약을 따른다.

플랫폼이 소유·구현하며(협력기관 제공물 아님), 배포는 external_container launch
메커니즘을 재사용한다 (SP-5 §2, SP-4 J-1 과 동형 — fb_evaluate 신규 서비스 회피).
SP-1 외부 컨테이너 계약을 그대로 따르므로 플랫폼/FE/eval_result 영속화 와이어링은
변경 없이 동작한다.

흐름:
  1. /dataset 에서 평가 파일(jsonl/json/csv/txt) 탐색 + 파싱
  2. /model 의 HF 모델 로드 (transformers)
  3. (prompt+reference 있으면) 생성 → BLEU/ROUGE,  (텍스트만 있으면) perplexity 만
  4. /output/metrics.json 작성 + result dict 보고 (플랫폼이 NFS 산출물로 영속화)

베이스 이미지(ghcr.io/ggml-org/llama.cpp:full)가 torch/transformers 를 제공한다.
메트릭은 외부 의존(sacrebleu/rouge-score) 없이 순수 파이썬으로 구현 — 빌드 단순화.
※ 토크나이저는 공백분리+소문자(데모용 단순화). 정밀 평가는 고려대 plugin(⑪) 으로 수용.
"""
from __future__ import annotations

import asyncio
import csv
import json
import math
import os
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse

# ── 플랫폼 주입 env (spec §3.2) ──
JF_ITEM_ID        = os.environ.get("JF_ITEM_ID", "local")
JF_JOB_TYPE       = os.environ.get("JF_JOB_TYPE", "evaluate")
JF_EXECUTION_MODE = os.environ.get("JF_EXECUTION_MODE", "async")
JF_PARAMS_PATH    = os.environ.get("JF_PARAMS_PATH", "/input/params.json")
JF_MODEL_PATH     = os.environ.get("JF_MODEL_PATH", "/model")
JF_DATASET_ROOT   = os.environ.get("JF_DATASET_ROOT", "/dataset")
JF_DATASET_NAME   = os.environ.get("JF_DATASET_NAME", "").strip()
JF_OUTPUT_PATH    = os.environ.get("JF_OUTPUT_PATH", "/output")
JF_PORT           = int(os.environ.get("JF_PORT", "8000"))

NAME    = "evaluate-selfmetric"
VERSION = "1.0.0"

# 데이터셋 컬럼 자동 감지 — prompt/reference/text 후보(우선순위순).
_PROMPT_FIELDS    = ["prompt", "instruction", "input", "question", "source", "query"]
_REFERENCE_FIELDS = ["reference", "output", "response", "answer", "target", "completion", "label"]
_TEXT_FIELDS      = ["text", "content", "sentence", "document"]

_ALL_METRICS = ["bleu", "rouge", "perplexity"]

# per-row 필드 길이 cap — ROUGE-L LCS(O(n*m)) 등 메트릭 DoS 방지(max_samples 와 별개).
_MAX_FIELD_CHARS = 4000

CAPABILITIES = {
    "supported_models": [],
    "min_gpu_memory_gb": None,   # CPU 로도 동작(소형 모델). GPU 있으면 자동 사용.
    "estimated_startup_seconds": 20,
    "estimated_duration_seconds": 300,
    "timeout_seconds": 3600,
}

app = FastAPI(title=NAME, version=VERSION)

_jobs: Dict[str, Dict[str, Any]] = {}


def _emit(event: str, **fields: Any) -> None:
    line = {"event": event, "timestamp": datetime.now(timezone.utc).isoformat(), **fields}
    print(json.dumps(line, ensure_ascii=False), flush=True)


def _load_params(body_params: Optional[dict]) -> dict:
    if body_params:
        return body_params
    try:
        with open(JF_PARAMS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"malformed or unreadable {JF_PARAMS_PATH}: {exc}") from exc


# ── 표준 endpoint (SP-1 규약) ──

@app.get("/health", tags=["표준"])
async def health():
    return JSONResponse(status_code=200, content={"status": "ready"})


@app.get("/live", tags=["표준"])
async def live():
    return JSONResponse(status_code=200, content={"status": "alive"})


@app.get("/info", tags=["표준"])
async def info():
    return {
        "name": NAME,
        "version": VERSION,
        "execution_mode": JF_EXECUTION_MODE,
        "job_type": JF_JOB_TYPE,
        "spec_api_version": "tango.acryl.ai/v1",
        "metrics": _ALL_METRICS,
        **CAPABILITIES,
    }


@app.post("/run", tags=["표준"])
async def run(body: Optional[dict] = Body(default=None)):
    body = body or {}
    raw = body["params"] if isinstance(body.get("params"), dict) else body
    try:
        params = _load_params(raw)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={
            "status": "error", "code": "E_PARAMS_INVALID", "message": str(exc)})

    if any(j["status"] == "running" for j in _jobs.values()):
        return JSONResponse(status_code=429, content={
            "status": "error", "code": "E_BUSY", "message": "a job is already running"})

    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {"status": "running", "progress": 0.0, "result": None,
                     "error": None, "cancel": False, "task": None}
    _jobs[job_id]["task"] = asyncio.create_task(_run_job(job_id, params))
    _emit("log", level="info", message="evaluate job started", job_id=job_id,
          item_id=JF_ITEM_ID, metric_set=params.get("metric_set", _ALL_METRICS))
    return JSONResponse(status_code=202, content={
        "status": "running", "job_id": job_id, "message": "accepted"})


@app.get("/jobs/{job_id}", tags=["표준"])
async def job_status(job_id: str):
    j = _jobs.get(job_id)
    if j is None:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "E_JOB_NOT_FOUND", "message": f"unknown job_id {job_id}"})
    return {
        "job_id": job_id,
        "status": j["status"],
        "progress": j["progress"],
        "result": j["result"],
        "error": j["error"],
    }


@app.post("/jobs/{job_id}/cancel", tags=["표준"])
async def job_cancel(job_id: str):
    j = _jobs.get(job_id)
    if j is None:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "E_JOB_NOT_FOUND", "message": f"unknown job_id {job_id}"})
    if j["status"] != "running":
        return {"job_id": job_id, "status": j["status"]}
    j["cancel"] = True
    return {"job_id": job_id, "status": "cancelling"}


# ── 메트릭 (순수 파이썬, 외부 의존 없음) ──

def _tok(s: str) -> List[str]:
    """데모용 토크나이저 — 공백분리 + 소문자. (정밀 평가는 고려대 plugin 으로 수용.)"""
    return str(s).lower().split()


def _ngrams(tokens: List[str], n: int) -> Counter:
    return Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)) if len(tokens) >= n else Counter()


def _bleu(preds: List[str], refs: List[str], max_n: int = 4) -> float:
    """코퍼스 BLEU-N (브레비티 페널티 + add-1 스무딩). 0~100 스케일."""
    if not preds:
        return 0.0
    clipped = [0] * max_n
    total = [0] * max_n
    pred_len = ref_len = 0
    for pred, ref in zip(preds, refs):
        p_tok, r_tok = _tok(pred), _tok(ref)
        pred_len += len(p_tok)
        ref_len += len(r_tok)
        for n in range(1, max_n + 1):
            p_ng = _ngrams(p_tok, n)
            r_ng = _ngrams(r_tok, n)
            overlap = sum(min(c, r_ng.get(g, 0)) for g, c in p_ng.items())
            clipped[n - 1] += overlap
            total[n - 1] += sum(p_ng.values())
    # add-1 스무딩 + 존재하는 차수만 기하평균. 짧은 텍스트(예: 3토큰 < 4-gram)에서
    # 상위 차수 n-gram 이 아예 없으면 그 차수를 0 으로 곱해 BLEU 가 죽던 버그 수정 —
    # n-gram 이 존재하는 차수에 대해서만 평균(표준 short-sentence BLEU 처리).
    precisions = []
    for n in range(max_n):
        c, t = clipped[n], total[n]
        if t == 0:
            continue
        precisions.append((c + 1.0) / (t + 1.0))
    if not precisions:
        return 0.0
    geo_mean = math.exp(sum(math.log(p) for p in precisions) / len(precisions))
    bp = 1.0 if pred_len >= ref_len else math.exp(1 - ref_len / pred_len) if pred_len > 0 else 0.0
    return round(bp * geo_mean * 100.0, 4)


def _rouge_n(pred: str, ref: str, n: int) -> float:
    p_ng, r_ng = _ngrams(_tok(pred), n), _ngrams(_tok(ref), n)
    if not r_ng or not p_ng:
        return 0.0
    overlap = sum(min(c, p_ng.get(g, 0)) for g, c in r_ng.items())
    recall = overlap / max(sum(r_ng.values()), 1)
    prec = overlap / max(sum(p_ng.values()), 1)
    return 2 * prec * recall / (prec + recall) if (prec + recall) > 0 else 0.0


def _lcs(a: List[str], b: List[str]) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0] * (len(b) + 1)
        for j, y in enumerate(b, 1):
            cur[j] = prev[j - 1] + 1 if x == y else max(prev[j], cur[j - 1])
        prev = cur
    return prev[-1]


def _rouge_l(pred: str, ref: str) -> float:
    p_tok, r_tok = _tok(pred), _tok(ref)
    if not p_tok or not r_tok:
        return 0.0
    lcs = _lcs(p_tok, r_tok)
    prec = lcs / len(p_tok)
    recall = lcs / len(r_tok)
    return 2 * prec * recall / (prec + recall) if (prec + recall) > 0 else 0.0


def _rouge_corpus(preds: List[str], refs: List[str]) -> Dict[str, float]:
    if not preds:
        return {"rouge1": 0.0, "rouge2": 0.0, "rougeL": 0.0}
    r1 = sum(_rouge_n(p, r, 1) for p, r in zip(preds, refs)) / len(preds)
    r2 = sum(_rouge_n(p, r, 2) for p, r in zip(preds, refs)) / len(preds)
    rl = sum(_rouge_l(p, r) for p, r in zip(preds, refs)) / len(preds)
    return {"rouge1": round(r1 * 100, 4), "rouge2": round(r2 * 100, 4), "rougeL": round(rl * 100, 4)}


# ── 데이터셋 로딩 ──

def _find_dataset_file(dataset_root: str, max_depth: int = 8) -> Optional[str]:
    """/dataset 하위에서 평가 파일을 찾는다(우선순위 jsonl>json>csv>txt). 최초 1개.

    가드: (1) 심링크 디렉토리 미추적(followlinks=False) + depth 제한으로 깊은 트리에서
    walk 가 지연/폭주하는 것 방지, (2) 최종 선택 파일이 dataset_root 밖을 가리키는
    심링크면 거부(임의 파일 읽기 차단).
    """
    if not os.path.isdir(dataset_root):
        return None
    root_real = os.path.realpath(dataset_root)
    base_depth = root_real.rstrip(os.sep).count(os.sep)
    candidates: List[Tuple[int, str]] = []
    pref = {".jsonl": 0, ".json": 1, ".csv": 2, ".tsv": 2, ".txt": 3}
    for root, dirs, files in os.walk(dataset_root, followlinks=False):
        if os.path.realpath(root).count(os.sep) - base_depth > max_depth:
            dirs[:] = []
            continue
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            if ext in pref:
                candidates.append((pref[ext], os.path.join(root, fn)))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]))
    winner = candidates[0][1]
    if os.path.commonpath([os.path.realpath(winner), root_real]) != root_real:
        raise RuntimeError("dataset file escapes dataset root (symlink?)")
    return winner


def _pick_field(row: dict, candidates: List[str]) -> Optional[str]:
    lower = {k.lower(): k for k in row.keys()}
    for c in candidates:
        if c in lower:
            return lower[c]
    return None


def _load_dataset_rows(path: str, max_samples: int) -> List[dict]:
    rows: List[dict] = []
    ext = os.path.splitext(path)[1].lower()
    if ext == ".jsonl":
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
                if len(rows) >= max_samples:
                    break
    elif ext == ".json":
        # .json 은 통째로 로드되므로(max_samples cap 적용 전) 대용량 OOM 방지 크기 가드.
        try:
            if os.path.getsize(path) > 50 * 1024 * 1024:
                raise RuntimeError(f"json dataset too large (>50MB): {os.path.basename(path)}")
        except OSError:
            return rows
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = data.get("data") or data.get("rows") or data.get("examples") or []
        if isinstance(data, list):
            rows = [r for r in data if isinstance(r, dict)][:max_samples]
    elif ext in (".csv", ".tsv"):
        delim = "\t" if ext == ".tsv" else ","
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f, delimiter=delim):
                rows.append(dict(r))
                if len(rows) >= max_samples:
                    break
    else:  # .txt — 한 줄 = 한 샘플(perplexity 전용)
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append({"text": line})
                if len(rows) >= max_samples:
                    break
    return rows


def _extract_pairs(rows: List[dict], params: dict) -> Tuple[List[str], List[str], List[str]]:
    """rows → (prompts, references, texts). 컬럼 자동 감지 + params override."""
    if not rows:
        return [], [], []
    sample = rows[0]
    pf = params.get("prompt_field") or _pick_field(sample, _PROMPT_FIELDS)
    rf = params.get("reference_field") or _pick_field(sample, _REFERENCE_FIELDS)
    tf = params.get("text_field") or _pick_field(sample, _TEXT_FIELDS)
    prompts, references, texts = [], [], []
    # 필드 길이 cap — ROUGE-L LCS(O(n*m)) 등 메트릭이 한 거대 row 로 CPU/메모리를
    # 태우는 것 방지(max_samples 와 별개의 per-row 가드).
    cap = _MAX_FIELD_CHARS
    for row in rows:
        prompt = str(row.get(pf, ""))[:cap] if pf else ""
        ref = str(row.get(rf, ""))[:cap] if rf else ""
        text = str(row.get(tf, ""))[:cap] if tf else ""
        # perplexity 용 텍스트: text 우선, 없으면 reference, 없으면 prompt+reference.
        ppl_text = text or ref or (prompt + " " + ref).strip()
        if prompt and ref:
            prompts.append(prompt)
            references.append(ref)
        if ppl_text:
            texts.append(ppl_text)
    return prompts, references, texts


# ── 평가 잡 ──

def _run_eval_sync(params: dict, cancel_flag: Dict[str, Any], progress_cb) -> dict:
    """blocking — 모델 로드 + 생성 + 메트릭. asyncio.to_thread 로 호출."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    try:
        max_samples = max(1, min(int(params.get("max_samples", 50)), 1000))
    except (TypeError, ValueError):
        max_samples = 50
    try:
        max_new_tokens = max(1, min(int(params.get("max_new_tokens", 64)), 512))
    except (TypeError, ValueError):
        max_new_tokens = 64

    metric_set = params.get("metric_set", _ALL_METRICS)
    if isinstance(metric_set, str):
        metric_set = [m.strip().lower() for m in metric_set.split(",") if m.strip()]
    metric_set = [m for m in metric_set if m in _ALL_METRICS] or _ALL_METRICS

    # /dataset/<name> 로 스코프 — 여러 데이터셋/split 이 마운트돼도 엉뚱한 파일을
    # 평가하지 않도록 플랫폼 주입 JF_DATASET_NAME 으로 루트 한정. params.eval_file 로
    # 특정 파일(단일 basename) 명시 가능.
    ds_root = JF_DATASET_ROOT
    if JF_DATASET_NAME:
        scoped = os.path.join(JF_DATASET_ROOT, JF_DATASET_NAME)
        if os.path.isdir(scoped):
            ds_root = scoped
    eval_file = params.get("eval_file")
    if eval_file:
        cand = os.path.join(ds_root, os.path.basename(str(eval_file)))
        ds_file = cand if os.path.isfile(cand) else None
    else:
        ds_file = _find_dataset_file(ds_root)
    if not ds_file:
        raise RuntimeError(f"no evaluation dataset found under {ds_root}")
    rows = _load_dataset_rows(ds_file, max_samples)
    prompts, references, texts = _extract_pairs(rows, params)
    if not prompts and not texts:
        raise RuntimeError(
            "dataset has no usable prompt/reference/text columns "
            f"(detected keys: {list(rows[0].keys()) if rows else []})")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    progress_cb("load model", 0.1)
    tokenizer = AutoTokenizer.from_pretrained(JF_MODEL_PATH)
    if tokenizer.pad_token is None and tokenizer.eos_token is not None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        JF_MODEL_PATH, torch_dtype=torch.float16 if device == "cuda" else torch.float32)
    model.to(device)
    model.eval()

    metrics: Dict[str, Any] = {}
    n_samples = max(len(prompts), len(texts))

    # BLEU / ROUGE — prompt+reference 가 있을 때만(생성 필요).
    if prompts and ("bleu" in metric_set or "rouge" in metric_set):
        preds: List[str] = []
        for i, prompt in enumerate(prompts):
            if cancel_flag.get("cancel"):
                raise _Cancelled()
            inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512).to(device)
            with torch.no_grad():
                out = model.generate(
                    **inputs, max_new_tokens=max_new_tokens, do_sample=False,
                    pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id)
            gen = tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
            preds.append(gen)
            if (i + 1) % 5 == 0:
                progress_cb(f"generate {i + 1}/{len(prompts)}", 0.1 + 0.6 * (i + 1) / len(prompts))
        if "bleu" in metric_set:
            metrics["bleu"] = _bleu(preds, references)
        if "rouge" in metric_set:
            metrics.update(_rouge_corpus(preds, references))
        metrics["_samples_generated"] = len(preds)

    # perplexity — held-out 텍스트의 토큰 평균 NLL → exp.
    if "perplexity" in metric_set and texts:
        progress_cb("perplexity", 0.8)
        total_nll = 0.0
        total_tok = 0
        for i, text in enumerate(texts):
            if cancel_flag.get("cancel"):
                raise _Cancelled()
            enc = tokenizer(text, return_tensors="pt", truncation=True, max_length=512).to(device)
            ids = enc["input_ids"]
            if ids.shape[1] < 2:
                continue
            with torch.no_grad():
                loss = model(input_ids=ids, labels=ids).loss
            n_tok = ids.shape[1] - 1
            total_nll += float(loss) * n_tok
            total_tok += n_tok
        if total_tok > 0:
            try:
                metrics["perplexity"] = round(math.exp(total_nll / total_tok), 4)
            except OverflowError:
                metrics["perplexity"] = None  # loss 발산 → exp 오버플로우. null 기록.

    progress_cb("done", 1.0)
    metrics["_eval_samples"] = n_samples
    metrics["_dataset_file"] = os.path.basename(ds_file)
    metrics["_device"] = device
    # non-finite(NaN/Inf) 메트릭 정리 — MySQL JSON 컬럼이 거부하고 json allow_nan 기본이
    # True 라 그대로 두면 BFF 영속화가 조용히 실패(ready 인데 이력 미저장). 유한값만 유지.
    for k, v in list(metrics.items()):
        if isinstance(v, float) and not math.isfinite(v):
            metrics[k] = None
    return metrics


class _Cancelled(Exception):
    pass


async def _run_job(job_id: str, params: dict) -> None:
    j = _jobs[job_id]
    try:
        os.makedirs(JF_OUTPUT_PATH, exist_ok=True)

        def _progress(step: str, frac: float) -> None:
            j["progress"] = round(max(0.0, min(1.0, frac)), 4)
            _emit("progress", job_id=job_id, percent=round(j["progress"] * 100, 1), message=step)

        metrics = await asyncio.to_thread(_run_eval_sync, params, j, _progress)

        # NFS 산출물로 영속화 — 플랫폼이 cleanup 후에도 jobs/<id>/output/metrics.json
        # 을 읽어 eval_result 를 lazy 마감(quantize 패키지와 동형).
        with open(os.path.join(JF_OUTPUT_PATH, "metrics.json"), "w", encoding="utf-8") as f:
            # allow_nan=False — 혹시 남은 non-finite 가 있으면 'Infinity' 리터럴(JSON 비표준,
            # MySQL JSON 거부)을 쓰지 않고 즉시 에러. _run_eval_sync 에서 이미 정리하지만 방어.
            json.dump(metrics, f, ensure_ascii=False, indent=2, allow_nan=False)

        j["result"] = {
            "metrics": metrics,
            "output_dir": JF_OUTPUT_PATH,
        }
        j["progress"] = 1.0
        j["status"] = "completed"
        _emit("log", level="info", message="evaluate completed", job_id=job_id, metrics=metrics)

    except _Cancelled:
        j["status"] = "cancelled"
        _emit("log", level="info", message="evaluate cancelled", job_id=job_id)
        _clean_output()
    except Exception as exc:
        j["status"] = "failed"
        j["error"] = {"code": "E_EVAL_FAILED", "message": str(exc), "fatal": True}
        _emit("error", job_id=job_id, code="E_EVAL_FAILED", message=str(exc), fatal=True)
        _clean_output()


def _clean_output() -> None:
    """실패/취소 시 부분 산출물(metrics.json) 정리 — 플랫폼이 ready 로 오인하지 않게.
    심링크는 건너뜀(밖을 가리키는 링크를 따라 임의 파일 삭제 방지)."""
    try:
        out_real = os.path.realpath(JF_OUTPUT_PATH)
        for fn in os.listdir(JF_OUTPUT_PATH):
            fp = os.path.join(JF_OUTPUT_PATH, fn)
            if os.path.islink(fp):
                continue
            if os.path.isfile(fp) and os.path.realpath(fp).startswith(out_real + os.sep):
                os.remove(fp)
    except OSError:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=JF_PORT)
