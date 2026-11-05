#!/usr/bin/env python3
"""데이터 파이프라인 — 전처리 노드(kind=prep).

스케줄러가 빌트인 잡 pod 안에서 아래로 실행한다.

    python3 -u /built_in/dp_prep.py --params_path=/dataset/_runs/<run_id>/<node_index>/params.json

파라미터를 `--key value` 로 펼치지 않고 **파일 경로 하나만** 받는 이유: 노드 설정은
기능 목록·순서·기능별 파라미터가 중첩된 구조인데, helm `--set` 으로 넘기면 콤마·중괄호
이스케이프에 걸린다. 호출부(BE)가 파일로 써 두고 경로만 넘기면 그 문제가 사라진다.

입력 마운트
  /datasets/{access}/{name}/{folder}   RO — 소스 데이터셋(여러 개 가능)
  /dataset                             RW — 이 파이프라인의 작업 데이터셋

산출(out_dir 아래)
  config.json    이 실행에 쓴 기능 목록·순서·파라미터 (비교의 기준)
  assets.jsonl   통과한 자산 1건 = 1줄
  drops.jsonl    제외된 자산: 원본 경로 + 어느 기능에서 왜
  funnel.json    [{stage, in, out, dropped{사유:건수}}]
  assets/        전처리 결과 이미지(다음 노드의 입력)
  samples/       화면에 보여줄 썸네일 일부

제외 항목의 원본은 복사하지 않는다 — 소스가 RO 로 살아 있으므로 경로와 사유만 남기고
썸네일은 화면이 원본에서 만든다.
"""
import argparse
import json
import os
import random
import time

from PIL import Image, ImageOps

# ── 기능 이름 (BE constants.PREPROCESS_LIBRARY 의 key 와 문자 단위로 같아야 한다) ──
STEP_CLEAN = "정제"
STEP_STRUCT = "구조 추출"
STEP_RESIZE = "리사이즈"
STEP_CROP = "크롭"
STEP_ROTATE = "회전"
STEP_FLIP = "좌우 반전"
STEP_REMAP = "영역 좌표 보정"

# 기하 변형 — 이걸 거치면 원본 기준 bbox 가 어긋난다(좌표 보정이 짝).
GEOMETRIC_STEPS = {STEP_RESIZE, STEP_CROP, STEP_ROTATE, STEP_FLIP}

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
PDF_EXT = {".pdf"}
SAMPLE_LIMIT = 24          # 화면 썸네일 상한. 전량 뽑으면 용량이 터진다.
THUMB_EDGE = 320


def log(event, **kw):
    """stdout JSON Lines. 플랫폼이 로그를 그대로 보관하고 사람이 읽는다."""
    print(json.dumps({"event": event, **kw}, ensure_ascii=False), flush=True)


class Item:
    """파이프라인을 흐르는 자산 하나."""

    __slots__ = ("asset_id", "src", "image", "text", "bbox", "geom_touched", "meta")

    def __init__(self, asset_id, src, image=None, text=None, bbox=None, meta=None):
        self.asset_id = asset_id
        self.src = src              # 원본 경로(제외 시 화면이 이걸로 되짚는다)
        # 상류 노드가 붙여 놓은 필드(해양이면 timestamp · frame_idx · scene_id).
        # 이걸 버리면 조인이 프레임과 AIS 씬을 붙일 키를 잃는다 — 그때 조인은 실패가
        # 아니라 **0건**으로 끝나서, 원인이 여기라는 사실이 어디에도 남지 않는다.
        self.meta = meta or {}
        self.image = image
        self.text = text
        self.bbox = bbox            # [x, y, w, h] 또는 None
        self.geom_touched = False   # 기하 변형을 거쳤는가(좌표 보정 필요 판정용)


