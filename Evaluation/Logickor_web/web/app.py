#!/usr/bin/env python3
"""
Logickor 평가 파이프라인 웹 서비스 (backend)

scripts/auto.sh (clean -> train -> generate -> evaluate -> score) 파이프라인을
브라우저에서 실행 / 중지하고, 설정값을 보고 수정하며, 결과를 확인한다.

- auto.sh 는 환경변수로만 제어된다(위치 인자 없음). 이 백엔드도 동일하게 env 로 전달한다.
- 실행 모드는 full / debug 두 가지다. debug 는 파이프라인 점검용으로 학습·평가 데이터의
  일부(TRAIN_FRACTION, 기본 10%)만 사용해 학습 시간을 줄인다(MODE / TRAIN_FRACTION env).
- 프로젝트 소스는 수정하지 않는다. 단, auto.sh 의 Step 0 이 runs/, generated/runs/,
  evaluated/*.jsonl 을 삭제하므로 이전 실행 산출물은 지워진다.
- 이 파일과 관련 자원은 모두 web/ 폴더 안에 있다.

실행:
    python web/app.py                 # http://0.0.0.0:8000
    HOST=127.0.0.1 PORT=8080 python web/app.py
"""
from __future__ import annotations

import glob
import json
import logging
import os
import re
import signal
import subprocess
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

# ---------------------------------------------------------------------------
# 경로
# ---------------------------------------------------------------------------
WEB_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = WEB_DIR.parent
AUTO_SH = PROJECT_ROOT / "scripts" / "auto.sh"
SAMPLE_PNG = PROJECT_ROOT / "sample.png"

SETTINGS_FILE = WEB_DIR / "settings.json"
LOG_DIR = WEB_DIR / "logs"
LOG_FILE = LOG_DIR / "pipeline.log"
LOG_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# 기본 설정값 (scripts/auto.sh 의 기본값과 동일)
# ---------------------------------------------------------------------------
# auto.sh 는 위치 인자를 받지 않고, 전부 환경변수(CONFIG_PATH / RUN_DIR / SEED / GPU /
# GEN_MODEL_LEN / JUDGE_MODEL / JUDGE_MODEL_LEN / MODE / TRAIN_FRACTION)로 제어된다.
# 키 이름을 그 변수에 1:1로 맞춘다.
DEFAULT_SETTINGS: Dict[str, Any] = {
    "config_path": "configs/train_gemma4_e4b_sft.yaml",
    "run_dir": "runs/gemma4_e4b_sft_high",
    "seed": "42",
    "gpu": "0",
    "gen_model_len": "4096",
    "judge_model": "gemma",
    "judge_model_len": "8192",
    # full  : 전체 데이터로 학습(기본)
    # debug : 파이프라인 확인용 짧은 실행 — train_fraction 만큼만 학습/평가
    "mode": "full",
    "train_fraction": "0.1",
}

# evaluator.py 의 JUDGE_MODEL_PRESETS 키. 프리셋 외에 로컬 경로/HF repo id 도 그대로 허용된다.
JUDGE_MODEL_PRESETS = ["gemma", "llama"]

# 실행 모드 프리셋 (UI 선택지)
MODE_FULL = "full"
MODE_DEBUG = "debug"
MODES = [
    {"value": MODE_FULL, "label": "full – 전체 데이터로 학습"},
    {"value": MODE_DEBUG, "label": "debug – 일부만 학습(빠른 테스트)"},
]


def resolve_train_fraction(s: Dict[str, Any]) -> float:
    """설정에서 실제로 사용할 학습 데이터 비율(0<f<=1)을 계산한다.

    full 모드면 항상 1.0, debug 모드면 train_fraction 값(잘못된 값은 기본 0.1).
    """
    if str(s.get("mode", MODE_FULL)).strip().lower() != MODE_DEBUG:
        return 1.0
    try:
        frac = float(str(s.get("train_fraction", DEFAULT_SETTINGS["train_fraction"])).strip())
    except ValueError:
        frac = float(DEFAULT_SETTINGS["train_fraction"])
    if not 0.0 < frac <= 1.0:
        frac = float(DEFAULT_SETTINGS["train_fraction"])
    return frac

