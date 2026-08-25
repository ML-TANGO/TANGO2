"""evaluate-intent — MixATIS 다중의도·슬롯 평가 컨테이너 (SP-1 계약, GPU).

ETRI `Evaluation/Intent_web` 의 평가 단계를 플랫폼 외부컨테이너로 옮긴 것이다.
원본은 웹 콘솔이 `docker run` 으로 컨테이너를 띄우고 stdout 을 정규식으로 되읽는
구조였다 — 클러스터는 containerd 라 도커 소켓이 없고, 지표도 파일로 받아야 하므로
그 두 겹(콘솔 + docker run)을 걷어내고 이미지를 K8s Job 으로 직접 돌린다.

0.2.0 부터 원본의 [1/2] 학습 단계도 함께 옮겼다. UGEN 은 정답을 고정 형식
(`"값 is one 슬롯명"`)으로 생성해야 채점되는 벤치마크라, 형식을 배우지 않은 모델은
내용을 알아도 0 점이 나온다 — Qwen3-8B 로 실측했을 때 828 발화 중 형식 준수 0 건,
joint_acc 0.0 이었다(같은 가중치에 1500 발화 1 에폭을 태우자 0.4855). ETRI README 의
95.89%/98.10% 도 학습 후 수치이고, 원본 웹데모 역시 학습→평가 두 단계를 함께 돈다.

그래서 이 컨테이너는 **커밋 체크포인트를 받아 (선택적으로) 그 위에 LoRA 를 학습한 뒤
평가**한다. 점수의 의미는 "체크포인트 단독"이 아니라 "체크포인트 + 이 레시피"가 되며,
어떤 레시피였는지는 metrics.json 의 `train` 절에 새긴다. `train: false` 로 부르면
0.1.0 과 완전히 같은 zero-shot 경로다(형식 미학습을 진단할 때 쓴다).

LogicKor 채점기와의 차이 — 이쪽은 심판 LLM 이 없다. 정답(BIO 태그 + 의도 라벨)이
데이터에 있어 지표가 결정론적이고, 같은 체크포인트면 몇 번을 돌려도 같은 값이 나온다.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse

import scoring

# ── 플랫폼 주입 env (SP-1 §3.2) ──
JF_ITEM_ID        = os.environ.get("JF_ITEM_ID", "local")
JF_JOB_TYPE       = os.environ.get("JF_JOB_TYPE", "evaluate")
JF_EXECUTION_MODE = os.environ.get("JF_EXECUTION_MODE", "async")
JF_PARAMS_PATH    = os.environ.get("JF_PARAMS_PATH", "/input/params.json")
JF_OUTPUT_PATH    = os.environ.get("JF_OUTPUT_PATH", "/output")
JF_TOTAL_GPU      = os.environ.get("JF_TOTAL_GPU", "1")
JF_PORT           = int(os.environ.get("JF_PORT", "8000"))

NAME = "evaluate-intent"
VERSION = "0.2.3"

# 평가: 828 발화 × 2 생성(의도·슬롯) = 1656 회. transformers generate(greedy) 라 vLLM
# 대비 느리다 — 배치 16 기준 A100 한 장에서 20~40 분.
# 학습(기본 on): 3000 예제 1 에폭 = 188 스텝, A100 한 장 실측 630 초.
# 둘을 합쳐 잡는다. train_examples/train_epochs 를 키우면 선형으로 늘어난다.
CAPABILITIES = {
    "supported_models": [],
    "min_gpu_memory_gb": 24,
    "estimated_startup_seconds": 120,
    "estimated_duration_seconds": 3600,
    "timeout_seconds": 21600,
}

# 차트가 마운트해 두는 가중치 위치(fb_scheduler/.../external_container/templates/pod.yaml).
# 컨테이너가 받는 것은 **커밋 이름 한 조각**이지 경로가 아니다 — 경로를 받으면 params 로
# 마운트 밖을 열 수 있고 NFS 실경로가 로그·응답으로 샌다.
CHECKPOINT_ROOT = "/models/checkpoints"
LATEST_CHECKPOINT_PATH = "/model"
# 학습 산출 LoRA 를 쓰는 자리. 루트가 읽기전용이라 차트가 emptyDir 로 주는 /tmp 만
# 쓸 수 있다. 기본은 잡과 함께 사라진다 — 남기려면 keep_adapter=true (NFS 로 174MB).
ADAPTER_SCRATCH = os.environ.get("MIXATIS_ADAPTER_DIR", "/tmp/mixatis-adapter")

# 실행 로그 — 플랫폼 로그 뷰어는 파드 stdout 이 아니라 NFS 파일을 읽는다
# (llm_model external/jobs/{job_id}/system-log). 그래서 stdout·stderr 를 잡 output 에
# 그대로 흘려 둔다. 잡이 끝난 뒤에도 남아야 하므로 파드 로그에 의존하지 않는다.
RUN_LOG_PATH = os.path.join(JF_OUTPUT_PATH, "run.log")


# stdout/stderr 두 _Tee 가 같은 파일에 각자 핸들로 쓴다. 학습·평가는 asyncio.to_thread
# 로 별 스레드에서 돌고 이벤트루프도 같은 스트림을 쓰므로, 락이 없으면 한 메시지가 다른
# 메시지 중간에 끼어들 수 있다. 진단이 목적인 파일이라 순서·완전성이 중요하다.
_RUN_LOG_LOCK = threading.Lock()


class _Tee:
    """스트림을 원본과 로그 파일 양쪽에 쓴다.

    tqdm 진행바는 걸러낸다 — 캐리지리턴만 있고 개행이 없는 쓰기는 같은 줄을 수백 번
    갱신하는 것이라, 파일에 그대로 쌓으면 실제 로그가 파묻힌다. 트레이스백(개행 포함)은
    그대로 통과시켜야 실패 진단이 된다.
    """

    def __init__(self, stream: Any, path: str, drop_progress: bool = False) -> None:
        self._stream = stream
        self._drop_progress = drop_progress
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self._fh = open(path, "a", encoding="utf-8", buffering=1)
        except OSError:
            self._fh = None            # 로그를 못 써도 잡 자체는 계속 돌아야 한다.

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
        """원본 스트림의 fd. **없으면 안 된다.**

        vLLM 의 `suppress_stdout()`(utils/system_utils.py)이 C 라이브러리 출력을 죽이려고
        `sys.stdout.fileno()` → `os.dup2(devnull, fd)` 를 한다. 이 메서드가 없으면
        AttributeError 로 EngineCore 프로세스가 통째로 죽는다(0.2.1 에서 실측).
        dup2 로 fd 가 devnull 로 바뀌어도 로그 파일 핸들은 별개라 기록은 계속된다 —
        오히려 콘솔에서 지운 소음이 파일에도 안 남아 의도와 맞는다.
        """
        return self._stream.fileno()

    def writelines(self, lines) -> None:
        for line in lines:
            self.write(line)

    def __getattr__(self, name: str) -> Any:
        """나머지 스트림 속성(encoding·buffer·writable…)은 원본에 위임한다.

        표준 스트림을 갈아끼우는 이상, 라이브러리가 무엇을 기대하는지 다 열거할 수 없다.
        fileno 를 빠뜨려 vLLM 을 죽인 것이 그 증거라 개별 대응 대신 위임으로 막는다.
        `_` 로 시작하는 이름은 위임하지 않는다 — `_stream` 이 아직 없는 시점에 무한재귀가 된다.
        """
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(object.__getattribute__(self, "_stream"), name)


sys.stdout = _Tee(sys.stdout, RUN_LOG_PATH)
sys.stderr = _Tee(sys.stderr, RUN_LOG_PATH, drop_progress=True)

app = FastAPI(title=NAME, version=VERSION)
_jobs: Dict[str, Dict[str, Any]] = {}


def _emit(event: str, **fields: Any) -> None:
    print(json.dumps({"event": event,
                      "timestamp": datetime.now(timezone.utc).isoformat(),
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


def _resolve_metric(params: dict) -> str:
    for item in (params.get("benchmarks") or []):
        if isinstance(item, dict) and item.get("benchmark") == scoring.BENCHMARK_ID:
            m = str(item.get("metric") or "").strip()
            if m in scoring.SUPPORTED_METRICS:
                return m
    m = str(params.get("metric") or "").strip()
    return m if m in scoring.SUPPORTED_METRICS else scoring.DEFAULT_METRIC


def _resolve_checkpoint(params: dict) -> str:
    """params → 평가할 체크포인트 디렉토리. evaluate-logickor-judge 와 같은 규약."""
    name = str(params.get("checkpoint_name") or "").strip()
    if name:
        if "/" in name or "\\" in name or name in (".", ".."):
            raise ValueError("checkpoint_name must be a single path segment")
        path = os.path.join(CHECKPOINT_ROOT, name)
    elif params.get("use_latest_checkpoint"):
        path = LATEST_CHECKPOINT_PATH
    else:
        raise ValueError(
            "checkpoint_name 이 필요하다 — 이 벤치마크는 평가할 모델 가중치가 있어야 한다 "
            "(BE 가 commit_id 를 커밋 이름으로 풀어 넘긴다)")

    real = os.path.realpath(path)
    if not any(real == os.path.realpath(root)
               or real.startswith(os.path.realpath(root) + os.sep)
               for root in (CHECKPOINT_ROOT, LATEST_CHECKPOINT_PATH)):
        raise ValueError("checkpoint path escapes the mounted checkpoint roots")
    if not os.path.isdir(real):
        raise ValueError(f"checkpoint not found: {path} "
                         "(모델의 commit_models 에 그 이름의 커밋이 있는지 확인)")
    if not os.path.isfile(os.path.join(real, "config.json")):
        raise ValueError(f"{path}: config.json 이 없다 — merged HF 체크포인트가 필요하다")
    return real


def _scaled_progress(fn, lo: float, hi: float):
    """0..1 로 보고하는 하위 단계를 전체 진행률 구간 [lo, hi] 로 옮긴다.

    run_evaluate 는 자기 구간을 0.02~0.97 로 보고한다. 학습이 앞에 붙으면 그 값을
    그대로 쓸 수 없다 — 진행률이 중간에 뒤로 가면 UI 가 튄다.
    """
    def inner(p: float, msg: str) -> None:
        fn(lo + (hi - lo) * max(0.0, min(1.0, p)), msg)
    return inner


def _gpu_devices() -> str:
    try:
        n = max(1, int(float(JF_TOTAL_GPU)))
    except (TypeError, ValueError):
        n = 1
    return ",".join(str(i) for i in range(n))


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
        "name": NAME, "version": VERSION,
        "execution_mode": JF_EXECUTION_MODE, "job_type": JF_JOB_TYPE,
        "spec_api_version": "tango.acryl.ai/v1",
        "benchmarks": [scoring.BENCHMARK_ID],
        "metrics": list(scoring.SUPPORTED_METRICS),
        "recommended_metric": {scoring.BENCHMARK_ID: scoring.DEFAULT_METRIC},
        "mock": False,
        # 0.2.0: 학습(LoRA SFT) → 평가 두 단계를 한 잡에서 돈다. params.train=false 로
        # 앞 단계를 끄면 0.1.0 과 같은 zero-shot 평가가 된다.
        "stage": "train+evaluate",
        "trains": True,
        "train_default": True,
        # 심판 LLM 이 없다는 사실 자체가 이 채점기의 성질이라 알린다(재현성 보장).
        "deterministic": True,
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
    _emit("log", level="info", message="mixatis evaluate job started", job_id=job_id,
          item_id=JF_ITEM_ID, gpu=_gpu_devices())
    return JSONResponse(status_code=202, content={
        "status": "running", "job_id": job_id, "message": "accepted"})


@app.get("/jobs/{job_id}", tags=["표준"])
async def job_status(job_id: str):
    j = _jobs.get(job_id)
    if j is None:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "E_JOB_NOT_FOUND",
            "message": f"unknown job_id {job_id}"})
    return {"job_id": job_id, "status": j["status"], "progress": j["progress"],
            "result": j["result"], "error": j["error"]}


@app.post("/jobs/{job_id}/cancel", tags=["표준"])
async def job_cancel(job_id: str):
    j = _jobs.get(job_id)
    if j is None:
        return JSONResponse(status_code=404, content={
            "status": "error", "code": "E_JOB_NOT_FOUND",
            "message": f"unknown job_id {job_id}"})
    if j["status"] != "running":
        return {"job_id": job_id, "status": j["status"]}
    j["cancel"] = True
    return {"job_id": job_id, "status": "cancelling"}


# ── 평가 잡 ──

async def _run_job(job_id: str, params: dict) -> None:
    j = _jobs[job_id]
    try:
        import evaluate  # torch/transformers 임포트가 무거워 잡 시작 시점에.

        metric = _resolve_metric(params)
        checkpoint = _resolve_checkpoint(params)
        # limit 은 디버그용 — 분모가 달라지므로 full 값과 나란히 비교하면 안 된다.
        limit = int(params.get("limit") or 0)
        batch_size = int(params.get("batch_size") or evaluate.DEFAULT_BATCH_SIZE)
        max_new_tokens = int(params.get("max_new_tokens") or evaluate.DEFAULT_MAX_NEW_TOKENS)
        use_4bit = bool(params.get("use_4bit"))
        split = str(params.get("split") or "test").strip() or "test"

        def progress(p: float, msg: str) -> None:
            if j["cancel"]:
                raise asyncio.CancelledError
            j["progress"] = round(p, 3)
            _emit("log", level="info", message=msg, job_id=job_id, progress=j["progress"])

        # ── [1/2] UGEN 포맷 학습 (기본 on) ─────────────────────────────────────
        # 끄는 경로를 남기는 이유: 0.0 이 나왔을 때 "형식을 몰라서"인지 "이식이 깨져서"인지
        # 가르는 진단 수단이 zero-shot 런이기 때문이다.
        train_enabled = params.get("train", True) is not False
        adapter_dir = ""
        train_info = {"trained": False}
        if train_enabled:
            import train as trainer  # peft/Trainer 임포트가 무거워 이 시점에.

            _emit("log", level="info", message="mixatis train phase start",
                  job_id=job_id, base=os.path.basename(checkpoint))
            train_info = await asyncio.to_thread(
                trainer.run_train, checkpoint, ADAPTER_SCRATCH, evaluate.DATA_DIR,
                _gpu_devices(), params, progress, 0.02, 0.45)
            adapter_dir = ADAPTER_SCRATCH
            if j["cancel"]:
                raise asyncio.CancelledError
            if params.get("keep_adapter"):
                kept = os.path.join(JF_OUTPUT_PATH, "adapter")
                shutil.rmtree(kept, ignore_errors=True)
                shutil.copytree(ADAPTER_SCRATCH, kept)
                train_info["kept_at"] = os.path.basename(kept)
            _emit("log", level="info", message="mixatis train phase done",
                  job_id=job_id, **{k: v for k, v in train_info.items()
                                    if k in ("examples", "epochs", "effective_batch")})

        # ── [2/2] 평가 ────────────────────────────────────────────────────────
        # transformers generate 는 동기·블로킹이라 스레드로 넘긴다 — 안 넘기면 평가 내내
        # /health 와 /jobs 폴링이 막혀 플랫폼이 잡을 죽은 것으로 본다.
        eval_progress = _scaled_progress(progress, 0.45, 1.0) if train_enabled else progress
        out = await asyncio.to_thread(
            evaluate.run_evaluate, checkpoint, JF_OUTPUT_PATH, _gpu_devices(),
            split, limit, batch_size, max_new_tokens, use_4bit,
            evaluate.DATA_DIR, eval_progress, adapter_dir)

        if j["cancel"]:
            raise asyncio.CancelledError

        agg = scoring.aggregate(out["pred_intents"], out["gold_intents"],
                                out["pred_slots"], out["gold_slots"])
        if agg is None:
            raise ValueError("집계할 발화가 없다")

        metrics = scoring.build_metrics(agg, metric, params.get("datasets") or [])
        metrics["evaluate"] = out["stats"]
        # 어떤 레시피로 낸 점수인지 — 0.2.0 부터 점수는 "체크포인트 + 이 학습"의 값이다.
        metrics["train"] = train_info
        # 어느 체크포인트로 낸 점수인지가 체크포인트 간 비교의 전제라 런에 새긴다.
        metrics["checkpoint"] = {"name": os.path.basename(checkpoint), "path": checkpoint}
        metrics["_meta"] = {"name": NAME, "version": VERSION, "item_id": JF_ITEM_ID}

        os.makedirs(JF_OUTPUT_PATH, exist_ok=True)
        with open(os.path.join(JF_OUTPUT_PATH, "metrics.json"), "w", encoding="utf-8") as fh:
            json.dump(metrics, fh, ensure_ascii=False, indent=2, allow_nan=False)

        j["result"] = {"metrics": metrics, "output_dir": JF_OUTPUT_PATH}
        j["progress"] = 1.0
        j["status"] = "succeeded"
        _emit("log", level="info", message="mixatis evaluate finished", job_id=job_id,
              joint_acc=agg["joint_acc"], intent_f1=agg["intent"]["f1"],
              slot_f1=agg["slot"]["f1"], count=agg["count"],
              checkpoint=os.path.basename(checkpoint),
              trained=bool(train_info.get("trained")))
    except asyncio.CancelledError:
        j["status"] = "cancelled"
        _emit("log", level="warn", message="mixatis evaluate cancelled", job_id=job_id)
    except Exception as exc:  # noqa: BLE001
        j["status"] = "failed"
        j["error"] = {"code": "E_EVALUATE_FAILED", "message": str(exc)}
        _emit("log", level="error", message="mixatis evaluate failed",
              job_id=job_id, error=str(exc))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=JF_PORT)
