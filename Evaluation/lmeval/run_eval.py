#!/usr/bin/env python
"""
run_eval.py — lm-evaluation-harness 로 대표 벤치마크 + 한국어 + 생성형 지표를
순차 평가하고, 진행 상황을 status.json 으로 실시간 기록한다.

단독 실행 (--model 은 HF repo id / 캐시 디렉터리 / 로컬 스냅샷 모두 가능):
  python run_eval.py --model Qwen/Qwen3-8B \
      --tasks arc_easy,hellaswag,kobest_boolq,squadv2 --limit 50 --out runs/test
  python run_eval.py --model google/gemma-4-E4B-it --tasks kobest_boolq --limit 20

캐시에 없는 repo id 는 자동으로 내려받는다. gated 모델은 `export HF_TOKEN=...` 필요.

웹 UI(app.py)는 이 스크립트를 서브프로세스로 띄우고 status.json / run.log 를 읽는다.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
import traceback
from typing import Any

import eval_tasks as REG
from model_loader import (download_model, load_model, load_tokenizer,
                          model_status, pretty_model_name, resolve_model_path)

STATUS_NAME = "status.json"
_state: dict[str, Any] = {}
_out_dir = "."
_last_write = 0.0
_stopping = False


# --------------------------------------------------------------------------
# 상태 기록
# --------------------------------------------------------------------------
def log(*a) -> None:
    print(*a, flush=True)


def write_status(force: bool = True) -> None:
    global _last_write
    now = time.time()
    if not force and (now - _last_write) < 0.4:
        return
    _last_write = now
    _state["updated_at"] = now
    _state["elapsed"] = round(now - _state.get("started_at", now), 1)
    path = os.path.join(_out_dir, STATUS_NAME)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_state, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] status 기록 실패: {e}", file=sys.stderr, flush=True)


def set_stage(key: str, status: str, note: str = "") -> None:
    for s in _state["stages"]:
        if s["key"] == key:
            s["status"] = status
            if note:
                s["note"] = note
    write_status()


def recompute_overall() -> None:
    done = _state["progress"]["tasks_done"]
    total = max(_state["progress"]["tasks_total"], 1)
    cur = _state["progress"].get("current_pct", 0) / 100.0
    _state["progress"]["overall_pct"] = round(
        min(100.0, 100.0 * (done + cur) / total), 1)


# --------------------------------------------------------------------------
# tqdm 후킹 → 태스크 내부 진행률
# --------------------------------------------------------------------------
def install_tqdm_hook() -> None:
    try:
        from tqdm.std import tqdm as _tqdm
    except Exception:  # pragma: no cover
        return

    orig_update = _tqdm.update
    orig_init = _tqdm.__init__

    def _report(self) -> None:
        total = getattr(self, "total", None)
        if not total:
            return
        pct = 100.0 * (self.n or 0) / total
        p = _state["progress"]
        p["current_pct"] = round(min(100.0, pct), 1)
        p["current_desc"] = (getattr(self, "desc", "") or "").strip(": ")
        p["current_n"] = self.n
        p["current_total"] = total
        recompute_overall()
        write_status(force=False)

    def update(self, n=1):
        r = orig_update(self, n)
        try:
            _report(self)
        except Exception:
            pass
        return r

    def __init__(self, *a, **kw):
        orig_init(self, *a, **kw)
        try:
            _report(self)
        except Exception:
            pass

    _tqdm.update = update
    _tqdm.__init__ = __init__


# --------------------------------------------------------------------------
# 결과 파싱
# --------------------------------------------------------------------------
def already_percent(metric: str, value: float, pct: set[str]) -> bool:
    """이 지표가 이미 0~100 스케일로 보고되었는가. (규칙은 eval_tasks 참고)"""
    return metric in pct or metric in REG.UNBOUNDED or value > 1.0


def _fmt(metric: str, value: float, pct: set[str]) -> tuple[float, str]:
    """(표시값, 표기문자열). 0~1 스케일 지표만 %로 변환."""
    v = value if already_percent(metric, value, pct) else 100 * value
    return round(v, 2), f"{v:.2f}"


def extract_task_metrics(task: str, raw: dict, primary: list[str],
                        pct: set[str] | None = None) -> dict:
    """lm-eval 결과 dict → 정규화된 벤치마크 결과."""
    pct = pct or set()
    src = (raw.get("results") or {}).get(task)
    if src is None:
        src = (raw.get("groups") or {}).get(task)
    if src is None:  # 서브태스크만 있는 경우 평균 시도
        subs = {k: v for k, v in (raw.get("results") or {}).items()
                if k.startswith(task)}
        src = next(iter(subs.values()), {}) if subs else {}

    values: dict[str, float] = {}
    stderrs: dict[str, float] = {}
    filters: dict[str, str] = {}
    skip = {"alias", "sample_len", "samples"}   # 점수가 아닌 항목
    for k, v in (src or {}).items():
        if k in skip or str(k).partition(",")[0] in skip or not isinstance(v, (int, float)):
            continue
        name, _, filt = str(k).partition(",")
        if name.endswith("_stderr"):
            stderrs[name[:-len("_stderr")]] = float(v)
        else:
            # 같은 지표가 여러 filter 로 있으면 먼저 나온(=대표) 값 유지
            if name not in values:
                values[name] = float(v)
                filters[name] = filt or "none"

    metrics = []
    for name, val in values.items():
        disp, txt = _fmt(name, val, pct)
        # stderr 은 값과 동일한 스케일로 변환해야 한다.
        se = stderrs.get(name)
        if se is not None:
            se = round(se if already_percent(name, val, pct) else 100 * se, 2)
        metrics.append({
            "metric": name,
            "label": REG.METRIC_LABELS.get(name, name),
            "filter": filters.get(name, "none"),
            "raw": val,
            "value": disp,
            "text": txt,
            "stderr": se,
        })

    pick = None
    for cand in primary:
        if cand in values:
            pick = cand
            break
    if pick is None and metrics:
        pick = metrics[0]["metric"]

    pm = next((m for m in metrics if m["metric"] == pick), None)
    return {
        "primary_metric": pick,
        "primary_label": pm["label"] if pm else None,
        "primary_value": pm["value"] if pm else None,
        "metrics": metrics,
        "n_samples": (raw.get("n-samples") or {}).get(task, {}).get("effective"),
    }


def summarize() -> None:
    """그룹 평균 / 생성형 지표 / 레이더 카테고리 집계."""
    bms = _state["results"]["benchmarks"]
    done = [b for b in bms if b.get("primary_value") is not None]

    def avg(items):
        vals = [b["primary_value"] for b in items]
        return round(sum(vals) / len(vals), 2) if vals else None

    summary = {
        "core_en": avg([b for b in done if b["group"] == "core_en"]),
        "korean": avg([b for b in done if b["group"] == "korean"]),
        "generative": avg([b for b in done if b["group"] == "generative"]),
        "custom": avg([b for b in done if b["group"] == "custom"]),
        "overall": avg(done),
        "counts": {g: len([b for b in done if b["group"] == g])
                   for g in ("core_en", "korean", "generative", "custom")},
    }

    # 생성형 지표 표 (F1/EM/BLEU/ROUGE)
    gen_rows = []
    want = ("f1", "best_f1", "exact", "em", "exact_match",
            "bleu", "bleu_max", "bleu_acc",
            "rouge1", "rouge1_max", "rouge2", "rouge2_max", "rougeL", "rougeL_max")
    for b in bms:
        if b["group"] not in ("generative", "custom"):
            continue
        picked = {m["metric"]: m["value"] for m in b.get("metrics", [])
                  if m["metric"] in want}
        if picked:
            gen_rows.append({"key": b["key"], "label": b["label"], "metrics": picked})
    summary["generative_table"] = gen_rows

    # 레이더: 카테고리별 평균
    cats: dict[str, list[float]] = {}
    for b in done:
        cats.setdefault(b.get("category") or "기타", []).append(b["primary_value"])
    summary["radar"] = [{"category": c, "value": round(sum(v) / len(v), 2)}
                        for c, v in cats.items()]

    _state["results"]["summary"] = summary
    write_status()


# --------------------------------------------------------------------------
# 메인 평가 루프
# --------------------------------------------------------------------------
def build_stages(sel_items: list[dict], has_custom: bool) -> list[dict]:
    stages = [
        dict(key="prepare", name="Prepare", sub="준비", status="pending"),
        dict(key="download", name="Download", sub="모델 내려받기", status="pending"),
        dict(key="load", name="Load", sub="모델 로드", status="pending"),
    ]
    if any(i["group"] == "core_en" for i in sel_items):
        stages.append(dict(key="core_en", name="English", sub="영어 벤치마크",
                           status="pending"))
    if any(i["group"] == "korean" for i in sel_items):
        stages.append(dict(key="korean", name="Korean", sub="한국어 벤치마크",
                           status="pending"))
    if any(i["group"] == "generative" for i in sel_items):
        stages.append(dict(key="generative", name="Generative",
                           sub="생성형(F1/BLEU/ROUGE)", status="pending"))
    if has_custom:
        stages.append(dict(key="custom", name="Custom", sub="커스텀 파일",
                           status="pending"))
    stages.append(dict(key="score", name="Score", sub="집계", status="pending"))
    return stages


def main() -> int:
    global _out_dir, _stopping

    ap = argparse.ArgumentParser(description="lm-eval-harness 통합 평가 러너")
    ap.add_argument("--model", required=True,
                    help="HF repo id(예: Qwen/Qwen3-8B) 또는 로컬/캐시 경로")
    ap.add_argument("--no-download", action="store_true",
                    help="캐시에 없어도 내려받지 않는다(오프라인)")
    ap.add_argument("--tasks", default=",".join(REG.DEFAULT_SELECTED),
                    help="eval_tasks.py 의 key 목록(콤마 구분)")
    ap.add_argument("--out", default="runs/latest")
    ap.add_argument("--limit", type=int, default=None,
                    help="태스크별 최대 샘플 수(스모크 테스트용)")
    ap.add_argument("--num-fewshot", type=int, default=None,
                    help="모든 태스크에 강제 적용할 few-shot 수(미지정=권장값)")
    ap.add_argument("--batch-size", default="8", help="정수 또는 auto")
    ap.add_argument("--max-batch-size", type=int, default=32)
    ap.add_argument("--dtype", default="bfloat16")
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--gpus", default="0", help="CUDA_VISIBLE_DEVICES 값")
    ap.add_argument("--max-length", type=int, default=4096)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--apply-chat-template", action="store_true")
    ap.add_argument("--fewshot-as-multiturn", action="store_true")
    ap.add_argument("--log-samples", action="store_true")
    ap.add_argument("--trust-remote-code", action="store_true", default=True)
    ap.add_argument("--parallelize", action="store_true",
                    help="여러 GPU 에 모델을 분산(device_map=auto)")
    ap.add_argument("--add-bos-token", default="auto",
                    choices=["auto", "true", "false"],
                    help="loglikelihood 입력에 BOS 추가 (gemma 계열은 auto→true)")
    # 커스텀 파일 평가
    ap.add_argument("--custom-file", default=None)
    ap.add_argument("--custom-max-new-tokens", type=int, default=256)
    ap.add_argument("--custom-lang", default="auto", choices=["auto", "ko", "en"])
    ap.add_argument("--custom-system-prompt", default=None)
    args = ap.parse_args()

    _out_dir = os.path.abspath(args.out)
    os.makedirs(_out_dir, exist_ok=True)
    os.makedirs(os.path.join(_out_dir, "tasks"), exist_ok=True)

    if args.gpus:
        os.environ.setdefault("CUDA_VISIBLE_DEVICES", str(args.gpus))
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("HF_DATASETS_TRUST_REMOTE_CODE", "1")

    sel_keys = [k.strip() for k in args.tasks.split(",") if k.strip()]
    sel_items = REG.resolve(sel_keys)
    unknown = sorted(set(sel_keys) - {i["key"] for i in sel_items})
    has_custom = any(i["group"] == "custom" for i in sel_items) and bool(args.custom_file)
    harness_items = [i for i in sel_items if i.get("task")]

    resolved = resolve_model_path(args.model)
    mstat = model_status(args.model)
    total_units = len(harness_items) + (1 if has_custom else 0)

    _state.clear()
    _state.update({
        "state": "running",
        "started_at": time.time(),
        "pid": os.getpid(),
        "model": {
            "input": args.model,
            "resolved": resolved,
            "name": pretty_model_name(resolved),
            "cached": mstat["cached"],
            "repo_id": mstat["repo_id"],
            "snapshot": mstat["snapshot"],
            "hf_token": mstat["hf_token"],
        },
        "config": {
            "tasks": sel_keys,
            "limit": args.limit,
            "num_fewshot": args.num_fewshot,
            "batch_size": args.batch_size,
            "dtype": args.dtype,
            "device": args.device,
            "gpus": args.gpus,
            "max_length": args.max_length,
            "seed": args.seed,
            "apply_chat_template": args.apply_chat_template,
            "add_bos_token": args.add_bos_token,
            "custom_file": args.custom_file,
            "out": _out_dir,
        },
        "stages": build_stages(sel_items, has_custom),
        "progress": {
            "tasks_total": total_units, "tasks_done": 0,
            "overall_pct": 0.0, "current_pct": 0.0,
            "current_task": None, "current_label": None,
            "current_desc": "", "current_index": 0,
        },
        "results": {"benchmarks": [], "summary": {}},
        "warnings": ([f"알 수 없는 벤치마크 key: {', '.join(unknown)}"] if unknown else []),
        "error": None,
    })
    write_status()

    def on_sigterm(signum, frame):  # noqa: ARG001
        global _stopping
        _stopping = True
        _state["state"] = "stopped"
        set_stage_running_to("stopped")
        write_status()
        log("\n[stop] 중지 신호를 받았습니다. 정리 후 종료합니다.")
        raise SystemExit(130)

    signal.signal(signal.SIGTERM, on_sigterm)
    signal.signal(signal.SIGINT, on_sigterm)

    log(f"=== lm-eval 통합 평가 시작 ===")
    log(f"모델      : {args.model}")
    log(f"실제 경로 : {resolved}")
    log(f"캐시      : {'있음 · ' + str(mstat['snapshot']) if mstat['cached'] else '없음 (다운로드 필요)'}")
    log(f"HF_TOKEN  : {'설정됨' if mstat['hf_token'] else '없음'}")
    log(f"벤치마크  : {[i['key'] for i in sel_items]}")
    log(f"출력      : {_out_dir}")
    log(f"limit={args.limit} batch_size={args.batch_size} dtype={args.dtype} "
        f"few-shot={'권장값' if args.num_fewshot is None else args.num_fewshot} "
        f"chat_template={args.apply_chat_template}")

    try:
        set_stage("prepare", "running")
        install_tqdm_hook()
        import lm_eval
        from lm_eval.models.huggingface import HFLM
        from lm_eval.utils import setup_logging
        try:
            setup_logging(verbosity="INFO")
        except Exception:
            pass
        log(f"[prepare] lm-eval {getattr(lm_eval, '__version__', '?')}")
        set_stage("prepare", "done")

        # ---------------- 모델 다운로드 (캐시에 없으면) ----------------
        set_stage("download", "running")
        if args.no_download:
            if not mstat["cached"]:
                raise FileNotFoundError(
                    f"--no-download 인데 캐시에 모델이 없습니다: {args.model}")
            resolved = mstat["snapshot"]
            set_stage("download", "done", "캐시 사용")
            log(f"[download] --no-download · 캐시 사용: {resolved}")
        else:
            _state["progress"]["current_label"] = "모델 내려받기"
            _state["progress"]["current_desc"] = pretty_model_name(args.model)
            write_status()
            resolved = download_model(args.model, log=log)
            _state["model"]["resolved"] = resolved
            _state["model"]["snapshot"] = resolved
            _state["model"]["cached"] = True
            _state["progress"].update(current_pct=0.0, current_desc="",
                                      current_label=None)
            set_stage("download", "done",
                      "캐시 사용" if mstat["cached"] else "다운로드 완료")

        # ---------------- 모델 로드 ----------------
        set_stage("load", "running")
        tok = load_tokenizer(resolved, args.trust_remote_code)
        hf_model = load_model(
            resolved, dtype=args.dtype,
            device_map="auto" if (args.parallelize or "," in str(args.gpus)) else None,
            trust_remote_code=args.trust_remote_code, log=log)
        if not args.parallelize and "," not in str(args.gpus):
            import torch
            if torch.cuda.is_available():
                hf_model.to("cuda:0")
        bs = args.batch_size if args.batch_size == "auto" else int(args.batch_size)
        if args.add_bos_token == "auto":
            # gemma 계열은 BOS 없이 평가하면 점수가 크게 떨어진다(하네스 공식 권고).
            hint = (resolved + " " + str(getattr(hf_model.config, "model_type", ""))).lower()
            add_bos = any(k in hint for k in ("gemma", "llama", "mistral"))
        else:
            add_bos = args.add_bos_token == "true"
        log(f"[load] add_bos_token={add_bos}")
        lm = HFLM(
            pretrained=hf_model, tokenizer=tok, backend="causal",
            batch_size=bs, max_batch_size=args.max_batch_size,
            max_length=args.max_length, trust_remote_code=args.trust_remote_code,
            add_bos_token=add_bos,
        )
        _state["model"]["dtype"] = str(getattr(hf_model, "dtype", args.dtype))
        _state["model"]["params"] = sum(p.numel() for p in hf_model.parameters())
        set_stage("load", "done")
        log(f"[load] 완료 · 파라미터 {_state['model']['params'] / 1e9:.2f}B")

        # ---------------- 벤치마크 루프 ----------------
        cur_group = None
        for idx, item in enumerate(harness_items):
            if _stopping:
                break
            group = item["group"]
            if group != cur_group:
                if cur_group:
                    set_stage(cur_group, "done")
                cur_group = group
                set_stage(group, "running")

            p = _state["progress"]
            p.update(current_task=item["task"], current_label=item["label"],
                     current_index=idx + 1, current_pct=0.0, current_desc="")
            recompute_overall()
            write_status()
            log(f"\n[{idx + 1}/{len(harness_items)}] {item['label']} "
                f"(task={item['task']}) 평가 중 ...")

            nfs = args.num_fewshot if args.num_fewshot is not None else item.get("num_fewshot")
            t0 = time.time()
            entry = {
                "key": item["key"], "label": item["label"], "group": group,
                "task": item["task"], "category": item.get("category"),
                "num_fewshot": nfs, "status": "running",
            }
            _state["results"]["benchmarks"].append(entry)
            write_status()

            try:
                raw = lm_eval.simple_evaluate(
                    model=lm,
                    tasks=[item["task"]],
                    num_fewshot=nfs,
                    limit=args.limit,
                    batch_size=bs,
                    apply_chat_template=args.apply_chat_template,
                    fewshot_as_multiturn=(args.fewshot_as_multiturn
                                          and args.apply_chat_template),
                    log_samples=args.log_samples,
                    random_seed=args.seed,
                    numpy_random_seed=args.seed,
                    torch_random_seed=args.seed,
                    fewshot_random_seed=args.seed,
                    verbosity="WARNING",
                )
                parsed = extract_task_metrics(item["task"], raw,
                                              item.get("primary", []),
                                              REG.pct_metrics(item))
                entry.update(parsed, status="done",
                             elapsed=round(time.time() - t0, 1))
                log(f"    → {entry.get('primary_label')}: "
                    f"{entry.get('primary_value')}  ({entry['elapsed']}s)")

                dump = {k: v for k, v in raw.items() if k != "samples"}
                with open(os.path.join(_out_dir, "tasks", f"{item['key']}.json"),
                          "w", encoding="utf-8") as f:
                    json.dump(dump, f, ensure_ascii=False, indent=2, default=str)
                if args.log_samples and raw.get("samples"):
                    sp = os.path.join(_out_dir, "tasks", f"{item['key']}_samples.jsonl")
                    with open(sp, "w", encoding="utf-8") as f:
                        for tname, rows in raw["samples"].items():
                            for r in rows:
                                f.write(json.dumps(
                                    {"task": tname, **r}, ensure_ascii=False,
                                    default=str) + "\n")
            except SystemExit:
                raise
            except Exception as e:  # noqa: BLE001
                entry.update(status="error", error=f"{type(e).__name__}: {e}",
                             elapsed=round(time.time() - t0, 1))
                _state["warnings"].append(f"{item['label']} 실패: {type(e).__name__}: {e}")
                log(f"    !! 실패: {type(e).__name__}: {e}")
                traceback.print_exc()

            p["tasks_done"] += 1
            p["current_pct"] = 0.0
            recompute_overall()
            summarize()

        if cur_group:
            set_stage(cur_group, "done")

        # ---------------- 커스텀 파일 평가 ----------------
        if has_custom and not _stopping:
            set_stage("custom", "running")
            import custom_eval
            citem = next(i for i in sel_items if i["group"] == "custom")
            p = _state["progress"]
            p.update(current_task="custom_file", current_label=citem["label"],
                     current_pct=0.0, current_index=len(harness_items) + 1)
            write_status()
            log(f"\n[custom] {args.custom_file} 평가 중 ...")
            entry = {"key": citem["key"], "label": citem["label"], "group": "custom",
                     "task": None, "category": citem.get("category"),
                     "status": "running"}
            _state["results"]["benchmarks"].append(entry)
            t0 = time.time()

            def cprog(done: int, total: int) -> None:
                _state["progress"]["current_pct"] = round(100.0 * done / max(total, 1), 1)
                _state["progress"]["current_desc"] = f"생성 {done}/{total}"
                recompute_overall()
                write_status(force=False)

            try:
                cres = custom_eval.run_custom_eval(
                    resolved, args.custom_file, _out_dir, limit=args.limit,
                    max_new_tokens=args.custom_max_new_tokens,
                    batch_size=int(bs) if str(bs).isdigit() else 8,
                    lang=args.custom_lang, system_prompt=args.custom_system_prompt,
                    use_chat_template=args.apply_chat_template or True,
                    model=hf_model, tokenizer=tok, log=log, progress=cprog)
                mets = []
                for name, val in cres["metrics"].items():
                    mets.append({"metric": name,
                                 "label": REG.METRIC_LABELS.get(name, name),
                                 "filter": "none", "raw": val / 100.0,
                                 "value": round(val, 2), "text": f"{val:.2f}",
                                 "stderr": None})
                entry.update(status="done", metrics=mets,
                             primary_metric="f1", primary_label="F1",
                             primary_value=round(cres["metrics"]["f1"], 2),
                             n_samples=cres["count"], file=args.custom_file,
                             elapsed=round(time.time() - t0, 1))
            except Exception as e:  # noqa: BLE001
                entry.update(status="error", error=f"{type(e).__name__}: {e}")
                _state["warnings"].append(f"커스텀 평가 실패: {type(e).__name__}: {e}")
                log(f"    !! 커스텀 평가 실패: {type(e).__name__}: {e}")
                traceback.print_exc()
            p["tasks_done"] += 1
            p["current_pct"] = 0.0
            set_stage("custom", "done" if entry["status"] == "done" else "error")

        # ---------------- 집계 ----------------
        set_stage("score", "running")
        summarize()
        _state["progress"].update(overall_pct=100.0, current_pct=100.0,
                                  current_task=None, current_label="완료",
                                  current_desc="")
        _state["state"] = "done"
        set_stage("score", "done")

        with open(os.path.join(_out_dir, "results.json"), "w", encoding="utf-8") as f:
            json.dump({"model": _state["model"], "config": _state["config"],
                       "results": _state["results"],
                       "warnings": _state["warnings"],
                       "elapsed": _state["elapsed"]},
                      f, ensure_ascii=False, indent=2)
        write_status()

        s = _state["results"]["summary"]
        log("\n=== 완료 ===")
        log(f"영어 평균   : {s.get('core_en')}")
        log(f"한국어 평균 : {s.get('korean')}")
        log(f"생성형 평균 : {s.get('generative')}")
        log(f"종합        : {s.get('overall')}")
        log(f"결과 파일   : {os.path.join(_out_dir, 'results.json')}")
        return 0

    except SystemExit:
        write_status()
        return 130
    except Exception as e:  # noqa: BLE001
        _state["state"] = "error"
        _state["error"] = f"{type(e).__name__}: {e}"
        set_stage_running_to("error")
        write_status()
        traceback.print_exc()
        log(f"\n[error] {type(e).__name__}: {e}")
        return 1


def set_stage_running_to(status: str) -> None:
    for s in _state.get("stages", []):
        if s["status"] == "running":
            s["status"] = status


if __name__ == "__main__":
    sys.exit(main())
