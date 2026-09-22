"""Edge remoteManager 에이전트 — 엣지 디바이스에서 native 실행.

플랫폼의 배포 지시를 실제 컨테이너 실행으로 이행한다(가상 디바이스 하네스의 실물 버전).
- POST /ops   : op=deploy → docker pull + run(교체) / op=stop → 컨테이너 제거
- GET  /metrics: 실제 컨테이너 상태 + 노드 자원(CPU/메모리/GPU)
- heartbeat   : (설정 시) 플랫폼 /api/edge/devices/{id}/heartbeat 로 Bearer 토큰 POST

계약 정본: 엣지 가상 디바이스 E2E 설계 문서(내부) §4.
동일 계약을 가상 디바이스(apps/edge_virtual_device)가 mock 하므로, 기존 e2e 드라이버로 계약 검증됨.

⚠️ /ops·/metrics 는 OPS_TOKEN 이 설정되면 Bearer 검증한다(계약 v1). 설정하지 않으면 무인증으로
   동작하므로 그 경우엔 신뢰 사설망/방화벽 안에서만 노출할 것. 호스트의 docker 를 관리하므로
   디바이스에서 host 프로세스로 실행(systemd/nohup). 컨테이너 안에서 X.
설정(env): AGENT_PORT(8600) DOCKER_BIN(docker) MODEL_DIR(/opt/edge/models) CONTAINER_NAME(edge-serve)
           GPU(auto|on|off|runtime|gpus — Jetson 은 자동 판별) PLATFORM_HEARTBEAT_URL
           DEVICE_ID DEVICE_TOKEN HEARTBEAT_INTERVAL(35)
           OPS_TOKEN / OPS_TOKEN_PREV(플랫폼→디바이스 인증. 회전 중 두 키 허용)
"""
import hmac
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

PORT = int(os.environ.get("AGENT_PORT", "8600"))
DOCKER = os.environ.get("DOCKER_BIN", "docker")
MODEL_DIR = os.environ.get("MODEL_DIR", "/opt/edge/models")
CONTAINER = os.environ.get("CONTAINER_NAME", "edge-serve")
USE_GPU = os.environ.get("GPU", "auto")  # auto | on | off
HB_URL = os.environ.get("PLATFORM_HEARTBEAT_URL")
HB_DEVICE = os.environ.get("DEVICE_ID")
HB_TOKEN = os.environ.get("DEVICE_TOKEN")
# 아티팩트 pull 도 같은 디바이스 토큰을 쓴다(플랫폼이 heartbeat 와 동일 게이트로 검증).
DEVICE_TOKEN_FOR_PULL = HB_TOKEN
HB_INTERVAL = max(31, int(os.environ.get("HEARTBEAT_INTERVAL", "35")))  # 플랫폼 30s 스로틀 회피
# 플랫폼이 우리에게 자신을 증명하는 토큰(heartbeat 의 DEVICE_TOKEN 과 방향이 반대다).
# 비어 있으면 검증하지 않는다 — 토큰을 배포하기 전 설치본이 즉시 죽지 않게 하는 폴백이며,
# 그 상태는 신뢰 사설망 전용이다.
OPS_TOKEN = os.environ.get("OPS_TOKEN", "")
# 회전 중 옛 키. 플랫폼이 새 키를 발급한 직후에도 아직 교체되지 않은 이 디바이스가
# 계속 동작하도록, 둘 중 하나와 맞으면 통과시킨다(계약 1.1 — 하위호환 추가).
OPS_TOKEN_PREV = os.environ.get("OPS_TOKEN_PREV", "")
# 계약 버전. 필드 추가는 하위호환(minor), 제거·의미변경은 major 로 올린다.
CONTRACT_VERSION = "1.1"
DOWNLOAD_TIMEOUT = 60          # 청크 간 유휴 상한(전체 전송 시간 아님)
DOWNLOAD_CHUNK = 1024 * 1024