# 예전 settings.json 키 -> 현재 키
_LEGACY_KEYS = {
    "output_dir": "run_dir",
    "gpu_devices": "gpu",
    "model_len": "gen_model_len",
}


def load_settings() -> Dict[str, Any]:
    data = dict(DEFAULT_SETTINGS)
    if SETTINGS_FILE.exists():
        try:
            saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            for old, new in _LEGACY_KEYS.items():
                if old in saved and new not in saved:
                    saved[new] = saved[old]
            for k in DEFAULT_SETTINGS:
                if k in saved:
                    data[k] = saved[k]
        except Exception:
            pass
    return data


def save_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    merged = load_settings()
    for k in DEFAULT_SETTINGS:
        if k in data:
            merged[k] = data[k]
    SETTINGS_FILE.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return merged


def derive_paths(s: Dict[str, Any]) -> Dict[str, str]:
    """auto.sh 와 동일하게 하위 경로들을 유도한다.

    auto.sh:  MERGED_DIR="${RUN_DIR}/merged"
              generator.py --model "${MERGED_DIR}"  -> ./generated/${MERGED_DIR}
              evaluator.py -o "generated/${MERGED_DIR}" -> ./evaluated/*.jsonl
    """
    run_dir = str(s.get("run_dir", DEFAULT_SETTINGS["run_dir"])).rstrip("/")
    merged_model = f"{run_dir}/merged"
    generated_dir = f"generated/{merged_model}"
    evaluated_glob = "evaluated/*.jsonl"
    mode = str(s.get("mode", DEFAULT_SETTINGS["mode"])).strip().lower()
    if mode not in (MODE_FULL, MODE_DEBUG):
        mode = MODE_FULL
    frac = resolve_train_fraction({**s, "mode": mode})
    return {
        "config_path": str(s.get("config_path", DEFAULT_SETTINGS["config_path"])),
        "run_dir": run_dir,
        "merged_model": merged_model,
        "generated_dir": generated_dir,
        "evaluated_glob": evaluated_glob,
        "mode": mode,
        "train_fraction": f"{frac:g}",
        "train_fraction_label": (
            "전체 데이터" if frac >= 1.0 else f"전체의 {frac * 100:g}% 만 사용"
        ),
    }