# ── 소스 수집 ────────────────────────────────────────────────────────────────
def collect_upstream(src, limit=None):
    """상류 노드가 남긴 자산 목록을 파일 경로로 돌려준다.

    해양 프리셋의 전처리는 `/datasets` 의 원본이 아니라 **항해 영상 노드가 뽑은 프레임**을
    받는다(목업 SDS_FLOW: 영상→전처리→필터→조인). 원본 이미지가 없는 항차에서 소스를
    훑으면 아무것도 못 찾는다.
    """
    path = os.path.join(src, "assets.jsonl")
    if not os.path.isfile(path):
        raise RuntimeError(f"상류 노드 산출물이 없습니다: {path}")
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line) or {}
            rel = row.get("path")
            if rel:
                rows.append({"path": os.path.join(src, rel), "meta": row})
    rows.sort(key=lambda r: r["path"])
    if not rows:
        raise RuntimeError(f"상류 산출물이 비어 있습니다: {path} — 앞 단계를 다시 실행하세요")
    return rows[:limit] if limit else rows


def collect_sources(datasets_root, sources, limit=None):
    """소스 데이터셋/폴더를 훑어 파일 목록을 만든다. 이미지와 PDF 만 본다.

    경로 순서를 정렬로 고정한다 — 같은 설정이면 같은 표본이 나와야 두 실행의 차이가
    '설정 차이'만 남는다(비교가 성립하는 조건).
    """
    # 소스 표기는 두 가지를 다 받는다.
    #   "1/sds_raw/raw/sample"          — /datasets 기준 상대경로. 하위 폴더까지 지정된다.
    #   {"access":1,"name":"sds_raw"}   — 데이터셋 단위(초기 형태). folder 로 하위 지정.
    # 화면과 다른 노드는 문자열을 쓰므로 그쪽이 정본이고, dict 는 기존 설정을 위한 호환이다.
    if not sources:
        # 여기서 조용히 빈 목록을 돌려주면 "성공, 0건" 이 되어 원인이 사라진다.
        raise RuntimeError("읽을 소스가 지정되지 않았습니다 — 데이터 소스(데이터셋 · 폴더)를 "
                           "먼저 고르세요 (params.sources 가 비어 있습니다)")
    roots = []
    for s in sources:
        if isinstance(s, str):
            roots.append(os.path.join(datasets_root, s.lstrip("/")))
            continue
        base = os.path.join(datasets_root, str(s["access"]), s["name"])
        sub = (s.get("folder") or "/").lstrip("/")
        roots.append(os.path.join(base, sub) if sub else base)

    found = []
    for root in roots:
        if not os.path.isdir(root):
            log("log", level="warn", message=f"소스 경로 없음: {root}")
            continue
        for dirpath, _dirs, files in os.walk(root):
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                if ext in IMAGE_EXT or ext in PDF_EXT:
                    found.append(os.path.join(dirpath, fn))
    found.sort()
    if limit is not None:
        found = found[:limit]
    return found


# ── 기능 구현 ────────────────────────────────────────────────────────────────
def step_clean(item, p):
    """디코딩 · RGB 변환 · EXIF 방향 보정. 열리지 않으면 드롭."""
    retry = int(p.get("retry", 2))
    last = None
    for _ in range(max(1, retry + 1)):
        try:
            img = ImageOps.exif_transpose(item.image)
            if img.mode != "RGB":
                img = img.convert("RGB")
            item.image = img
            return None
        except Exception as e:  # noqa: BLE001 - 한 건 실패가 배치를 죽이지 않는다
            last = e
    return f"decode_error:{type(last).__name__}"


def step_resize(item, p):
    """긴 변을 상한으로 축소. 이미지 토큰 예산을 여기서 잡는다."""
    long_edge = int(p.get("longEdge", 1024))
    w, h = item.image.size
    longest = max(w, h)
    if longest <= long_edge:
        return None
    scale = long_edge / longest
    item.image = item.image.resize((max(1, round(w * scale)), max(1, round(h * scale))))
    item.geom_touched = True
    return None


def step_crop(item, p):
    """가운데 영역만 남긴다."""
    pct = max(1, min(100, int(p.get("cropPct", 90))))
    if pct >= 100:
        return None
    w, h = item.image.size
    nw, nh = max(1, int(w * pct / 100)), max(1, int(h * pct / 100))
    left, top = (w - nw) // 2, (h - nh) // 2
    item.image = item.image.crop((left, top, left + nw, top + nh))
    item.geom_touched = True
    return None


