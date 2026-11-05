#!/usr/bin/env python3
"""데이터 파이프라인 — AIS 로그 수집·정제 노드(kind=src, stage=sds_ais).

스케줄러가 빌트인 잡 pod 안에서 아래로 실행한다.

    python3 -u /built_in/dp_sds_ais.py --params_path=/dataset/_runs/<run_id>/<node_index>/params.json

선박 자동식별(AIS) CSV 시계열을 타임스탬프 단위 '씬'으로 정형화한다. 위치·속도·침로는
충돌 기하의 근거라, 여기서 걸러내지 못한 잘못된 행은 뒤의 COLREG 계산을 그대로 오염시킨다.

입력 마운트
  /datasets/{access}/{name}/...   RO — 소스 데이터셋(ais_log.csv)
  /dataset                        RW — 이 파이프라인의 작업 데이터셋

씬 = 같은 timestamp 를 공유하는 행 묶음. 자선(my_ship=1) 한 척 + 주변선 N 척.
자선 행이 없는 묶음은 기준선이 없어 조우 기하를 세울 수 없으므로 통째로 뺀다.

산출(out_dir 아래)
  config.json    이 실행에 쓴 기능 목록·파라미터 (비교의 기준)
  rows.jsonl     단위 정규화를 통과한 AIS 행(다음 노드 = 행 정제)
  drops.jsonl    제외된 행/씬: 어느 기능에서 왜
  funnel.json    [{stage, in, out, dropped{사유:건수}}]

이미지가 없는 노드라 assets/ · samples/ 는 만들지 않는다 — 화면은 funnel 과 표로 본다.
"""
import argparse
import csv
import re
import json
import os
import time
from collections import OrderedDict

# ── 기능 이름 (BE constants.SDS_AIS_LIBRARY 의 key 와 문자 단위로 같아야 한다) ──
STEP_UNIT = "단위 정규화"
STEP_SORT = "시간 정렬"
STEP_SCENE = "씬 구조화"
STEP_ZERO = "무효 좌표"
STEP_RANGE = "범위 위반"
STEP_DUP = "중복 행"

TS_FMT = "%Y-%m-%d %H:%M:%S"
# 이 컬럼들이 다 있어야 AIS 로그로 인정한다. 데이터셋에 다른 CSV 가 섞여 있어도
# (frames_index.csv 처럼) 잘못 집어 들지 않게.
REQUIRED_COLS = {"timestamp", "my_ship", "ship_id", "latitude", "longitude", "knot", "heading"}


def log(event, **kw):
    """stdout JSON Lines. 플랫폼이 로그를 그대로 보관하고 사람이 읽는다."""
    print(json.dumps({"event": event, **kw}, ensure_ascii=False), flush=True)


# ── 소스 찾기 ────────────────────────────────────────────────────────────────
def _walk(datasets_root, sources):
    """소스로 지정된 하위 경로만 훑는다. 지정이 없으면 마운트 전체를 훑는다."""
    # 소스가 비었을 때 /datasets 전체로 폴백하지 않는다 — 워크스페이스의 무관한
    # 데이터셋까지 빨아들이면서 화면상으로는 정상으로 보인다(가장 찾기 어려운 실패다).
    if not sources:
        raise RuntimeError("읽을 소스가 지정되지 않았습니다 — 데이터 소스(데이터셋 · 폴더)를 "
                           "먼저 고르세요 (params.sources 가 비어 있습니다)")
    roots = [os.path.join(datasets_root, s.lstrip("/")) for s in sources]
    for root in roots:
        if not os.path.isdir(root):
            log("log", level="warn", message=f"소스 경로가 없습니다: {root}")
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in sorted(filenames):
                yield os.path.join(dirpath, name)


def find_ais_csvs(datasets_root, sources):
    """AIS 컬럼을 갖춘 CSV 만 고른다. 여러 개면 전부 이어 붙인다(항차 분할 대비)."""
    found = []
    for p in _walk(datasets_root, sources):
        if os.path.splitext(p)[1].lower() != ".csv":
            continue
        try:
            with open(p, encoding="utf-8-sig", newline="") as f:
                header = next(csv.reader(f), [])
        except OSError:
            continue
        if REQUIRED_COLS.issubset({h.strip() for h in header}):
            found.append(p)
    return found


