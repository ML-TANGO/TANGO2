"""Edge remoteManager 에이전트 — 엣지 디바이스에서 native 실행.

플랫폼의 배포 지시를 실제 컨테이너 실행으로 이행한다(가상 디바이스 하네스의 실물 버전).
- POST /ops   : op=deploy → docker pull + run(교체) / op=stop → 컨테이너 제거
- GET  /metrics: 실제 컨테이너 상태 + 노드 자원(CPU/메모리/GPU)
- heartbeat   : (설정 시) 플랫폼 /api/edge/devices/{id}/heartbeat 로 Bearer 토큰 POST

계약 정본: 엣지 가상 디바이스 E2E 설계 문서(내부) §4.
동일 계약을 가상 디바이스(apps/edge_virtual_device)가 mock 하므로, 기존 e2e 드라이버로 계약 검증됨.

⚠️ 신뢰 LAN 전용: /ops·/metrics 는 무인증(플랫폼↔remoteManager 계약이 그러함). 방화벽/사설망 안에서만 노출.
   호스트의 docker 를 관리하므로 디바이스에서 host 프로세스로 실행(systemd/nohup). 컨테이너 안에서 X.
설정(env): AGENT_PORT(8600) DOCKER_BIN(docker) MODEL_DIR(/opt/edge/models) CONTAINER_NAME(edge-serve)
           GPU(auto|on|off) PLATFORM_HEARTBEAT_URL DEVICE_ID DEVICE_TOKEN HEARTBEAT_INTERVAL(35)
"""
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.request

from fastapi import FastAPI, Request

PORT = int(os.environ.get("AGENT_PORT", "8600"))
DOCKER = os.environ.get("DOCKER_BIN", "docker")
MODEL_DIR = os.environ.get("MODEL_DIR", "/opt/edge/models")
CONTAINER = os.environ.get("CONTAINER_NAME", "edge-serve")
USE_GPU = os.environ.get("GPU", "auto")  # auto | on | off
HB_URL = os.environ.get("PLATFORM_HEARTBEAT_URL")
HB_DEVICE = os.environ.get("DEVICE_ID")
HB_TOKEN = os.environ.get("DEVICE_TOKEN")
HB_INTERVAL = max(31, int(os.environ.get("HEARTBEAT_INTERVAL", "35")))  # 플랫폼 30s 스로틀 회피

app = FastAPI()
_lock = threading.Lock()
_last_deploy = {}  # {image, model, version} — /metrics 주석용


# ---------- docker helpers ----------
def _docker(args, timeout=600):
    return subprocess.run([DOCKER, *args], capture_output=True, text=True, timeout=timeout)


def _docker_available():
    return shutil.which(DOCKER) is not None or os.path.isabs(DOCKER)


def _gpu_available():
    return shutil.which("nvidia-smi") is not None


def _gpu_flags():
    if USE_GPU == "off":
        return []
    if USE_GPU == "on":
        return ["--gpus", "all"]
    return ["--gpus", "all"] if _gpu_available() else []  # auto


def _mem_total_gb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(int(line.split()[1]) / 1024 / 1024)  # kB → GB
    except Exception:
        pass
    return 0


def _gpu_info():
    if not _gpu_available():
        return "none"
    try:
        r = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, timeout=10)
        names = [ln.split(":", 1)[1].split("(")[0].strip()
                 for ln in r.stdout.strip().splitlines() if ":" in ln]
        return (", ".join(names) or "gpu")[:256]
    except Exception:
        return "gpu"


# ---------- /ops ----------
@app.post("/ops")
async def ops(req: Request):
    body = await req.json()
    op = body.get("op")
    if op == "deploy":
        return _deploy(body)
    if op == "stop":
        # 실패를 stopped 로 보고하면 안 된다. 이전 판본은 docker 부재 시 rm 을 건너뛰고,
        # rm 이 실패해도 returncode 를 보지 않은 채 항상 {"status":"stopped"} 를 돌려줬다.
        # 플랫폼은 그걸 확정 성공으로 받아 deploy_state=stopped 로 새기므로, 컨테이너가
        # 살아 있는데 화면은 "중지됨" 이라 말하는 조용한 거짓이 된다(2026-09-11 리뷰).
        # _last_deploy.clear() 도 성공한 뒤에만 한다 — 실패했는데 /metrics 주석에서
        # 배포 흔적을 지우면 플랫폼이 실상태를 되짚을 근거까지 사라진다.
        if not _docker_available():
            return {"status": "error", "detail": "docker not available on device"}
        try:
            proc = _docker(["rm", "-f", CONTAINER], timeout=60)
        except Exception as e:  # timeout·실행 실패
            return {"status": "error", "detail": f"docker rm failed: {type(e).__name__}"}
        if proc.returncode != 0:
            # 이미 없는 컨테이너는 실패가 아니다 — 목표 상태(중지)가 이미 충족됐다.
            err = (proc.stderr or "").strip()
            if "No such container" not in err:
                return {"status": "error", "detail": f"docker rm failed: {err[:300]}"}
        with _lock:
            _last_deploy.clear()
        return {"status": "stopped"}
    return {"status": "error", "detail": f"unknown op: {op}"}


