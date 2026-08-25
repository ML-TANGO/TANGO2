"""evaluate-logickor-judge — LogicKor 심판 채점 + 집계 컨테이너 (SP-1 계약, GPU).

LogicKor 파이프라인 `generate → **evaluate(심판)** → **score(집계)**` 두 단계를 한 런에
수행한다. 입력은 미채점 생성물(evaluator 를 거치지 않은 generator 산출 jsonl)이고,
출력은 심판 점수가 박힌 evaluated jsonl + 플랫폼 벤치마크 계약 metrics.json 이다.

evaluate-logickor(CPU, 집계 전용)와의 관계
  - 그쪽은 "이미 채점된 산출물"을 집계만 한다(GPU 0). GPU 없이 계약·화면·이력을 먼저
    세우기 위한 경로였다.
  - 이쪽은 채점 자체를 수행한다. 집계 로직(scoring.py)은 **같은 파일을 공유**하므로
    두 경로의 점수 정의가 갈라지지 않는다.
  - 플랫폼은 LOGICKOR_MANIFEST_NAME env 로 어느 쪽을 쓸지 고른다(코드 변경 없음).

생성(generate) 단계
  - `checkpoint_name` 을 주면 그 체크포인트로 42문항 × 2턴을 먼저 생성한 뒤 채점한다
    (`generate → judge → score` 한 런). 가중치는 차트가 이미 RO 마운트해 둔
    /models/checkpoints/<commit_name> 에서 읽는다 — 컨테이너가 받는 것은 경로가 아니라
    커밋 이름뿐이다.
  - 대상 모델과 심판 모델은 **순차로** 올린다(생성 → GPU 해제 → 심판). 동시에 올리면
    카드가 2장 필요해지고 manifest 의 gpu:1 전제가 깨진다.
  - `checkpoint_name` 이 없으면 종전대로 데이터셋의 미채점 생성물을 채점한다(하위호환).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse

import scoring

# ── 플랫폼 주입 env (SP-1 §3.2) ──
JF_ITEM_ID        = os.environ.get("JF_ITEM_ID", "local")
JF_JOB_TYPE       = os.environ.get("JF_JOB_TYPE", "evaluate")
JF_EXECUTION_MODE = os.environ.get("JF_EXECUTION_MODE", "async")
JF_PARAMS_PATH    = os.environ.get("JF_PARAMS_PATH", "/input/params.json")
JF_DATASET_ROOT   = os.environ.get("JF_DATASET_ROOT", "/dataset")
JF_DATASET_NAME   = os.environ.get("JF_DATASET_NAME", "").strip()
JF_OUTPUT_PATH    = os.environ.get("JF_OUTPUT_PATH", "/output")
JF_TOTAL_GPU      = os.environ.get("JF_TOTAL_GPU", "1")
JF_PORT           = int(os.environ.get("JF_PORT", "8000"))

NAME = "evaluate-logickor-judge"
VERSION = "0.2.3"

# 모델 로드가 (생성 1회 + 심판 1회) 수 분씩, 생성·채점이 각각 42문항×2턴이라 mock/집계기와
# 시간 규모가 다르다. 생성 단계가 붙어 0.1.x 대비 소요가 대략 2배다.
CAPABILITIES = {
    "supported_models": [],
    "min_gpu_memory_gb": 24,
    "estimated_startup_seconds": 240,
    "estimated_duration_seconds": 3600,
    "timeout_seconds": 14400,
}

# 차트가 마운트해 두는 가중치 위치(apps/fb_scheduler/.../external_container/templates/pod.yaml).
#   /models/checkpoints ← models/<base_model>/commit_models  (RO)
#   /model              ← models/<base_model>/latest_checkpoint
# 컨테이너는 이 두 루트 밖을 절대 읽지 않는다 — 임의 경로를 params 로 받아 열면
# 마운트 밖 파일이 프롬프트·산출물로 흘러나간다.
CHECKPOINT_ROOT = "/models/checkpoints"
LATEST_CHECKPOINT_PATH = "/model"

# 실행 로그 — 플랫폼 로그 뷰어(llm_model external/jobs/{job_id}/system-log)는 파드
# stdout 이 아니라 NFS 파일을 읽는다. 잡이 끝나면 파드가 사라져 로그를 다시 볼 수 없기
# 때문이다. evaluate-intent 0.2.1 과 같은 규약으로 잡 output 에 남긴다.
RUN_LOG_PATH = os.path.join(JF_OUTPUT_PATH, "run.log")


# stdout/stderr 두 _Tee 가 같은 파일에 각자 핸들로 쓴다. 학습·평가는 asyncio.to_thread
# 로 별 스레드에서 돌고 이벤트루프도 같은 스트림을 쓰므로, 락이 없으면 한 메시지가 다른
# 메시지 중간에 끼어들 수 있다. 진단이 목적인 파일이라 순서·완전성이 중요하다.
_RUN_LOG_LOCK = threading.Lock()


class _Tee:
    """스트림을 원본과 로그 파일 양쪽에 쓴다.

    tqdm/vLLM 진행바는 걸러낸다 — 캐리지리턴만 있고 개행이 없는 쓰기는 같은 줄을 수백 번
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
            self._fh = None            # 로그를 못 써도 채점 자체는 계속 돌아야 한다.

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


