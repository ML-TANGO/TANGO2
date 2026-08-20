#!/usr/bin/env python3
"""데이터 파이프라인 — COLREG 계산 노드(kind=calc, stage=sds_colreg).

스케줄러가 빌트인 잡 pod 안에서 아래로 실행한다.

    python3 -u /built_in/dp_colreg.py --params_path=/dataset/_runs/<run_id>/<node_index>/params.json

조인된 씬의 AIS 기하로 조우 유형·피항선·적용 조항·근접위험도를 **결정론적으로** 계산한다.
생성 모델에 넣을 앵커라서 모델을 쓰지 않는다 — 여기서 모델이 판단하면 뒤의 심사가
모델의 답을 모델의 답으로 검증하는 꼴이 되어 환각을 걸러 낼 수 없다.

이 노드는 상류(조인) 산출물을 읽는다. BE 가 params.inputs 에 넣어 준다.

    inputs = {"scenes": "/dataset/_runs/<run>/<idx>"}   # dp_sds_join 산출

산출(out_dir 아래)
  config.json    이 실행에 쓴 기능 목록·임계각 (비교의 기준)
  assets.jsonl   씬 1건 = 1줄 (조인 결과 + colreg 사실)
  drops.jsonl    계산할 수 없던 씬: 왜
  funnel.json    [{stage, in, out, dropped{사유:건수}}]
  assets/        씬 이미지(다음 노드의 입력)
  samples/       화면에 보여줄 썸네일 일부

알려진 한계: 프로토타입 검증에서 head_on 분류가 정답과 45% 일치했다. 임계각(HEAD_ON_ARC
13°)이 좁아 조금만 비껴도 crossing 으로 떨어지는 것이 원인으로 보인다. 값을 바꾸면 기존
결과와 비교가 안 되므로 프로토타입 값을 그대로 두고, 조정은 GT 대조와 함께 별도로 다룬다.
"""
import argparse
import json
import math
import os
import shutil
import time

# ── 기능 이름 (BE constants.SDS_COLREG_LIBRARY 의 key 와 문자 단위로 같아야 한다) ──
STEP_GEOMETRY = "상대방위 · 침로차"
STEP_ENCOUNTER = "조우 분류"
STEP_RISK = "근접 위험도"

TS_FMT = "%Y-%m-%d %H:%M:%S"
SAMPLE_LIMIT = 24
THUMB_EDGE = 320

# COLREG 판정 임계. 프로토타입과 같은 값 — 바꾸면 기존 실행과 비교가 성립하지 않는다.
HEAD_ON_ARC = 13.0        # deg. 상대방위가 이 안이면 정면
HEAD_ON_RECIP = 13.0      # deg. 침로차가 180°에서 이 안이면 상호 반대침로
STARBOARD_ARC = 112.5     # deg. 우현측 조우 구역
STERN_ARC = 112.5         # deg. 타선 선미측에서 접근 = 추월
NM_PER_DEG_LAT = 60.0


def log(event, **kw):
    """stdout JSON Lines. 플랫폼이 로그를 그대로 보관하고 사람이 읽는다."""
    print(json.dumps({"event": event, **kw}, ensure_ascii=False), flush=True)


def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_upstream(inputs):
    """조인 산출물. 없으면 어느 단계를 먼저 돌려야 하는지 말하고 죽는다."""
    src = (inputs or {}).get("scenes")
    if not src:
        raise RuntimeError("상류 노드 산출물 경로가 없습니다 — 조인 단계를 먼저 실행하세요 (inputs.scenes)")
    path = os.path.join(src, "assets.jsonl")
    if not os.path.isfile(path):
        raise RuntimeError(f"조인 노드 산출물이 없습니다: {path}")
    return read_jsonl(path), src


# ── 기하 ────────────────────────────────────────────────────────────────────
def _norm180(a):
    return (a + 180.0) % 360.0 - 180.0


