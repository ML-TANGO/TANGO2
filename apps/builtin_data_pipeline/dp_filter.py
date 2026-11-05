#!/usr/bin/env python3
"""데이터 파이프라인 — 필터 노드(kind=filter, stage=filter).

스케줄러가 빌트인 잡 pod 안에서 아래로 실행한다.

    python3 -u /built_in/dp_filter.py --params_path=/dataset/_runs/<run_id>/<node_index>/params.json

전처리를 통과한 자산에서 학습에 해가 되는 것을 걸러 낸다. 버리는 노드이므로 **왜 버렸는지**를
남기는 것이 본체다 — 사유 없이 숫자만 줄면 사용자는 기준이 과한지 데이터가 나쁜지 알 수 없다.

이 노드는 상류 노드의 산출물을 읽는다(소스 데이터셋이 아니다).
BE 가 params.inputs 에 상류 out_dir 을 넣어 준다.

    inputs = {"assets": "/dataset/_runs/<run>/<idx>"}   # dp_prep 등의 산출

산출(out_dir 아래)
  config.json    이 실행에 쓴 기능 목록·파라미터 (비교의 기준)
  assets.jsonl   통과한 자산
  drops.jsonl    제외된 자산: 어느 기능에서 왜 (+ 근거 수치)
  funnel.json    [{stage, in, out, dropped{사유:건수}}]
  assets/        통과 자산 이미지(다음 노드의 입력)
  samples/       화면에 보여줄 썸네일 일부

제외 자산의 이미지는 복사하지 않는다 — 상류 산출물이 그대로 남아 있으므로 화면은
상류 실행의 미리보기에서 원본을 본다.
"""
import argparse
import json
import os
import re
import shutil
import time

# ── 기능 이름 (BE constants.FILTER_LIBRARY 의 key 와 문자 단위로 같아야 한다) ──
STEP_DEDUP = "중복 제거"
# '저품질 이미지' 한 스위치를 셋으로 쪼갰다 — 해양 프레임(선명도 1.8~9.8 실측)에서
# 해상도 컷만 켜려면 흐림과 분리돼야 한다. BE constants.FILTER_LIBRARY 와 key 가 같아야 한다.
STEP_BLUR = "흐림"
STEP_MIN_EDGE = "최소 해상도"
STEP_EXPO = "노출 이상"
STEP_SENSITIVE = "민감 콘텐츠"

TS_FMT = "%Y-%m-%d %H:%M:%S"
SAMPLE_LIMIT = 24          # 화면 썸네일 상한. 전량 뽑으면 용량이 터진다.
THUMB_EDGE = 320

# pHash 는 64비트라 해밍거리 0~64 다. 화면의 '비슷한 이미지 기준값'(80~99%)을
# 거리로 환산한다: 95% → 3, 92% → 5(프로토타입 기본값과 같은 자리).
PHASH_BITS = 64

# 셋 다 화면에서 조절한다. 아래는 설정이 없을 때의 기본값(라이브러리 default 와 같다).
BLUR_DEFAULT = 40.0
MIN_EDGE_DEFAULT = 512
EXPO_STD_DEFAULT = 25.0
EXPO_LOW, EXPO_HIGH = 15.0, 240.0
# 평균이 극단이면서 **분산이 낮을 때만** 노출 이상으로 본다. 흰 종이에 검은 글씨인
# 문서는 평균이 높지만 분산도 높아, 이 조건이 없으면 문서가 통째로 탈락한다.
# 그 분산 하한이 화면의 '대비 하한' 이다.

# 문서 페이지는 이미지가 서로 비슷해 pHash 로는 안 갈린다. 추출된 텍스트의
# 단어집합 자카드로 가른다(모델 불요).
TEXT_SIM = 0.9
TEXT_MIN_WORDS = 5
_WORD_RE = re.compile(r"\w+")


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
    """상류 산출물. 없으면 어느 단계를 먼저 돌려야 하는지 말하고 죽는다."""
    src = (inputs or {}).get("assets")
    if not src:
        raise RuntimeError("상류 노드 산출물 경로가 없습니다 — 앞 단계를 먼저 실행하세요 (inputs.assets)")
    path = os.path.join(src, "assets.jsonl")
    if not os.path.isfile(path):
        raise RuntimeError(f"상류 산출물이 없습니다: {path}")
    return read_jsonl(path), src