# ---------------------------------------------------------------------------
# 파이프라인 프로세스 관리
# ---------------------------------------------------------------------------
class Pipeline:
    def __init__(self) -> None:
        self.proc: Optional[subprocess.Popen] = None
        self.lock = threading.Lock()
        self.started_at: Optional[str] = None
        self.last_returncode: Optional[int] = None

    def is_running(self) -> bool:
        with self.lock:
            return self.proc is not None and self.proc.poll() is None

    def start(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            if self.proc is not None and self.proc.poll() is None:
                return {"ok": False, "error": "이미 실행 중입니다."}

            paths = derive_paths(settings)

            # auto.sh 는 모든 설정을 환경변수로 읽는다(위치 인자 없음).
            env = dict(os.environ)
            env["CONFIG_PATH"] = paths["config_path"]
            env["RUN_DIR"] = paths["run_dir"]
            env["SEED"] = str(settings.get("seed", DEFAULT_SETTINGS["seed"]))
            env["GPU"] = str(settings.get("gpu", DEFAULT_SETTINGS["gpu"]))
            env["GEN_MODEL_LEN"] = str(
                settings.get("gen_model_len", DEFAULT_SETTINGS["gen_model_len"])
            )
            env["JUDGE_MODEL"] = str(
                settings.get("judge_model", DEFAULT_SETTINGS["judge_model"])
            )
            env["JUDGE_MODEL_LEN"] = str(
                settings.get("judge_model_len", DEFAULT_SETTINGS["judge_model_len"])
            )
            # 실행 모드: debug 면 학습/평가 데이터의 일부(TRAIN_FRACTION)만 사용한다.
            env["MODE"] = paths["mode"]
            env["TRAIN_FRACTION"] = paths["train_fraction"]
            env.setdefault("PYTHONUNBUFFERED", "1")

            cmd = ["bash", str(AUTO_SH)]

            logf = open(LOG_FILE, "wb")
            header = (
                "==> Web launcher\n"
                f"  cmd            : {' '.join(cmd)}\n"
                f"  MODE           : {env['MODE']} ({paths['train_fraction_label']})\n"
                f"  TRAIN_FRACTION : {env['TRAIN_FRACTION']}\n"
                f"  CONFIG_PATH    : {env['CONFIG_PATH']}\n"
                f"  RUN_DIR        : {env['RUN_DIR']}\n"
                f"  merged model   : {paths['merged_model']}\n"
                f"  generated dir  : {paths['generated_dir']}\n"
                f"  evaluated glob : {paths['evaluated_glob']}\n"
                f"  SEED           : {env['SEED']}\n"
                f"  GPU            : {env['GPU']}\n"
                f"  GEN_MODEL_LEN  : {env['GEN_MODEL_LEN']}\n"
                f"  JUDGE_MODEL    : {env['JUDGE_MODEL']}\n"
                f"  JUDGE_MODEL_LEN: {env['JUDGE_MODEL_LEN']}\n\n"
            )
            logf.write(header.encode("utf-8"))
            logf.flush()

            self.proc = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                env=env,
                stdout=logf,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # 자식 프로세스까지 함께 종료할 수 있도록
            )
            self.last_returncode = None
            return {"ok": True}

    def stop(self) -> Dict[str, Any]:
        with self.lock:
            if self.proc is None or self.proc.poll() is not None:
                return {"ok": False, "error": "실행 중인 작업이 없습니다."}
            pid = self.proc.pid
            try:
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            proc = self.proc
        # 락 밖에서 대기
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        with self.lock:
            self.last_returncode = proc.poll()
        return {"ok": True}

    def status(self) -> Dict[str, Any]:
        with self.lock:
            running = self.proc is not None and self.proc.poll() is None
            rc = None if running else (self.proc.poll() if self.proc else self.last_returncode)
            return {"running": running, "returncode": rc}

    def clear(self) -> None:
        """종료된 프로세스 핸들과 종료코드를 버려 대기 상태로 되돌린다."""
        with self.lock:
            if self.proc is not None and self.proc.poll() is None:
                return
            self.proc = None
            self.last_returncode = None


pipeline = Pipeline()


# ---------------------------------------------------------------------------
# 결과 집계 (logickor_eval/score.py 와 동일한 로직)
# ---------------------------------------------------------------------------
# 실행 전(또는 실행 중) 표시용 0 초기화 결과값.
# 채점이 완료되면 compute_results() 가 계산한 실제 값으로 대체된다.
_CATEGORY_NAMES = [
    "추론(Reasoning)",
    "수학(Math)",
    "글쓰기(Writing)",
    "코딩(Coding)",
    "이해(Understanding)",
    "문법(Grammar)",
]
ZERO_RESULTS: Dict[str, Any] = {
    "available": True,
    "completed": False,
    "pattern": "evaluated/*.jsonl",
    "files": [],
    "categories": [
        {"category": name, "single": 0.0, "multi": 0.0}
        for name in _CATEGORY_NAMES
    ],
    "single_turn": 0.0,
    "multi_turn": 0.0,
    "overall": 0.0,
    "count": 0,
}


def _extract_scores(item: Dict[str, Any]) -> Optional[tuple]:
    if "query_single" in item and "query_multi" in item:
        return item["query_single"]["judge_score"], item["query_multi"]["judge_score"]
    if "judge_single_score" in item and "judge_multi_score" in item:
        return item["judge_single_score"], item["judge_multi_score"]
    return None


