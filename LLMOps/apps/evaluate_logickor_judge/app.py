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

생성(generate) 단계 — 세 경로
  - `checkpoint_name` 을 주면 그 체크포인트로 42문항 × 2턴을 먼저 생성한 뒤 채점한다
    (`generate → judge → score` 한 런). 가중치는 차트가 이미 RO 마운트해 둔
    /models/checkpoints/<commit_name> 에서 읽는다 — 컨테이너가 받는 것은 경로가 아니라
    커밋 이름뿐이다.
  - `generate_base_url` 을 주면 **이미 떠 있는 배포**에 생성을 위임하고 대상 모델을
    올리지 않는다. 체크포인트 마운트가 필요 없어지고 생성 단계의 GPU 점유가 사라진다.
    ⚠️ chat template 과 생성 파라미터를 배포가 정하므로 로컬 경로 점수와 직접 비교할 수
    없다(generate.py `_generate_remote` 주석에 계약·한계 전부). 둘 다 오면 원격이 이긴다.
  - 대상 모델과 심판 모델은 **순차로** 올린다(생성 → GPU 해제 → 심판). 동시에 올리면
    카드가 2장 필요해지고 manifest 의 gpu:1 전제가 깨진다.
  - 둘 다 없으면 종전대로 데이터셋의 미채점 생성물을 채점한다(하위호환).

심판(judge) 단계 — 두 경로
  - 기본: 심판 모델 가중치를 이 잡이 vLLM 으로 직접 올린다(종전 그대로).
  - `judge_base_url` 을 주면 **이미 떠 있는 배포**(플랫폼의 OpenAI 호환 shim)에 채점을
    요청하고 vLLM 로드를 건너뛴다. 심판 가중치 로드(수 분)와 GPU 점유가 사라지지만,
    ⚠️ shim 이 temperature·max_tokens 를 무시하므로 **생성 파라미터가 배포 시점 설정을
    따른다** — 점수 재현성이 심판 배포 설정에 매인다(judge.py 상단 주석 참고).
    심판 배포가 없는 환경도 있으므로 vLLM 경로는 유지된다.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import socket
import sys
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

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
VERSION = "0.2.5"

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


def _resolve_remote_base_url(params: dict, key: str):
    """원격 엔드포인트(OpenAI 호환 base) 검증. 미지정이면 None(= 종전 로컬 vLLM 경로).
    반환은 judge.RemoteEndpoint — 표시용 원본 URL + **연결용으로 고정한 IP** + Host 헤더다.

    두 키가 같은 규칙을 쓴다 — `judge_base_url`(심판 위임)과 `generate_base_url`
    (생성 위임). 가리키는 곳은 둘 다 플랫폼 배포의 OpenAI shim
    (`http://<llm-playground>/api/playgrounds/<id>/openai/v1`)이다 — 서빙 pod 자체는
    OpenAI HTTP API 를 노출하지 않는다. 이 값을 주면 해당 단계의 모델을 GPU 에 새로
    올리지 않고 이미 떠 있는 배포에 요청한다.

    params 로 받은 URL 을 검증 없이 열면 SSRF 다. llm_evaluation 의 `_validate_local_url`
    (evaluation/service.py) 과 같은 목적·수준으로 막는다:
      - scheme 은 http/https 만
      - 경로에 '..' 금지, userinfo(자격증명) 금지
      - **모든** resolve 결과를 검사한다(라운드로빈/멀티레코드로 한 건만 통과시키는 우회
        차단). link-local(169.254.169.254 등 메타데이터)·multicast·unspecified 면 거부.
      - 검증한 IP 를 **연결에 고정**한다. 호스트명만 돌려주면 httpx 가 연결 시점에 다시
        resolve 해서, 검사한 주소와 실제로 붙는 주소가 달라지는 DNS rebinding TOCTOU
        창이 열린다. `_judge_local`(service.py) 이 (safe_ip, host_header) 로 붙는 것과
        같은 방식이다.
    loopback/private 는 허용한다 — 대상이 클러스터 내부 svc 라 막으면 기능 자체가 성립하지
    않는다(is_reserved 는 IPv6 loopback(::1)까지 잡아 127.0.0.1 과 비일관이라 쓰지 않는다).

    IP 고정은 잡 시작 시 1회다. 대상은 Service DNS 이름 → ClusterIP 이고 ClusterIP 는
    Service 수명 동안 고정이라(파드가 재스케줄돼도 바뀌지 않는다) 잡이 도는 내내 유효하다.
    """
    # judge 는 이 시점에 이미 로드돼 있다(_run_job 이 잡 시작 시 import 한다). vLLM 런타임
    # env 를 앱 기동이 아니라 잡 시작에 세팅한다는 그쪽 결정을 깨지 않으려 여기서 늦게 받는다.
    from judge import RemoteEndpoint

    raw = str(params.get(key) or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"{key} must be http or https")
    if not parsed.hostname:
        raise ValueError(f"{key} has no host")
    if parsed.username or parsed.password:
        raise ValueError(f"{key} must not carry credentials")
    if ".." in (parsed.path or ""):
        raise ValueError(f"{key} path must not contain '..'")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(parsed.hostname, port)
    except OSError as exc:
        # 여기서 실패하면 84건을 쏘아 전량 실패하는 대신 바로 멈춘다(사유가 명확하다).
        raise ValueError(f"{key} host not resolvable: {parsed.hostname}") from exc
    safe_ip = None
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            raise ValueError(f"{key} resolves to a disallowed address")
        if safe_ip is None:
            safe_ip = info[4][0]
    if safe_ip is None:
        raise ValueError(f"{key} host not resolvable: {parsed.hostname}")
    port_seg = f":{parsed.port}" if parsed.port else ""
    path = (parsed.path or "").rstrip("/")
    # query/fragment 는 base URL 에 의미가 없어 버린다(종전에도 'base?x=1' + '/models' 는
    # 깨진 URL 이 됐다). IPv6 는 대괄호로 감싼다 — 안 그러면 포트 구분자와 섞인다.
    connect_url = f"{parsed.scheme}://{_bracket(safe_ip)}{port_seg}{path}"
    host_header = f"{_bracket(parsed.hostname)}{port_seg}"
    return RemoteEndpoint(url=raw.rstrip("/"), connect_url=connect_url,
                          host_header=host_header,
                          # https 면 IP 로 붙되 TLS SNI·인증서 검증은 원래 이름으로 한다.
                          sni=parsed.hostname if parsed.scheme == "https" else None)