# ── 품질 ────────────────────────────────────────────────────────────────────
def _gray(image):
    import numpy as np
    return np.asarray(image.convert("L"), dtype=np.float64)


def laplacian_variance(image):
    """라플라시안 분산 = 선명도. 값이 낮을수록 흐리다."""
    import numpy as np
    from numpy.lib.stride_tricks import sliding_window_view
    g = _gray(image)
    if g.shape[0] < 3 or g.shape[1] < 3:
        return 0.0
    kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float64)
    lap = (sliding_window_view(g, (3, 3)) * kernel).sum(axis=(-1, -2))
    return float(lap.var())


# 검사 셋을 따로 둔다. 하나로 묶여 있으면 사용자가 끄고 켤 수 없고, funnel 에도 어느
# 검사가 몇 건을 떨어뜨렸는지 남지 않는다(합계만 보인다).
def min_edge_reason(image, limit):
    w, h = image.size
    if min(w, h) < limit:
        return "low_resolution", {"min_edge": min(w, h), "limit": limit}
    return None, {"min_edge": min(w, h)}


def exposure_reason(image, std_min):
    g = _gray(image)
    lum, std = float(g.mean()), float(g.std())
    if (lum > EXPO_HIGH or lum < EXPO_LOW) and std < std_min:
        return "exposure", {"luma": round(lum, 1), "std": round(std, 1), "std_limit": std_min}
    return None, {"luma": round(lum, 1), "std": round(std, 1)}


def blur_reason(image, blur_min):
    var = laplacian_variance(image)
    if var < blur_min:
        return "blur", {"sharpness": round(var, 1), "limit": blur_min}
    return None, {"sharpness": round(var, 1)}


# ── 중복 ────────────────────────────────────────────────────────────────────
def _word_set(text):
    return set(_WORD_RE.findall((text or "").lower()))