def compute_results(evaluated_glob: str) -> Dict[str, Any]:
    pattern = str(PROJECT_ROOT / evaluated_glob)
    files = glob.glob(pattern, recursive=True)
    if not files:
        return {"available": False, "pattern": evaluated_glob, "files": []}

    cat: Dict[str, Dict[str, List[float]]] = {}
    total_single: List[float] = []
    total_multi: List[float] = []

    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8-sig") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    scores = _extract_scores(item)
                    if scores is None:
                        continue
                    s, m = scores
                    category = item.get("category", "기타")
                    cat.setdefault(category, {"s": [], "m": []})
                    cat[category]["s"].append(s)
                    cat[category]["m"].append(m)
                    total_single.append(s)
                    total_multi.append(m)
        except Exception:
            continue

    if not total_single:
        return {"available": False, "pattern": evaluated_glob, "files": files}

    categories = []
    for name, sc in cat.items():
        avg_s = sum(sc["s"]) / len(sc["s"])
        avg_m = sum(sc["m"]) / len(sc["m"])
        categories.append(
            {"category": name, "single": round(avg_s, 2), "multi": round(avg_m, 2)}
        )

    avg_total_single = sum(total_single) / len(total_single)
    avg_total_multi = sum(total_multi) / len(total_multi)
    avg_total = (avg_total_single + avg_total_multi) / 2

    return {
        "available": True,
        "pattern": evaluated_glob,
        "files": [os.path.relpath(f, PROJECT_ROOT) for f in files],
        "categories": categories,
        "single_turn": round(avg_total_single, 2),
        "multi_turn": round(avg_total_multi, 2),
        "overall": round(avg_total, 2),
        "count": len(total_single),
    }


# ---------------------------------------------------------------------------
# 진행 상황 파싱 (auto.sh 로그를 읽어 단계별 상태 + tqdm 진행률 추출)
# ---------------------------------------------------------------------------
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
# auto.sh 의 step() 은 다음 형태로 단계 시작을 알린다.
#   [2026-08-06 11:22:33] Step 2/4: generating LogicKor answers with runs/.../merged
# (Step 0/4 = 이전 산출물 정리)
STAGE_RE = re.compile(r"^\[[^\]\n]*\]\s*Step\s*(\d)\s*/\s*4\s*:", re.MULTILINE)
# 마지막 step() 호출 문구
FINISH_MARK = "Pipeline finished successfully"

# tqdm 진행 줄 한 개를 통째로 파싱한다.
#   "Loading weights:  42%|████▏     | 169/399 [00:03<00:07, 45.2it/s]"
#   " 32%|███▏      | 50/156 [05:00<10:00, 1.2s/it, loss=1.02]"
TQDM_RE = re.compile(
    r"(?:(?P<desc>[A-Za-z][A-Za-z0-9 ()/_.\-]*?)\s*:\s*)?"  # 선택적 설명(라벨)
    r"(?P<pct>\d{1,3})%\|[^|\n]*\|\s*"                       # 퍼센트 + 막대
    r"(?P<cur>\d+)\s*/\s*(?P<total>\d+)"                     # 현재/전체
    r"(?:\s*\[(?P<meta>[^\]]*)\])?"                          # 선택적 [경과<ETA, 속도]
)
META_RE = re.compile(r"^\s*([0-9:]+)\s*<\s*([0-9:?]+)\s*,?\s*(.*)$")

# (key, 영문명, 국문명) — auto.sh 의 Step 0/4 ~ Step 4/4 와 같은 순서
STAGE_DEFS = [
    ("clean", "Clean", "정리"),
    ("train", "Train", "학습"),
    ("generate", "Generate", "생성"),
    ("evaluate", "Evaluate", "평가"),
    ("score", "Score", "채점"),
]
STAGE_ORDER = [d[0] for d in STAGE_DEFS]