app = FastAPI()
_lock = threading.Lock()
_last_deploy = {}  # {image, model, version} — /metrics 주석용
# 비동기 배포 상태. model_url 로 수 GB 를 받는 동안 /ops 를 붙잡고 있으면 플랫폼의
# 호출(5초 예산)이 반드시 타임아웃난다 → 202 로 즉시 답하고 백그라운드로 진행한다.
# 그동안 /metrics 에는 컨테이너가 없으므로, 이 두 값이 없으면 플랫폼은 '중지됨' 으로
# 오판한다(진행 중을 실패로 새기는 거짓).
_progress = {"in_progress": False, "error": None, "gen": 0}
# 컨테이너를 바꾸는 구간(stop 의 rm, deploy 의 rm+run)은 서로 겹치면 안 된다. 이 락이
# 없으면 "gen 확인 → run" 사이에 stop 이 끼어들어, 방금 중지한 컨테이너를 배포 스레드가
# 되살린다(사용자는 껐는데 잠시 뒤 다시 켜지는 유령 재기동).
_container_lock = threading.Lock()


# ---------- docker helpers ----------
def _docker(args, timeout=600):
    return subprocess.run([DOCKER, *args], capture_output=True, text=True, timeout=timeout)


def _docker_available():
    return shutil.which(DOCKER) is not None or os.path.isabs(DOCKER)


def _is_tegra():
    """Jetson(Tegra) 인가. 데스크톱 NVIDIA 와 컨테이너 GPU 접근 방식이 다르다.

    ⚠️ `nvidia-smi` 유무로 판단하면 안 된다 — Jetson 은 그 도구를 기본 제공하지 않고
    tegrastats 를 쓴다. 그래서 `nvidia-smi` 기준으로는 Orin 이 'GPU 없음' 으로 잡히고,
    GPU=auto 가 조용히 CPU 로 컨테이너를 띄운다(오류 없이 느려지기만 한다).
    """
    if os.path.exists("/etc/nv_tegra_release"):
        return True
    try:
        with open("/proc/device-tree/model", "rb") as f:
            model = f.read().decode("utf-8", "ignore").lower()
        return "jetson" in model or "tegra" in model or "orin" in model
    except Exception:
        return False


def _docker_runtimes():
    """docker 에 등록된 런타임 집합. 판별 실패 시 빈 집합."""
    try:
        r = _docker(["info", "--format", "{{json .Runtimes}}"], timeout=15)
        if r.returncode == 0:
            return set(json.loads(r.stdout or "{}").keys())
    except Exception:
        pass
    return set()


def _gpu_available():
    # Jetson 은 GPU 가 SoC 에 내장돼 있어 별도 탐지가 필요 없다.
    return _is_tegra() or shutil.which("nvidia-smi") is not None


def _gpu_flags():
    """컨테이너 GPU 접근 인자. JetPack 버전에 따라 방식이 갈려 런타임에 판별한다.

    · `--runtime nvidia` — JetPack/L4T 의 표준. nvidia-container-runtime 이 등록돼 있을 때.
    · `--gpus all`       — 데스크톱 NVIDIA + nvidia-container-toolkit. JetPack 6 의 최신
                           toolkit 에서도 동작하지만 구버전 L4T 에서는 실패한다.
    GPU 환경변수로 강제할 수 있다: off | on(자동 선택) | runtime | gpus
    """
    if USE_GPU == "off":
        return []
    if USE_GPU == "runtime":
        return ["--runtime", "nvidia"]
    if USE_GPU == "gpus":
        return ["--gpus", "all"]
    if USE_GPU != "on" and not _gpu_available():      # auto 에서 GPU 없음
        return []
    # on / auto(+GPU 있음) — 환경에 맞는 방식을 고른다.
    if _is_tegra():
        # nvidia 런타임이 등록돼 있으면 그쪽이 가장 넓게 동작한다. 없으면 최신 toolkit
        # 이 깔린 JetPack 6 일 수 있으므로 --gpus 로 떨어진다.
        return ["--runtime", "nvidia"] if "nvidia" in _docker_runtimes() else ["--gpus", "all"]
    return ["--gpus", "all"]


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
    if _is_tegra():
        # Jetson 은 nvidia-smi 가 없으므로 디바이스 트리의 모델명을 쓴다.
        try:
            with open("/proc/device-tree/model", "rb") as f:
                name = f.read().decode("utf-8", "ignore").strip("\x00").strip()
            return (name or "NVIDIA Jetson")[:256]
        except Exception:
            return "NVIDIA Jetson"
    try:
        r = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, timeout=10)
        names = [ln.split(":", 1)[1].split("(")[0].strip()
                 for ln in r.stdout.strip().splitlines() if ":" in ln]
        return (", ".join(names) or "gpu")[:256]
    except Exception:
        return "gpu"


