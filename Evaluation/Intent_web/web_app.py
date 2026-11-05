#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
web_app.py — Qwen3 × MixATIS 실험 웹 콘솔.

  * 설정(MODE / MODEL_NAME / DATA_DIR / OUTPUT_DIR / 4bit)을 웹에서 수정
  * [실행] 버튼 -> auto2.sh 를 그 설정으로 실행
  * 학습/평가 진행률(progress) + 실시간 로그 표시
  * 평가 결과(Intent/Slot F1 등)를 카드로 파싱해서 표시

의존성 없음(파이썬 표준 라이브러리만). 실행:
  python3 web_app.py            # 기본 0.0.0.0:8080
  PORT=9000 python3 web_app.py
"""
import json
import os
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8080"))

# 웹페이지에 보여줄 기본값 (run_experiment.sh 기본값과 동일).
DEFAULTS = {
    "MODE": "debug",
    "MODEL_NAME": "Qwen/Qwen3-8B",
    "DATA_DIR": "/workspace/UGEN/data/MixATIS_clean",
    "OUTPUT_DIR": "/workspace/out/qwen3-8b-mixatis-lora",
    "USE_4BIT": "1",
}


# --------------------------------------------------------------------------
# 터미널 버퍼: \r(줄 덮어쓰기) / \n(줄 확정) 을 흉내내 tqdm 진행바를 예쁘게 유지
# --------------------------------------------------------------------------
class TermBuffer:
    MAX_LINES = 3000

    def __init__(self):
        self.lines = [""]
        self.lock = threading.Lock()

    def feed(self, text):
        with self.lock:
            for ch in text:
                if ch == "\n":
                    self.lines.append("")
                elif ch == "\r":
                    self.lines[-1] = ""
                elif ch == "\t":
                    self.lines[-1] += "    "
                else:
                    self.lines[-1] += ch
            if len(self.lines) > self.MAX_LINES:
                self.lines = self.lines[-self.MAX_LINES:]

    def snapshot(self, tail=600):
        with self.lock:
            return list(self.lines[-tail:])

    def full_text(self):
        with self.lock:
            return "\n".join(self.lines)

    def reset(self):
        with self.lock:
            self.lines = [""]


# --------------------------------------------------------------------------
# 실행 관리 (한 번에 하나만)
# --------------------------------------------------------------------------
class Runner:
    def __init__(self):
        self.buf = TermBuffer()
        self.proc = None
        self.thread = None
        self.returncode = None
        self.config = dict(DEFAULTS)
        self.lock = threading.Lock()

    def is_running(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self, config):
        with self.lock:
            if self.is_running():
                return False, "이미 실행 중입니다."
            self.buf.reset()
            self.returncode = None
            self.config = config

            env = dict(os.environ)
            for k in ("MODE", "MODEL_NAME", "DATA_DIR", "OUTPUT_DIR", "USE_4BIT"):
                env[k] = config.get(k, DEFAULTS[k])
            env["PYTHONUNBUFFERED"] = "1"

            self.buf.feed(
                "$ MODE=%s MODEL_NAME=%s USE_4BIT=%s bash auto2.sh\n"
                % (env["MODE"], env["MODEL_NAME"], env["USE_4BIT"])
            )

            try:
                self.proc = subprocess.Popen(
                    ["bash", os.path.join(HERE, "auto2.sh")],
                    cwd=HERE,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=0,
                )
            except Exception as e:  # noqa: BLE001
                self.buf.feed("[web_app] 실행 실패: %s\n" % e)
                return False, str(e)

            self.thread = threading.Thread(target=self._reader, daemon=True)
            self.thread.start()
            return True, "started"

    def _reader(self):
        fd = self.proc.stdout.fileno()
        while True:
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            self.buf.feed(chunk.decode("utf-8", "replace"))
        self.proc.wait()
        self.returncode = self.proc.returncode
        self.buf.feed("\n[web_app] 프로세스 종료 (exit=%s)\n" % self.returncode)

    def stop(self):
        if not self.is_running():
            return False, "실행 중이 아닙니다."
        name = os.environ.get("CONTAINER_NAME", "qwen3_web_run")
        subprocess.run(["docker", "rm", "-f", name],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            self.proc.terminate()
        except Exception:  # noqa: BLE001
            pass
        self.buf.feed("\n[web_app] 사용자에 의해 중지됨.\n")
        return True, "stopped"


runner = Runner()


# --------------------------------------------------------------------------
# 진행률 / 지표 파싱
# --------------------------------------------------------------------------
RE_TQDM = re.compile(r"(\d+)%\|")
RE_STEPS = re.compile(r"(\d+)/(\d+)\s*\[")          # tqdm: 20/100 [
RE_EVAL = re.compile(r"\.\.\.(\d+)/(\d+)")           # 평가: ...16/20
RE_PHASE1 = re.compile(r"\[1/2\]")
RE_PHASE2 = re.compile(r"\[2/2\]")

RE_M_IACC = re.compile(r"Intent Acc\s*:\s*([\d.]+)")
RE_M_IF1 = re.compile(r"Intent F1 \(P/R/F1\):\s*([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)")
RE_M_SF1 = re.compile(r"Slot\s+F1 \(P/R/F1\):\s*([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)")
RE_M_JOINT = re.compile(r"Overall\(Joint\) Acc:\s*([\d.]+)")


def parse_progress(lines):
    """가장 최근 상태 기준으로 단계/진행률 계산."""
    phase = "대기"
    percent = 0
    detail = ""
    text = "\n".join(lines)

    in_eval = RE_PHASE2.search(text) is not None
    in_train = RE_PHASE1.search(text) is not None

    if in_eval:
        phase = "평가"
        # 평가 진행 (...N/M) 최신값
        last = None
        for ln in reversed(lines):
            m = RE_EVAL.search(ln)
            if m:
                last = m
                break
        if last:
            cur, tot = int(last.group(1)), int(last.group(2))
            percent = int(cur * 100 / tot) if tot else 0
            detail = "%d/%d 발화" % (cur, tot)
        else:
            detail = "평가 모델 로딩 중…"
            percent = 0
    elif in_train:
        phase = "학습"
        last_pct, last_step = None, None
        # 준비 단계 진행바(모델 다운로드/토크나이즈/가중치 로딩)는 학습 진행률에서 제외.
        skip = ("Loading weights", "tokenizing", "Fetching", "Loading checkpoint")
        for ln in reversed(lines):
            if any(s in ln for s in skip):
                continue
            ms = RE_STEPS.search(ln)
            mp = RE_TQDM.search(ln)
            if ms and last_step is None:
                last_step = ms
            if mp and last_pct is None:
                last_pct = mp
            if last_step and last_pct:
                break
        if last_step is None and last_pct is None:
            detail = "모델 로딩 / 준비 중…"
        if last_pct:
            percent = int(last_pct.group(1))
        if last_step:
            detail = "%s/%s step" % (last_step.group(1), last_step.group(2))

    return {"phase": phase, "percent": percent, "detail": detail}


def parse_metrics(text):
    out = {}
    m = RE_M_IACC.search(text)
    if m:
        out["intent_acc"] = float(m.group(1))
    m = RE_M_IF1.search(text)
    if m:
        out["intent_p"], out["intent_r"], out["intent_f1"] = map(float, m.groups())
    m = RE_M_SF1.search(text)
    if m:
        out["slot_p"], out["slot_r"], out["slot_f1"] = map(float, m.groups())
    m = RE_M_JOINT.search(text)
    if m:
        out["joint_acc"] = float(m.group(1))
    return out or None


# --------------------------------------------------------------------------
# HTTP 핸들러
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # 콘솔 소음 억제
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            self._send(200, PAGE, "text/html; charset=utf-8")
        elif self.path.startswith("/state"):
            lines = runner.buf.snapshot()
            full = runner.buf.full_text()
            state = {
                "running": runner.is_running(),
                "returncode": runner.returncode,
                "lines": lines,
                "progress": parse_progress(lines),
                "metrics": parse_metrics(full),
                "config": runner.config,
                "defaults": DEFAULTS,
            }
            self._send(200, json.dumps(state, ensure_ascii=False))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except Exception:  # noqa: BLE001
            payload = {}

        if self.path == "/run":
            config = {}
            for k in DEFAULTS:
                v = str(payload.get(k, DEFAULTS[k])).strip()
                config[k] = v or DEFAULTS[k]
            if config["MODE"] not in ("debug", "full"):
                config["MODE"] = "debug"
            if config["USE_4BIT"] not in ("0", "1"):
                config["USE_4BIT"] = "1"
            ok, msg = runner.start(config)
            self._send(200 if ok else 409,
                       json.dumps({"ok": ok, "msg": msg}, ensure_ascii=False))
        elif self.path == "/stop":
            ok, msg = runner.stop()
            self._send(200, json.dumps({"ok": ok, "msg": msg}, ensure_ascii=False))
        else:
            self._send(404, json.dumps({"error": "not found"}))


# --------------------------------------------------------------------------
# 프론트엔드 (단일 HTML)
# --------------------------------------------------------------------------
PAGE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Qwen3 × MixATIS 실험 콘솔</title>
<style>
  :root{
    --bg:#0f1116; --panel:#171a21; --panel2:#1e222b; --border:#2a2f3a;
    --text:#e6e9ef; --muted:#9aa4b2; --accent:#4f8cff; --accent2:#22c55e;
    --warn:#f59e0b; --term-bg:#0b0d12;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans KR",sans-serif;}
  header{padding:18px 24px;border-bottom:1px solid var(--border);
    display:flex;align-items:center;gap:12px;background:var(--panel);}
  header h1{font-size:18px;margin:0;font-weight:650}
  header .dot{width:10px;height:10px;border-radius:50%;background:#555}
  header .dot.on{background:var(--accent2);box-shadow:0 0 8px var(--accent2)}
  .wrap{max-width:1180px;margin:0 auto;padding:22px;display:grid;
    grid-template-columns:360px 1fr;gap:22px}
  @media (max-width:900px){.wrap{grid-template-columns:1fr}}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:18px}
  .card h2{font-size:14px;margin:0 0 14px;color:var(--muted);text-transform:uppercase;
    letter-spacing:.5px;font-weight:650}
  label{display:block;font-size:12px;color:var(--muted);margin:12px 0 5px}
  input,select{width:100%;padding:10px 12px;background:var(--panel2);color:var(--text);
    border:1px solid var(--border);border-radius:8px;font-size:13px;font-family:inherit}
  input:focus,select:focus{outline:none;border-color:var(--accent)}
  .row{display:flex;gap:10px}
  .row>div{flex:1}
  .btns{display:flex;gap:10px;margin-top:18px}
  button{flex:1;padding:12px;border:none;border-radius:8px;font-size:14px;font-weight:650;
    cursor:pointer;transition:.15s}
  .run{background:var(--accent);color:#fff}
  .run:hover{background:#3b7cff}
  .run:disabled{background:#33405e;color:#89a;cursor:not-allowed}
  .stop{background:#33212a;color:#ff8a9c;border:1px solid #5a2b38}
  .stop:hover{background:#42222e}
  .stop:disabled{opacity:.4;cursor:not-allowed}
  .reset{flex:0 0 auto;background:var(--panel2);color:var(--muted);border:1px solid var(--border)}

  .prog-wrap{margin-bottom:16px}
  .prog-head{display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px}
  .prog-head .phase{font-weight:650}
  .bar{height:12px;background:var(--panel2);border-radius:8px;overflow:hidden;border:1px solid var(--border)}
  .bar>i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--accent),#7aa7ff);
    transition:width .3s}
  .bar.eval>i{background:linear-gradient(90deg,var(--accent2),#5ee08a)}

  .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:8px}
  @media (max-width:640px){.metrics{grid-template-columns:repeat(2,1fr)}}
  .metric{background:var(--panel2);border:1px solid var(--border);border-radius:10px;padding:14px}
  .metric .k{font-size:11px;color:var(--muted);margin-bottom:6px}
  .metric .v{font-size:24px;font-weight:700}
  .metric .sub{font-size:11px;color:var(--muted);margin-top:4px}
  .metric.joint .v{color:var(--warn)}
  .metric.acc .v{color:var(--accent2)}
  .hidden{display:none}

  .term{background:var(--term-bg);border:1px solid var(--border);border-radius:10px;
    padding:14px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Noto Sans Mono",monospace;
    font-size:12.5px;line-height:1.5;white-space:pre-wrap;word-break:break-all;
    height:460px;overflow-y:auto;color:#cdd3dd}
  .term::-webkit-scrollbar{width:10px}
  .term::-webkit-scrollbar-thumb{background:#2a2f3a;border-radius:5px}
  .muted{color:var(--muted);font-size:12px}
  .pill{display:inline-block;font-size:11px;padding:2px 8px;border-radius:20px;
    background:var(--panel2);border:1px solid var(--border);color:var(--muted)}
</style>
</head>
<body>
<header>
  <span class="dot" id="dot"></span>
  <h1>Qwen3-8B × MixATIS 실험 콘솔</h1>
  <span class="pill" id="statuspill">대기</span>
</header>

<div class="wrap">
  <!-- 좌: 설정 -->
  <section class="card">
    <h2>실험 설정</h2>

    <label>MODE</label>
    <select id="MODE">
      <option value="debug">debug (200 학습 / 20 평가 · 빠른 점검)</option>
      <option value="full">full (전체 학습 3epoch / 828 평가)</option>
    </select>

    <label>MODEL_NAME</label>
    <input id="MODEL_NAME" spellcheck="false">

    <label>DATA_DIR</label>
    <input id="DATA_DIR" spellcheck="false">

    <label>OUTPUT_DIR</label>
    <input id="OUTPUT_DIR" spellcheck="false">

    <label>4bit (QLoRA)</label>
    <select id="USE_4BIT">
      <option value="1">1 · 켜짐 (권장)</option>
      <option value="0">0 · 꺼짐 (bf16 LoRA, 80GB+ GPU)</option>
    </select>

    <div class="btns">
      <button class="run" id="runBtn" onclick="run()">▶ 실행 (학습 + 평가)</button>
      <button class="stop" id="stopBtn" onclick="stop()" disabled>■ 중지</button>
    </div>
    <div class="btns">
      <button class="reset" onclick="resetDefaults()">기본값 복원</button>
    </div>
    <p class="muted" style="margin-top:14px">설정을 바꾸면 그 값으로 실행됩니다. 실행 스크립트: <b>auto2.sh</b></p>
  </section>

  <!-- 우: 진행 / 지표 / 로그 -->
  <div style="display:flex;flex-direction:column;gap:22px">
    <section class="card">
      <h2>진행 상황</h2>
      <div class="prog-wrap">
        <div class="prog-head">
          <span class="phase" id="phase">대기</span>
          <span class="muted" id="progdetail"></span>
        </div>
        <div class="bar" id="bar"><i id="barfill"></i></div>
      </div>

      <div class="metrics hidden" id="metrics">
        <div class="metric acc"><div class="k">Intent Acc</div><div class="v" id="m_iacc">–</div></div>
        <div class="metric"><div class="k">Intent F1</div><div class="v" id="m_if1">–</div>
          <div class="sub" id="m_if1sub"></div></div>
        <div class="metric"><div class="k">Slot F1</div><div class="v" id="m_sf1">–</div>
          <div class="sub" id="m_sf1sub"></div></div>
        <div class="metric joint"><div class="k">Overall (Joint) Acc</div><div class="v" id="m_joint">–</div></div>
      </div>
      <p class="muted" id="nometric">평가가 끝나면 지표가 여기에 표시됩니다.</p>
    </section>

    <section class="card">
      <h2>실행 로그</h2>
      <div class="term" id="term"></div>
    </section>
  </div>
</div>

<script>
const $ = id => document.getElementById(id);
const FIELDS = ["MODE","MODEL_NAME","DATA_DIR","OUTPUT_DIR","USE_4BIT"];
let DEFAULTS = {};
let autoScroll = true;

$("term").addEventListener("scroll", () => {
  const t = $("term");
  autoScroll = (t.scrollHeight - t.scrollTop - t.clientHeight) < 40;
});

function collect(){
  const c = {};
  FIELDS.forEach(f => c[f] = $(f).value);
  return c;
}
function fill(cfg){ FIELDS.forEach(f => { if(cfg[f]!==undefined) $(f).value = cfg[f]; }); }
function resetDefaults(){ fill(DEFAULTS); }

async function run(){
  $("runBtn").disabled = true;
  const r = await fetch("/run", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify(collect())});
  const j = await r.json();
  if(!j.ok){ alert("실행 불가: " + j.msg); $("runBtn").disabled = false; }
}
async function stop(){
  await fetch("/stop", {method:"POST"});
}

function fmt(x){ return (x*100).toFixed(2) + "%"; }

function render(s){
  // 상태
  $("dot").classList.toggle("on", s.running);
  $("statuspill").textContent = s.running ? "실행 중"
     : (s.returncode===0 ? "완료" : (s.returncode!==null ? "종료(exit="+s.returncode+")" : "대기"));
  $("runBtn").disabled = s.running;
  $("stopBtn").disabled = !s.running;

  // 진행률
  const p = s.progress || {phase:"대기", percent:0, detail:""};
  $("phase").textContent = p.phase;
  $("progdetail").textContent = p.detail || "";
  $("barfill").style.width = (p.percent||0) + "%";
  $("bar").classList.toggle("eval", p.phase==="평가");

  // 지표
  const m = s.metrics;
  if(m){
    $("metrics").classList.remove("hidden");
    $("nometric").classList.add("hidden");
    if(m.intent_acc!==undefined) $("m_iacc").textContent = fmt(m.intent_acc);
    if(m.intent_f1!==undefined){ $("m_if1").textContent = fmt(m.intent_f1);
      $("m_if1sub").textContent = "P "+fmt(m.intent_p)+" · R "+fmt(m.intent_r); }
    if(m.slot_f1!==undefined){ $("m_sf1").textContent = fmt(m.slot_f1);
      $("m_sf1sub").textContent = "P "+fmt(m.slot_p)+" · R "+fmt(m.slot_r); }
    if(m.joint_acc!==undefined) $("m_joint").textContent = fmt(m.joint_acc);
  }

  // 로그
  const term = $("term");
  term.textContent = (s.lines||[]).join("\n");
  if(autoScroll) term.scrollTop = term.scrollHeight;
}

let first = true;
async function poll(){
  try{
    const s = await (await fetch("/state")).json();
    if(first){
      DEFAULTS = s.defaults || {};
      // 실행중이면 서버 config, 아니면 기본값으로 폼 초기화
      fill(s.running ? s.config : DEFAULTS);
      first = false;
    }
    render(s);
  }catch(e){ /* 서버 재시작 등 무시 */ }
}
setInterval(poll, 800);
poll();
</script>
</body>
</html>
"""


def main():
    os.chdir(HERE)
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("Qwen3 × MixATIS 웹 콘솔 실행: http://0.0.0.0:%d  (Ctrl+C 종료)" % PORT)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")


if __name__ == "__main__":
    main()
