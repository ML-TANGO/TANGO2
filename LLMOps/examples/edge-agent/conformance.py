#!/usr/bin/env python3
"""Edge agent 적합성 검사기 (계약 v1) — 플랫폼 없이 단독 실행.

에이전트를 구현했으면 이 스크립트를 그 에이전트에 걸어 통과시키면 된다. 플랫폼·DB·
K8s 가 필요 없고 표준 라이브러리만 쓴다(Python 3.8+).

  python3 conformance.py --url http://localhost:8600 --ops-token <토큰>
  python3 conformance.py --url http://localhost:8600 --ops-token <토큰> --image hello-world

`--image` 를 주면 실제 배포까지 검사한다(모델 파일 수신 → 컨테이너 기동 → 중지).
이때 이 스크립트가 임시 HTTP 서버를 띄워 가짜 아티팩트를 제공하므로, **에이전트가
이 스크립트의 주소로 접속할 수 있어야 한다**(같은 장비에서 돌리는 것을 권장).

종료코드: 0=전 항목 통과, 1=실패 항목 있음.
"""
import argparse
import hashlib
import json
import os
import random
import re
import socket
import string
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CONTRACT_MAJOR = 1
ARTIFACT_SIZE = 3 * 1024 * 1024          # 3MB — Range 이어받기를 실제로 태우기에 충분
DEPLOY_WAIT_SEC = 300                    # 비동기 배포 대기 상한(모델 수신 + 컨테이너 기동)
# 아티팩트마다 **다른 이름**을 쓴다. 실제 플랫폼도 산출물마다 고유한 이름
# (`lineage-<id>-…`)을 보내며, 계약은 에이전트가 그 이름 그대로 저장하도록 요구한다.
# 검사기가 이름을 고정하면, '같은 이름 + 같은 크기' 를 이미 받은 것으로 간주하는 캐시
# 판정 때문에 두 번째 이후 배포가 전송 없이 끝나 검사 자체가 무력해진다(실측).
def _new_artifact_name():
    return "conformance-" + "".join(random.choices(string.ascii_lowercase, k=8)) + ".gguf"

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


