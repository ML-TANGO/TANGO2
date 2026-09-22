"""Edge 가상 디바이스 하네스 — mock remoteManager(/ops,/metrics) + heartbeat sender.

실장비 없이 엣지 배포 e2e 검증용 (테스트 전용, 외부 비노출).
스펙: 엣지 가상 디바이스 E2E 설계 문서(내부)
계약 v1: /ops POST {op,image,model,version,gguf_path,model_url,params} -> 200 {"status":"running"},
          /metrics GET -> {contract_version,containers,container_count,node_cpu_total,memory_total,gpu},
          heartbeat: 플랫폼 /api/edge/devices/{id}/heartbeat 로 Bearer 토큰 POST(>=30s 간격),
          /ops·/metrics 는 OPS_TOKEN 설정 시 Bearer 검증(실 에이전트와 동일 게이트).
model_url 이 오면 실 에이전트처럼 **실제로 받아서** MODEL_DIR 에 쓴다 — 받는 시늉만 하면
다운로드 경로가 하네스에서 검증되지 않는다(계약이 깨져도 e2e 가 통과해 버린다).

받은 파일이 진짜 GGUF 면 거기서 멈추지 않고 **llama-server 를 실제로 띄운다**. 파일 수신까지만
보고 배포 성공이라 부르면 못 뜨는 모델도 running 으로 보고된다 — 실장비에서만 터지는 종류의
거짓이다. 실장비의 remoteManager 는 `docker run` 으로 서빙 컨테이너를 띄우고, 우리는 같은
바이너리(/app/llama-server)를 subprocess 로 띄운다(플랫폼 서빙 playground_llamacpp.py 와 동일).
GGUF 가 아니면(conformance 하네스의 더미 아티팩트) 엔진을 건너뛰고 기존 mock 응답을 유지한다 —
계약 검사는 엔진이 아니라 규약을 보는 것이므로 더미 파일로도 통과해야 한다.
"""
import hmac
import json
import os
import subprocess
import threading
import time
import urllib.request

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

CONTRACT_VERSION = "1.1"
OPS_TOKEN = os.environ.get("OPS_TOKEN", "")
# 회전 중 옛 키. 플랫폼이 새 키를 발급한 직후에도 아직 교체되지 않은 이 디바이스가
# 계속 동작하도록, 둘 중 하나와 맞으면 통과시킨다(계약 1.1 — 하위호환 추가).
OPS_TOKEN_PREV = os.environ.get("OPS_TOKEN_PREV", "")
MODEL_DIR = os.environ.get("MODEL_DIR", "/tmp/edge-virtual-models")
DOWNLOAD_TIMEOUT = 60

# ===== 서빙 엔진(llama.cpp) =====
# 플랫폼 서빙(playground_llamacpp.py)과 같은 바이너리·같은 규약. ENGINE=off 면 기존처럼
# 파일 수신까지만 하고 mock 응답을 준다(엔진 없는 환경에서 계약 검사만 돌릴 때).
LLAMA_SERVER_BIN = os.environ.get("LLAMA_SERVER_BIN", "/app/llama-server")
ENGINE = os.environ.get("ENGINE", "auto")           # auto | off
ENGINE_PORT = int(os.environ.get("ENGINE_PORT", "8081"))
ENGINE_THREADS = os.environ.get("ENGINE_THREADS", "8")
ENGINE_CTX = os.environ.get("ENGINE_CTX", "2048")
# CPU 빌드로 2.5GB q4 를 여는 데 수십 초가 걸린다. 배포는 이미 비동기(202)라 그동안
# deploy_in_progress 가 true 로 남는다 — 실장비의 `docker run` 대기와 같은 자리.
ENGINE_START_TIMEOUT = int(os.environ.get("ENGINE_START_TIMEOUT", "300"))
ENGINE_INFER_TIMEOUT = int(os.environ.get("ENGINE_INFER_TIMEOUT", "300"))
ENGINE_URL = f"http://127.0.0.1:{ENGINE_PORT}"
ENGINE_LOG = os.path.join(MODEL_DIR, "llama-server.log")

_lock = threading.Lock()
# 실 에이전트와 동일 — model_url 배포는 202 로 답하고 백그라운드로 받는다.
_progress = {"in_progress": False, "error": None, "gen": 0}
_state = {
    "deploy": None,          # 마지막 /ops deploy payload
    "device_id": None,
    "token": None,
    "heartbeat_url": None,
    "hb_thread_started": False,
    "hb_count": 0,
    "hb_last_status": None,
}
# 실제로 떠 있는 서빙 프로세스. proc 이 None 이면 엔진 없이 mock 응답으로 동작한다.
_engine = {"proc": None, "model": None, "path": None}