# 전체 진행률 가중치(합 1.0). 단계별 소요 시간이 크게 다르므로 균등 분배하지 않는다.
STAGE_WEIGHTS = {
    "clean": 0.01,
    "train": 0.55,
    "generate": 0.17,
    "evaluate": 0.25,
    "score": 0.02,
}

# tqdm 설명 라벨 → 사람이 읽기 좋은 국문 세부 작업명
SUBTASK_KO = {
    "Loading weights": "가중치 로딩",
    "Tokenizing train dataset": "학습 데이터 토크나이징",
    "Tokenizing eval dataset": "평가 데이터 토크나이징",
    "Writing model shards": "모델 병합 저장",
    "Map": "데이터셋 매핑",
    "Rendering prompts": "프롬프트 준비",
    "Processed prompts": "응답 생성",
    "Adding requests": "요청 준비",
}
# 라벨이 없는 tqdm 바(예: Trainer 학습 루프)의 단계별 기본 세부 작업명
STAGE_DEFAULT_SUB = {
    "clean": "이전 산출물 삭제",
    "train": "학습 스텝",
    "generate": "생성 진행",
    "evaluate": "채점 추론",
    "score": "집계",
}

# 전체 진행률을 단조증가로 유지하기 위한 상태(새 실행 감지 시 초기화).
_overall_state = {"done_units": -1, "max": 0.0}


def reset_run_state() -> None:
    """실행 상태(로그 · 단계 진행률 · 종료코드)를 실행 전 상태로 되돌린다.

    호출 시점: 웹 서비스 기동(run.sh), 중지 버튼, 실행 시작.
    로그 파일이 사라지면 parse_progress() 는 started=False 를 돌려주므로
    스텝퍼 · 진행률 · 점수(ZERO_RESULTS)가 모두 초기 상태로 표시된다.
    학습 산출물(runs/, generated/, evaluated/)은 건드리지 않는다.
    """
    try:
        LOG_FILE.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass
    _overall_state["done_units"] = -1
    _overall_state["max"] = 0.0
    pipeline.clear()


def _parse_last_tqdm(region: str, stage_key: str) -> Dict[str, Any]:
    """단계 구간에서 마지막 tqdm 진행 줄을 찾아 구조화한다."""
    last = None
    for line in region.split("\n"):
        m = TQDM_RE.search(line)
        if m:
            last = m
    if last is None:
        return {}

    cur = int(last.group("cur"))
    total = int(last.group("total"))
    pct_raw = int(last.group("pct"))
    # 분수(현재/전체)가 있으면 소수점까지 정밀하게, 없으면 정수 퍼센트 사용
    if total > 0:
        percent = min(cur / total * 100.0, 100.0)
    else:
        percent = float(min(pct_raw, 100))

    desc = (last.group("desc") or "").strip()
    sub = SUBTASK_KO.get(desc) or desc or STAGE_DEFAULT_SUB.get(stage_key, "")

    eta = ""
    rate = ""
    meta = (last.group("meta") or "").strip()
    if meta:
        mm = META_RE.match(meta)
        if mm:
            eta = mm.group(2)
            rate = mm.group(3).strip()
        else:
            rate = meta

    return {
        "sub": sub,
        "current": cur,
        "total": total,
        "percent": round(percent, 1),
        "eta": eta,
        "rate": rate,
    }