# ---------- 인증 ----------
def _authorized(req):
    """플랫폼이 보낸 Bearer 토큰 검증(계약 v1). OPS_TOKEN 미설정이면 검증하지 않는다."""
    if not OPS_TOKEN:
        return True
    auth = req.headers.get("authorization") or ""
    if not auth.startswith("Bearer "):
        return False
    got = auth[len("Bearer "):]
    # 두 키 모두 허용 — 키 교체 직후 플랫폼이 잠시 옛 키를 보낼 수 있는 구간을
    # 덮는다(§계약 1.1). 상수시간 비교를 유지한다.
    if hmac.compare_digest(got, OPS_TOKEN):
        return True
    return bool(OPS_TOKEN_PREV) and hmac.compare_digest(got, OPS_TOKEN_PREV)


def _unauthorized():
    return JSONResponse(status_code=401,
                        content={"status": "error", "detail": "unauthorized"})


# ---------- 모델 아티팩트 수신 ----------
def _remote_size(url, headers):
    """HEAD 로 총 크기 확인. 모르면 None(스킵/이어받기 판단을 포기하고 전량 받는다)."""
    try:
        req = urllib.request.Request(url, method="HEAD", headers=headers)
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
            cl = resp.headers.get("Content-Length")
            return int(cl) if cl is not None else None
    except Exception:
        return None


def _download_model(url, filename, gen=None):
    """플랫폼 아티팩트 URL → MODEL_DIR/<filename>. 반환: (ok, detail).

    수 GB 파일이라 (1) 이미 같은 크기로 받아 둔 게 있으면 건너뛰고, (2) 중간까지
    받았으면 Range 로 이어받는다. 인증은 heartbeat 와 **같은** DEVICE_TOKEN 이다.
    부분 파일은 .part 에 쓰고 완료 후에만 제자리로 옮긴다 — 중단된 전송이 완성본으로
    보이면 다음 배포가 깨진 모델을 그대로 마운트한다.
    """
    if not DEVICE_TOKEN_FOR_PULL:
        return False, "model_url is set but DEVICE_TOKEN is missing"
    headers = {"Authorization": f"Bearer {DEVICE_TOKEN_FOR_PULL}"}
    try:
        os.makedirs(MODEL_DIR, exist_ok=True)
    except Exception as e:
        return False, f"cannot create MODEL_DIR: {type(e).__name__}"
    dest = os.path.join(MODEL_DIR, filename)
    # ⚠️ 부분 파일 이름에 세대를 넣는다. stop 은 진행 중 스레드를 즉시 멈추지 못하고
    # 그 스레드는 다음 확인 지점까지 계속 쓰므로, 같은 아티팩트를 곧바로 재배포하면
    # 취소된 스레드와 새 스레드가 같은 .part 를 동시에 써서 파일이 깨진다.
    part = f"{dest}.{gen}.part" if gen is not None else dest + ".part"
    total = _remote_size(url, headers)

    if os.path.isfile(dest) and total is not None and os.path.getsize(dest) == total:
        return True, "already present"

    have = os.path.getsize(part) if os.path.isfile(part) else 0
    if total is not None and have > total:
        have = 0                      # 서버 파일이 바뀐 경우 — 처음부터 다시
    elif total is not None and have == total:
        # 마지막 바이트까지 받고 os.replace 직전에 죽은 경우다. 이대로 두면 다음 시도가
        # `Range: bytes=<total>-` 를 보내 416 을 받고, 운영자가 .part 를 지우기 전까지
        # 영구히 재시도 불가가 된다. 받을 것이 없으니 그냥 확정한다.
        try:
            os.replace(part, dest)
            return True, "finalized partial download"
        except Exception as e:
            return False, f"cannot finalize download: {type(e).__name__}"
    req_headers = dict(headers)
    if have:
        req_headers["Range"] = f"bytes={have}-"
    try:
        req = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
            # 206 이 아니면 서버가 Range 를 무시한 것 → 처음부터 쓴다.
            mode = "ab" if (have and resp.status == 206) else "wb"
            with open(part, mode) as f:
                while True:
                    chunk = resp.read(DOWNLOAD_CHUNK)
                    if not chunk:
                        break
                    f.write(chunk)
    except urllib.error.HTTPError as e:
        return False, f"download failed: HTTP {e.code}"
    except Exception as e:
        return False, f"download failed: {type(e).__name__}"

    if total is not None and os.path.getsize(part) != total:
        return False, "download incomplete"
    try:
        os.replace(part, dest)
    except Exception as e:
        return False, f"cannot finalize download: {type(e).__name__}"
    _sweep_stale_parts(dest, part)
    return True, "downloaded"


