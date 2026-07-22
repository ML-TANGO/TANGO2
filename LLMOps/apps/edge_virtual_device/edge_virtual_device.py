"""Edge 가상 디바이스 하네스 — mock remoteManager(/ops,/metrics) + heartbeat sender.

실장비 없이 엣지 배포 e2e 검증용 (테스트 전용, 외부 비노출).
스펙: docs/superpowers/specs/2026-07-21-edge-virtual-device-e2e-design.md
계약(§4): /ops POST {op,image,model,version,gguf_path,params} -> 200 {"status":"running"},
          /metrics GET -> {containers,container_count,node_cpu_total,memory_total,gpu},
          heartbeat: 플랫폼 /api/edge/devices/{id}/heartbeat 로 Bearer 토큰 POST(>=30s 간격).
"""
import json
import threading
import time
import urllib.request

from fastapi import FastAPI, Request

app = FastAPI()

_lock = threading.Lock()
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


@app.post("/ops")
async def ops(req: Request):
    body = await req.json()
    if body.get("op") == "deploy":
        with _lock:
            _state["deploy"] = {
                "image": body.get("image"),
                "model": body.get("model"),
                "version": body.get("version"),
                "gguf_path": body.get("gguf_path"),
                "params": body.get("params") or {},
            }
    return {"status": "running"}


@app.get("/metrics")
def metrics():
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
    return {
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