def _jaccard(a, b):
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def dedup_verdicts(items, images, max_dist):
    """자산별 (사유, 근거) 또는 (None, _).

    1) pHash 근접중복 — 이미지 전반.
    2) 텍스트 자카드 — 문서 페이지처럼 text 가 있는 자산. 흰 배경에 글씨인 문서는
       이미지가 서로 비슷해 pHash 로 안 갈리고, 통째로 지우면 서로 다른 페이지가
       사라진다. 그래서 본문 단어로 가른다.

    의미 기반(CLIP) 중복 제거는 모델이 필요해 이 노드에 없다. 프로토타입에서도
    문서 페이지 오탐이 11% 나온 축이라, 붙일 때 별도 검증이 필요하다.
    """
    import imagehash
    verdicts = [(None, {}) for _ in items]
    kept_hashes = []
    survivors = []
    for i, image in enumerate(images):
        if image is None:
            verdicts[i] = ("decode_error", {})
            continue
        try:
            ph = imagehash.phash(image)
        except Exception as e:  # noqa: BLE001 - 한 장이 나빠도 배치를 죽이지 않는다
            verdicts[i] = ("hash_error", {"message": str(e)[:120]})
            continue
        hit = next((kh for kh in kept_hashes if (ph - kh) <= max_dist), None)
        if hit is not None:
            verdicts[i] = ("near_duplicate", {"distance": int(ph - hit), "limit": max_dist})
        else:
            kept_hashes.append(ph)
            survivors.append(i)

    kept_words = []
    for i in survivors:
        ws = _word_set(items[i].get("text"))
        if len(ws) < TEXT_MIN_WORDS:
            # 단어가 너무 적으면 자카드가 우연히 높게 나온다. 지우지 않고 남긴다.
            continue
        sim = max((_jaccard(ws, kws) for kws in kept_words), default=0.0)
        if sim >= TEXT_SIM:
            verdicts[i] = ("text_duplicate", {"similarity": round(sim, 3), "limit": TEXT_SIM})
        else:
            kept_words.append(ws)
    return verdicts


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
    from PIL import Image

    out_dir = params["out_dir"]
    steps = params.get("steps") or []
    dry_run = bool(params.get("dry_run"))
    sample_size = int(params.get("sample_size", 10))
    run_id = str(params.get("run_id", "run"))

    os.makedirs(os.path.join(out_dir, "assets"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "samples"), exist_ok=True)

    enabled = _step_params(steps)
    dup_th = float((enabled.get(STEP_DEDUP) or {}).get("dupTh", 95) or 95)
    max_dist = max(0, round((100.0 - dup_th) / 100.0 * PHASH_BITS))
    blur_min = float((enabled.get(STEP_BLUR) or {}).get("blur") or BLUR_DEFAULT)
    min_edge = int((enabled.get(STEP_MIN_EDGE) or {}).get("minEdge") or MIN_EDGE_DEFAULT)
    expo_std = float((enabled.get(STEP_EXPO) or {}).get("expoStd") or EXPO_STD_DEFAULT)

    items, src_dir = load_upstream(params.get("inputs"))
    if dry_run:
        items = items[:sample_size]
    log("phase", name="collect", count=len(items), dry_run=dry_run)

    funnel = [{"stage": "수집", "in": len(items), "out": len(items), "dropped": {}, "kind": "source"}]
    drops = []

    # 이미지를 한 번만 연다. 품질·중복이 같은 픽셀을 보므로 두 번 열면 IO 가 두 배다.
    images = []
    for it in items:
        path = os.path.join(src_dir, it.get("path") or "")
        try:
            with Image.open(path) as im:
                images.append(im.convert("RGB"))
        except Exception as e:  # noqa: BLE001 - 못 여는 자산은 사유를 남기고 뺀다
            images.append(None)
            log("log", level="warn", message=f"이미지를 열지 못했습니다({it.get('asset_id')}): {e}")

    alive = [True] * len(items)

    def _apply(step, check):
        """검사 하나를 **아직 살아 있는** 자산에만 적용하고 funnel 에 한 단계로 남긴다.

        이미 떨어진 것을 다시 세면 단계별 in/out 이 어긋나 사용자가 어디서 빠졌는지
        읽을 수 없다.
        """
        if step not in enabled:
            return
        before = sum(alive)
        by_reason = {}
        for i in range(len(items)):
            if not alive[i] or images[i] is None:
                continue
            reason, detail = check(images[i])
            if reason:
                alive[i] = False
                by_reason[reason] = by_reason.get(reason, 0) + 1
                drops.append({"asset_id": items[i].get("asset_id"), "src": items[i].get("src"),
                              "step": step, "reason": reason, "detail": detail})
        funnel.append({"stage": step, "in": before, "out": sum(alive),
                       "dropped": by_reason, "kind": "filter"})

    # 싼 검사부터: 크기(픽셀 안 봄) → 밝기·대비(그레이 한 번) → 흐림(라플라시안).
    _apply(STEP_MIN_EDGE, lambda im: min_edge_reason(im, min_edge))
    _apply(STEP_EXPO, lambda im: exposure_reason(im, expo_std))
    _apply(STEP_BLUR, lambda im: blur_reason(im, blur_min))

    if STEP_DEDUP in enabled:
        live_idx = [i for i, ok in enumerate(alive) if ok]
        verdicts = dedup_verdicts([items[i] for i in live_idx],
                                  [images[i] for i in live_idx], max_dist)
        before = len(live_idx)
        by_reason = {}
        for pos, i in enumerate(live_idx):
            reason, detail = verdicts[pos]
            if reason:
                alive[i] = False
                by_reason[reason] = by_reason.get(reason, 0) + 1
                drops.append({"asset_id": items[i].get("asset_id"), "src": items[i].get("src"),
                              "step": STEP_DEDUP, "reason": reason, "detail": detail})
        funnel.append({"stage": STEP_DEDUP, "in": before, "out": sum(alive),
                       "dropped": by_reason, "kind": "filter"})

    if STEP_SENSITIVE in enabled:
        # 유해 이미지·개인정보 검출은 모델이 필요해 이 노드에 없다. 조용히 통과시키면
        # 안전 필터가 도는 줄 알게 되므로, 켜져 있으면 분명히 말하고 넘어간다.
        log("log", level="warn",
            message=f"'{STEP_SENSITIVE}' 는 아직 동작하지 않습니다(판별 모델 미연결) — "
                    "이 실행에서는 걸러지지 않았습니다")
        funnel.append({"stage": STEP_SENSITIVE, "in": sum(alive), "out": sum(alive),
                       "dropped": {}, "kind": "filter", "note": "미구현(모델 미연결)"})

    n_sample = 0
    kept_n = 0
    with open(os.path.join(out_dir, "assets.jsonl"), "w", encoding="utf-8") as f:
        for i, it in enumerate(items):
            if not alive[i]:
                continue
            asset_id = it.get("asset_id") or f"k{i:06d}"
            rel = f"assets/{asset_id}.jpg"
            try:
                shutil.copyfile(os.path.join(src_dir, it.get("path") or ""),
                                os.path.join(out_dir, rel))
            except OSError as e:
                drops.append({"asset_id": asset_id, "src": it.get("src"), "step": "출력",
                              "reason": "copy_failed", "detail": {"message": str(e)[:120]}})
                continue
            if n_sample < SAMPLE_LIMIT and images[i] is not None:
                th = images[i].copy()
                th.thumbnail((THUMB_EDGE, THUMB_EDGE))
                th.save(os.path.join(out_dir, "samples", f"{asset_id}.jpg"), quality=80)
                n_sample += 1
            kept_n += 1
            f.write(json.dumps({**it, "path": rel}, ensure_ascii=False) + "\n")

    with open(os.path.join(out_dir, "drops.jsonl"), "w", encoding="utf-8") as f:
        for d in drops:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    # 마지막 단계의 out 은 실제로 써 낸 건수와 맞춰야 화면 숫자와 파일 수가 어긋나지 않는다.
    if len(funnel) > 1:
        funnel[-1]["out"] = kept_n

    summary = {
        "node": "filter", "run_id": run_id, "node_index": params.get("node_index"),
        "dry_run": dry_run, "in": len(items), "out": kept_n,
        "dropped_total": len(drops), "sample_count": n_sample,
        # 켜진 검사의 기준값만 남긴다 — 끈 검사의 값을 적어 두면 나중에 그것이
        # 적용된 줄 오해한다.
        "thresholds": {
            **({"dup_max_distance": max_dist} if STEP_DEDUP in enabled else {}),
            **({"min_edge": min_edge} if STEP_MIN_EDGE in enabled else {}),
            **({"expo_std": expo_std} if STEP_EXPO in enabled else {}),
            **({"blur_min": blur_min} if STEP_BLUR in enabled else {}),
        },
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

    log("metric", name="filter/in", value=len(items))
    log("metric", name="filter/out", value=kept_n)
    log("metric", name="filter/dropped", value=len(drops))
    if items and not kept_n:
        # 어느 검사가 전부 떨어뜨렸는지 말해 준다 — 켜지도 않은 검사의 값을 안내하면
        # 사용자가 엉뚱한 슬라이더를 만진다.
        applied = ", ".join(
            f"{name} {val}" for name, val, on in (
                ("짧은 변 최소", min_edge, STEP_MIN_EDGE in enabled),
                ("대비 하한", expo_std, STEP_EXPO in enabled),
                ("선명도 하한", blur_min, STEP_BLUR in enabled),
                ("중복 허용거리", max_dist, STEP_DEDUP in enabled),
            ) if on)
        log("log", level="warn",
            message=f"전부 걸러졌습니다 — 기준값이 이 데이터에 과한지 확인하세요({applied})")
    print(f"[dp_filter] {len(items)} → {kept_n} (제외 {len(drops)}) → {out_dir}", flush=True)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="데이터 파이프라인 필터 노드")
    ap.add_argument("--params_path", required=True, help="노드 설정 JSON 경로")
    args = ap.parse_args(argv)

    with open(args.params_path, encoding="utf-8") as f:
        params = json.load(f)
    if not params.get("out_dir"):
        params["out_dir"] = os.path.dirname(os.path.abspath(args.params_path))

    try:
        run(params)
    except Exception as e:  # noqa: BLE001 - 사유를 남기고 비-0 으로 죽는다
        log("error", code="E_FILTER_FAILED", message=f"{type(e).__name__}: {e}", fatal=True)
        raise


if __name__ == "__main__":
    main()