def _bracket(host: str) -> str:
    """IPv6 리터럴은 대괄호로 감싼다(URL 의 포트 구분자와 섞이지 않게)."""
    return f"[{host}]" if ":" in host else host


def _resolve_judge_base_url(params: dict):
    """원격 심판 엔드포인트(judge.RemoteEndpoint). 없으면 None(= 심판 가중치를 직접 올린다)."""
    return _resolve_remote_base_url(params, "judge_base_url")


def _resolve_generate_base_url(params: dict):
    """원격 생성 엔드포인트(judge.RemoteEndpoint). 없으면 None(= 체크포인트를 직접 올린다).

    이 값이 있으면 체크포인트 마운트가 아예 필요 없다 — 배포가 이미 그 가중치를 올려 뒀다.
    """
    return _resolve_remote_base_url(params, "generate_base_url")


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
        # checkpoint_name 또는 generate_base_url 을 주면 generate 부터, 없으면 judge
        # 부터 — 런타임 파라미터로 갈리므로 두 경우를 다 알린다.
        "stage": "generate+judge+score",
        # 생성·심판 둘 다 이미 떠 있는 배포에 위임할 수 있다(GPU 0 으로도 완주 가능).
        "remote_generate": True,
        "remote_judge": True,
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
        # 원격 심판이 있으면 그쪽이 이긴다 — judge_model(HF repo id)은 "심판 가중치를 이
        # GPU 에 올려라" 는 지시이고 judge_base_url 은 "이미 떠 있는 배포에 물어봐라" 라서
        # 둘은 배타적이다. 원격이 지정된 이상 어떤 모델인지는 엔드포인트가 확정하므로
        # (GET /models 의 data[0].id) judge_model 을 따르는 척하면 결과가 거짓이 된다.
        judge_base_url = _resolve_judge_base_url(params)
        if judge_base_url and str(params.get("judge_model") or "").strip():
            _emit("log", level="warn", job_id=job_id,
                  message="judge_base_url 이 지정되어 judge_model 을 무시한다 "
                          "(심판 모델은 엔드포인트가 확정한다)",
                  judge_model=str(params.get("judge_model")).strip())
        if judge_base_url:
            # 재현성 경고 — shim 은 temperature·max_tokens 를 무시하고 배포 시점 설정을
            # 따른다. 심판 배포가 temperature 0 이 아니면 같은 입력에 다른 점수가 나온다.
            _emit("log", level="warn", job_id=job_id, endpoint=judge_base_url.url,
                  message="원격 심판 사용 — 생성 파라미터(temperature/max_tokens)는 "
                          "요청이 아니라 **배포 시점 설정**을 따른다. 점수 재현이 필요하면 "
                          "심판 배포를 temperature 0 으로 띄워라")
        # HF 토큰은 params 로 받되 로그·산출물에 절대 싣지 않는다.
        hf_token = params.get("hf_token") or os.environ.get("HF_TOKEN") or None

        # 생성 위임 — 있으면 체크포인트를 올리지 않는다. 둘 다 오면 원격이 이긴다
        # (judge_base_url vs judge_model 과 같은 배타 규약): 배포가 이미 어떤 가중치를
        # 올려 뒀는지 컨테이너는 알 수 없으므로, 체크포인트를 따르는 척하면 결과가 거짓이 된다.
        generate_base_url = _resolve_generate_base_url(params)
        checkpoint = _resolve_checkpoint(params) if not generate_base_url else None
        if generate_base_url and (params.get("checkpoint_name")
                                  or params.get("use_latest_checkpoint")):
            _emit("log", level="warn", job_id=job_id, endpoint=generate_base_url.url,
                  message="generate_base_url 이 지정되어 checkpoint_name/"
                          "use_latest_checkpoint 를 무시한다 "
                          "(생성 대상은 배포가 확정한다)")
        if generate_base_url:
            _emit("log", level="warn", job_id=job_id, endpoint=generate_base_url.url,
                  message="원격 생성 사용 — chat template 과 생성 파라미터"
                          "(temperature/max_tokens)는 이 컨테이너가 아니라 **배포**가 "
                          "정한다. enable_thinking=False 를 걸 수 없으므로 thinking "
                          "모델은 배포 쪽에서 꺼야 한다(사고 블록은 걷어내지만 그 답변은 "
                          "빈 출력이 된다)")

        def progress(p: float, msg: str) -> None:
            if j["cancel"]:
                raise asyncio.CancelledError
            j["progress"] = round(p, 3)
            _emit("log", level="info", message=msg, job_id=job_id, progress=j["progress"])

        # ── 1) 생성 (checkpoint_name 을 준 경우만) ──
        # 대상 모델을 올려 42문항 × 2턴을 만들고 GPU 를 비운다. 심판 로드가 그 뒤에 온다.
        gen_stats = None
        if checkpoint or generate_base_url:
            import generate  # vLLM 로드가 무거워 이 시점에.

            gen_model_len = int(params.get("generate_model_len") or 4096)
            strategy = str(params.get("strategy") or generate.DEFAULT_STRATEGY).strip()
            gen_stats = await asyncio.to_thread(
                generate.run_generate, checkpoint or "", generated_dir, _gpu_devices(),
                gen_model_len, strategy, generate.QUESTIONS_PATH,
                _scaled(0.0, 0.5, progress), generate_base_url)
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
            _scaled(0.5, 0.95, progress), judge_base_url=judge_base_url)

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
            # 심판 호출 자체가 실패한 건수(원격 경로에서만 0 이 아닐 수 있다). unscored 의
            # 부분집합이다 — "0 점" 중 몇 건이 모델의 판단이 아니라 통신 실패였는지.
            "errors": stats.get("errors", 0),
            # vllm(가중치를 이 잡이 직접 로드) | remote(이미 떠 있는 배포에 요청).
            "mode": stats.get("judge_mode", "vllm"),
            "endpoint": stats.get("judge_endpoint"),
        }
        if stats.get("judge_mode") == "remote":
            # 결과만 보고도 추적되게 남긴다 — 같은 체크포인트·같은 문항인데 점수가
            # 달라졌을 때 첫 단서다(로그는 잡이 지워지면 같이 사라진다).
            metrics["judge"]["note"] = (
                "원격 심판 사용 · 생성 파라미터(temperature/max_tokens)는 배포 설정을 따른다 "
                "— 요청의 temperature=0 은 플랫폼 shim 에서 무시된다")
        if gen_stats:
            # 어느 체크포인트로 만든 점수인지가 이 기능의 존재 이유(체크포인트 간 비교)라
            # metrics 에 남긴다 — eval_result 스키마를 건드리지 않고 런에 새기는 방법이다.
            metrics["generate"] = {
                "strategy": gen_stats["strategy"], "rows": gen_stats["rows"],
                "model_len": gen_stats["model_len"],
                "max_output_tokens": gen_stats["max_output_tokens"],
                # 전부는 아니지만 일부가 빈 출력이면 점수가 조용히 깎이므로 노출한다.
                "empty_rows": gen_stats["empty_rows"],
                # vllm(이 잡이 가중치 로드) | remote(이미 떠 있는 배포에 위임).
                "mode": gen_stats["mode"], "endpoint": gen_stats["endpoint"],
                "model": gen_stats["model"], "errors": gen_stats["errors"],
            }
            if gen_stats["mode"] == "remote":
                # 결과만 보고도 추적되게 남긴다 — 심판 쪽 note 와 같은 취지다.
                metrics["generate"]["note"] = (
                    "원격 생성 위임 · chat template 과 생성 파라미터는 배포 설정을 따른다 "
                    "— 이 컨테이너는 대화 내용과 2턴 구조만 소유하며 "
                    "enable_thinking=False 를 걸 수 없다. 로컬 vLLM 경로 점수와 직접 "
                    "비교하지 마라")
            if checkpoint:
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
              unscored=stats["unscored"], errors=stats.get("errors", 0),
              judge_mode=stats.get("judge_mode", "vllm"),
              generate_mode=(gen_stats or {}).get("mode"),
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