def _sweep_old_artifacts(current):
    """이전 배포의 아티팩트 정리 — 디바이스당 컨테이너는 1개라 옛 모델은 쓰이지 않는다.

    플랫폼이 산출물마다 고유한 `lineage-<id>-…` 이름을 보내므로 지우지 않으면 계속
    쌓인다. Jetson 계열은 저장공간이 넉넉하지 않아 2.5GB 급 몇 개면 찬다.
    ⚠️ **우리가 받은 파일(`lineage-` 접두)만** 지운다 — 운영자가 직접 넣어 둔 모델
    (model_url 없이 쓰는 기존 경로)을 삭제하면 안 된다.
    """
    import glob
    for f in glob.glob(os.path.join(MODEL_DIR, "lineage-*")):
        if os.path.basename(f) == current:
            continue
        try:
            os.remove(f)
        except Exception:
            pass


def _sweep_stale_parts(dest, keep):
    """옛 세대의 .part 잔해 정리 — 에이전트 재시작으로 세대가 되감기면 남는다."""
    import glob
    for f in glob.glob(f"{dest}.*.part"):
        if f != keep:
            try:
                os.remove(f)
            except Exception:
                pass


# ---------- /ops ----------
def _superseded(gen):
    """이 배포가 stop(또는 다음 배포)으로 무효화됐는가."""
    if gen is None:
        return False
    with _lock:
        return _progress["gen"] != gen


def _deploy_async(body, gen):
    """백그라운드 배포 — 결과를 _progress 에 남긴다(플랫폼은 /metrics 로 확인)."""
    err = None
    try:
        res = _deploy(body, gen=gen)
        err = res.get("detail") if res.get("status") == "error" else None
    except Exception as e:                       # 스레드에서 죽으면 흔적이 남지 않는다
        err = f"{type(e).__name__}: {e}"
    with _lock:
        if _progress["gen"] != gen:
            return        # 이미 stop/재배포가 상태를 넘겨받았다 — 덮어쓰지 않는다
        _progress["error"] = err
        _progress["in_progress"] = False


