#!/usr/bin/env python3
"""
demo_video/server.py — 영상 기반 SDS-VLM 데모 웹 서버 (Jetson Orin 에서 실행).

표준 라이브러리만 쓴다. Orin 기본 이미지에 pip 가 없기 때문이다.
모델 추론은 같은 장비의 llama-server(/completion) 에 맡기고, 이 서버는
  - 화면(static/)과 데이터(data/)를 제공하고 (영상은 Range 요청 지원)
  - /api/status  : llama-server 상태와 모델 정보
  - /api/analyze : 분석 격자 프레임 하나를 실시간 추론하고 토큰을 SSE 로 중계
를 맡는다. llama-server 는 슬롯 하나(-np 1)로 띄우므로 분석 요청은 한 번에 하나만 받는다.

사용:
  python3 demo_video/server.py --llm http://127.0.0.1:8080 --port 8000
"""
import argparse
import base64
import json
import mimetypes
import os
import re
import threading
import time
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
CHUNK = 1 << 16
MAX_BODY = 4096            # /api/analyze 요청은 시나리오 id 와 프레임 번호뿐이다


class LLM:
    """llama-server 접근. 미디어 마커는 서버 기동마다 바뀌므로 /props 에서 읽어 둔다."""

    def __init__(self, url):
        self.url = url.rstrip("/")
        self.lock = threading.Lock()   # 분석은 한 번에 하나
        self._props = None

    def _get(self, path, timeout=5):
        with urllib.request.urlopen(self.url + path, timeout=timeout) as r:
            return json.loads(r.read())

    def props(self, refresh=False):
        if self._props is None or refresh:
            self._props = self._get("/props")
        return self._props

    def status(self):
        try:
            self._get("/health", timeout=2)
            p = self.props(refresh=True)
            settings = p.get("default_generation_settings", {})
            return {"ready": True,
                    "busy": self.lock.locked(),
                    "model": os.path.basename(p.get("model_path", "")),
                    "n_ctx": settings.get("n_ctx"),
                    "vision": bool(p.get("modalities", {}).get("vision"))}
        except (urllib.error.URLError, OSError, ValueError) as e:
            return {"ready": False, "busy": False, "error": str(e)}

    def stream(self, prompt, image_png, n_predict):
        """/completion 을 stream=true 로 부르고 SSE 의 data 줄(JSON)을 하나씩 낸다."""
        marker = self.props()["media_marker"]
        body = {
            "prompt": {"prompt_string": prompt.replace("<image>", marker),
                       "multimodal_data": [base64.b64encode(image_png).decode()]},
            "n_predict": n_predict, "temperature": 0.0, "top_k": 1,
            "cache_prompt": False, "stream": True,
        }
        req = urllib.request.Request(self.url + "/completion", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as r:
            for raw in r:
                line = raw.decode("utf-8").strip()
                if line.startswith("data:"):
                    yield json.loads(line[5:].strip())
                elif line.startswith("error:"):          # 생성 도중 llama-server 오류
                    raise RuntimeError(line[6:].strip())


class Handler(BaseHTTPRequestHandler):
    server_version = "EVA-demo/1.0"
    timeout = 30            # 느리거나 멈춘 연결이 스레드를 붙잡지 않게 한다 (스트리밍 쓰기에는 영향 없음)
    data_dir = static_dir = None
    llm = None
    n_predict = 512

    def log_message(self, fmt, *args):
        if not self.path.startswith(("/data/", "/static/")):
            super().log_message(fmt, *args)

    # ── 공통 ────────────────────────────────────────────────────────────────
    def _json(self, obj, status=HTTPStatus.OK):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _safe_path(self, root, rel):
        try:
            path = os.path.realpath(os.path.join(root, rel))
        except ValueError:                       # NUL 문자 등
            return None
        if not path.startswith(os.path.realpath(root) + os.sep) or not os.path.isfile(path):
            return None
        return path

    def _file(self, path):
        """정적 파일. 영상 탐색(seek)을 위해 Range 요청을 처리한다."""
        size = os.path.getsize(path)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if path.endswith(".js"):
            ctype = "text/javascript"
        start, end = 0, size - 1
        m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", ""))
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
            else:                                   # bytes=-N (끝에서 N 바이트)
                start = max(0, size - int(m.group(2)))
            end = min(end, size - 1)
            if start > end:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if path.endswith((".html", ".js", ".css", ".json")):
            self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            try:
                while left > 0:
                    buf = f.read(min(CHUNK, left))
                    if not buf:
                        break
                    self.wfile.write(buf)
                    left -= len(buf)
            except (BrokenPipeError, ConnectionResetError):
                pass                                # 탐색 중 브라우저가 연결을 끊는 일은 흔하다

    # ── GET ─────────────────────────────────────────────────────────────────
    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path in ("/", "/index.html"):
            return self._file(os.path.join(self.static_dir, "index.html"))
        if path == "/api/status":
            return self._json(self.llm.status())
        for prefix, root in (("/static/", self.static_dir), ("/data/", self.data_dir)):
            if path.startswith(prefix):
                f = self._safe_path(root, path[len(prefix):])
                if f:
                    return self._file(f)
        self.send_error(HTTPStatus.NOT_FOUND)

    # ── POST /api/analyze ───────────────────────────────────────────────────
    def do_POST(self):
        if urlparse(self.path).path != "/api/analyze":
            return self.send_error(HTTPStatus.NOT_FOUND)
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY:
            return self._json({"error": "요청 형식이 올바르지 않습니다"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        try:
            req = json.loads(self.rfile.read(length))
            sid, frame = str(req["scenario"]), int(req["frame"])
        except (ValueError, KeyError, TypeError):
            return self._json({"error": "scenario, frame 이 필요합니다"}, HTTPStatus.BAD_REQUEST)

        frames_path = self._safe_path(self.data_dir, f"{sid}/frames.json")
        image_path = self._safe_path(self.data_dir, f"{sid}/inputs/f{frame:06d}.png")
        if not frames_path or not image_path:
            return self._json({"error": "분석할 수 없는 프레임입니다"}, HTTPStatus.NOT_FOUND)
        with open(frames_path, encoding="utf-8") as f:
            prompt = json.load(f)["prompts"].get(str(frame))
        if prompt is None:
            return self._json({"error": "분석 격자에 없는 프레임입니다"}, HTTPStatus.NOT_FOUND)

        if not self.llm.lock.acquire(blocking=False):
            return self._json({"error": "다른 분석이 진행 중입니다. 잠시 후 다시 시도해 주세요."},
                              HTTPStatus.CONFLICT)
        try:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            t0 = time.time()
            first = None
            with open(image_path, "rb") as f:
                image = f.read()
            for ev in self.llm.stream(prompt, image, self.n_predict):
                if first is None and ev.get("content"):
                    first = time.time() - t0
                out = {"content": ev.get("content", ""), "stop": ev.get("stop", False)}
                if ev.get("stop"):
                    out.update(timings=ev.get("timings"), wall_s=round(time.time() - t0, 3),
                               first_token_s=round(first or 0.0, 3))
                self.wfile.write(f"data: {json.dumps(out, ensure_ascii=False)}\n\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:                   # 업스트림 오류는 모두 스트림 끝에 알린다
            try:
                self.wfile.write(f"data: {json.dumps({'error': str(e), 'stop': True})}\n\n".encode())
            except OSError:
                pass
        finally:
            self.llm.lock.release()


def main():
    ap = argparse.ArgumentParser("SDS-VLM 영상 데모 서버")
    ap.add_argument("--llm", default="http://127.0.0.1:8080", help="llama-server 주소")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--data", default=os.path.join(HERE, "data"))
    ap.add_argument("--n_predict", type=int, default=512)
    args = ap.parse_args()

    Handler.data_dir = os.path.abspath(args.data)
    Handler.static_dir = os.path.join(HERE, "static")
    Handler.llm = LLM(args.llm)
    Handler.n_predict = args.n_predict
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    httpd.daemon_threads = True
    print(f"[Demo] http://{args.host}:{args.port}  (llama-server: {args.llm})", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