def parse_progress(running: bool) -> Dict[str, Any]:
    text = ""
    if LOG_FILE.exists():
        try:
            text = LOG_FILE.read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = ""
    clean = ANSI_RE.sub("", text)

    status = {k: "pending" for k in STAGE_ORDER}
    started = "==> Web launcher" in clean
    finished = FINISH_MARK in clean

    # 단계 마커 수집: (key, marker_end_pos). Step 0/4 -> clean, Step 4/4 -> score
    marks = []
    for m in STAGE_RE.finditer(clean):
        idx = int(m.group(1))
        if 0 <= idx < len(STAGE_ORDER):
            marks.append((STAGE_ORDER[idx], m.end()))

    for key, _ in marks:
        status[key] = "done"

    # 가장 마지막으로 시작된 단계가 현재 실행 단계
    active = marks[-1] if marks else None

    current = None
    percent = 0.0
    detail = ""
    info: Dict[str, Any] = {}
    if running and not finished and active is not None:
        current = active[0]
        status[current] = "running"
        # 현재 단계 구간(active 마커 이후, 다음 마커 전까지)에서 마지막 tqdm 진행률 추출
        region_end = len(clean)
        for _k, pos in marks:
            if active[1] < pos < region_end:
                region_end = pos
        region = clean[active[1]:region_end].replace("\r", "\n")
        info = _parse_last_tqdm(region, current)
        if info:
            percent = info["percent"]
            bits = [f"{info['current']}/{info['total']}"]
            if info.get("eta"):
                bits.append(f"남은시간 {info['eta']}")
            if info.get("rate"):
                bits.append(info["rate"])
            detail = " · ".join(bits)
    elif started and not running and not finished and active is not None:
        # 중지되었거나 오류로 종료됨
        status[active[0]] = "stopped"

    # 전체 진행률: 완료 단계는 가중치 전부, 실행 중 단계는 가중치 × 현재 %
    done_units = 0.0
    units = 0.0
    for k in STAGE_ORDER:
        w = STAGE_WEIGHTS[k]
        if status[k] == "done":
            units += w
            done_units += 1
        elif status[k] == "running":
            units += w * percent / 100.0
    overall = round(units * 100, 1)
    if finished:
        overall = 100.0

    # 전체 진행률 단조증가 유지: 완료 단계 수가 줄면(=새 실행) 초기화
    if not started:
        _overall_state["done_units"] = -1
        _overall_state["max"] = 0.0
    else:
        if done_units < _overall_state["done_units"]:
            _overall_state["max"] = 0.0
        _overall_state["done_units"] = done_units
        if overall < _overall_state["max"]:
            overall = _overall_state["max"]
        else:
            _overall_state["max"] = overall

    stages = [
        {"key": k, "name": name, "ko": ko, "status": status[k]}
        for (k, name, ko) in STAGE_DEFS
    ]
    return {
        "running": running,
        "started": started,
        "finished": finished,
        "stages": stages,
        "current": current,
        "percent": percent,
        "detail": detail,
        "overall": overall,
        # 세부 진행 정보 (로그 기반)
        "sub": info.get("sub", ""),
        "current_step": info.get("current"),
        "total_step": info.get("total"),
        "eta": info.get("eta", ""),
        "rate": info.get("rate", ""),
    }


# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서비스 기동(web/run.sh) 시 이전 실행에서 남은 로그 · 진행률을 지우고 시작한다.
    reset_run_state()
    yield


app = FastAPI(title="Logickor 평가 웹", lifespan=lifespan)


class SettingsIn(BaseModel):
    """auto.sh 의 환경변수와 1:1 대응."""

    config_path: Optional[str] = None      # CONFIG_PATH
    run_dir: Optional[str] = None          # RUN_DIR
    seed: Optional[str] = None             # SEED
    gpu: Optional[str] = None              # GPU
    gen_model_len: Optional[str] = None    # GEN_MODEL_LEN
    judge_model: Optional[str] = None      # JUDGE_MODEL
    judge_model_len: Optional[str] = None  # JUDGE_MODEL_LEN
    mode: Optional[str] = None             # MODE (full | debug)
    train_fraction: Optional[str] = None   # TRAIN_FRACTION (debug 모드에서만 적용)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((WEB_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/sample.png")
def sample_png():
    if SAMPLE_PNG.exists():
        return FileResponse(str(SAMPLE_PNG), media_type="image/png")
    return JSONResponse({"error": "sample.png not found"}, status_code=404)