def read_jsonl(path):
    """JSON Lines 읽기. 뒤 노드(행 정제·씬 구조화)가 이 노드의 산출을 읽을 때 쓴다."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def read_rows(paths):
    """여러 CSV → 행 리스트. 어느 파일에서 왔는지 남겨 드롭 사유를 되짚을 수 있게."""
    rows = []
    for p in paths:
        with open(p, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                r["_src"] = p
                rows.append(r)
    return rows


# ── 정제 ────────────────────────────────────────────────────────────────────
def _f(row, key):
    try:
        return float(row.get(key, "") or 0)
    except (TypeError, ValueError):
        return 0.0


def _i(row, key):
    return int(_f(row, key))


def _safe_text(value, limit=120):
    """사람이 적는 자유 문자열을 씬에 싣기 전에 공백만 정리한다.

    ⚠️ 상한이 `vessel_category` 의 판정 품질을 정한다 — 씬에는 절단된 값만 남고 분류는
    그 값으로 돌기 때문에, 판별어가 상한 뒤로 밀리면 조용히 동력선으로 떨어진다(그 방향이
    "자선이 유지선" 이라 위험한 쪽이다). 120 은 ITU 선종 전체 문구와 흔한 수식어가 함께
    들어갈 여유다. 그보다 긴 표기는 여전히 뒤집힐 수 있고, 그건 문서화된 한계다.

    ⚠️ 이 값을 프롬프트에 그대로 넣지 않는다. 프롬프트에는 `category_label()` 의 정규
    라벨만 내보낸다 — 자유 문자열은 판사 프롬프트로 가는 유일한 통로다.
    """
    return " ".join(str(value or "").split())[:limit]


# ── 선종 어휘 ───────────────────────────────────────────────────────────────
# AIS 선종 표기 → 범주. COLREG 제18조 서열의 입력이라 dp_colreg 가 이 함수를 쓴다.
#
# **부분일치**로 본다. 한국어는 공백 분절이 없어 '화물선'·'유조선'·'어로종사선' 같은
# 합성어가 어절 단위 일치로는 통째로 빠진다. 대신 부분일치가 위험한 라틴 축약(nuc·ram·
# wig·sail)과 접두 충돌(unrestricted / not under commander / stowing)만 경계로 좁힌다.
_NEEDLES = (
    ("not_under_command", r"(?<![a-z])nuc(?![a-z])|not under command(?!er)|조종불능"),
    # 3조(g) 의 예시(준설·잠수)만 받는다. 맨 'towing' 은 "조종능력을 심각하게 제한하는"
    # 한정을 버리므로 넣지 않는다 — 단순 예인 예선까지 최상위 서열이 된다.
    ("restricted", r"(?<![a-z])ram(?![a-z])|(?<!un)restricted in ability"
                   r"|dredging|diving|조종제한|준설|잠수"),
    ("fishing", r"fishing|trawl|어선|어로"),
    ("sailing", r"sailing|(?<![a-z])sail(?![a-z])|범선|요트"),
    # 18(d)/(e)/(f) — 서열이 (a)~(c)와 다른 별도 의무라 dp_colreg 가 판정을 보류한다.
    ("constrained_draught", r"constrained by (?:her )?draught|흘수제약"),
    ("seaplane", r"seaplane|수상항공기"),
    ("wig", r"(?<![a-z])wig(?![a-z])|wing in ground|위그"),
    ("power_driven", r"cargo|tanker|passenger|cruise|ferry|tug|pilot|military|boat"
                     r"|ship|vessel|motor|craft|yacht|화물|유조|여객|동력|예선|선박"),
)
_NEEDLE_RES = tuple((category, re.compile(pattern)) for category, pattern in _NEEDLES)
# 어로 '종사' 를 명시적으로 부정하거나 지원선이라고 적은 표기는 제3조(d) 의 어로종사선이
# 아니다. 부정이 지원선 예외보다 강하다 — 둘이 함께 있으면 부정을 따른다.
_NOT_FISHING_RE = re.compile(r"not engaged|종사하지|미종사")
_SUPPORT_RE = re.compile(r"support|지원")
_ENGAGED_FISHING_RE = re.compile(r"engaged in fishing|어로 종사")
# ITU-R M.1371 선종 숫자코드. 자선이 보통 70·80대라 특수선 코드만 넣으면 자선이 미인식
# 되어 제18조가 통째로 보류된다 — 그래서 범위 전체를 덮는다. "70.0"(pandas 재저장)도 받는다.
_CODE_RE = re.compile(r"(\d{1,3})(?:\.0+)?$")
_AIS_CODE_RANGES = (
    (20, 29, "wig"), (30, 30, "fishing"), (31, 34, "restricted"), (35, 35, "power_driven"),
    (36, 36, "sailing"), (37, 37, "power_driven"), (40, 49, "power_driven"),
    (50, 59, "power_driven"), (60, 99, "power_driven"),
)
# 프롬프트·화면에 내보내는 정규 라벨. 원문을 내보내지 않는 이유는 _safe_text 주석 참조.
CATEGORY_LABELS = {
    "not_under_command": ("조종불능선", "not under command"),
    "restricted": ("조종제한선", "restricted in ability to manoeuvre"),
    "fishing": ("어선", "fishing vessel"),
    "sailing": ("범선", "sailing vessel"),
    "power_driven": ("동력선", "power-driven vessel"),
    "constrained_draught": ("흘수제약선", "constrained by draught"),
    "seaplane": ("수상항공기", "seaplane"),
    "wig": ("위그선", "WIG craft"),
}


def vessel_category(name):
    """AIS 선종 → 범주. 알아볼 수 없으면 None.

    None 을 동력선으로 치지 않는다 — 모르는 표기를 동력선으로 가정하면 실제로는 어선인
    배에 대해 자선을 유지선으로 라벨링하게 되고, 그것이 그대로 학습데이터의 정답이 된다.
    dp_colreg 는 None 을 받으면 제18조 판정을 보류한다.
    """
    flat = re.sub(r"[^0-9a-z가-힣.]+", " ", str(name or "").lower()).strip()
    if not flat:
        return None
    code = _CODE_RE.fullmatch(flat)
    if code:
        number = int(code.group(1))
        for low, high, category in _AIS_CODE_RANGES:
            if low <= number <= high:
                return category
        return None
    skip_fishing = bool(_NOT_FISHING_RE.search(flat)) or (
        bool(_SUPPORT_RE.search(flat)) and not _ENGAGED_FISHING_RE.search(flat))
    for category, pattern in _NEEDLE_RES:
        if category == "fishing" and skip_fishing:
            continue
        if pattern.search(flat):
            return category
    return None


def category_label(name, lang="ko"):
    """프롬프트·화면용 정규 라벨. 알아볼 수 없으면 '기타'."""
    category = vessel_category(name)
    if category is None:
        return "other" if lang == "en" else "기타"
    return CATEGORY_LABELS[category][1 if lang == "en" else 0]


def _ident(row):
    return {"timestamp": row.get("timestamp", ""), "ship_id": row.get("ship_id", "")}


def refine_rows(rows, checks):
    """행 단위 정제. `checks` 로 켜진 검사만 돈다(기능을 껐다 켰다 하며 결과를 비교하게).

    검사 순서는 싼 것부터: 식별자 → 파싱 → 좌표 → 범위 → 중복. 앞에서 떨어진 행이
    뒤 검사를 통과할 리 없으므로 사유가 겹치지 않는다.
    """
    seen = set()
    clean, drops = [], []
    for r in rows:
        if r.get("ship_id") in (None, ""):
            drops.append({**_ident(r), "reason": "missing_ship_id"})
            continue
        if checks.get(STEP_UNIT, True):
            # 숫자로 못 읽는 행은 여기서 잡는다. 정규화를 꺼도 아래 검사가 0.0 으로
            # 읽고 넘어가므로, 이 검사는 정규화 기능에 묶어 둔다.
            try:
                for key in ("latitude", "longitude", "heading", "knot"):
                    float(r.get(key, "") or 0)
            except (TypeError, ValueError):
                drops.append({**_ident(r), "reason": "parse"})
                continue
        lat, lon = _f(r, "latitude"), _f(r, "longitude")
        hdg, knot = _f(r, "heading"), _f(r, "knot")
        if checks.get(STEP_ZERO, True) and lat == 0 and lon == 0:
            drops.append({**_ident(r), "reason": "zero_coords"})
            continue
        if checks.get(STEP_RANGE, True) and (not 0.0 <= hdg < 360.0 or knot < 0):
            drops.append({**_ident(r), "reason": "out_of_range"})
            continue
        if checks.get(STEP_DUP, True):
            key = (r.get("timestamp"), str(r.get("ship_id")))
            if key in seen:
                drops.append({**_ident(r), "reason": "duplicate"})
                continue
            seen.add(key)
        clean.append(r)
    return clean, drops


def row_to_ship(row):
    return {
        "ship_id": _i(row, "ship_id"), "is_own": _i(row, "my_ship") == 1,
        # Rule 18 판정 근거. 선택 컬럼이라 없으면 빈 문자열 — 그 경우 18조는 적용되지
        # 않고 기하만으로 판정한다(예전 데이터셋과 같은 동작).
        "type": _safe_text(row.get("ship_type")),
        "lat": _f(row, "latitude"), "lon": _f(row, "longitude"),
        "knot": _f(row, "knot"), "heading": _f(row, "heading"),
        "length": _i(row, "length"), "width": _i(row, "width"), "draft": _i(row, "draft"),
        "bbox": [_f(row, "bbox_x"), _f(row, "bbox_y"),
                 _f(row, "bbox_width"), _f(row, "bbox_height")],
    }


def _fmt_ko(s):
    # 선종은 제18조(동력선은 어선·범선 등에 양보)의 근거라, 계산된 사실에만 있고 AIS
    # 서술에 없으면 모델이 "왜 양보하는지" 를 쓸 수 없다.
    kind = f"선종:{category_label(s['type'], 'ko')} | " if s.get("type") else ""
    head = (f"{kind}위도:{s['lat']:.6f} 경도:{s['lon']:.6f} | 속도:{s['knot']:.1f}kt "
            f"방향:{s['heading']:.1f}° | 선체:{s['length']}m × {s['width']}m 흘수:{s['draft']}m")
    if s["is_own"]:
        return f"- 자선 (ID:{s['ship_id']}) | {head}"
    x, y, w, h = s["bbox"]
    return (f"- 주변선박 (ID:{s['ship_id']}) | {head} | "
            f"바운딩박스:[x={x:.0f} y={y:.0f} w={w:.0f} h={h:.0f}]")


def _fmt_en(s):
    kind = f"Type:{category_label(s['type'], 'en')} | " if s.get("type") else ""
    head = (f"{kind}Lat:{s['lat']:.6f} Lon:{s['lon']:.6f} | Speed:{s['knot']:.1f}kt "
            f"Heading:{s['heading']:.1f}° | Size:{s['length']}m x {s['width']}m Draft:{s['draft']}m")
    if s["is_own"]:
        return f"- Own vessel (ID:{s['ship_id']}) | {head}"
    x, y, w, h = s["bbox"]
    return (f"- Nearby vessel (ID:{s['ship_id']}) | {head} | "
            f"BoundingBox:[x={x:.0f} y={y:.0f} w={w:.0f} h={h:.0f}]")


def ais_text(own, others, lang):
    """생성 모델에 넣을 AIS 서술. 한국어·영어를 둘 다 만들어 두고 생성 노드가 고른다."""
    fmt = _fmt_en if lang == "en" else _fmt_ko
    head = "[Vessel AIS Information]" if lang == "en" else "[선박 AIS 정보]"
    return "\n".join([head, fmt(own)] + [fmt(o) for o in others])


def build_scenes(rows, structure):
    """타임스탬프별 씬. 구조화를 끄면 행을 그대로 1행=1씬으로 흘려보낸다."""
    if not structure:
        return [{"timestamp": r.get("timestamp", ""), "own": row_to_ship(r), "others": []}
                for r in rows], []
    groups = OrderedDict()
    for r in rows:
        groups.setdefault(r.get("timestamp", ""), []).append(row_to_ship(r))
    scenes, drops = [], []
    for ts, ships in groups.items():
        own = next((s for s in ships if s["is_own"]), None)
        if own is None:
            # 자선이 없으면 기준선이 없어 상대방위·침로차를 세울 수 없다.
            drops.append({"timestamp": ts, "ship_id": "", "reason": "no_own_ship",
                          "message": f"my_ship=1 행이 없는 묶음({len(ships)}행)"})
            continue
        scenes.append({"timestamp": ts, "own": own,
                       "others": [s for s in ships if not s["is_own"]]})
    return scenes, drops


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


def run(params):
    out_dir = params["out_dir"]
    steps = params.get("steps") or []
    dry_run = bool(params.get("dry_run"))
    sample_size = int(params.get("sample_size", 10))
    run_id = str(params.get("run_id", "run"))
    datasets_root = params.get("datasets_root", "/datasets")
    os.makedirs(out_dir, exist_ok=True)

    enabled = _step_params(steps)
    no_config = not enabled
    # 이 노드는 **적재와 단위 정규화까지**만 한다. 행 정제(무효 좌표·범위·중복)와
    # 씬 구조화는 각각 뒤 노드가 맡는다 — 파이프라인이면 단계마다 결과를 보고 임계값을
    # 바꿔 다시 돌릴 수 있어야 하고, 한 잡에 몰아 두면 그게 불가능하다.
    checks = {STEP_UNIT: no_config or STEP_UNIT in enabled,
              STEP_ZERO: False, STEP_RANGE: False, STEP_DUP: False}

    paths = find_ais_csvs(datasets_root, params.get("sources") or [])
    if not paths:
        raise RuntimeError("소스에서 AIS 로그 CSV 를 찾지 못했습니다 "
                           f"(필요 컬럼: {', '.join(sorted(REQUIRED_COLS))})")
    rows = read_rows(paths)
    log("phase", name="collect", files=paths, rows=len(rows), dry_run=dry_run)

    funnel = [{"stage": "수집", "in": len(rows), "out": len(rows), "dropped": {}, "kind": "source"}]

    clean, row_drops = refine_rows(rows, checks)
    by_reason = {}
    for d in row_drops:
        by_reason[d["reason"]] = by_reason.get(d["reason"], 0) + 1
    funnel.append({"stage": STEP_UNIT, "in": len(rows), "out": len(clean),
                   "dropped": by_reason, "kind": "filter"})

    n_all = len(clean)
    if dry_run:
        clean = clean[:sample_size]

    # 통과분은 아직 '행'이다. 씬이 되는 것은 씬 구조화 노드를 지난 뒤다.
    with open(os.path.join(out_dir, "rows.jsonl"), "w", encoding="utf-8") as f:
        for r in clean:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    drops = row_drops
    with open(os.path.join(out_dir, "drops.jsonl"), "w", encoding="utf-8") as f:
        for d in drops:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    summary = {
        "node": "sds_ais", "run_id": run_id, "node_index": params.get("node_index"),
        "dry_run": dry_run, "in": len(rows), "out": len(clean),
        "rows_total": n_all, "dropped_total": len(drops), "sources": paths,
        "funnel": funnel,
    }
    with open(os.path.join(out_dir, "funnel.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 어떤 설정으로 돌렸는지를 산출물 옆에 남긴다. 이게 없으면 두 결과를 나란히 놔도
    # 무엇이 달라서 그런지 알 수 없어 비교가 의미를 잃는다.
    with open(os.path.join(out_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"steps": steps, "sources": params.get("sources"),
                   "dry_run": dry_run, "sample_size": sample_size,
                   "created_at": time.strftime(TS_FMT)},
                  f, ensure_ascii=False, indent=2)

    log("metric", name="sds_ais/in", value=len(rows))
    log("metric", name="sds_ais/out", value=len(clean))
    log("metric", name="sds_ais/dropped", value=len(drops))
    if not clean:
        log("log", level="warn",
            message="통과한 행이 0건입니다 — CSV 컬럼과 숫자 형식을 확인하세요")
    print(f"[dp_sds_ais] {len(rows)}행 → {len(clean)}행 (제외 {len(drops)}) → {out_dir}", flush=True)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="데이터 파이프라인 AIS 로그 수집·정제 노드")
    ap.add_argument("--params_path", required=True, help="노드 설정 JSON 경로")
    args = ap.parse_args(argv)

    with open(args.params_path, encoding="utf-8") as f:
        params = json.load(f)
    if not params.get("out_dir"):
        params["out_dir"] = os.path.dirname(os.path.abspath(args.params_path))

    try:
        run(params)
    except Exception as e:  # noqa: BLE001 - 사유를 남기고 비-0 으로 죽는다
        log("error", code="E_SDS_AIS_FAILED", message=f"{type(e).__name__}: {e}", fatal=True)
        raise


if __name__ == "__main__":
    main()