def _is_gguf(path):
    """GGUF 매직('GGUF') 확인. conformance 의 더미 아티팩트를 엔진에 물리지 않기 위한 게이트."""
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"GGUF"
    except OSError:
        return False


def _engine_alive():
    p = _engine["proc"]
    return p is not None and p.poll() is None


def _engine_stop():
    """실장비의 `docker rm -f` 자리. 멈췄다고 말하려면 실제로 죽여야 한다."""
    p = _engine["proc"]
    _engine["proc"] = _engine["model"] = _engine["path"] = None
    if p is None or p.poll() is not None:
        return
    p.terminate()
    try:
        p.wait(timeout=20)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait(timeout=10)


def _engine_ready():
    """실제 1토큰 추론이 되는지로 준비 완료를 판정한다.

    /health 는 HTTP 서버가 바인드되면 바로 200 {"status":"ok"} 를 준다 — 모델 슬롯이
    아직 준비되기 전이다. 그걸 준비 완료로 보면 배포 직후 첫 추론이 503 "Loading model"
    로 떨어진다(2026-09-22 실측). 뜬 것과 답하는 것은 다르므로, 답하는 쪽으로 판정한다.
    """
    try:
        with urllib.request.urlopen(f"{ENGINE_URL}/health", timeout=3) as r:
            if r.status != 200:
                return False
    except Exception:
        return False
    try:
        _engine_proxy("/v1/chat/completions",
                      {"messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
                      timeout=30)
        return True
    except Exception:
        return False


def _engine_log_tail(n=400):
    try:
        with open(ENGINE_LOG, "rb") as f:
            return f.read()[-n:].decode("utf-8", "replace").replace("\n", " | ")
    except OSError:
        return "(no log)"


def _engine_start(path, model):
    """llama-server 를 띄우고 /health 가 200 이 될 때까지 기다린다. 실패하면 예외."""
    _engine_stop()
    # 기동 실패 사유를 남긴다 — rc 만 보고하면 왜 안 떴는지 알 길이 없다.
    log = open(ENGINE_LOG, "ab", buffering=0)
    proc = subprocess.Popen(
        [LLAMA_SERVER_BIN, "-m", path, "--host", "127.0.0.1", "--port", str(ENGINE_PORT),
         "-t", ENGINE_THREADS, "-c", ENGINE_CTX],
        stdout=log, stderr=log,
    )
    _engine["proc"] = proc
    deadline = time.time() + ENGINE_START_TIMEOUT
    while time.time() < deadline:
        if proc.poll() is not None:
            _engine["proc"] = None
            raise RuntimeError(
                f"llama-server exited rc={proc.returncode}: {_engine_log_tail()}")
        if _engine_ready():
            _engine["model"], _engine["path"] = model, path
            return
        time.sleep(2)
    _engine_stop()
    raise RuntimeError(f"llama-server health timeout ({ENGINE_START_TIMEOUT}s)")


def _engine_proxy(route, payload, timeout=None):
    """엔진에 그대로 넘기고 그대로 돌려준다 — 하네스가 응답을 꾸미면 실모델 검증이 안 된다."""
    req = urllib.request.Request(
        f"{ENGINE_URL}{route}", data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout or ENGINE_INFER_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


@app.get("/")
def root():
    with _lock:
        return {
            "role": "edge-virtual-device",
            "deploy": _state["deploy"],
            "device_id": _state["device_id"],
            "hb_count": _state["hb_count"],
            "hb_last_status": _state["hb_last_status"],
            # 계약 밖 — 하네스 관찰용. 엔진이 실제로 떠 있는지 한 눈에.
            "engine": {"alive": _engine_alive(), "model": _engine["model"],
                       "path": _engine["path"], "url": ENGINE_URL},
        }


def _authorized(req):
    if not OPS_TOKEN:
        return True
    auth = req.headers.get("authorization") or ""
    if not auth.startswith("Bearer "):
        return False
    got = auth[len("Bearer "):]
    if hmac.compare_digest(got, OPS_TOKEN):
        return True
    return bool(OPS_TOKEN_PREV) and hmac.compare_digest(got, OPS_TOKEN_PREV)


def _unauthorized():
    return JSONResponse(status_code=401,
                        content={"status": "error", "detail": "unauthorized"})


def _pull_model(url, filename, token):
    """실 에이전트와 같은 자리에서 같은 일을 한다(디바이스 토큰으로 인증 다운로드)."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    dest = os.path.join(MODEL_DIR, filename)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp, open(dest, "wb") as f:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
    return dest, os.path.getsize(dest)


def _record_deploy(body, artifact):
    with _lock:
        _state["deploy"] = {
            "image": body.get("image"),
            "model": body.get("model"),
            "version": body.get("version"),
            "gguf_path": body.get("gguf_path"),
            "model_url": body.get("model_url"),
            "artifact": artifact,       # e2e 가 '파일이 실제로 도착했나' 를 본다
            "params": body.get("params") or {},
        }


def _deploy_async(body, gen):
    err = None
    try:
        with _lock:
            token = _state["token"]
        path, size = _pull_model(body["model_url"], os.path.basename(body["gguf_path"]), token)
        with _lock:
            superseded = _progress["gen"] != gen
        if superseded:
            return            # stop 이 끼어들었다 — 배포를 기록하지 않는다
        # 진짜 GGUF 면 엔진을 띄운다. 여기서 실패하면 배포 실패다 — 파일만 받아 놓고
        # running 이라 보고하는 것이 실장비에서 터지는 바로 그 거짓이다.
        if ENGINE != "off" and _is_gguf(path) and os.path.exists(LLAMA_SERVER_BIN):
            try:
                _engine_start(path, body.get("model"))
            except Exception as e:
                raise RuntimeError(f"engine start failed: {type(e).__name__}: {e}")
            with _lock:
                superseded = _progress["gen"] != gen
            if superseded:
                _engine_stop()    # 로딩 중 stop 이 왔다 — 띄운 것을 도로 내린다
                return
        _record_deploy(body, {"path": path, "size": size, "engine": _engine_alive()})
    except RuntimeError as e:
        err = str(e)
    except Exception as e:
        err = f"download failed: {type(e).__name__}: {e}"
    with _lock:
        if _progress["gen"] != gen:
            return
        _progress["error"] = err
        _progress["in_progress"] = False


@app.post("/ops")
async def ops(req: Request):
    if not _authorized(req):
        return _unauthorized()
    body = await req.json()
    # op:"stop" — 실 remote_manager_agent 는 `docker rm -f` 로 컨테이너를 제거하고
    # {"status":"stopped"} 를 준다. 하네스가 이걸 구현하지 않으면 플랫폼은 stopped 로
    # 기록하는데 /metrics 는 컨테이너 1건을 계속 보고하고, 다음 refresh 가 deploy_state
    # 를 running 으로 되돌린다 — "중지했다" 는 거짓이 조용히 복구된다(2026-09-11 실측).
    if body.get("op") == "stop":
        # 실 에이전트와 동일 — 진행 중 배포 무효화 + 직전 실패 해제.
        with _lock:
            _progress["gen"] += 1
            _progress["in_progress"] = False
            _progress["error"] = None
            _state["deploy"] = None
        _engine_stop()          # 락 밖에서 — 프로세스 종료 대기가 heartbeat 를 막지 않도록
        return {"status": "stopped", "contract_version": CONTRACT_VERSION}
    if body.get("op") == "deploy":
        with _lock:
            if _progress["in_progress"]:
                return JSONResponse(status_code=409, content={
                    "status": "error", "detail": "deploy already in progress"})
        model_url = body.get("model_url")
        if model_url:
            if not body.get("gguf_path"):
                return {"status": "error", "detail": "model_url given without gguf_path"}
            with _lock:
                _progress["gen"] += 1
                gen = _progress["gen"]
                _progress["in_progress"] = True
                _progress["error"] = None
            threading.Thread(target=_deploy_async, args=(body, gen), daemon=True).start()
            return JSONResponse(status_code=202, content={
                "status": "deploying", "contract_version": CONTRACT_VERSION})
        # model_url 없는 배포(디바이스에 파일이 이미 있다고 가정하는 구형 경로)로
        # 교체될 때 이전 엔진을 내리지 않으면, 죽지 않은 llama-server 가 메모리를 물고
        # 남는데 /metrics 는 새 배포를 running 이라 보고한다 — 실제로 도는 모델과
        # 화면이 어긋난다(2026-09-22 재현).
        _engine_stop()
        _record_deploy(body, None)
        return {"status": "running", "contract_version": CONTRACT_VERSION}
    # 계약: 모르는 op 는 error 로 답한다. running 을 돌려주면 플랫폼이 오타난 op 를
    # 성공으로 기록한다(참조 에이전트 remote_manager_agent.py:372 와 동일 응답).
    return {"status": "error", "detail": f"unknown op: {body.get('op')}"}


@app.get("/metrics")
def metrics(req: Request):
    if not _authorized(req):
        return _unauthorized()
    with _lock:
        d = _state["deploy"]
        dev = _state["device_id"] or "edge-virtual"
    containers = []
    if d:
        # 엔진을 띄운 배포라면 상태는 실제 프로세스에서 읽는다. 엔진 없이 받은 배포
        # (더미 아티팩트·model_url 없는 배포)는 기존대로 running.
        engine_backed = bool((d.get("artifact") or {}).get("engine"))
        containers = [{
            "name": dev,
            "image": d.get("image"),
            "state": "running" if (not engine_backed or _engine_alive()) else "stopped",
            "model": d.get("model"),
            "version": d.get("version"),
        }]
    with _lock:
        in_progress = _progress["in_progress"]
        last_error = _progress["error"]
    return {
        "contract_version": CONTRACT_VERSION,
        "deploy_in_progress": in_progress,
        "last_deploy_error": last_error,
        "containers": containers,
        "container_count": len(containers),
        "node_cpu_total": 8,
        "memory_total": 16,
        "gpu": "virtual-gpu x1 (mock)",
    }


def _deployed_model():
    with _lock:
        return (_state["deploy"] or {}).get("model") or "unknown"


def _engine_backed():
    """지금 기록된 배포가 엔진을 띄운 배포인가."""
    with _lock:
        return bool(((_state["deploy"] or {}).get("artifact") or {}).get("engine"))


def _engine_gone():
    """엔진을 띄웠어야 하는데 죽어 있다 — 모의 응답으로 때우면 안 되는 상태."""
    return JSONResponse(status_code=503, content={
        "status": "error",
        "detail": "serving engine is not running (deployed with a model but the engine died)",
    })


# 배포된 서빙 컨테이너를 흉내내는 mock 추론 엔드포인트(가상 디바이스 — 실제 모델 아님).
#   실장비에선 remoteManager 가 띄운 llama.cpp 서버가 이 역할을 실제로 수행.
@app.post("/v1/chat/completions")
async def chat_completions(req: Request):
    body = await req.json()
    model = _deployed_model()
    # 엔진을 띄운 배포였으면 엔진 응답만 정답이다. 엔진이 죽었는데 모의 응답으로 때우면
    # /metrics 는 stopped 라 정직한데 추론만 200 으로 거짓을 돌려주게 된다 — 이 하네스를
    # 실모델로 바꾼 이유가 바로 그 거짓을 없애는 것이었다.
    if _engine_alive():
        try:
            return _engine_proxy("/v1/chat/completions", body)   # 실모델 응답 그대로
        except Exception:
            return _engine_gone()          # 요청 중 엔진이 죽었다
    if _engine_backed():
        return _engine_gone()
    msgs = body.get("messages") or []
    prompt = next((m.get("content", "") for m in reversed(msgs) if m.get("role") == "user"), "")
    reply = f"[edge-mock:{model}] 요청 '{prompt[:80]}' 에 대한 모의 응답 (가상 디바이스, 실제 모델 아님)"
    return {
        "id": "edge-mock-cmpl",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": len(prompt.split()), "completion_tokens": 12,
                  "total_tokens": len(prompt.split()) + 12},
    }


@app.post("/completion")
async def completion(req: Request):
    body = await req.json()
    model = _deployed_model()
    if _engine_alive():
        try:
            return _engine_proxy("/completion", body)
        except Exception:
            return _engine_gone()
    if _engine_backed():
        return _engine_gone()
    prompt = body.get("prompt", "")
    return {"content": f"[edge-mock:{model}] {prompt[:80]} …(모의 응답)", "model": model, "stop": True}


def _heartbeat_loop():
    while True:
        with _lock:
            url = _state["heartbeat_url"]
            token = _state["token"]
            model = (_state["deploy"] or {}).get("model") or ""
            count = _state["hb_count"]
        if not url or not token:
            time.sleep(2)
            continue
        payload = json.dumps({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "cpu_pct": 12.5,
            "gpu_pct": 30.0,
            "gpu_mem_gb": 24.0,
            "gpu_mem_used_gb": 6.0,
            "disk_gb": 512.0,
            "disk_used_gb": 100.0,
            "model_loaded": model,
            "inference_count_total": count,
        }).encode()
        request = urllib.request.Request(
            url, data=payload, method="POST",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as resp:
                with _lock:
                    _state["hb_last_status"] = resp.status
                    _state["hb_count"] += 1
        except Exception as e:
            with _lock:
                _state["hb_last_status"] = f"err:{getattr(e, 'code', str(e))}"
        time.sleep(35)  # 30s 스로틀 회피


@app.post("/configure")
async def configure(req: Request):
    cfg = await req.json()
    with _lock:
        _state["device_id"] = cfg.get("device_id")
        _state["token"] = cfg.get("token")
        _state["heartbeat_url"] = cfg.get("heartbeat_url")
        if not _state["hb_thread_started"]:
            _state["hb_thread_started"] = True
            threading.Thread(target=_heartbeat_loop, daemon=True).start()
    return {"configured": True, "device_id": _state["device_id"]}
