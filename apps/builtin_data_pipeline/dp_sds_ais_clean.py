#!/usr/bin/env python3
"""데이터 파이프라인 — AIS 행 정제 노드(kind=filter, stage=sds_ais_clean).

    python3 -u /built_in/dp_sds_ais_clean.py --params_path=/dataset/_runs/<run_id>/<node_index>/params.json

AIS 적재 노드가 넘긴 행에서 쓸 수 없는 것을 제거한다 — 좌표가 0,0 인 행 · 침로가
0~360° 밖이거나 속도가 음수인 행 · timestamp+ship_id 가 겹치는 행.

**씬 구조화보다 앞**에 둔다. 목업은 전처리(구조화) → 필터 순으로 그리지만, 그 순서로는
씬을 만든 뒤에 행을 지우게 되어 씬 안에 무효 행이 남거나 씬을 다시 만들어야 한다.
목업의 숫자도 그 모순을 드러낸다(필터가 200'행'을 받는다 = 아직 씬이 아니다).

상류(BE 가 params.inputs 에 넣어 준다)
    inputs = {"assets": "/dataset/_runs/<run>/<idx>"}   # dp_sds_ais 산출(rows.jsonl)

산출(out_dir 아래)
  config.json    이 실행에 쓴 기능 목록 (비교의 기준)
  rows.jsonl     통과한 행(다음 노드 = 씬 구조화)
  drops.jsonl    제거한 행: 왜
  funnel.json    검사별 in/out/dropped
"""
import argparse
import json
import os
import time

# 파싱·정제 로직은 적재 노드와 **같은 함수**를 쓴다. 복사하면 한쪽만 고쳐졌을 때
# 같은 데이터가 노드마다 다르게 판정되고, 그건 화면에서 알아낼 수 없다.
# /built_in 은 스크립트 실행 디렉터리라 sys.path 에 들어간다.
from dp_sds_ais import (
    STEP_DUP,
    STEP_RANGE,
    STEP_UNIT,
    STEP_ZERO,
    _step_params,
    log,
    read_jsonl,
    refine_rows,
)

TS_FMT = "%Y-%m-%d %H:%M:%S"


def load_upstream(inputs):
    """적재 노드 산출물. 없으면 어느 단계를 먼저 돌려야 하는지 말하고 죽는다."""
    src = (inputs or {}).get("assets")
    if not src:
        raise RuntimeError("상류 노드 산출물 경로가 없습니다 — AIS 로그 적재 단계를 "
                           "먼저 실행하세요 (inputs.assets)")
    path = os.path.join(src, "rows.jsonl")
    if not os.path.isfile(path):
        raise RuntimeError(f"AIS 적재 노드 산출물이 없습니다: {path}")
    return read_jsonl(path)


def run(params):
    out_dir = params["out_dir"]
    steps = params.get("steps") or []
    dry_run = bool(params.get("dry_run"))
    sample_size = int(params.get("sample_size", 10))
    run_id = str(params.get("run_id", "run"))
    os.makedirs(out_dir, exist_ok=True)

    enabled = _step_params(steps)
    no_config = not enabled
    # 설정을 저장하지 않았으면 전량 검사로 돈다 — 정제를 통째로 건너뛴 결과를
    # 정상처럼 보여주는 편이 더 위험하다.
    on = lambda step: no_config or step in enabled  # noqa: E731

    rows = load_upstream(params.get("inputs"))
    if dry_run:
        rows = rows[:sample_size]
    log("phase", name="collect", rows=len(rows), dry_run=dry_run)

    funnel = [{"stage": "수집", "in": len(rows), "out": len(rows), "dropped": {}, "kind": "source"}]

    # 검사별로 따로 돌린다. 한 번에 묶으면 어느 검사가 몇 행을 떨어뜨렸는지 화면에
    # 남지 않는다(영상 필터를 흐림·최소 해상도·노출로 쪼갠 것과 같은 이유).
    drops = []
    current = rows
    for step, key in ((STEP_ZERO, STEP_ZERO), (STEP_RANGE, STEP_RANGE), (STEP_DUP, STEP_DUP)):
        if not on(step):
            continue
        before = len(current)
        # 단위 정규화는 적재 노드가 이미 했다 — 여기서 다시 켜면 같은 사유가 두 번 집계된다.
        checks = {STEP_UNIT: False, STEP_ZERO: False, STEP_RANGE: False, STEP_DUP: False}
        checks[key] = True
        current, step_drops = refine_rows(current, checks)
        by_reason = {}
        for d in step_drops:
            by_reason[d["reason"]] = by_reason.get(d["reason"], 0) + 1
            d["step"] = step
        drops.extend(step_drops)
        funnel.append({"stage": step, "in": before, "out": len(current),
                       "dropped": by_reason, "kind": "filter"})

    with open(os.path.join(out_dir, "rows.jsonl"), "w", encoding="utf-8") as f:
        for r in current:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(os.path.join(out_dir, "drops.jsonl"), "w", encoding="utf-8") as f:
        for d in drops:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    summary = {
        "node": "sds_ais_clean", "run_id": run_id, "node_index": params.get("node_index"),
        "dry_run": dry_run, "in": len(rows), "out": len(current),
        "dropped_total": len(drops), "funnel": funnel,
    }
    with open(os.path.join(out_dir, "funnel.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"steps": steps, "inputs": params.get("inputs"),
                   "dry_run": dry_run, "sample_size": sample_size,
                   "created_at": time.strftime(TS_FMT)},
                  f, ensure_ascii=False, indent=2)

    log("metric", name="sds_ais_clean/in", value=len(rows))
    log("metric", name="sds_ais_clean/out", value=len(current))
    log("metric", name="sds_ais_clean/dropped", value=len(drops))
    if rows and not current:
        log("log", level="warn",
            message="행이 전부 제거됐습니다 — 좌표·침로 컬럼이 이 CSV 규약과 맞는지 확인하세요")
    print(f"[dp_sds_ais_clean] {len(rows)}행 → {len(current)}행 (제외 {len(drops)}) → {out_dir}",
          flush=True)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="데이터 파이프라인 AIS 행 정제 노드")
    ap.add_argument("--params_path", required=True, help="노드 설정 JSON 경로")
    args = ap.parse_args(argv)
    with open(args.params_path, encoding="utf-8") as f:
        params = json.load(f)
    if not params.get("out_dir"):
        params["out_dir"] = os.path.dirname(os.path.abspath(args.params_path))
    try:
        run(params)
    except Exception as e:  # noqa: BLE001 - 사유를 남기고 비-0 으로 죽는다
        log("error", code="E_SDS_AIS_CLEAN_FAILED", message=f"{type(e).__name__}: {e}", fatal=True)
        raise


if __name__ == "__main__":
    main()