@app.post("/ops")
async def ops(req: Request):
    if not _authorized(req):
        return _unauthorized()
    body = await req.json()
    op = body.get("op")
    if op == "deploy":
        # 진행 중 배포가 있으면 **어느 형태의 deploy 든** 거절한다. 가드를 model_url
        # 분기 안에만 두면, 레거시(동기) deploy 가 백그라운드 스레드와 동시에 같은
        # 컨테이너 이름으로 rm/run 을 실행한다.
        with _lock:
            if _progress["in_progress"]:
                return JSONResponse(status_code=409, content={
                    "status": "error", "detail": "deploy already in progress"})
        # model_url 이 있으면 다운로드가 붙어 길어진다 → 202 로 즉시 답하고 백그라운드로.
        # 없으면 종전대로 동기 처리한다(빠른 경로, 기존 계약 유지).
        if body.get("model_url"):
            with _lock:
                _progress["gen"] += 1
                gen = _progress["gen"]
                _progress["in_progress"] = True
                _progress["error"] = None
            threading.Thread(target=_deploy_async, args=(body, gen), daemon=True).start()
            return JSONResponse(status_code=202, content={
                "status": "deploying", "contract_version": CONTRACT_VERSION})
        return _deploy(body)
    if op == "stop":
        # 진행 중 비동기 배포를 **무효화**한다. gen 을 올리면 그 스레드는 컨테이너를
        # 건드리기 직전에 자신이 밀려났음을 보고 중단한다. 직전 실패(error)도 함께
        # 지운다 — 남겨 두면 플랫폼이 확정한 stopped 를 다음 폴링이 error 로 되돌린다.
        with _lock:
            _progress["gen"] += 1
            _progress["in_progress"] = False
            _progress["error"] = None
        # 실패를 stopped 로 보고하면 안 된다. 이전 판본은 docker 부재 시 rm 을 건너뛰고,
        # rm 이 실패해도 returncode 를 보지 않은 채 항상 {"status":"stopped"} 를 돌려줬다.
        # 플랫폼은 그걸 확정 성공으로 받아 deploy_state=stopped 로 새기므로, 컨테이너가
        # 살아 있는데 화면은 "중지됨" 이라 말하는 조용한 거짓이 된다(2026-09-11 리뷰).
        # _last_deploy.clear() 도 성공한 뒤에만 한다 — 실패했는데 /metrics 주석에서
        # 배포 흔적을 지우면 플랫폼이 실상태를 되짚을 근거까지 사라진다.
        if not _docker_available():
            return {"status": "error", "detail": "docker not available on device"}
        try:
            with _container_lock:
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
        return {"status": "stopped", "contract_version": CONTRACT_VERSION}
    return {"status": "error", "detail": f"unknown op: {op}"}


def _deploy(body, gen=None):
    image = body.get("image")
    if not image:
        return {"status": "error", "detail": "image required"}
    if not _docker_available():
        return {"status": "error", "detail": "docker not available on device"}

    params = body.get("params") or {}
    port = params.get("port", 8000)
    gguf = body.get("gguf_path")

    # 계약 v1 — model_url 이 오면 모델 파일을 **지금** 받아 온다. 이전 판본은 파일이
    # MODEL_DIR 에 이미 있다고 가정했는데 그 파일을 장비로 옮기는 경로가 계약에 없어서,
    # 규약대로 구현해도 모델 없는 컨테이너가 떴다. 실패하면 배포를 진행하지 않는다.
    model_url = body.get("model_url")
    if model_url:
        if not gguf:
            return {"status": "error", "detail": "model_url given without gguf_path"}
        ok, detail = _download_model(model_url, os.path.basename(gguf), gen=gen)
        if not ok:
            return {"status": "error", "detail": detail}
    if _superseded(gen):
        return {"status": "error", "detail": "deploy superseded before pull"}

    pull = _docker(["pull", image], timeout=1800)  # 오프라인/캐시면 실패해도 run 시도(IfNotPresent)

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

    # 컨테이너 교체는 stop 과 **직렬화**한다. 락 안에서 무효화를 한 번 더 확인해야
    # "확인 → run" 사이에 stop 이 끼어드는 창이 닫힌다.
    with _container_lock:
        if _superseded(gen):
            return {"status": "error", "detail": "deploy superseded by stop"}
        _docker(["rm", "-f", CONTAINER], timeout=60)    # 멱등 교체
        res = _docker(run_args, timeout=120)
    if res.returncode != 0:
        detail = (res.stderr or pull.stderr or "docker run failed").strip()[:500]
        return {"status": "error", "detail": detail}

    if gguf:
        _sweep_old_artifacts(os.path.basename(gguf))
    with _lock:
        _last_deploy.update({"image": image, "model": body.get("model"), "version": body.get("version")})
        _progress["error"] = None
    return {"status": "running", "container": CONTAINER,
            "contract_version": CONTRACT_VERSION}


# ---------- /metrics ----------
@app.get("/metrics")
def metrics(req: Request):
    if not _authorized(req):
        return _unauthorized()
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
    with _lock:
        in_progress = _progress["in_progress"]
        last_error = _progress["error"]
    return {
        "contract_version": CONTRACT_VERSION,
        # 진행 중/직전 실패를 명시한다. 컨테이너 목록만으로는 "아직 받는 중" 과
        # "실패했다" 와 "중지됐다" 가 전부 '컨테이너 없음' 으로 같아 보인다.
        "deploy_in_progress": in_progress,
        "last_deploy_error": last_error,
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