def step_rotate(item, p, rng):
    """무작위 회전 증강. 각도는 run_id+asset_id 로 시드해 같은 설정이면 같은 결과."""
    max_deg = float(p.get("rotDeg", 15))
    if max_deg <= 0:
        return None
    deg = rng.uniform(-max_deg, max_deg)
    item.image = item.image.rotate(deg, expand=True, fillcolor=(0, 0, 0))
    item.geom_touched = True
    return None


def step_flip(item, p, rng):
    """좌우 반전 증강. 적용 비율만큼만 뒤집는다(시드 고정)."""
    pct = max(0, min(100, int(p.get("flipPct", 50))))
    if pct <= 0 or rng.random() * 100 >= pct:
        return None
    item.image = ImageOps.mirror(item.image)
    item.geom_touched = True
    return None


def step_remap(item, _p):
    """기하 변형에 맞춰 bbox 를 다시 계산한다.

    지금은 bbox 를 들고 오는 소스가 없어(SDS 의 AIS bbox 는 join 노드 소관) 실질
    동작은 기하 변형 흔적을 지우는 것뿐이다. 좌표를 가진 자산이 들어오면 여기서
    변환행렬을 적용하도록 확장한다 — 그 전까지는 bbox 를 **버려서** 원본 기준 좌표가
    살아남아 이미지와 어긋나는 일을 막는다.
    """
    if item.bbox is not None and item.geom_touched:
        item.bbox = None
    item.geom_touched = False
    return None


def expand_pdf(item, p):
    """구조 추출 — PDF 를 페이지별 (이미지, 텍스트) 로 편다. 1건 → N건."""
    import fitz  # pymupdf. 이 기능을 켤 때만 필요해서 지역 import.

    dpi = int(p.get("dpi", 200))
    out = []
    with fitz.open(item.src) as doc:
        for pno, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            out.append(Item(f"{item.asset_id}-p{pno:03d}", item.src, img,
                            page.get_text(), meta=item.meta))
    return out


# 이미지 1건을 받아 사유(또는 None)를 돌려주는 기능들.
_UNARY = {
    STEP_CLEAN: step_clean,
    STEP_RESIZE: step_resize,
    STEP_CROP: step_crop,
    STEP_REMAP: step_remap,
}
_RANDOMIZED = {STEP_ROTATE: step_rotate, STEP_FLIP: step_flip}


def _step_parts(step):
    """steps 항목은 [기능명, 파라미터] 또는 {name, params} 둘 다 받는다.

    두 번째 값이 dict 가 아니면(예: 캔버스 표시값 "1024px") 파라미터가 아니라 표시
    문자열이므로 무시하고 기본값으로 돈다 — 문자열에 .get 을 걸면 전 항목이 error 로
    드롭돼 "왜 결과가 0 건이지"가 된다.
    """
    if isinstance(step, (list, tuple)):
        name = step[0]
        raw = step[1] if len(step) > 1 else {}
    else:
        name = step.get("name")
        raw = step.get("params")
    return name, (raw if isinstance(raw, dict) else {})


