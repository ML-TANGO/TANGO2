#!/usr/bin/env python3
"""데이터 파이프라인 — 프레임 × AIS 조인 노드(kind=join, stage=sds_join).

스케줄러가 빌트인 잡 pod 안에서 아래로 실행한다.

    python3 -u /built_in/dp_sds_join.py --params_path=/dataset/_runs/<run_id>/<node_index>/params.json

영상 노드가 뽑은 프레임과 AIS 노드가 만든 씬을 타임스탬프로 맞붙인다. 프레임마다
시각이 가장 가까운 씬을 고르고, 허용오차를 넘으면 짝이 없는 것으로 보고 뺀다.

이 노드는 **상류 두 노드의 산출물**을 읽는다 — 소스 데이터셋이 아니다.
BE 가 params.inputs 에 각 상류 노드의 out_dir 을 넣어 준다.

    inputs = {"frames": "/dataset/_runs/<run>/<idx>",   # dp_sds_video 산출
              "scenes": "/dataset/_runs/<run>/<idx>"}   # dp_sds_ais 산출

프레임 이미지는 참조가 아니라 **복사**한다. 상류 실행이 지워지거나 덮여도 이 노드의
산출물만으로 뒤 단계(계산·생성·심사)가 성립해야 하기 때문이다. 프레임 한 장이 수십 KB
수준이라 복사 비용보다 자립성이 훨씬 값지다.

산출(out_dir 아래)
  config.json    이 실행에 쓴 기능 목록·파라미터 (비교의 기준)
  assets.jsonl   조인된 씬 1건 = 1줄 (프레임 + AIS + Δt)
  drops.jsonl    짝을 못 찾은 프레임: 시각과 Δt
  funnel.json    [{stage, in, out, dropped{사유:건수}}]
  assets/        조인에 성공한 프레임 이미지
  samples/       화면에 보여줄 썸네일 일부
"""
import argparse
import bisect
import json
import os
import shutil
import time
from datetime import datetime

# ── 기능 이름 (BE constants.SDS_JOIN_LIBRARY 의 key 와 문자 단위로 같아야 한다) ──
STEP_MATCH = "프레임 × AIS"
STEP_TOL = "허용오차"
STEP_UNMATCHED = "무매칭 처리"

TS_FMT = "%Y-%m-%d %H:%M:%S"
SAMPLE_LIMIT = 24          # 화면 썸네일 상한. 전량 뽑으면 용량이 터진다.
THUMB_EDGE = 320


def log(event, **kw):
    """stdout JSON Lines. 플랫폼이 로그를 그대로 보관하고 사람이 읽는다."""
    print(json.dumps({"event": event, **kw}, ensure_ascii=False), flush=True)


def parse_dt(s):
    """ISO / 공백구분을 모두 받아 naive datetime 으로. 못 읽으면 None."""
    s = (s or "").strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s).replace(tzinfo=None)
    except ValueError:
        pass
    head = s.split("+")[0].split(".")[0]
    for fmt in (TS_FMT, "%Y-%m-%dT%H:%M:%S", "%Y%m%dT%H%M%S"):
        try:
            return datetime.strptime(head, fmt)
        except ValueError:
            continue
    return None


def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_upstream(inputs):
    """상류 두 노드의 산출물. 어느 쪽이 없는지 이름을 대고 죽는다 —
    '조인 결과 0건'으로 끝나면 사람이 원인을 못 찾는다."""
    frames_dir = (inputs or {}).get("frames")
    scenes_dir = (inputs or {}).get("scenes")
    if not frames_dir or not scenes_dir:
        raise RuntimeError("상류 노드 산출물 경로가 없습니다 — 영상 노드와 AIS 노드를 "
                           "먼저 실행하세요 (inputs.frames / inputs.scenes)")

    frames_path = os.path.join(frames_dir, "assets.jsonl")
    scenes_path = os.path.join(scenes_dir, "scenes.jsonl")
    if not os.path.isfile(frames_path):
        raise RuntimeError(f"영상 노드 산출물이 없습니다: {frames_path}")
    if not os.path.isfile(scenes_path):
        raise RuntimeError(f"AIS 노드 산출물이 없습니다: {scenes_path}")

    return read_jsonl(frames_path), read_jsonl(scenes_path), frames_dir