def _resolve_input_root(params: dict) -> str:
    """생성물이 담긴 루트. 마운트된 데이터셋 안으로 한정(evaluate-logickor 동일 규약)."""
    root = JF_DATASET_ROOT
    if JF_DATASET_NAME:
        scoped = os.path.join(JF_DATASET_ROOT, JF_DATASET_NAME)
        if os.path.isdir(scoped):
            root = scoped
    subdir = str(params.get("generated_subdir") or "").strip().strip("/")
    if subdir:
        if ".." in subdir or os.path.isabs(subdir):
            raise ValueError("generated_subdir must be a relative path without '..'")
        candidate = os.path.join(root, subdir)
        if os.path.commonpath([os.path.realpath(candidate), os.path.realpath(root)]) \
                != os.path.realpath(root):
            raise ValueError("generated_subdir escapes the dataset root")
        root = candidate
    return root


def _resolve_checkpoint(params: dict) -> Optional[str]:
    """params → 생성에 쓸 체크포인트 디렉토리. 미지정이면 None(= 채점 전용 모드).

    받는 것은 **커밋 이름 한 조각**뿐이다(경로가 아니다). BE 가 commit_id 를 이름으로
    풀어 넘기고, 컨테이너가 차트 마운트 루트에 붙인다 — 그래야 params 로 임의 경로를
    열 수 없다. use_latest_checkpoint 는 /model(latest_checkpoint) 을 쓰는 폴백이다.
    """
    name = str(params.get("checkpoint_name") or "").strip()
    if name:
        # 단일 세그먼트 강제 — '/' 나 '..' 이 들어오면 루트 밖을 가리킬 수 있다.
        if "/" in name or "\\" in name or name in (".", ".."):
            raise ValueError("checkpoint_name must be a single path segment")
        path = os.path.join(CHECKPOINT_ROOT, name)
    elif params.get("use_latest_checkpoint"):
        path = LATEST_CHECKPOINT_PATH
    else:
        return None

    # 심볼릭 링크로 마운트 밖을 가리키는 경우 차단(입력 수집 규칙과 같은 수준의 방어).
    real = os.path.realpath(path)
    if not any(real == os.path.realpath(root)
               or real.startswith(os.path.realpath(root) + os.sep)
               for root in (CHECKPOINT_ROOT, LATEST_CHECKPOINT_PATH)):
        raise ValueError("checkpoint path escapes the mounted checkpoint roots")
    if not os.path.isdir(real):
        raise ValueError(f"checkpoint not found: {path} "
                         "(모델의 commit_models 에 그 이름의 커밋이 있는지 확인)")
    # merged HF 체크포인트여야 vLLM 이 로드한다. adapter-only 디렉토리를 넘기면 로드가
    # 한참 뒤에 죽으므로 여기서 먼저 거른다.
    if not os.path.isfile(os.path.join(real, "config.json")):
        raise ValueError(f"{path}: config.json 이 없다 — merged HF 체크포인트가 필요하다")
    return real


def _scaled(lo: float, hi: float, cb):
    """단계별 progress 를 전체 구간으로 환산한다(생성 0~0.5, 채점 0.5~0.95)."""
    def inner(p: float, msg: str) -> None:
        cb(lo + (hi - lo) * max(0.0, min(1.0, p)), msg)
    return inner