# ── 실행 ────────────────────────────────────────────────────────────────────
def run(params):
    out_dir = params["out_dir"]
    steps = params.get("steps") or []
    dry_run = bool(params.get("dry_run"))
    sample_size = int(params.get("sample_size", 10))
    run_id = str(params.get("run_id", "run"))
    datasets_root = params.get("datasets_root", "/datasets")

    os.makedirs(os.path.join(out_dir, "assets"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "samples"), exist_ok=True)

    limit = sample_size if dry_run else None
    upstream = (params.get("inputs") or {}).get("assets")
    if upstream:
        entries = collect_upstream(upstream, limit=limit)
    else:
        entries = [{"path": p, "meta": None}
                   for p in collect_sources(datasets_root, params.get("sources") or [],
                                            limit=limit)]
    files = [e["path"] for e in entries]
    log("phase", name="collect", count=len(files), dry_run=dry_run,
        source="upstream" if upstream else "datasets")

    funnel = [{"stage": "수집", "in": len(files), "out": len(files), "dropped": {}, "kind": "source"}]
    drops = []

    # 파일 → Item. 여는 데 실패하면 그 자리에서 드롭(정제 기능 유무와 무관한 하드 실패).
    items = []
    open_err = 0
    for i, entry in enumerate(entries):
        path, meta = entry["path"], entry.get("meta") or {}
        # 상류가 붙인 asset_id 를 그대로 쓴다 — 새로 번호를 매기면 같은 프레임이 노드마다
        # 다른 이름을 갖게 되어 제외 사유를 원본까지 되짚을 수 없다.
        asset_id = meta.get("asset_id") or f"a{i:06d}"
        if os.path.splitext(path)[1].lower() in PDF_EXT:
            items.append(Item(asset_id, path, None, None, meta=meta))
            continue
        try:
            items.append(Item(asset_id, path, Image.open(path), meta=meta))
        except Exception as e:  # noqa: BLE001
            drops.append({"asset_id": asset_id, "src": path, "stage": "적재",
                          "reason": f"open_error:{type(e).__name__}"})
            open_err += 1
    funnel.append({"stage": "적재", "in": len(files), "out": len(items),
                   "dropped": ({"open_error": open_err} if open_err else {}), "kind": "filter"})

    step_names = [_step_parts(s)[0] for s in steps]

    # PDF 는 구조 추출을 켜야만 처리된다. 안 켜면 이미지가 없어 이후 기능이 전부 실패하므로
    # 여기서 명시적으로 드롭한다(뒤에서 알 수 없는 에러로 죽는 것보다 사유가 분명하다).
    if STEP_STRUCT not in step_names:
        kept, pdf_dropped, n_before = [], 0, len(items)
        for it in items:
            if it.image is None:
                drops.append({"asset_id": it.asset_id, "src": it.src, "stage": "적재",
                              "reason": "pdf_without_구조추출"})
                pdf_dropped += 1
            else:
                kept.append(it)
        if pdf_dropped:
            funnel.append({"stage": "적재(PDF)", "in": n_before, "out": len(kept),
                           "dropped": {"pdf_without_구조추출": pdf_dropped}, "kind": "filter"})
        items = kept

    # 기능을 목록 순서대로 적용한다. 노드 안에서 순차 실행 — 기능마다 잡을 띄우면
    # 중간 이미지를 기능 수만큼 NFS 에 왕복시키게 된다.
    for step in steps:
        name, sparams = _step_parts(step)
        n_in = len(items)
        dropped = {}

        if name == STEP_STRUCT:
            expanded = []
            for it in items:
                if it.image is not None:      # 이미 이미지인 자산은 그대로 통과
                    expanded.append(it)
                    continue
                try:
                    expanded.extend(expand_pdf(it, sparams))
                except Exception as e:  # noqa: BLE001
                    reason = f"pdf_error:{type(e).__name__}"
                    drops.append({"asset_id": it.asset_id, "src": it.src, "stage": name, "reason": reason})
                    dropped[reason] = dropped.get(reason, 0) + 1
            items = expanded
            funnel.append({"stage": name, "in": n_in, "out": len(items), "dropped": dropped, "kind": "expand"})
            log("phase", name=name, **{"in": n_in, "out": len(items)})
            continue

        fn = _UNARY.get(name)
        rnd = _RANDOMIZED.get(name)
        if fn is None and rnd is None:
            log("log", level="warn", message=f"모르는 기능 — 건너뜀: {name!r}")
            continue

        kept = []
        for it in items:
            # 아직 이미지가 없는 자산(= 구조 추출 전의 PDF)에는 이미지 연산을 걸지 않는다.
            # 걸면 '정제'가 '구조 추출'보다 앞에 있을 때 PDF 가 전부 decode_error 로
            # 사라진다 — 기능 순서는 사용자가 정하므로 순서에 의존하면 안 된다.
            if it.image is None:
                kept.append(it)
                continue
            try:
                if rnd is not None:
                    # 시드를 run_id+asset_id+기능명으로 고정 → 같은 설정이면 같은 결과가 나와
                    # 두 실행의 차이가 '설정 차이'만 남는다.
                    reason = rnd(it, sparams, random.Random(f"{run_id}:{it.asset_id}:{name}"))
                else:
                    reason = fn(it, sparams)
            except Exception as e:  # noqa: BLE001 - 한 건 실패가 배치를 죽이지 않는다
                reason = f"error:{type(e).__name__}"
            if reason:
                drops.append({"asset_id": it.asset_id, "src": it.src, "stage": name, "reason": reason})
                dropped[reason] = dropped.get(reason, 0) + 1
            else:
                kept.append(it)
        items = kept
        funnel.append({"stage": name, "in": n_in, "out": len(items), "dropped": dropped, "kind": "filter"})
        log("phase", name=name, **{"in": n_in, "out": len(items)})

    # 기하 변형을 걸고 좌표 보정을 안 걸면 bbox 가 원본 기준으로 남는다 — 경고로 남긴다.
    warn_remap = bool(GEOMETRIC_STEPS & set(step_names)) and STEP_REMAP not in step_names

    # ── 산출 ────────────────────────────────────────────────────────────────
    n_sample = 0
    with open(os.path.join(out_dir, "assets.jsonl"), "w", encoding="utf-8") as f:
        for it in items:
            rel = f"assets/{it.asset_id}.jpg"
            it.image.save(os.path.join(out_dir, rel), quality=90)
            if n_sample < SAMPLE_LIMIT:
                th = it.image.copy()
                th.thumbnail((THUMB_EDGE, THUMB_EDGE))
                th.save(os.path.join(out_dir, "samples", f"{it.asset_id}.jpg"), quality=80)
                n_sample += 1
            w, h = it.image.size
            # 상류 필드를 먼저 깔고 이 노드가 바꾼 것(경로·크기)으로 덮는다.
            row = {**it.meta, "asset_id": it.asset_id, "src": it.src,
                   "path": rel, "w": w, "h": h}
            if it.text:
                row["text"] = it.text
            if it.bbox:
                row["bbox"] = it.bbox
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with open(os.path.join(out_dir, "drops.jsonl"), "w", encoding="utf-8") as f:
        for d in drops:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    summary = {
        "node": "prep", "run_id": run_id, "node_index": params.get("node_index"),
        "dry_run": dry_run, "in": len(files), "out": len(items),
        "dropped_total": len(drops), "sample_count": n_sample,
        "warn_coord_remap_missing": warn_remap,
        "funnel": funnel,
    }
    with open(os.path.join(out_dir, "funnel.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 어떤 설정으로 돌렸는지를 산출물 옆에 남긴다. 이게 없으면 두 결과를 나란히 놔도
    # 무엇이 달라서 그런지 알 수 없어 비교가 의미를 잃는다.
    with open(os.path.join(out_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"steps": steps, "sources": params.get("sources"),
                   "dry_run": dry_run, "sample_size": sample_size,
                   "created_at": time.strftime("%Y-%m-%d %H:%M:%S")},
                  f, ensure_ascii=False, indent=2)

    log("metric", name="prep/in", value=len(files))
    log("metric", name="prep/out", value=len(items))
    log("metric", name="prep/dropped", value=len(drops))
    if warn_remap:
        log("log", level="warn",
            message="기하 변형이 있는데 '영역 좌표 보정'이 빠졌습니다 — bbox 를 쓰는 자산이면 좌표가 어긋납니다")
    print(f"[dp_prep] {len(files)} → {len(items)} (제외 {len(drops)}) → {out_dir}", flush=True)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="데이터 파이프라인 전처리 노드")
    ap.add_argument("--params_path", required=True, help="노드 설정 JSON 경로")
    args = ap.parse_args(argv)

    with open(args.params_path, encoding="utf-8") as f:
        params = json.load(f)
    if not params.get("out_dir"):
        params["out_dir"] = os.path.dirname(os.path.abspath(args.params_path))

    try:
        run(params)
    except Exception as e:  # noqa: BLE001 - 사유를 남기고 비-0 으로 죽는다
        log("error", code="E_PREP_FAILED", message=f"{type(e).__name__}: {e}", fatal=True)
        raise


if __name__ == "__main__":
    main()