# ── 조인 ────────────────────────────────────────────────────────────────────
def join(frames, scenes, tolerance_s, drop_unmatched):
    """프레임마다 시각이 가장 가까운 씬. tolerance_s 가 None 이면 전부 붙인다.

    씬을 시각순으로 정렬해 두고 이분 탐색으로 후보 2개만 본다 — 프레임 × 씬 전수
    비교는 항차가 길어지면 그대로 O(n·m) 으로 터진다(112 × 200 은 괜찮지만
    수만 프레임 항차에서는 아니다).
    """
    dated = [(parse_dt(s.get("timestamp")), s) for s in scenes]
    bad_scene_ts = sum(1 for d, _ in dated if d is None)
    dated = sorted(((d, s) for d, s in dated if d is not None), key=lambda t: t[0])
    keys = [d for d, _ in dated]

    joined, drops = [], []
    for fr in frames:
        ft = parse_dt(fr.get("timestamp"))
        if ft is None:
            drops.append({"asset_id": fr.get("asset_id"), "timestamp": fr.get("timestamp"),
                          "delta_s": None, "reason": "bad_frame_timestamp"})
            continue
        if not keys:
            drops.append({"asset_id": fr.get("asset_id"), "timestamp": fr.get("timestamp"),
                          "delta_s": None, "reason": "no_ais_scene"})
            continue
        i = bisect.bisect_left(keys, ft)
        best, best_delta = None, None
        for cand in (i - 1, i):
            if 0 <= cand < len(keys):
                delta = abs((keys[cand] - ft).total_seconds())
                if best_delta is None or delta < best_delta:
                    best, best_delta = dated[cand][1], delta
        if tolerance_s is not None and best_delta > tolerance_s and drop_unmatched:
            drops.append({"asset_id": fr.get("asset_id"), "timestamp": fr.get("timestamp"),
                          "delta_s": round(best_delta, 3), "reason": "no_ais_within_tolerance"})
            continue
        joined.append((fr, best, best_delta))
    return joined, drops, bad_scene_ts


# ── 실행 ────────────────────────────────────────────────────────────────────
def _step_params(steps):
    """[[기능명, {파라미터}], ...] → {기능명: {파라미터}}. 꺼진 기능은 애초에 안 온다."""
    enabled = {}
    for s in steps or []:
        if isinstance(s, (list, tuple)) and s:
            enabled[s[0]] = (s[1] if len(s) > 1 and isinstance(s[1], dict) else {})
        elif isinstance(s, str):
            enabled[s] = {}
    return enabled


def _thumb(src, dst):
    """썸네일. 실패해도 조인 자체는 성공이므로 삼키고 넘어간다."""
    try:
        from PIL import Image
        with Image.open(src) as im:
            th = im.copy()
            th.thumbnail((THUMB_EDGE, THUMB_EDGE))
            th.save(dst, quality=80)
    except Exception as e:  # noqa: BLE001 - 썸네일 실패로 노드를 죽이지 않는다
        log("log", level="warn", message=f"썸네일 생성 실패({os.path.basename(src)}): {e}")