# ── 가짜 아티팩트 서버 (플랫폼의 다운로드 엔드포인트를 흉내) ──────────────────
class _ArtifactHandler(BaseHTTPRequestHandler):
    payload = b""
    token = ""
    hits = []
    slow = False          # True 면 천천히 흘려 '진행 중' 상태를 관찰할 창을 만든다

    def _unauthorized(self):
        self.send_response(401)
        self.end_headers()

    def do_HEAD(self):                      # noqa: N802 (stdlib 규약)
        if not self._auth_ok():
            return self._unauthorized()
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.payload)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

    def do_GET(self):                       # noqa: N802
        if not self._auth_ok():
            return self._unauthorized()
        rng = self.headers.get("Range")
        start = 0
        m = re.match(r"^bytes=(\d+)-$", rng.strip()) if rng else None
        if m:
            start = int(m.group(1))
        body = self.payload[start:]
        self.__class__.hits.append({"range": rng, "start": start, "bytes": len(body)})
        self.send_response(206 if start else 200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Accept-Ranges", "bytes")
        if start:
            self.send_header("Content-Range",
                             f"bytes {start}-{len(self.payload) - 1}/{len(self.payload)}")
        self.end_headers()
        if not self.slow:
            self.wfile.write(body)
            return
        step = max(1, len(body) // 20)
        for i in range(0, len(body), step):
            try:
                self.wfile.write(body[i:i + step])
                self.wfile.flush()
            except Exception:
                return                     # 상대가 끊었다(= 취소) — 정상 경로
            time.sleep(0.5)

    def _auth_ok(self):
        auth = self.headers.get("Authorization") or ""
        return auth == f"Bearer {self.token}"

    def log_message(self, *_args):
        pass                                 # 조용히


def start_artifact_server(token):
    _ArtifactHandler.payload = os.urandom(ARTIFACT_SIZE)
    _ArtifactHandler.token = token
    _ArtifactHandler.hits = []
    srv = ThreadingHTTPServer(("0.0.0.0", 0), _ArtifactHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1], _new_artifact_name()


def local_ip_for(host):
    """에이전트가 우리에게 되돌아올 때 쓸 주소 — 그 호스트로 나가는 인터페이스 IP."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((host, 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ── HTTP 헬퍼 ────────────────────────────────────────────────────────────────
def call(url, method="GET", body=None, token=None, timeout=900):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except ValueError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode()[:300]
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


# ── 검사 항목 ────────────────────────────────────────────────────────────────
def check_metrics(base, token):
    print("\n[1] GET /metrics — 스키마와 계약 버전")
    st, body = call(f"{base}/metrics", token=token)
    if not check("/metrics 가 200 을 준다", st == 200, f"status={st}"):
        return
    if not check("/metrics 응답이 JSON 객체다", isinstance(body, dict), str(body)[:120]):
        return
    ver = str(body.get("contract_version") or "")
    check("contract_version 이 있고 major 가 1 이다",
          ver.split(".")[0] == str(CONTRACT_MAJOR), f"contract_version={ver!r}")
    # minor 는 하위호환 추가분 — 1.1 부터 회전 창(OPS_TOKEN_PREV)을 지원한다.
    try:
        minor = int(ver.split(".")[1])
    except (IndexError, ValueError):
        minor = -1
    check("minor 를 읽을 수 있다(회전 창 지원 여부 판단)", minor >= 0, f"contract_version={ver!r}")
    for key, typ in (("containers", list), ("container_count", int),
                     ("node_cpu_total", int)):
        check(f"{key} 필드가 {typ.__name__} 이다", isinstance(body.get(key), typ),
              f"got {type(body.get(key)).__name__}")
    check("deploy_in_progress 필드가 bool 이다",
          isinstance(body.get("deploy_in_progress"), bool),
          f"got {type(body.get('deploy_in_progress')).__name__}")
    check("last_deploy_error 필드가 있다(없으면 null)", "last_deploy_error" in body,
          "비동기 배포 실패를 알릴 수 없다")
    for c in (body.get("containers") or []):
        check("containers[] 항목에 name/image/state 가 있다",
              all(k in c for k in ("name", "image", "state")), str(c)[:120])
        break


def check_auth(base, token):
    print("\n[2] 인증 — 토큰 없이 접근하면 401")
    if not token:
        print("  [SKIP] --ops-token 미지정 (무인증 설치는 신뢰 사설망 전용)")
        return
    st, _ = call(f"{base}/metrics")
    check("토큰 없는 /metrics 는 401", st == 401, f"status={st}")
    st, _ = call(f"{base}/ops", method="POST", body={"op": "stop"})
    check("토큰 없는 /ops 는 401", st == 401, f"status={st}")
    st, _ = call(f"{base}/metrics", token=token + "x")
    check("틀린 토큰의 /metrics 는 401", st == 401, f"status={st}")


def check_rotation_window(base, token, prev):
    """회전 중에는 두 키가 모두 통과해야 한다(계약 1.1).

    이게 없으면 플랫폼이 키를 재발급하는 순간 아직 교체되지 않은 디바이스가 전부 401 이
    되어, 무중단 회전이 성립하지 않는다.
    """
    print("\n[2-1] 회전 창 — 새 키와 직전 키가 모두 통과하는가")
    if not prev:
        print("  [SKIP] --ops-token-prev 미지정")
        return
    st, _ = call(f"{base}/metrics", token=token)
    check("현재 키로 /metrics 통과", st == 200, f"status={st}")
    st, _ = call(f"{base}/metrics", token=prev)
    check("직전 키로도 /metrics 통과", st == 200, f"status={st}")
    st, _ = call(f"{base}/metrics", token=(prev or "x") + "-nope")
    check("무관한 키는 여전히 401", st == 401, f"status={st}")


def check_bad_op(base, token):
    print("\n[3] 알 수 없는 op — 오류를 오류로 보고하는가")
    st, body = call(f"{base}/ops", method="POST", body={"op": "nonexistent-op"}, token=token)
    ok_shape = isinstance(body, dict) and body.get("status") == "error" and body.get("detail")
    check("알 수 없는 op 는 {status:'error',detail:...} 로 답한다",
          ok_shape or st >= 400, f"status={st} body={str(body)[:120]}")


def check_stop_idempotent(base, token):
    print("\n[4] stop 멱등 — 이미 없는 컨테이너를 중지해도 성공")
    st, body = call(f"{base}/ops", method="POST", body={"op": "stop"}, token=token)
    got = body.get("status") if isinstance(body, dict) else None
    check("아무것도 없을 때 stop 은 'stopped'", st == 200 and got == "stopped",
          f"status={st} body={str(body)[:120]}")


def check_deploy(base, token, image, host_for_agent):
    print("\n[5] 배포 — 모델 파일 수신 → 기동 → 중지")
    srv, port, name = start_artifact_server(token=DEVICE_TOKEN)
    model_url = f"http://{host_for_agent}:{port}/{name}"
    print(f"      아티팩트 서버: {model_url} ({ARTIFACT_SIZE // 1024}KB)")
    st, body = call(f"{base}/ops", method="POST", token=token, body={
        "op": "deploy", "image": image, "model": "conformance",
        "version": "v1", "gguf_path": name, "model_url": model_url,
        "params": {"port": 18080},
    })
    got = body.get("status") if isinstance(body, dict) else None
    check("model_url 배포는 202 deploying 으로 즉시 답한다",
          st == 202 and got == "deploying", f"status={st} body={str(body)[:200]}")
    if got == "error":
        print(f"      (deploy 가 error: {body.get('detail')})")
        srv.shutdown()
        return

    # 비동기 — deploy_in_progress 가 내려갈 때까지(또는 결과가 나올 때까지) 기다린다.
    names, last_error, waited = [], None, 0
    while waited < DEPLOY_WAIT_SEC:
        time.sleep(2)
        waited += 2
        _st, m = call(f"{base}/metrics", token=token)
        if not isinstance(m, dict):
            continue
        last_error = m.get("last_deploy_error")
        names = [c.get("name") for c in (m.get("containers") or [])]
        if last_error or names:
            break
        if not m.get("deploy_in_progress"):
            break
    hits = list(_ArtifactHandler.hits)
    check("에이전트가 model_url 에서 아티팩트를 실제로 받아갔다", bool(hits),
          f"요청 {len(hits)}건")
    if hits:
        check("받아간 바이트 수가 아티팩트 크기와 같다",
              sum(h["bytes"] for h in hits) >= ARTIFACT_SIZE,
              f"{sum(h['bytes'] for h in hits)}/{ARTIFACT_SIZE}")
    check("비동기 배포가 실패를 남기지 않았다", not last_error, str(last_error)[:200])
    check("/metrics 가 기동된 컨테이너를 보고한다", bool(names),
          f"containers={names} ({waited}s 대기)")
    if not names:
        srv.shutdown()
        return
    st, body = call(f"{base}/ops", method="POST", body={"op": "stop"}, token=token)
    check("stop 이 'stopped' 로 답한다",
          isinstance(body, dict) and body.get("status") == "stopped", str(body)[:120])
    time.sleep(1)
    st, m = call(f"{base}/metrics", token=token)
    left = [c for c in (m.get("containers") or []) if c.get("state") == "running"] \
        if isinstance(m, dict) else []
    check("중지 후 /metrics 에 running 컨테이너가 없다", not left, f"남음={left}")
    srv.shutdown()


# 에이전트가 아티팩트를 받아올 때 쓰는 토큰. 실제 운용에선 플랫폼이 발급해 에이전트의
# DEVICE_TOKEN 으로 들어가는 값이고, 이 검사에선 그 값을 그대로 넘겨받는다(지정하지
# 않으면 임의값을 만들고, 에이전트에 같은 값을 넣어야 [5] 가 통과한다).
def check_stop_cancels_deploy(base, token, image, host_for_agent):
    """진행 중 배포를 stop 이 실제로 무효화하는가 — 안 하면 유령 재기동이 된다."""
    print("\n[6] 중지-취소 — 다운로드 중 stop 이 배포를 되살리지 않아야 한다")
    _ArtifactHandler.slow = True
    srv, port, name = start_artifact_server(token=DEVICE_TOKEN)
    try:
        model_url = f"http://{host_for_agent}:{port}/{name}"
        st, body = call(f"{base}/ops", method="POST", token=token, body={
            "op": "deploy", "image": image, "model": "cancel-test", "version": "v1",
            "gguf_path": name, "model_url": model_url, "params": {"port": 18081}})
        if not check("느린 배포가 202 deploying 으로 시작된다",
                     st == 202, f"status={st} body={str(body)[:160]}"):
            return
        time.sleep(1.5)
        check("새 이름의 아티팩트는 캐시로 건너뛰지 않고 실제로 전송된다",
              bool(_ArtifactHandler.hits), "전송 요청 0건 — 캐시 판정이 이름을 무시했다")
        st2, b2 = call(f"{base}/ops", method="POST", token=token, body={
            "op": "deploy", "image": image, "gguf_path": name,
            "model_url": model_url})
        check("진행 중 재배포 요청은 409", st2 == 409, f"status={st2}")
        st3, b3 = call(f"{base}/ops", method="POST", body={"op": "stop"}, token=token)
        check("진행 중에도 stop 은 stopped 로 답한다",
              isinstance(b3, dict) and b3.get("status") == "stopped", str(b3)[:160])
        # 취소된 배포가 뒤늦게 완주해 컨테이너를 되살리는지 충분히 기다려 본다.
        ghost, err_left = [], None
        for _ in range(12):
            time.sleep(2)
            _st, m = call(f"{base}/metrics", token=token)
            if not isinstance(m, dict):
                continue
            err_left = m.get("last_deploy_error")
            ghost = [c for c in (m.get("containers") or []) if c.get("state") == "running"]
            if ghost:
                break
        check("중지 후 컨테이너가 되살아나지 않는다", not ghost, f"유령={ghost}")
        check("stop 이 last_deploy_error 를 해제한다", not err_left, str(err_left)[:160])
    finally:
        _ArtifactHandler.slow = False
        srv.shutdown()


DEVICE_TOKEN = "conformance-" + "".join(random.choices(string.ascii_letters, k=16))


def main():
    ap = argparse.ArgumentParser(description="Edge agent 계약 v1 적합성 검사")
    ap.add_argument("--url", required=True, help="에이전트 주소 (예: http://localhost:8600)")
    ap.add_argument("--ops-token", default="", help="플랫폼→디바이스 인증 토큰(OPS_TOKEN)")
    ap.add_argument("--ops-token-prev", default="",
                    help="회전 중 직전 토큰(OPS_TOKEN_PREV). 주면 회전 창 검사를 수행")
    ap.add_argument("--image", default="", help="배포까지 검사할 때 쓸 컨테이너 이미지")
    ap.add_argument("--callback-host", default="",
                    help="에이전트가 이 스크립트로 되돌아올 주소(기본: 자동 판별)")
    ap.add_argument("--device-token", default="",
                    help="에이전트에 설정된 DEVICE_TOKEN(아티팩트 수신 인증). 미지정 시 임의값")
    args = ap.parse_args()

    global DEVICE_TOKEN
    if args.device_token:
        DEVICE_TOKEN = args.device_token

    base = args.url.rstrip("/")
    token = args.ops_token or None
    print(f"대상: {base}  (계약 v{CONTRACT_MAJOR}.x)")
    print(f"디바이스 토큰(아티팩트 수신용): {DEVICE_TOKEN}")
    if not args.device_token:
        print("  → --device-token 미지정. 에이전트의 DEVICE_TOKEN 을 위 값으로 맞춰야 [5] 가 통과합니다.")

    check_metrics(base, token)
    check_auth(base, token)
    check_rotation_window(base, token, args.ops_token_prev)
    check_bad_op(base, token)
    check_stop_idempotent(base, token)
    if args.image:
        host = args.callback_host or local_ip_for(
            base.split("//", 1)[-1].split(":")[0].split("/")[0])
        check_deploy(base, token, args.image, host)
    else:
        print("\n[5] 배포 — [SKIP] --image 미지정")

    if args.image:
        check_stop_cancels_deploy(base, token, args.image,
                                  args.callback_host or local_ip_for(
                                      base.split("//", 1)[-1].split(":")[0].split("/")[0]))
    else:
        print("\n[6] 중지-취소 — [SKIP] --image 미지정")

    passed = sum(1 for _, ok, _ in results if ok)
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{'=' * 60}\n결과: {passed}/{len(results)} 통과")
    if failed:
        print("실패 항목:")
        for n in failed:
            print(f"  - {n}")
        return 1
    print("적합성 검사 통과 — 계약 v1 을 만족합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
