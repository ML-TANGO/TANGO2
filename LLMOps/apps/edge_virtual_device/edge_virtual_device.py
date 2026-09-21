"""Edge 가상 디바이스 하네스 — mock remoteManager(/ops,/metrics) + heartbeat sender.

실장비 없이 엣지 배포 e2e 검증용 (테스트 전용, 외부 비노출).
스펙: 엣지 가상 디바이스 E2E 설계 문서(내부)
계약 v1: /ops POST {op,image,model,version,gguf_path,model_url,params} -> 200 {"status":"running"},
          /metrics GET -> {contract_version,containers,container_count,node_cpu_total,memory_total,gpu},
          heartbeat: 플랫폼 /api/edge/devices/{id}/heartbeat 로 Bearer 토큰 POST(>=30s 간격),
          /ops·/metrics 는 OPS_TOKEN 설정 시 Bearer 검증(실 에이전트와 동일 게이트).
model_url 이 오면 실 에이전트처럼 **실제로 받아서** MODEL_DIR 에 쓴다 — 받는 시늉만 하면
다운로드 경로가 하네스에서 검증되지 않는다(계약이 깨져도 e2e 가 통과해 버린다).
"""
import hmac
import json
import os
import threading
import time
import urllib.request

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

CONTRACT_VERSION = "1.0"
OPS_TOKEN = os.environ.get("OPS_TOKEN", "")
MODEL_DIR = os.environ.get("MODEL_DIR", "/tmp/edge-virtual-models")
DOWNLOAD_TIMEOUT = 60

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


@app.get("/")
def root():
    with _lock:
        return {
            "role": "edge-virtual-device",
            "deploy": _state["deploy"],
            "device_id": _state["device_id"],
            "hb_count": _state["hb_count"],
            "hb_last_status": _state["hb_last_status"],
        }


def _authorized(req):
    if not OPS_TOKEN:
        return True
    auth = req.headers.get("authorization") or ""
    return auth.startswith("Bearer ") and hmac.compare_digest(auth[len("Bearer "):], OPS_TOKEN)


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
        _record_deploy(body, {"path": path, "size": size})
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
        _record_deploy(body, None)
    return {"status": "running", "contract_version": CONTRACT_VERSION}


@app.get("/metrics")
def metrics(req: Request):
    if not _authorized(req):
        return _unauthorized()
    with _lock:
        d = _state["deploy"]
        dev = _state["device_id"] or "edge-virtual"
    containers = []
    if d:
        containers = [{
            "name": dev,
            "image": d.get("image"),
            "state": "running",
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


# 배포된 서빙 컨테이너를 흉내내는 mock 추론 엔드포인트(가상 디바이스 — 실제 모델 아님).
#   실장비에선 remoteManager 가 띄운 llama.cpp 서버가 이 역할을 실제로 수행.
@app.post("/v1/chat/completions")
async def chat_completions(req: Request):
    body = await req.json()
    model = _deployed_model()
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