@app.get("/api/settings")
def api_get_settings():
    s = load_settings()
    return {
        "settings": s,
        "derived": derive_paths(s),
        "defaults": DEFAULT_SETTINGS,
        "configs": sorted(
            os.path.relpath(p, PROJECT_ROOT)
            for p in glob.glob(str(PROJECT_ROOT / "configs" / "*.yaml"))
        ),
        "judge_presets": JUDGE_MODEL_PRESETS,
        "modes": MODES,
    }


@app.post("/api/settings")
def api_post_settings(payload: SettingsIn):
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    s = save_settings(data)
    return {"ok": True, "settings": s, "derived": derive_paths(s)}


@app.post("/api/reset")
def api_reset():
    s = save_settings(dict(DEFAULT_SETTINGS))
    return {"ok": True, "settings": s, "derived": derive_paths(s)}


@app.get("/api/config-file")
def api_get_config_file(path: str):
    """선택된 config yaml 파일 내용 조회."""
    target = (PROJECT_ROOT / path).resolve()
    if PROJECT_ROOT not in target.parents and target != PROJECT_ROOT:
        return JSONResponse({"ok": False, "error": "경로 벗어남"}, status_code=400)
    if not target.exists():
        return {"ok": False, "error": "파일이 없습니다.", "content": ""}
    return {"ok": True, "content": target.read_text(encoding="utf-8")}


class ConfigFileIn(BaseModel):
    path: str
    content: str


@app.post("/api/config-file")
def api_post_config_file(payload: ConfigFileIn):
    target = (PROJECT_ROOT / payload.path).resolve()
    if PROJECT_ROOT not in target.parents:
        return JSONResponse({"ok": False, "error": "경로 벗어남"}, status_code=400)
    target.write_text(payload.content, encoding="utf-8")
    return {"ok": True}


@app.post("/api/start")
def api_start():
    if pipeline.is_running():
        return {"ok": False, "error": "이미 실행 중입니다."}
    s = load_settings()
    reset_run_state()          # 새 실행 전에 이전 로그 · 진행률 제거
    return pipeline.start(s)


@app.post("/api/stop")
def api_stop():
    res = pipeline.stop()
    reset_run_state()          # 중지하면 실행 전 상태로 초기화
    return res


@app.get("/api/status")
def api_status():
    st = pipeline.status()
    st["started"] = LOG_FILE.exists()
    return st


@app.get("/api/logs")
def api_logs(offset: int = 0):
    if not LOG_FILE.exists():
        return {"data": "", "offset": 0, "running": pipeline.is_running()}
    with open(LOG_FILE, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        if offset > size:
            offset = 0
        fh.seek(offset)
        chunk = fh.read()
    return {
        "data": chunk.decode("utf-8", errors="replace"),
        "offset": offset + len(chunk),
        "running": pipeline.is_running(),
    }


@app.get("/api/progress")
def api_progress():
    return parse_progress(pipeline.is_running())


@app.get("/api/results")
def api_results():
    # 파이프라인이 완료("Pipeline finished successfully")된 경우에는 실제 채점 결과
    # (evaluated/*.jsonl 집계)를 계산해 그래프에 반영하고,
    # 그 전(실행 전 · 실행 중)에는 모든 점수를 0 으로 초기화한 값을 반환한다.
    prog = parse_progress(pipeline.is_running())
    if prog.get("finished"):
        s = load_settings()
        paths = derive_paths(s)
        res = compute_results(paths["evaluated_glob"])
        if res.get("available"):
            res["completed"] = True
            return res
    return dict(ZERO_RESULTS)


class _SilencePollEndpoints(logging.Filter):
    """폴링용 엔드포인트(/api/logs, /api/progress)의 접근 로그를 숨긴다."""

    _SILENCED = ("/api/logs", "/api/progress")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(ep in msg for ep in self._SILENCED)


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    print(f"Logickor 평가 웹 서비스 -> http://{host}:{port}")
    logging.getLogger("uvicorn.access").addFilter(_SilencePollEndpoints())
    uvicorn.run(app, host=host, port=port, log_level="info")