def bearing_deg(lat1, lon1, lat2, lon2):
    """정북 기준 진방위(0~360)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.degrees(math.atan2(y, x)) % 360.0


def rel_bearing(own, other):
    """자선 선수 기준 상대방위(-180~180). 양수면 우현."""
    return _norm180(bearing_deg(own["lat"], own["lon"], other["lat"], other["lon"])
                    - own["heading"])


def cpa_tcpa(own, other):
    """평면 근사 최근접점(NM)과 도달시간(분).

    위경도를 NM 로 펴서 상대속도 벡터로 푼다. 항해 수분 규모의 조우에서는 지구 곡률
    오차가 판정에 영향을 주지 않는다.
    """
    coslat = math.cos(math.radians(own["lat"])) or 1e-9
    rx = (other["lon"] - own["lon"]) * NM_PER_DEG_LAT * coslat   # 동쪽 NM
    ry = (other["lat"] - own["lat"]) * NM_PER_DEG_LAT            # 북쪽 NM

    def vel(s):
        th = math.radians(s["heading"])
        return s["knot"] * math.sin(th), s["knot"] * math.cos(th)

    ovx, ovy = vel(own)
    tvx, tvy = vel(other)
    vx, vy = tvx - ovx, tvy - ovy
    v2 = vx * vx + vy * vy
    if v2 < 1e-9:
        # 상대속도가 0 = 거리가 변하지 않는다. 지금 거리가 곧 최근접이다.
        return round(math.hypot(rx, ry), 3), 0.0
    tcpa_h = max(0.0, -(rx * vx + ry * vy) / v2)
    cx, cy = rx + vx * tcpa_h, ry + vy * tcpa_h
    return round(math.hypot(cx, cy), 3), round(tcpa_h * 60.0, 1)


def classify(own, others):
    """조우 판정. 가장 앞선 1척을 기준으로 한다(프로토타입과 동일).

    여러 척이 있어도 첫 대상만 보는 것은 프로토타입 동작을 그대로 유지한 것이다.
    다중 조우 판정은 규칙이 달라(제17조 협력동작 등) 별도 설계가 필요하다.
    """
    if not others:
        return {"encounter": "safe", "own_role": "n/a", "rel_bearing_deg": 0.0,
                "heading_diff_deg": 0.0, "cpa_nm": 0.0, "tcpa_min": 0.0,
                "articles": [], "maneuver": "위험 대상 없음"}
    other = others[0]
    rb = rel_bearing(own, other)
    hd = _norm180(other["heading"] - own["heading"])
    cpa, tcpa = cpa_tcpa(own, other)
    # 타선에서 본 자선의 방위 — 자선이 타선 선미측에서 접근하는지(추월) 판정용
    rb_from_other = _norm180(
        bearing_deg(other["lat"], other["lon"], own["lat"], own["lon"]) - other["heading"])

    base = {"rel_bearing_deg": round(rb, 2), "heading_diff_deg": round(hd, 2),
            "cpa_nm": cpa, "tcpa_min": tcpa}
    if abs(rb) <= HEAD_ON_ARC and abs(abs(hd) - 180.0) <= HEAD_ON_RECIP:
        return {**base, "encounter": "head_on", "own_role": "both_give_way",
                "articles": [14, 6],
                "maneuver": "우현으로 대각도 변침하여 좌현 대 좌현(Port-to-port) 통과"}
    if abs(rb_from_other) > STERN_ARC and own["knot"] > other["knot"]:
        return {**base, "encounter": "overtaking", "own_role": "give_way",
                "articles": [13],
                "maneuver": "피추월선을 완전히 벗어날 때까지 타선 진로를 피함"}
    if 0.0 <= rb <= STARBOARD_ARC:
        return {**base, "encounter": "crossing", "own_role": "give_way",
                "articles": [15, 16],
                "maneuver": "타선 선미로 피하도록 우현 변침, 타선 전방 횡단 금지"}
    return {**base, "encounter": "crossing", "own_role": "stand_on",
            "articles": [17], "maneuver": "침로·속력 유지, 타선 미동작 시 협력동작"}


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
    """썸네일. 실패해도 계산 결과는 유효하므로 삼키고 넘어간다."""
    try:
        from PIL import Image
        with Image.open(src) as im:
            th = im.copy()
            th.thumbnail((THUMB_EDGE, THUMB_EDGE))
            th.save(dst, quality=80)
    except Exception as e:  # noqa: BLE001
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
    # 세 기능은 한 계산의 단계라 따로 끌 수 없다(조우 분류는 상대방위를, 위험도는
    # 속도벡터를 쓴다). 설정은 화면 표시를 위해 받되 계산은 항상 전부 수행한다.
    if enabled and STEP_ENCOUNTER not in enabled:
        log("log", level="warn",
            message=f"'{STEP_ENCOUNTER}' 가 꺼져 있으나 이 노드의 계산은 분리할 수 없어 "
                    "전체를 수행합니다")

    items, src_dir = load_upstream(params.get("inputs"))
    if dry_run:
        items = items[:sample_size]
    log("phase", name="collect", count=len(items), dry_run=dry_run)

    funnel = [{"stage": "수집", "in": len(items), "out": len(items), "dropped": {}, "kind": "source"}]
    drops = []
    rows = []
    by_encounter = {}
    for it in items:
        own = it.get("own")
        if not isinstance(own, dict) or "lat" not in own:
            drops.append({"asset_id": it.get("asset_id"), "timestamp": it.get("timestamp"),
                          "reason": "no_own_ship",
                          "message": "자선 상태가 없어 기하를 세울 수 없습니다"})
            continue
        try:
            facts = classify(own, it.get("others") or [])
        except Exception as e:  # noqa: BLE001 - 한 씬이 나빠도 배치를 죽이지 않는다
            drops.append({"asset_id": it.get("asset_id"), "timestamp": it.get("timestamp"),
                          "reason": "calc_error", "message": f"{type(e).__name__}: {e}"[:160]})
            continue
        by_encounter[facts["encounter"]] = by_encounter.get(facts["encounter"], 0) + 1
        rows.append({**it, "colreg": facts})

    by_reason = {}
    for d in drops:
        by_reason[d["reason"]] = by_reason.get(d["reason"], 0) + 1
    funnel.append({"stage": "COLREG 계산", "in": len(items), "out": len(rows),
                   "dropped": dict(by_reason), "kind": "transform"})

    n_sample = 0
    written = 0
    with open(os.path.join(out_dir, "assets.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            asset_id = r.get("asset_id") or f"c{written:06d}"
            rel = f"assets/{asset_id}.jpg"
            try:
                shutil.copyfile(os.path.join(src_dir, r.get("path") or ""),
                                os.path.join(out_dir, rel))
            except OSError as e:
                drops.append({"asset_id": asset_id, "timestamp": r.get("timestamp"),
                              "reason": "image_copy_failed", "message": str(e)[:120]})
                by_reason["image_copy_failed"] = by_reason.get("image_copy_failed", 0) + 1
                continue
            if n_sample < SAMPLE_LIMIT:
                _thumb(os.path.join(out_dir, rel),
                       os.path.join(out_dir, "samples", f"{asset_id}.jpg"))
                n_sample += 1
            written += 1
            f.write(json.dumps({**r, "path": rel}, ensure_ascii=False) + "\n")

    with open(os.path.join(out_dir, "drops.jsonl"), "w", encoding="utf-8") as f:
        for d in drops:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    funnel[-1]["out"] = written
    funnel[-1]["dropped"] = dict(by_reason)

    summary = {
        "node": "sds_colreg", "run_id": run_id, "node_index": params.get("node_index"),
        "dry_run": dry_run, "in": len(items), "out": written,
        "dropped_total": len(drops), "sample_count": n_sample,
        # 조우 유형 분포는 이 노드의 핵심 산출이다. 한쪽으로 쏠려 있으면 임계각이
        # 이 항차에 맞지 않는다는 신호라, 화면이 바로 보여줘야 한다.
        "encounter_distribution": by_encounter,
        "funnel": funnel,
    }
    with open(os.path.join(out_dir, "funnel.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 어떤 설정으로 돌렸는지를 산출물 옆에 남긴다. 이게 없으면 두 결과를 나란히 놔도
    # 무엇이 달라서 그런지 알 수 없어 비교가 의미를 잃는다.
    with open(os.path.join(out_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"steps": steps, "inputs": params.get("inputs"),
                   "dry_run": dry_run, "sample_size": sample_size,
                   "thresholds": {"head_on_arc": HEAD_ON_ARC, "head_on_recip": HEAD_ON_RECIP,
                                  "starboard_arc": STARBOARD_ARC, "stern_arc": STERN_ARC},
                   "created_at": time.strftime(TS_FMT)},
                  f, ensure_ascii=False, indent=2)

    log("metric", name="sds_colreg/in", value=len(items))
    log("metric", name="sds_colreg/out", value=written)
    log("metric", name="sds_colreg/dropped", value=len(drops))
    log("log", level="info", message=f"조우 분포: {json.dumps(by_encounter, ensure_ascii=False)}")
    if written and len(by_encounter) == 1:
        only = next(iter(by_encounter))
        log("log", level="warn",
            message=f"모든 씬이 '{only}' 로 분류됐습니다 — 임계각이 이 항차에 맞는지 확인하세요")
    print(f"[dp_colreg] {len(items)} → {written} (제외 {len(drops)}) {by_encounter} → {out_dir}",
          flush=True)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="데이터 파이프라인 COLREG 계산 노드")
    ap.add_argument("--params_path", required=True, help="노드 설정 JSON 경로")
    args = ap.parse_args(argv)

    with open(args.params_path, encoding="utf-8") as f:
        params = json.load(f)
    if not params.get("out_dir"):
        params["out_dir"] = os.path.dirname(os.path.abspath(args.params_path))

    try:
        run(params)
    except Exception as e:  # noqa: BLE001 - 사유를 남기고 비-0 으로 죽는다
        log("error", code="E_COLREG_FAILED", message=f"{type(e).__name__}: {e}", fatal=True)
        raise


if __name__ == "__main__":
    main()
