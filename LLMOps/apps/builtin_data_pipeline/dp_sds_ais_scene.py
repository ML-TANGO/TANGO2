#!/usr/bin/env python3
"""데이터 파이프라인 — AIS 씬 구조화 노드(kind=prep, stage=sds_ais_scene).

    python3 -u /built_in/dp_sds_ais_scene.py --params_path=/dataset/_runs/<run_id>/<node_index>/params.json

정제된 AIS 행을 시각 순으로 세우고, 같은 timestamp 를 한 묶음으로 만들어
**자선 1척 + 주변선 N척**의 씬으로 구조화한다. 여기서 조인이 먹을 형식이 완성된다.

산출 형식은 예전 단일 AIS 노드와 **같다**(`scenes.jsonl` + ais_text_ko/en) — 조인 노드의
입력 계약을 바꾸지 않으려는 것이다. 노드를 쪼개는 일이 그 뒤 체인을 건드리면 안 된다.

상류(BE 가 params.inputs 에 넣어 준다)
    inputs = {"assets": "/dataset/_runs/<run>/<idx>"}   # dp_sds_ais_clean 산출(rows.jsonl)

산출(out_dir 아래)
  config.json    이 실행에 쓴 기능 목록 (비교의 기준)
  scenes.jsonl   씬 1건 = 1줄 (조인 노드의 입력)
  drops.jsonl    씬이 되지 못한 묶음: 왜(자선 없음)
  funnel.json    단계별 in/out/dropped
"""
import argparse
import json
import os
import time

from dp_sds_ais import (
    STEP_SCENE,
    STEP_SORT,
    _step_params,
    ais_text,
    build_scenes,
    log,
    read_jsonl,
)

TS_FMT = "%Y-%m-%d %H:%M:%S"


def load_upstream(inputs):
    """행 정제 노드 산출물. 없으면 어느 단계를 먼저 돌려야 하는지 말하고 죽는다."""
    src = (inputs or {}).get("assets")
    if not src:
        raise RuntimeError("상류 노드 산출물 경로가 없습니다 — AIS 행 정제 단계를 "
                           "먼저 실행하세요 (inputs.assets)")
    path = os.path.join(src, "rows.jsonl")
    if not os.path.isfile(path):
        raise RuntimeError(f"AIS 행 정제 노드 산출물이 없습니다: {path}")
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

    rows = load_upstream(params.get("inputs"))
    log("phase", name="collect", rows=len(rows), dry_run=dry_run)
    funnel = [{"stage": "수집", "in": len(rows), "out": len(rows), "dropped": {}, "kind": "source"}]

    if no_config or STEP_SORT in enabled:
        # 시각 순이 아니면 같은 시각 행이 흩어져 묶음이 쪼개진다.
        rows.sort(key=lambda r: r.get("timestamp", ""))
        funnel.append({"stage": STEP_SORT, "in": len(rows), "out": len(rows),
                       "dropped": {}, "kind": "filter"})

    scenes, scene_drops = build_scenes(rows, no_config or STEP_SCENE in enabled)
    funnel.append({"stage": STEP_SCENE, "in": len(rows), "out": len(scenes),
                   "dropped": {"no_own_ship": len(scene_drops)} if scene_drops else {},
                   "kind": "transform"})

    n_all = len(scenes)
    if dry_run:
        scenes = scenes[:sample_size]

    with open(os.path.join(out_dir, "scenes.jsonl"), "w", encoding="utf-8") as f:
        for sc in scenes:
            row = {**sc,
                   "n_others": len(sc["others"]),
                   "ais_text_ko": ais_text(sc["own"], sc["others"], "ko"),
                   "ais_text_en": ais_text(sc["own"], sc["others"], "en")}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with open(os.path.join(out_dir, "drops.jsonl"), "w", encoding="utf-8") as f:
        for d in scene_drops:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    summary = {
        "node": "sds_ais_scene", "run_id": run_id, "node_index": params.get("node_index"),
        "dry_run": dry_run, "in": len(rows), "out": len(scenes),
        "scenes_total": n_all, "dropped_total": len(scene_drops), "funnel": funnel,
    }
    with open(os.path.join(out_dir, "funnel.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"steps": steps, "inputs": params.get("inputs"),
                   "dry_run": dry_run, "sample_size": sample_size,
                   "created_at": time.strftime(TS_FMT)},
                  f, ensure_ascii=False, indent=2)

    log("metric", name="sds_ais_scene/in", value=len(rows))
    log("metric", name="sds_ais_scene/out", value=len(scenes))
    if rows and not scenes:
        log("log", level="warn",
            message="씬이 0건입니다 — my_ship=1 행이 남아 있는지 확인하세요"
                    "(행 정제가 자선 행을 걸러냈을 수 있습니다)")
    print(f"[dp_sds_ais_scene] {len(rows)}행 → 씬 {len(scenes)} "
          f"(제외 {len(scene_drops)}) → {out_dir}", flush=True)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="데이터 파이프라인 AIS 씬 구조화 노드")
    ap.add_argument("--params_path", required=True, help="노드 설정 JSON 경로")
    args = ap.parse_args(argv)
    with open(args.params_path, encoding="utf-8") as f:
        params = json.load(f)
    if not params.get("out_dir"):
        params["out_dir"] = os.path.dirname(os.path.abspath(args.params_path))
    try:
        run(params)
    except Exception as e:  # noqa: BLE001 - 사유를 남기고 비-0 으로 죽는다
        log("error", code="E_SDS_AIS_SCENE_FAILED", message=f"{type(e).__name__}: {e}", fatal=True)
        raise


if __name__ == "__main__":
    main()
