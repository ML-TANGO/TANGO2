#!/usr/bin/env python
"""
app.py — lm-eval-harness 평가 대시보드 웹 서버 (Flask).

  python app.py --host 0.0.0.0 --port 7860

브라우저에서 실험 설정(모델/GPU/배치/few-shot/벤치마크 선택)을 입력하고
[실행] 을 누르면 run_eval.py 를 서브프로세스로 띄워 진행 상황과 결과를
실시간(폴링)으로 보여준다.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shlex
import signal
import subprocess
import sys
import time

import yaml
from flask import Flask, jsonify, render_template, request, send_from_directory

import eval_tasks as REG
from model_loader import (MODEL_CATALOG, hf_token, model_status,
                          pretty_model_name, repo_id_of)

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE, "configs")
RUNS_DIR = os.path.join(BASE, "runs")
DEFAULT_CONFIG = os.path.join(CONFIG_DIR, "default.yaml")

app = Flask(__name__, template_folder=os.path.join(BASE, "templates"),
            static_folder=os.path.join(BASE, "static"))


# --------------------------------------------------------------------------
# 액세스 로그 억제
#   대시보드는 /api/status, /api/gpus 를 수 초마다 폴링하기 때문에 werkzeug 기본
#   액세스 로그가 콘솔을 가득 채운다. 성공(2xx/3xx) 폴링 요청만 조용히 버리고
#   오류(4xx/5xx)와 그 밖의 요청은 그대로 남긴다.  --access-log 로 전부 켤 수 있다.
# --------------------------------------------------------------------------
QUIET_PATHS = ("/api/status", "/api/gpus", "/api/config", "/api/registry",
               "/api/runs", "/static/", "/favicon.ico")
_ACCESS_RE = re.compile(r'"(?:GET|POST|HEAD) (\S+) HTTP/[\d.]+" (\d{3})')


class _QuietAccessLog(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        m = _ACCESS_RE.search(record.getMessage())
        if not m:
            return True
        path, code = m.group(1), m.group(2)
        if code[0] in "45":          # 오류는 항상 보여준다
            return True
        return not path.startswith(QUIET_PATHS)


def quiet_access_log(enabled: bool = True) -> None:
    wlog = logging.getLogger("werkzeug")
    wlog.filters = [f for f in wlog.filters if not isinstance(f, _QuietAccessLog)]
    if enabled:
        wlog.addFilter(_QuietAccessLog())

# 실행 중인 프로세스 상태
PROC: dict = {"popen": None, "out_dir": None, "log_path": None,
              "cmd": None, "started_at": None}


# --------------------------------------------------------------------------
# 설정 파일
# --------------------------------------------------------------------------
def base_defaults() -> dict:
    return {
        "model_path": MODEL_CATALOG[0]["repo_id"],
        "run_dir": MODEL_CATALOG[0]["run_dir"],
        "seed": 42,
        "gpus": "0",
        "batch_size": "8",
        "max_length": 4096,
        "dtype": "bfloat16",
        "limit": 50,
        "num_fewshot": "",
        "apply_chat_template": True,
        "fewshot_as_multiturn": False,
        "log_samples": False,
        "parallelize": False,
        "tasks": list(REG.DEFAULT_SELECTED),
        "custom_file": "custom_data/sample_ko.jsonl",
        "custom_max_new_tokens": 256,
        "custom_lang": "auto",
        "custom_system_prompt": "",
    }


def normalize_model(cfg: dict) -> dict:
    """예전 설정의 ``~/.cache/.../models--org--name`` 경로를 repo id 로 바꿔 준다."""
    mp = str(cfg.get("model_path") or "").strip()
    if "models--" in mp and not os.path.exists(os.path.join(mp, "config.json")):
        rid = repo_id_of(mp)
        if rid:
            cfg["model_path"] = rid
    return cfg


def load_config(path: str = DEFAULT_CONFIG) -> dict:
    cfg = base_defaults()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                user = yaml.safe_load(f) or {}
            if isinstance(user, dict):
                cfg.update(user)
        except Exception as e:  # noqa: BLE001
            app.logger.warning("설정 로드 실패 %s: %s", path, e)
    return normalize_model(cfg)


def save_config(cfg: dict, path: str = DEFAULT_CONFIG) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)


# --------------------------------------------------------------------------
# 실행 / 상태
# --------------------------------------------------------------------------
def build_command(cfg: dict) -> tuple[list[str], str]:
    out_dir = os.path.expanduser(str(cfg.get("run_dir") or "runs/latest"))
    if not os.path.isabs(out_dir):
        out_dir = os.path.join(BASE, out_dir)

    tasks = cfg.get("tasks") or REG.DEFAULT_SELECTED
    cmd = [sys.executable, "-u", os.path.join(BASE, "run_eval.py"),
           "--model", str(cfg["model_path"]),
           "--tasks", ",".join(tasks),
           "--out", out_dir,
           "--batch-size", str(cfg.get("batch_size", "8")),
           "--dtype", str(cfg.get("dtype", "bfloat16")),
           "--gpus", str(cfg.get("gpus", "0")),
           "--max-length", str(int(cfg.get("max_length", 4096))),
           "--seed", str(int(cfg.get("seed", 42)))]

    if str(cfg.get("limit", "")).strip() not in ("", "0", "None", "none"):
        cmd += ["--limit", str(int(cfg["limit"]))]
    if str(cfg.get("num_fewshot", "")).strip() not in ("", "None", "none"):
        cmd += ["--num-fewshot", str(int(cfg["num_fewshot"]))]
    if cfg.get("apply_chat_template"):
        cmd += ["--apply-chat-template"]
    if cfg.get("fewshot_as_multiturn"):
        cmd += ["--fewshot-as-multiturn"]
    if cfg.get("log_samples"):
        cmd += ["--log-samples"]
    if cfg.get("parallelize"):
        cmd += ["--parallelize"]
    if "custom_file" in (tasks or []) and cfg.get("custom_file"):
        cmd += ["--custom-file", str(cfg["custom_file"]),
                "--custom-max-new-tokens", str(int(cfg.get("custom_max_new_tokens", 256))),
                "--custom-lang", str(cfg.get("custom_lang", "auto"))]
        if str(cfg.get("custom_system_prompt", "")).strip():
            cmd += ["--custom-system-prompt", str(cfg["custom_system_prompt"])]
    return cmd, out_dir


def is_running() -> bool:
    p = PROC.get("popen")
    return p is not None and p.poll() is None


def read_status(out_dir: str | None) -> dict:
    if not out_dir:
        return {}
    path = os.path.join(out_dir, "status.json")
    for _ in range(3):  # 쓰기 도중 읽기 충돌 대비
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except Exception:
            time.sleep(0.05)
    return {}


def tail_log(path: str | None, lines: int = 200) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = min(size, 256 * 1024)
            f.seek(size - block)
            data = f.read().decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        return f"(로그 읽기 실패: {e})"
    data = data.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(data.split("\n")[-lines:])


# --------------------------------------------------------------------------
# 라우트
# --------------------------------------------------------------------------
@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/registry")
def api_registry():
    return jsonify(REG.registry_json())


def _human_size(n: int) -> str:
    if not n:
        return "-"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0
    return f"{n:.1f} TiB"


def model_info(model_path: str) -> dict:
    """모델 지정값 → UI 표시용 정보(캐시 여부/다운로드 필요 여부 포함)."""
    st = model_status(model_path)
    cat = next((m for m in MODEL_CATALOG if m["repo_id"] == st["repo_id"]), None)
    ready = st["cached"] or st["downloadable"]
    if st["cached"]:
        note = "캐시에 있음"
    elif st["downloadable"]:
        note = "캐시에 없음 — 실행 시 자동 다운로드"
        if cat and cat.get("gated") and not st["hf_token"]:
            note += " (gated 모델: export HF_TOKEN 필요)"
    else:
        note = "로컬 경로를 찾을 수 없습니다"
    return {
        **st,
        "size_text": _human_size(st["size_bytes"]),
        "label": (cat or {}).get("label") or pretty_model_name(st["resolved"]),
        "gated": bool((cat or {}).get("gated")),
        "in_catalog": cat is not None,
        "ready": ready,
        "note": note,
    }


@app.get("/api/models")
def api_models():
    """드롭다운용 모델 목록 + 각 모델의 캐시 상태."""
    items = []
    for m in MODEL_CATALOG:
        st = model_status(m["repo_id"])
        items.append({**m, "cached": st["cached"], "snapshot": st["snapshot"],
                      "size_bytes": st["size_bytes"],
                      "size_text": _human_size(st["size_bytes"])})
    return jsonify({"models": items, "hf_token": bool(hf_token()),
                    "hub_cache": os.path.expanduser(
                        os.environ.get("HF_HUB_CACHE")
                        or "~/.cache/huggingface/hub")})


@app.get("/api/config")
def api_get_config():
    cfg = load_config()
    minfo = model_info(str(cfg["model_path"]))
    out_dir = os.path.expanduser(str(cfg.get("run_dir") or "runs/latest"))
    if not os.path.isabs(out_dir):
        out_dir = os.path.join(BASE, out_dir)
    cmd, _ = build_command(cfg)
    return jsonify({
        "config": cfg,
        "defaults": base_defaults(),
        "derived": {
            "resolved_model": minfo["snapshot"] or minfo["resolved"],
            "model_name": minfo["label"],
            "model_exists": minfo["ready"],
            "model": minfo,
            "hf_token": minfo["hf_token"],
            "out_dir": out_dir,
            "results_json": os.path.join(out_dir, "results.json"),
            "log_path": os.path.join(out_dir, "run.log"),
            "config_path": DEFAULT_CONFIG,
            "command": " ".join(shlex.quote(c) for c in cmd),
        },
        "running": is_running(),
    })


@app.post("/api/config")
def api_save_config():
    cfg = load_config()
    body = request.get_json(force=True, silent=True) or {}
    cfg.update(body)
    save_config(cfg)
    return jsonify({"ok": True, "config": cfg, "path": DEFAULT_CONFIG})


@app.get("/api/config/raw")
def api_config_raw():
    if not os.path.exists(DEFAULT_CONFIG):
        save_config(base_defaults())
    with open(DEFAULT_CONFIG, encoding="utf-8") as f:
        return jsonify({"path": DEFAULT_CONFIG, "text": f.read()})


@app.post("/api/config/raw")
def api_config_raw_save():
    body = request.get_json(force=True, silent=True) or {}
    text = body.get("text", "")
    try:
        parsed = yaml.safe_load(text)
        if parsed is not None and not isinstance(parsed, dict):
            raise ValueError("YAML 최상위는 매핑(dict)이어야 합니다.")
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"YAML 오류: {e}"}), 400
    with open(DEFAULT_CONFIG, "w", encoding="utf-8") as f:
        f.write(text)
    return jsonify({"ok": True, "config": load_config()})


@app.post("/api/run")
def api_run():
    if is_running():
        return jsonify({"ok": False, "error": "이미 평가가 실행 중입니다."}), 409

    body = request.get_json(force=True, silent=True) or {}
    cfg = load_config()
    cfg.update(body.get("config") or {})
    if body.get("save", True):
        save_config(cfg)

    minfo = model_info(str(cfg["model_path"]))
    if not minfo["ready"]:
        return jsonify({"ok": False,
                        "error": f"모델을 찾을 수 없습니다: {cfg['model_path']} — "
                                 f"'org/name' 형태의 HF repo id 또는 config.json 이 "
                                 f"있는 로컬 경로를 입력하세요."}), 400
    if minfo["gated"] and not minfo["cached"] and not minfo["hf_token"]:
        return jsonify({"ok": False,
                        "error": f"'{minfo['repo_id']}' 는 gated 모델이라 다운로드에 "
                                 f"토큰이 필요합니다. 서버를 띄운 셸에서 "
                                 f"`export HF_TOKEN=hf_xxx` 후 재시작하세요."}), 400
    if not cfg.get("tasks"):
        return jsonify({"ok": False, "error": "벤치마크를 1개 이상 선택하세요."}), 400

    cmd, out_dir = build_command(cfg)
    os.makedirs(out_dir, exist_ok=True)
    # 이전 실행 산출물 초기화 (status/log 만)
    for name in ("status.json", "run.log"):
        p = os.path.join(out_dir, name)
        if os.path.exists(p):
            os.remove(p)
    log_path = os.path.join(out_dir, "run.log")

    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    env["CUDA_VISIBLE_DEVICES"] = str(cfg.get("gpus", "0"))
    logf = open(log_path, "wb")
    logf.write((" ".join(shlex.quote(c) for c in cmd) + "\n\n").encode())
    logf.flush()
    popen = subprocess.Popen(cmd, cwd=BASE, stdout=logf, stderr=subprocess.STDOUT,
                             env=env, start_new_session=True)
    PROC.update(popen=popen, out_dir=out_dir, log_path=log_path,
                cmd=cmd, started_at=time.time(), logf=logf)
    return jsonify({"ok": True, "pid": popen.pid, "out_dir": out_dir,
                    "will_download": not minfo["cached"],
                    "model": minfo["label"],
                    "command": " ".join(shlex.quote(c) for c in cmd)})


@app.post("/api/stop")
def api_stop():
    if not is_running():
        return jsonify({"ok": False, "error": "실행 중인 평가가 없습니다."}), 400
    p = PROC["popen"]
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
    except Exception:
        p.terminate()
    return jsonify({"ok": True})


@app.get("/api/status")
def api_status():
    out_dir = PROC.get("out_dir")
    if not out_dir:
        # 서버를 새로 띄운 직후 — 이전 실행의 status/log 를 끌어오지 않고
        # 빈 상태(0 / 공란)로 시작한다. ?last=1 로 마지막 실행 결과를 볼 수 있다.
        cfg = load_config()
        d = os.path.expanduser(str(cfg.get("run_dir") or "runs/latest"))
        out_dir = d if os.path.isabs(d) else os.path.join(BASE, d)
        if request.args.get("last") not in ("1", "true", "yes"):
            return jsonify({"running": False, "fresh": True, "out_dir": out_dir,
                            "status": {}, "log": ""})
    st = read_status(out_dir)
    running = is_running()
    if not running and st.get("state") == "running":
        st["state"] = "stopped"   # 프로세스가 죽었는데 status 가 남아있는 경우
    return jsonify({
        "running": running,
        "fresh": False,
        "out_dir": out_dir,
        "status": st,
        "log": tail_log(os.path.join(out_dir, "run.log"),
                        int(request.args.get("log_lines", 300))),
    })


@app.get("/api/runs")
def api_runs():
    out = []
    if os.path.isdir(RUNS_DIR):
        for name in sorted(os.listdir(RUNS_DIR)):
            d = os.path.join(RUNS_DIR, name)
            rj = os.path.join(d, "results.json")
            if os.path.exists(rj):
                try:
                    with open(rj, encoding="utf-8") as f:
                        data = json.load(f)
                    out.append({
                        "name": name, "path": d,
                        "mtime": os.path.getmtime(rj),
                        "model": (data.get("model") or {}).get("name"),
                        "summary": (data.get("results") or {}).get("summary", {}),
                    })
                except Exception:
                    continue
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return jsonify(out)


@app.get("/api/gpus")
def api_gpus():
    try:
        r = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=index,name,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5)
        gpus = []
        for line in r.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                gpus.append({"index": int(parts[0]), "name": parts[1],
                             "mem_used": int(float(parts[2])),
                             "mem_total": int(float(parts[3])),
                             "util": int(float(parts[4]))})
        return jsonify(gpus)
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)})


@app.get("/download/<path:relpath>")
def download(relpath: str):
    full = os.path.abspath(os.path.join(BASE, relpath))
    if not full.startswith(BASE) or not os.path.exists(full):
        return "not found", 404
    return send_from_directory(os.path.dirname(full), os.path.basename(full),
                               as_attachment=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=7860)
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--access-log", action="store_true",
                    help="폴링 요청(/api/status, /api/gpus 등) 액세스 로그도 모두 출력")
    a = ap.parse_args()
    os.makedirs(RUNS_DIR, exist_ok=True)
    if not os.path.exists(DEFAULT_CONFIG):
        save_config(base_defaults())
    quiet_access_log(not a.access_log)
    print(f"  →  http://localhost:{a.port}  (설정: {DEFAULT_CONFIG})")
    print(f"  모델    : {', '.join(m['repo_id'] for m in MODEL_CATALOG)}")
    print(f"  HF_TOKEN: {'설정됨' if hf_token() else '없음 (gated 모델은 export HF_TOKEN 필요)'}")
    if not a.access_log:
        print("  로그    : 폴링 요청 액세스 로그는 숨깁니다 (--access-log 로 켜기)")
    app.run(host=a.host, port=a.port, debug=a.debug, threaded=True)


if __name__ == "__main__":
    main()
