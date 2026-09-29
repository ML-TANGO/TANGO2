"""evaluate-lmeval — lm-evaluation-harness 벤치마크 실채점 컨테이너 (SP-1 계약, GPU).

evaluate-benchmark-mock(해시 점수)을 대체한다. ETRI 가 올린 `Evaluation/lmeval` 러너의
채점 루프를 플랫폼 외부컨테이너로 옮긴 것이고, 대시보드·모델 다운로드·스케일 휴리스틱은
가져오지 않았다(설계: LLMOps/docs/2026-09-28-lmeval-benchmark-scorer-design.md).

왜 배포 위임이 아니라 로컬 가중치인가 — 객관식 벤치마크(ARC·MMLU·KoBEST…)는 보기별
로그확률로 채점하는데, 배포 shim 은 비스트리밍 chat/completions 만 있고 logprobs·stop·
max_tokens 를 전달하지 못한다. 그래서 BE 가 **고른 배포가 서빙 중인 커밋 이름**을 넘기고
(llm_evaluation `_resolve_deployment_checkpoint`) 이 잡이 그 가중치를 GPU 한 장에 올린다.
엔진은 vLLM(lm_eval `vllm` 모델)이고 chat template 은 쓰지 않는다(리더보드 관례 — 공개
수치와 비교 가능하고, Qwen3 류의 사고 모드가 로그확률 채점을 오염시키지 않는다).

같은 이미지를 두 매니페스트가 쓴다.
  - evaluate-lmeval      : lm-eval 17종 + custom. 코드 실행 불가.
  - evaluate-lmeval-code : HumanEval 전용. 매니페스트 env LMEVAL_ALLOW_CODE_EXEC=1 일 때만
                           모델 생성 코드를 실행하고, 그 파드에서는 코드 벤치마크만 받는다.
둘 다 network.isolate=true 로 뜬다(egress 전면 차단) — 로컬 모드라 나갈 곳이 없다.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse

import checkpoint as CKPT
import registry as REG
import scoring

# ── 플랫폼 주입 env (SP-1 §3.2) ──
JF_ITEM_ID        = os.environ.get("JF_ITEM_ID", "local")
JF_JOB_TYPE       = os.environ.get("JF_JOB_TYPE", "evaluate")
JF_EXECUTION_MODE = os.environ.get("JF_EXECUTION_MODE", "async")
JF_PARAMS_PATH    = os.environ.get("JF_PARAMS_PATH", "/input/params.json")
JF_OUTPUT_PATH    = os.environ.get("JF_OUTPUT_PATH", "/output")
JF_DATASET_PATH   = os.environ.get("JF_DATASET_PATH", "/dataset")
JF_DATASET_NAME   = os.environ.get("JF_DATASET_NAME", "")
JF_PORT           = int(os.environ.get("JF_PORT", "8000"))

NAME = os.environ.get("LMEVAL_MANIFEST_NAME", "evaluate-lmeval")
VERSION = "0.1.2"

# 코드 실행 허용은 **매니페스트 env 로만** 켠다 — params 로는 어떻게 보내도 켤 수 없다.
ALLOW_CODE_EXEC = os.environ.get("LMEVAL_ALLOW_CODE_EXEC") == "1"

# 빌드 때 적재한 HF 캐시(데이터셋·지표 스크립트)와 수정본 태스크(drop_tango).
BAKED_HF_HOME = os.environ.get("LMEVAL_BAKED_HF_HOME", "/opt/lmeval/hf")
TASKS_DIR = os.environ.get("LMEVAL_TASKS_DIR", "/opt/lmeval/tasks")

MAX_MODEL_LEN = 4096          # ARC 25-shot·HellaSwag 10-shot 문맥이 들어간다(P0 실측)
GPU_MEMORY_UTILIZATION = 0.85
# lm-eval 이 vLLM 에 한 번에 넘기는 요청 수. "auto" 면 요청 전체가 한 덩어리가 되고(lm_eval
# vllm_causallms `get_batched(n=0)`), vLLM 은 모든 요청의 **프롬프트 전 토큰 logprob**
# (prompt_logprobs=1)을 다 모은 뒤에야 돌려준다 — 호스트 메모리가 벤치마크 크기에 비례해 쌓여
# KMMLU 전체(약 3.5만 문항 × 보기 4, 5-shot)가 파드 한도 39.9G 에서 OOMKilled 됐다(2026-09-29,
# dev). 파드 메모리는 매니페스트가 아니라 스케줄러의 GPU 인스턴스 번들(GPU 1장 ≈ 40G)이 정하므로
# (fb_scheduler external_run._apply_instance_resource_bundle) 한도를 늘리지 않고 여기서 묶는다 —
# 청크마다 결과를 파싱하고 버려 메모리가 청크 크기로 고정된다. vLLM 은 청크 안에서 계속 배치를
# 채우므로 처리량 손해는 청크 경계뿐이다. ⚠️ 정수로 주면 lm-eval 이 vLLM 의 'Processed prompts' 막대를
# 끈다(use_tqdm=batch_size=="auto") — 진행률·취소는 lm-eval 의 'Running …' 막대로 이어지되 청크 단위로
# 거칠어진다(_Progress, 취소는 청크가 끝날 때 반영).
VLLM_BATCH_SIZE = 1024
SEED = 42
# stderr 부트스트랩 반복. lm-eval 기본(100000)은 f1 류 집계(kobest)에서 분 단위로 늘어난다.
# stderr 만 영향받고 점수는 그대로다.
BOOTSTRAP_ITERS = 1000
CUSTOM_MAX_NEW_TOKENS = 256
CUSTOM_MAX_NEW_TOKENS_CAP = 2048

# 3B 모델 실측(A100 80GB, vLLM 0.19.1): KMMLU 전체 65분·MMLU 31분·HellaSwag 27분이 가장
# 무겁다. 8B 는 2~3 배. timeout 은 매니페스트가 정한다(36000).
CAPABILITIES = {
    "supported_models": [],
    "min_gpu_memory_gb": 24,
    "estimated_startup_seconds": 180,
    "estimated_duration_seconds": 3600,
    "timeout_seconds": 36000,
}

RUN_LOG_PATH = os.path.join(JF_OUTPUT_PATH, "run.log")
_RUN_LOG_LOCK = threading.Lock()

# 벤치마크별 진행·중간 결과. metrics.json 과 이름을 나누는 이유 — 플랫폼(llm_evaluation
# get_eval_result)은 metrics.json 이 생기면 곧바로 런을 completed 로 마감한다. 중간 결과를 거기
# 쓰면 채점 도중에 런이 끝난 것으로 굳는다.
PROGRESS_PATH = os.path.join(JF_OUTPUT_PATH, "progress.json")
ERROR_MAX_CHARS = 500


class _Tee:
    """stdout/stderr 를 원본과 잡 output 의 run.log 양쪽에 쓴다(evaluate-intent 와 같은 이유 —
    플랫폼 로그 뷰어는 파드 stdout 이 아니라 NFS 파일을 읽는다). tqdm 갱신(개행 없는 \\r)은
    파일에서 거른다. fileno 는 반드시 원본에 위임한다 — vLLM 이 dup2 로 stdout 을 막는다."""

    def __init__(self, stream: Any, path: str, drop_progress: bool = False) -> None:
        self._stream = stream
        self._drop_progress = drop_progress
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self._fh = open(path, "a", encoding="utf-8", buffering=1)
        except OSError:
            self._fh = None

    def write(self, data: str) -> int:
        n = self._stream.write(data)
        if self._fh and not (self._drop_progress and "\r" in data and "\n" not in data):
            with _RUN_LOG_LOCK:
                try:
                    self._fh.write(data)
                except OSError:
                    pass
        return n

    def flush(self) -> None:
        self._stream.flush()
        if self._fh:
            try:
                self._fh.flush()
            except OSError:
                pass

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        return self._stream.fileno()

    def writelines(self, lines) -> None:
        for line in lines:
            self.write(line)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(object.__getattribute__(self, "_stream"), name)


sys.stdout = _Tee(sys.stdout, RUN_LOG_PATH)
sys.stderr = _Tee(sys.stderr, RUN_LOG_PATH, drop_progress=True)

app = FastAPI(title=NAME, version=VERSION)
_jobs: Dict[str, Dict[str, Any]] = {}


class _Cancelled(BaseException):
    """취소 신호. BaseException 인 이유 — lm-eval·vLLM 내부의 `except Exception` 이 삼키지
    않고 잡 루프까지 올라와야 한다."""


def _emit(event: str, **fields: Any) -> None:
    print(json.dumps({"event": event, "timestamp": datetime.now(timezone.utc).isoformat(),
                      **fields}, ensure_ascii=False), flush=True)


def _load_params(body_params: Optional[dict]) -> dict:
    if body_params:
        return body_params
    try:
        with open(JF_PARAMS_PATH, "r", encoding="utf-8") as fh:
            loaded = json.load(fh)
        return loaded if isinstance(loaded, dict) else {}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"params.json is not valid JSON: {exc}") from exc


def _int_param(params: dict, key: str, default: Optional[int], lo: int, hi: int) -> Optional[int]:
    raw = params.get(key)
    if raw in (None, "", 0):
        return default
    try:
        val = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be an integer")
    if not lo <= val <= hi:
        raise ValueError(f"{key} must be between {lo} and {hi}")
    return val


def _plan(params: dict) -> List[REG.Benchmark]:
    """요청 벤치마크 → 실행 목록. 코드 실행 게이트를 여기서 판정한다."""
    benches = REG.resolve(params.get("benchmarks"))
    code = [b.id for b in benches if b.unsafe_code]
    other = [b.id for b in benches if not b.unsafe_code]
    if code and not ALLOW_CODE_EXEC:
        raise ValueError(f"{code} 는 모델이 생성한 코드를 실행해 채점한다 — 이 채점기({NAME})는 "
                         "코드 실행이 꺼져 있다(evaluate-lmeval-code 로 보내야 한다)")
    if ALLOW_CODE_EXEC and other:
        raise ValueError(f"코드 실행 채점기는 코드 벤치마크만 받는다 — {other} 는 "
                         "evaluate-lmeval 로 보내라")
    return benches


def _dataset_dir(params: dict) -> str:
    names = [str(x) for x in (params.get("datasets") or []) if str(x).strip()]
    name = (names[0] if names else JF_DATASET_NAME).strip()
    if not name or "/" in name or name in (".", ".."):
        raise ValueError("custom 벤치마크는 평가 데이터셋이 필요하다(datasets[0])")
    path = os.path.realpath(os.path.join(JF_DATASET_PATH, name))
    if not path.startswith(os.path.realpath(JF_DATASET_PATH) + os.sep) or not os.path.isdir(path):
        raise ValueError(f"데이터셋 {name!r} 이 마운트되지 않았다")
    return path


def _prepare_hf_cache() -> None:
    """이미지에 굽은 HF 캐시를 쓰기 가능한 /tmp 로 옮긴다 — datasets 는 캐시 디렉토리에 락
    파일을 만들어 읽기전용 루트에서는 로드가 실패한다. HF_HOME 은 Dockerfile 이 /tmp/hf 로 둔다."""
    dst = os.environ.get("HF_HOME", "/tmp/hf")
    if os.path.isdir(BAKED_HF_HOME) and not os.path.isdir(dst):
        shutil.copytree(BAKED_HF_HOME, dst, symlinks=True)


class _Progress:
    """tqdm 후킹 → 잡 진행률·취소. lm-eval·vLLM 은 진행 콜백이 없어 막대 갱신에 올라탄다.
    요청을 실제로 처리하는 막대(vLLM 'Processed prompts', lm-eval 'Running …')만 본다."""

    def __init__(self, job: dict) -> None:
        self.job = job
        self.lo, self.hi = 0.0, 1.0

    def span(self, lo: float, hi: float) -> None:
        self.lo, self.hi = lo, hi
        self.set(0.0)

    def set(self, frac: float) -> None:
        if self.job["cancel"]:
            raise _Cancelled
        self.job["progress"] = round(self.lo + (self.hi - self.lo) * max(0.0, min(1.0, frac)), 3)

    def install(self) -> None:
        from tqdm.std import tqdm as _tqdm
        orig_update = _tqdm.update
        prog = self

        def update(bar, n=1):
            r = orig_update(bar, n)
            desc = str(getattr(bar, "desc", "") or "")
            if bar.total and (desc.startswith("Processed prompts") or desc.startswith("Running")):
                prog.set((bar.n or 0) / bar.total)
            elif prog.job["cancel"]:
                raise _Cancelled
            return r

        _tqdm.update = update


class _BenchTracker:
    """벤치마크별 상태 → PROGRESS_PATH(progress.json). 한 런이 여러 벤치마크를 직렬로 채점하므로
    (플랫폼 묶음 실행이 GPU 수만큼 런을 나눠 벤치마크를 담는다) 런 상태 하나로는 "지금 무엇이
    끝났나"를 말할 수 없다. 끝난 벤치마크의 점수는 partial(metrics.json 과 같은 shape)로 함께
    싣는다 — 파드가 타임아웃·OOM 으로 죽거나 취소돼도 그때까지 낸 점수가 남는다.
    쓰기는 best-effort(원자적 교체) — 진행 기록 실패가 채점을 멈추지 않는다."""

    def __init__(self, benches: List[REG.Benchmark], path: str = PROGRESS_PATH) -> None:
        self.path = path
        self.rows = [{"benchmark": b.id, "metric": b.metric, "status": "pending"}
                     for b in benches]
        self.summaries: List[dict] = []
        self.failures: List[dict] = []
        self.build = None          # summaries, failures → metrics dict (모델 로드 뒤에 붙는다)

    def start(self, i: int) -> None:
        self.rows[i]["status"] = "running"
        self.write()

    def done(self, i: int, summary: dict) -> None:
        self.summaries.append(summary)
        self.rows[i].update(status="done", score=summary["score"],
                            elapsed_sec=summary.get("elapsed_sec"))
        self.write()

    def fail(self, i: int, error: str, elapsed_sec: float) -> None:
        self.failures.append({"benchmark": self.rows[i]["benchmark"],
                              "metric": self.rows[i]["metric"], "error": error})
        self.rows[i].update(status="failed", error=error, elapsed_sec=elapsed_sec)
        self.write()

    def write(self) -> None:
        partial = (self.build(self.summaries, self.failures)
                   if self.build and self.summaries else None)
        tmp = f"{self.path}.tmp"
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"benchmarks": self.rows, "partial": partial}, fh,
                          ensure_ascii=False, allow_nan=False)
            os.replace(tmp, self.path)
        except (OSError, ValueError) as exc:
            _emit("log", level="warn", message="progress write failed", error=str(exc))


def _score_benchmarks(benches: List[REG.Benchmark], score_one, tracker: _BenchTracker):
    """벤치마크를 차례로 채점한다 — **한 벤치마크의 실패가 런 전체를 버리지 않는다**.

    score_one(i, bench) → 요약 dict. Exception 은 그 벤치마크의 실패로 기록하고 다음으로 간다
    (8번째가 죽어도 앞의 7개 점수는 metrics.json 에 남는다). 취소(_Cancelled)는 BaseException 이라
    여기서 잡히지 않고 잡 루프까지 올라간다. 전부 실패하면 런을 실패로 올린다 — 점수가 하나도 없는
    metrics.json 은 "채점이 끝났다"는 거짓 신호다."""
    for i, bench in enumerate(benches):
        tracker.start(i)
        t1 = time.time()
        _emit("log", level="info", message="benchmark start", benchmark=bench.id,
              tasks=list(bench.tasks))
        try:
            s = score_one(i, bench)
        except Exception as exc:  # noqa: BLE001 — 벤치마크 하나의 어떤 실패도 격리한다
            err = f"{type(exc).__name__}: {exc}"[:ERROR_MAX_CHARS]
            tracker.fail(i, err, round(time.time() - t1, 1))
            _emit("log", level="error", message="benchmark failed", benchmark=bench.id, error=err)
            continue
        s["elapsed_sec"] = round(time.time() - t1, 1)
        tracker.done(i, s)
        _emit("log", level="info", message="benchmark done", benchmark=bench.id,
              score=s["score"], n=s["n"], seconds=s["elapsed_sec"], warnings=s["warnings"])
    if not tracker.summaries:
        detail = "; ".join(f"{f['benchmark']}: {f['error']}" for f in tracker.failures)
        raise RuntimeError(f"모든 벤치마크가 실패했다 — {detail}"[:ERROR_MAX_CHARS * 2])
    return tracker.summaries, tracker.failures


def _run_lmeval(lm, bench: REG.Benchmark, limit: Optional[int], task_manager) -> dict:
    from lm_eval import simple_evaluate

    raw = simple_evaluate(
        model=lm, tasks=list(bench.tasks), num_fewshot=bench.num_fewshot, limit=limit,
        task_manager=task_manager, log_samples=False, bootstrap_iters=BOOTSTRAP_ITERS,
        random_seed=SEED, numpy_random_seed=SEED, torch_random_seed=SEED,
        fewshot_random_seed=SEED, confirm_run_unsafe_code=bench.unsafe_code)
    return scoring.summarize_lmeval(bench, raw)


def _run_custom(lm, params: dict, limit: Optional[int]) -> dict:
    import custom_eval as CE
    from vllm import SamplingParams, TokensPrompt

    ddir = _dataset_dir(params)
    pairs, stats = CE.load_pairs(ddir, limit)
    if not pairs:
        raise ValueError(f"데이터셋 {os.path.basename(ddir)} 에서 입력-정답 쌍을 찾지 못했다 "
                         f"(입력 키 {CE.PROMPT_KEYS}, 정답 키 {CE.REFERENCE_KEYS})")
    max_new = _int_param(params, "max_new_tokens", CUSTOM_MAX_NEW_TOKENS, 1, CUSTOM_MAX_NEW_TOKENS_CAP)
    tokenizer = lm.tokenizer
    templated = bool(getattr(tokenizer, "chat_template", None))
    # vLLM 0.19 SamplingParams 에는 truncate_prompt_tokens 가 없다 — 직접 토큰화해 넘긴다
    # (넘치는 입력은 템플릿 전 내용을 잘라 다시 입힌다 — CE.fit_prompt).
    token_prompts, truncated = [], 0
    for p, _ in pairs:
        ids, cut = CE.fit_prompt(tokenizer, p, MAX_MODEL_LEN - max_new)
        truncated += cut
        token_prompts.append(TokensPrompt(prompt_token_ids=ids))
    sp = SamplingParams(temperature=0.0, max_tokens=max_new, seed=SEED)
    outs = lm.model.generate(token_prompts, sp, use_tqdm=True)
    preds = [CE.strip_think(o.outputs[0].text if o.outputs else "") for o in outs]
    res = CE.evaluate_pairs(preds, [r for _, r in pairs], lang=str(params.get("lang") or "auto"))

    with open(os.path.join(JF_OUTPUT_PATH, "custom_samples.jsonl"), "w", encoding="utf-8") as fh:
        for (prompt, _), row in zip(pairs, res["per_sample"]):
            fh.write(json.dumps({"input": prompt, **row}, ensure_ascii=False) + "\n")
    m = res["metrics"]
    return {
        "benchmark": "custom", "metric": "f1", "score": m["f1"], "tasks": [],
        "num_fewshot": 0, "lm_metric": "f1", "lm_filter": "none",
        "metrics": [{"metric": k, "filter": "none", "score": v, "stderr": None}
                    for k, v in m.items()],
        "subtasks": [], "n": res["count"], "warnings": [],
        "dataset": os.path.basename(ddir), "korean": res["korean"],
        "chat_template": templated, "truncated_prompts": truncated,
        "max_new_tokens": max_new, "skipped_rows": stats["skipped_rows"],
        "empty_predictions": sum(1 for p in preds if not p),
    }


def _evaluate(job: dict, params: dict) -> dict:
    benches = _plan(params)
    tracker = _BenchTracker(benches)
    tracker.write()        # 요청 목록을 먼저 남긴다 — 모델 로드 중에도 플랫폼이 무엇을 재는지 안다
    ckpt = CKPT.resolve(params.get("checkpoint_name"))
    limit = _int_param(params, "limit", None, 1, 1_000_000)
    prog = _Progress(job)

    _prepare_hf_cache()
    prog.span(0.0, 0.05)
    model_dir = CKPT.materialize(ckpt, log=lambda m: _emit("log", level="info", message=m))

    import lm_eval
    import vllm
    from lm_eval.models.vllm_causallms import VLLM
    from lm_eval.tasks import TaskManager

    prog.install()
    t0 = time.time()
    lm = VLLM(pretrained=model_dir, dtype="bfloat16", seed=SEED, batch_size=VLLM_BATCH_SIZE,
              gpu_memory_utilization=GPU_MEMORY_UTILIZATION, max_model_len=MAX_MODEL_LEN)
    _emit("log", level="info", message="model loaded", seconds=round(time.time() - t0, 1),
          checkpoint=ckpt.name, format=ckpt.format)
    task_manager = TaskManager(include_path=TASKS_DIR) if os.path.isdir(TASKS_DIR) else None

    def build(summaries: List[dict], failures: List[dict]) -> dict:
        return scoring.build_metrics(
            summaries, datasets=[str(x) for x in (params.get("datasets") or [])],
            checkpoint={"name": ckpt.name, "format": ckpt.format, "base": ckpt.base},
            engine={"engine": "vllm", "vllm_version": vllm.__version__,
                    "lm_eval_version": lm_eval.__version__, "dtype": "bfloat16",
                    "chat_template": False, "seed": SEED, "max_model_len": MAX_MODEL_LEN,
                    "bootstrap_iters": BOOTSTRAP_ITERS},
            limit=limit, meta={"name": NAME, "version": VERSION, "item_id": JF_ITEM_ID},
            failures=failures)

    def score_one(i: int, bench: REG.Benchmark) -> dict:
        prog.span(0.05 + 0.95 * i / len(benches), 0.05 + 0.95 * (i + 1) / len(benches))
        return (_run_custom(lm, params, limit) if bench.kind == "custom"
                else _run_lmeval(lm, bench, limit, task_manager))

    tracker.build = build
    summaries, failures = _score_benchmarks(benches, score_one, tracker)
    return build(summaries, failures)


# ── 표준 endpoint (SP-1 규약) ──

@app.get("/health", tags=["표준"])
async def health():
    return JSONResponse(status_code=200, content={"status": "ready"})


@app.get("/live", tags=["표준"])
async def live():
    return JSONResponse(status_code=200, content={"status": "alive"})


@app.get("/info", tags=["표준"])
async def info():
    ids = [b.id for b in REG.BENCHMARKS.values() if b.unsafe_code == ALLOW_CODE_EXEC]
    return {
        "name": NAME, "version": VERSION,
        "execution_mode": JF_EXECUTION_MODE, "job_type": JF_JOB_TYPE,
        "spec_api_version": "tango.acryl.ai/v1",
        "benchmarks": ids,
        "recommended_metric": {i: REG.BENCHMARKS[i].metric for i in ids},
        "mock": False, "engine": "vllm", "code_execution": ALLOW_CODE_EXEC,
        "deterministic": True,
        **CAPABILITIES,
    }


@app.post("/run", tags=["표준"])
async def run(body: Optional[dict] = Body(default=None)):
    body = body or {}
    raw = body["params"] if isinstance(body.get("params"), dict) else body
    try:
        params = _load_params(raw)
        _plan(params)          # 모르는 id·코드 게이트는 파드 자원을 쓰기 전에 400 으로
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
    _emit("log", level="info", message="lmeval job started", job_id=job_id, item_id=JF_ITEM_ID)
    return JSONResponse(status_code=202, content={
        "status": "running", "job_id": job_id, "message": "accepted"})


@app.get("/jobs/{job_id}", tags=["표준"])
async def job_status(job_id: str):
    j = _jobs.get(job_id)
    if j is None:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "E_JOB_NOT_FOUND", "message": f"unknown job_id {job_id}"})
    return {"job_id": job_id, "status": j["status"], "progress": j["progress"],
            "result": j["result"], "error": j["error"]}


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


async def _run_job(job_id: str, params: dict) -> None:
    j = _jobs[job_id]
    try:
        # vLLM·lm-eval 은 동기·블로킹이라 스레드로 넘긴다 — 안 넘기면 채점 내내 /health 와
        # /jobs 폴링이 막혀 플랫폼이 잡을 죽은 것으로 본다.
        metrics = await asyncio.to_thread(_evaluate, j, params)
        os.makedirs(JF_OUTPUT_PATH, exist_ok=True)
        with open(os.path.join(JF_OUTPUT_PATH, "metrics.json"), "w", encoding="utf-8") as fh:
            json.dump(metrics, fh, ensure_ascii=False, indent=2, allow_nan=False)
        j["result"] = {"metrics": metrics, "output_dir": JF_OUTPUT_PATH}
        j["progress"] = 1.0
        j["status"] = "succeeded"
        _emit("log", level="info", message="lmeval job finished", job_id=job_id,
              averages=metrics["averages"])
    except _Cancelled:
        j["status"] = "cancelled"
        _emit("log", level="warn", message="lmeval job cancelled", job_id=job_id)
    except Exception as exc:  # noqa: BLE001
        j["status"] = "failed"
        j["error"] = {"code": "E_EVALUATE_FAILED", "message": str(exc)}
        _emit("log", level="error", message="lmeval job failed", job_id=job_id, error=str(exc))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=JF_PORT)