def run(params):
    out_dir = params["out_dir"]
    steps = params.get("steps") or []
    dry_run = bool(params.get("dry_run"))
    sample_size = int(params.get("sample_size", 10))
    run_id = str(params.get("run_id", "run"))

    os.makedirs(os.path.join(out_dir, "assets"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "samples"), exist_ok=True)

    enabled = _step_params(steps)
    no_config = not enabled
    # 허용오차 기능을 끄면 시각이 아무리 벌어져도 붙인다(비교용). 기본은 1초.
    # 0 은 '제한 없음'이 아니라 '정확히 일치만' 이다 — 값을 falsy 로 뭉뚱그리면
    # 가장 엄격한 설정이 가장 느슨한 설정으로 뒤집힌다.
    tolerance_s = None
    if no_config or STEP_TOL in enabled:
        raw = (enabled.get(STEP_TOL) or {}).get("toleranceS", 1)
        tolerance_s = 1.0 if raw is None else float(raw)
    drop_unmatched = no_config or STEP_UNMATCHED in enabled

    frames, scenes, frames_dir = load_upstream(params.get("inputs"))
    if dry_run:
        frames = frames[:sample_size]
    log("phase", name="collect", frames=len(frames), scenes=len(scenes), dry_run=dry_run)

    funnel = [{"stage": "수집", "in": len(frames), "out": len(frames), "dropped": {},
               "kind": "source", "note": f"AIS 씬 {len(scenes)}건"}]

    joined, drops, bad_scene_ts = join(frames, scenes, tolerance_s, drop_unmatched)
    by_reason = {}
    for d in drops:
        by_reason[d["reason"]] = by_reason.get(d["reason"], 0) + 1
    funnel.append({"stage": "조인", "in": len(frames), "out": len(joined),
                   "dropped": by_reason, "kind": "transform"})

    n_sample = 0
    copy_fail = 0
    with open(os.path.join(out_dir, "assets.jsonl"), "w", encoding="utf-8") as f:
        for fr, sc, delta in joined:
            asset_id = fr.get("asset_id") or f"j{fr.get('frame_idx', 0):06d}"
            rel = f"assets/{asset_id}.jpg"
            src_img = os.path.join(frames_dir, fr.get("path") or "")
            try:
                shutil.copyfile(src_img, os.path.join(out_dir, rel))
            except OSError as e:
                copy_fail += 1
                drops.append({"asset_id": asset_id, "timestamp": fr.get("timestamp"),
                              "delta_s": None, "reason": "frame_copy_failed",
                              "message": str(e)})
                continue
            if n_sample < SAMPLE_LIMIT:
                _thumb(os.path.join(out_dir, rel),
                       os.path.join(out_dir, "samples", f"{asset_id}.jpg"))
                n_sample += 1
            row = {
                "asset_id": asset_id, "src": fr.get("src", ""), "path": rel,
                "w": fr.get("w"), "h": fr.get("h"),
                "frame_idx": fr.get("frame_idx"), "timestamp": fr.get("timestamp"),
                "ais_timestamp": sc.get("timestamp"), "delta_s": round(delta, 3),
                "own": sc.get("own"), "others": sc.get("others") or [],
                "n_others": len(sc.get("others") or []),
                "ais_text_ko": sc.get("ais_text_ko", ""),
                "ais_text_en": sc.get("ais_text_en", ""),
            }
            if fr.get("scene_id"):
                row["scene_id"] = fr["scene_id"]
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    out_n = len(joined) - copy_fail
    with open(os.path.join(out_dir, "drops.jsonl"), "w", encoding="utf-8") as f:
        for d in drops:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    # 조인 단계 카운트는 복사 실패까지 반영해야 화면 숫자와 파일 수가 맞는다.
    funnel[-1]["out"] = out_n
    if copy_fail:
        funnel[-1]["dropped"]["frame_copy_failed"] = copy_fail

    deltas = [d for _, _, d in joined]
    summary = {
        "node": "sds_join", "run_id": run_id, "node_index": params.get("node_index"),
        "dry_run": dry_run, "in": len(frames), "out": out_n,
        "dropped_total": len(drops), "sample_count": n_sample,
        "scene_count": len(scenes), "tolerance_s": tolerance_s,
        "max_delta_s": round(max(deltas), 3) if deltas else None,
        "warn_bad_scene_timestamp": bad_scene_ts,
        "funnel": funnel,
    }
    with open(os.path.join(out_dir, "funnel.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 어떤 설정으로 돌렸는지를 산출물 옆에 남긴다. 이게 없으면 두 결과를 나란히 놔도
    # 무엇이 달라서 그런지 알 수 없어 비교가 의미를 잃는다.
    with open(os.path.join(out_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"steps": steps, "inputs": params.get("inputs"),
                   "dry_run": dry_run, "sample_size": sample_size,
                   "created_at": time.strftime(TS_FMT)},
                  f, ensure_ascii=False, indent=2)

    log("metric", name="sds_join/in", value=len(frames))
    log("metric", name="sds_join/out", value=out_n)
    log("metric", name="sds_join/dropped", value=len(drops))
    if bad_scene_ts:
        log("log", level="warn",
            message=f"시각을 읽을 수 없는 AIS 씬 {bad_scene_ts}건은 후보에서 빠졌습니다")
    if not out_n and frames:
        log("log", level="warn",
            message="조인 결과가 0건입니다 — 프레임과 AIS 의 시각대가 겹치는지, "
                    "허용오차가 너무 좁지 않은지 확인하세요")
    print(f"[dp_sds_join] 프레임 {len(frames)} × 씬 {len(scenes)} → {out_n} "
          f"(제외 {len(drops)}) → {out_dir}", flush=True)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="데이터 파이프라인 프레임 × AIS 조인 노드")
    ap.add_argument("--params_path", required=True, help="노드 설정 JSON 경로")
    args = ap.parse_args(argv)

    with open(args.params_path, encoding="utf-8") as f:
        params = json.load(f)
    if not params.get("out_dir"):
        params["out_dir"] = os.path.dirname(os.path.abspath(args.params_path))

    try:
        run(params)
    except Exception as e:  # noqa: BLE001 - 사유를 남기고 비-0 으로 죽는다
        log("error", code="E_SDS_JOIN_FAILED", message=f"{type(e).__name__}: {e}", fatal=True)
        raise


if __name__ == "__main__":
    main()