def _gpu_devices() -> str:
    """컨테이너에 보이는 GPU 인덱스. 플랫폼이 device 를 격리해 넣어주므로 0..n-1 이다."""
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
        # checkpoint_name 을 주면 generate 부터, 없으면 judge 부터 — 런타임 파라미터로
        # 갈리므로 두 경우를 다 알린다.
        "stage": "generate+judge+score",
        "strategies": ["default"],
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
    _emit("log", level="info", message="logickor judge job started", job_id=job_id,
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


# ── 채점 + 집계 잡 ──

async def _run_job(job_id: str, params: dict) -> None:
    j = _jobs[job_id]
    try:
        import judge  # vLLM 임포트가 무거워 잡 시작 시점에 로드한다.

        metric = _resolve_metric(params)
        evaluated_dir = os.path.join(JF_OUTPUT_PATH, "evaluated")
        generated_dir = os.path.join(JF_OUTPUT_PATH, "generated")

        judge_model = str(params.get("judge_model") or judge.DEFAULT_JUDGE_MODEL).strip()
        model_len = int(params.get("judge_model_len") or 8192)
        max_out = int(params.get("judge_max_output_tokens") or 1024)
        # HF 토큰은 params 로 받되 로그·산출물에 절대 싣지 않는다.
        hf_token = params.get("hf_token") or os.environ.get("HF_TOKEN") or None

        checkpoint = _resolve_checkpoint(params)

        def progress(p: float, msg: str) -> None:
            if j["cancel"]:
                raise asyncio.CancelledError
            j["progress"] = round(p, 3)
            _emit("log", level="info", message=msg, job_id=job_id, progress=j["progress"])

        # ── 1) 생성 (checkpoint_name 을 준 경우만) ──
        # 대상 모델을 올려 42문항 × 2턴을 만들고 GPU 를 비운다. 심판 로드가 그 뒤에 온다.
        gen_stats = None
        if checkpoint:
            import generate  # vLLM 로드가 무거워 이 시점에.

            gen_model_len = int(params.get("generate_model_len") or 4096)
            strategy = str(params.get("strategy") or generate.DEFAULT_STRATEGY).strip()
            gen_stats = await asyncio.to_thread(
                generate.run_generate, checkpoint, generated_dir, _gpu_devices(),
                gen_model_len, strategy, generate.QUESTIONS_PATH,
                _scaled(0.0, 0.5, progress))
            in_root = generated_dir
            if j["cancel"]:
                raise asyncio.CancelledError
        else:
            # 하위호환 — 데이터셋에 담긴 미채점 생성물을 채점한다.
            in_root = _resolve_input_root(params)

        # ── 2) 심판 채점 ──
        # vLLM 은 동기·블로킹이라 이벤트 루프를 막지 않도록 스레드로 넘긴다
        # (안 넘기면 /jobs 폴링과 /health 가 채점 내내 응답하지 않아 플랫폼이 죽은 줄 안다).
        stats = await asyncio.to_thread(
            judge.run_judge, in_root, evaluated_dir, judge_model,
            _gpu_devices(), model_len, max_out, hf_token,
            _scaled(0.5, 0.95, progress))

        if j["cancel"]:
            raise asyncio.CancelledError

        agg = scoring.aggregate(scoring.iter_records(
            [os.path.join(dp, f) for dp, _, fs in os.walk(evaluated_dir)
             for f in fs if f.endswith(".jsonl")]))
        if agg is None:
            raise ValueError("채점 후에도 집계할 행이 없다 — 심판 출력 파싱을 확인하라")

        metrics = scoring.build_metrics(agg, metric, params.get("datasets") or [])
        metrics["source_files"] = stats["outputs"]
        metrics["judge"] = {
            "model": stats["judge_model"], "files": stats["files"],
            "judged": stats["judged"],
            # 점수 파싱 실패(0점 처리) 개수 — 조용히 평균을 끌어내리므로 반드시 노출한다.
            "unscored": stats["unscored"],
            # 형식 불량으로 아예 제외된 행 수 — 조용한 누락을 결과에 남긴다.
            "skipped": stats["skipped"],
        }
        if gen_stats:
            # 어느 체크포인트로 만든 점수인지가 이 기능의 존재 이유(체크포인트 간 비교)라
            # metrics 에 남긴다 — eval_result 스키마를 건드리지 않고 런에 새기는 방법이다.
            metrics["generate"] = {
                "strategy": gen_stats["strategy"], "rows": gen_stats["rows"],
                "model_len": gen_stats["model_len"],
                "max_output_tokens": gen_stats["max_output_tokens"],
                # 전부는 아니지만 일부가 빈 출력이면 점수가 조용히 깎이므로 노출한다.
                "empty_rows": gen_stats["empty_rows"],
            }
            metrics["checkpoint"] = {"name": os.path.basename(checkpoint),
                                     "path": checkpoint}
        metrics["_meta"] = {"name": NAME, "version": VERSION, "item_id": JF_ITEM_ID}

        os.makedirs(JF_OUTPUT_PATH, exist_ok=True)
        with open(os.path.join(JF_OUTPUT_PATH, "metrics.json"), "w", encoding="utf-8") as fh:
            json.dump(metrics, fh, ensure_ascii=False, indent=2, allow_nan=False)

        j["result"] = {"metrics": metrics, "output_dir": JF_OUTPUT_PATH}
        j["progress"] = 1.0
        j["status"] = "succeeded"
        _emit("log", level="info",
              message="logickor generate+judge+score finished" if gen_stats
                      else "logickor judge+score finished",
              job_id=job_id, overall=agg["overall"], count=agg["count"],
              unscored=stats["unscored"],
              checkpoint=os.path.basename(checkpoint) if checkpoint else None)
    except asyncio.CancelledError:
        j["status"] = "cancelled"
        _emit("log", level="warn", message="logickor judge cancelled", job_id=job_id)
    except Exception as exc:  # noqa: BLE001
        j["status"] = "failed"
        j["error"] = {"code": "E_JUDGE_FAILED", "message": str(exc)}
        _emit("log", level="error", message="logickor judge failed",
              job_id=job_id, error=str(exc))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=JF_PORT)