def _deploy(body):
    image = body.get("image")
    if not image:
        return {"status": "error", "detail": "image required"}
    if not _docker_available():
        return {"status": "error", "detail": "docker not available on device"}

    params = body.get("params") or {}
    port = params.get("port", 8000)
    gguf = body.get("gguf_path")

    pull = _docker(["pull", image], timeout=1800)  # 오프라인/캐시면 실패해도 run 시도(IfNotPresent)
    _docker(["rm", "-f", CONTAINER], timeout=60)    # 멱등 교체

    run_args = ["run", "-d", "--name", CONTAINER, "--restart", "unless-stopped"]
    run_args += _gpu_flags()
    run_args += ["-p", f"{port}:{port}"]
    if os.path.isdir(MODEL_DIR):
        run_args += ["-v", f"{MODEL_DIR}:/models"]
    if gguf:
        run_args += ["-e", f"MODEL_PATH=/models/{gguf}"]
    for k, v in (params.get("env") or {}).items():
        run_args += ["-e", f"{k}={v}"]
    run_args += list(params.get("docker_args") or [])  # 이미지별 추가 플래그
    run_args += [image]
    run_args += list(params.get("cmd") or [])          # 이미지별 실행 인자

    res = _docker(run_args, timeout=120)
    if res.returncode != 0:
        detail = (res.stderr or pull.stderr or "docker run failed").strip()[:500]
        return {"status": "error", "detail": detail}

    with _lock:
        _last_deploy.update({"image": image, "model": body.get("model"), "version": body.get("version")})
    return {"status": "running", "container": CONTAINER}


# ---------- /metrics ----------
@app.get("/metrics")
def metrics():
    containers = []
    if _docker_available():
        ps = _docker(["ps", "-a", "--format", "{{json .}}"], timeout=15)
        if ps.returncode == 0:
            with _lock:
                d = dict(_last_deploy)
            for line in ps.stdout.strip().splitlines():
                try:
                    c = json.loads(line)
                except ValueError:
                    continue
                name = c.get("Names", "")
                if CONTAINER not in name:
                    continue
                st = str(c.get("State", "")).lower()
                status_txt = str(c.get("Status", "")).lower()
                state = "running" if (st == "running" or status_txt.startswith("up")) else "stopped"
                containers.append({
                    "name": name,
                    "image": c.get("Image"),
                    "state": state,
                    "model": d.get("model"),
                    "version": d.get("version"),
                })
    return {
        "containers": containers,
        "container_count": len(containers),
        "node_cpu_total": os.cpu_count() or 0,
        "memory_total": _mem_total_gb(),
        "gpu": _gpu_info(),
    }


@app.get("/")
def root():
    return {"role": "edge-remote-manager", "docker": _docker_available(), "gpu": _gpu_info()}


# ---------- heartbeat sender ----------
def _cpu_pct():
    try:
        return round(os.getloadavg()[0] / (os.cpu_count() or 1) * 100, 1)
    except Exception:
        return 0.0


def _heartbeat_loop():
    while True:
        payload = json.dumps({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "cpu_pct": _cpu_pct(),
            "gpu_mem_gb": float(_mem_total_gb()),
            "model_loaded": (_last_deploy or {}).get("model") or "",
        }).encode()
        request = urllib.request.Request(
            HB_URL, data=payload, method="POST",
            headers={"Authorization": f"Bearer {HB_TOKEN}", "Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(request, timeout=5).read()
        except Exception:
            pass
        time.sleep(HB_INTERVAL)


@app.on_event("startup")
def _maybe_start_heartbeat():
    if HB_URL and HB_DEVICE and HB_TOKEN:
        threading.Thread(target=_heartbeat_loop, daemon=True).start()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
