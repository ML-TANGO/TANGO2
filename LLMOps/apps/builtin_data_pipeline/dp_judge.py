#!/usr/bin/env python3
"""데이터 파이프라인 — VLM 심사 노드(kind=gate, stage=gate).

    python3 -u /built_in/dp_judge.py --params_path=/dataset/_runs/<run_id>/<node_index>/params.json

생성 노드가 만든 서술·조언을 4축으로 채점하고 임계값으로 게이트한다.

    situation_accuracy   서술이 AIS·이미지 사실과 일치하는가      (루브릭)
    colreg_correctness   조우유형·조항·피항 판단이 타당한가        (루브릭 + **앵커 대조**)
    actionability        변침각·CPA·안전속력처럼 구체적인가        (루브릭)
    image_grounding      이미지를 실제로 보고 썼는가              (**어블레이션**)

두 축이 평점이 아니라는 점이 이 노드의 핵심이다.

  · colreg_correctness — 앞 노드가 기하로 계산해 둔 조우유형·조항이 조언에 실제로
    등장하는지 문자로 대조한다. 없으면 모델이 몇 점을 줬든 **0 으로 강등**한다.
    모델의 답을 모델의 점수로만 검증하면 같은 맹점이 통과한다.
  · image_grounding — 점수를 물어보지 않는다. 같은 AIS 만으로 **이미지 없이** 조언을
    다시 만들게 하고, 원본과 같은 조치인지 비교해 `1 - 같음` 으로 정한다. 이미지를 보지
    않고도 같은 답이 나온다면 그 조언은 이미지에 근거한 것이 아니다.

레코드당 판사 호출 3회(루브릭 / 어블레이션 생성 / 어블레이션 비교). 어블레이션 생성도
**판사**가 한다(프로토타입과 같음) — 생성 모델을 함께 띄우지 않아도 되므로 이 노드는
판사 서빙 하나만 필요하다.

게이트 미달 레코드는 **버리지 않는다.** 재생성·사람 검수 대상이므로 점수와 실패 축을
달아 그대로 흘려보낸다(버리면 왜 떨어졌는지 화면에서 볼 수 없다).

상류(BE 가 params.inputs 에 넣어 준다)
    inputs  = {"records": "/dataset/_runs/<run>/<idx>"}   # dp_generate 산출
    serving = {"judge": {"url": "http://...:18555/", "model_id": "..."}}

산출(out_dir 아래)
  config.json     이 실행에 쓴 임계값·모델 (비교의 기준)
  records.jsonl   채점된 레코드 전량 (scores · gate_passed · failed_axes)
  drops.jsonl     채점 자체가 불가능했던 레코드: 왜(서빙 오류·파싱 실패)
  funnel.json     수집 → 채점 → 게이트
  assets/         레코드 이미지(다음 노드 = 조립)
"""
import argparse
import base64
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

TS_FMT = "%Y-%m-%d %H:%M:%S"
SAMPLE_LIMIT = 24
THUMB_EDGE = 320

REQUEST_TIMEOUT_S = 300
DEFAULT_CONCURRENCY = 4

# BE constants.SDS_THRESHOLDS 와 같은 값. 설정을 저장하지 않은 파이프라인의 기본값이다.
DEFAULT_THRESHOLDS = {"situation_accuracy": 0.75, "colreg_correctness": 0.80,
                      "image_grounding": 0.70, "actionability": 0.75}
RUBRIC_AXES = ("situation_accuracy", "colreg_correctness", "actionability")
ALL_AXES = ("situation_accuracy", "colreg_correctness", "image_grounding", "actionability")

# 조우유형이 조언에 등장했는지 볼 때 인정하는 표기. 한국어 생성과 영어 생성을 모두 받는다.
ENCOUNTER_KW = {
    "head_on": ["head_on", "head-on", "정면", "마주"],
    "crossing": ["crossing", "교차", "횡단"],
    "overtaking": ["overtaking", "추월", "앞지르"],
    "safe": ["safe", "안전", "위험 없"],
}

RUBRIC_P = (
    "당신은 해상 항해 조력 평가자다. AIS 정보와 이미지, 아래 생성된 서술/조언을 보고 "
    "세 축을 0~1로 채점하라. situation_accuracy(서술이 AIS·이미지 사실과 일치), "
    "colreg_correctness(COLREG 조우유형·조항·give-way 판단이 타당), "
    "actionability(구체적·안전한 조치: 변침각·CPA·안전속력).\n"
    "AIS:\n{ais}\n\n서술: {describe}\n조언: {advice}\n\n"
    'JSON만: {{"situation_accuracy":{{"score":..}},"colreg_correctness":{{"score":..}},'
    '"actionability":{{"score":..}}}}'
)
# 지시를 **데이터 뒤에** 두고 형식 태그를 요구한다.
# 예전에는 "…생성하라\nAIS:\n{ais}" 였는데, 프롬프트가 AIS 블록으로 끝나 모델이 조언 대신
# AIS 행을 계속 이어 썼다(2B·8B 모두). 그러면 비교 점수가 난수가 되고 image_grounding 축이
# 통째로 무의미해진다. 생성 노드에서 검증된 순서(데이터 → 지시 → 태그)를 따른다.
ABLATE_P = ("{ais}\n\n위 AIS 정보만 보고(이미지 없음) 항해 조언을 한 문장으로 작성하라.\n"
            "반드시 <advice>...</advice> 형식으로만 답하라.")
_ADVICE_RE = re.compile(r"<advice>(.*?)</advice>", re.DOTALL | re.IGNORECASE)
ABLATE_CMP_P = ("두 조언이 실질적으로 같은 조치인가? 0(다름)~1(같음) score만 JSON으로.\n"
                "A(이미지없음): {pred}\nB(원본): {advice}")


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
    """생성 노드 산출물. 없으면 어느 단계를 먼저 돌려야 하는지 말하고 죽는다."""
    src = (inputs or {}).get("records")
    if not src:
        raise RuntimeError("상류 노드 산출물 경로가 없습니다 — 생성 단계를 먼저 "
                           "실행하세요 (inputs.records)")
    path = os.path.join(src, "assets.jsonl")
    if not os.path.isfile(path):
        raise RuntimeError(f"생성 노드 산출물이 없습니다: {path}")
    return read_jsonl(path), src


def resolve_serving(params):
    url = ((params.get("serving") or {}).get("judge") or {}).get("url")
    if not url:
        raise RuntimeError("심사 모델 서빙 주소가 없습니다(params.serving.judge.url) — "
                           "모델 배포가 준비된 뒤에 실행됩니다")
    return url


# ── 파싱 ────────────────────────────────────────────────────────────────────
def _json_object(raw):
    """판사 응답에서 JSON 객체를 뽑는다. 코드펜스와 앞뒤 잡담을 견딘다."""
    text = (raw or "").strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return {}
    return {}


def _clamp(v):
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return None


def _axis_score_from_text(text, ax):
    """JSON 이 아닌 답에서 축 점수를 건져낸다.

    작은 판사 모델은 형식 지시를 자주 무시하고 이렇게 답한다:
        - situation_accuracy: 0.6
        1. situation_accuracy: 0점 (근거...)
    축 이름 바로 뒤의 첫 숫자면 그 축의 점수로 볼 수 있다. 읽을 수 있는 답을 형식만
    이유로 버리면 레코드가 통째로 사라지고, 그 손실은 화면에서 '제외'로만 보인다.
    """
    m = re.search(rf"{re.escape(ax)}\D{{0,24}}?([0-9]*\.?[0-9]+)", text or "", re.IGNORECASE)
    if not m:
        return None
    v = _clamp(m.group(1))
    if v is None:
        return None
    # "80" 처럼 백분율로 답하는 경우가 있다. 1 을 넘는 값은 100 분율로 보고 환산한다.
    raw_v = float(m.group(1))
    return v if raw_v <= 1.0 else _clamp(raw_v / 100.0)


def parse_rubric(raw, axes=RUBRIC_AXES):
    """{축: (점수, 근거)}. JSON 이 우선이고, 아니면 축 이름 옆 숫자를 읽는다.

    끝까지 못 읽으면 실패로 올려 그 레코드만 격리한다 — 점수를 지어내면 게이트가
    통과율만 만들어 내고 걸러내지 못한다.
    """
    obj = _json_object(raw)
    out = {}
    for ax in axes:
        node = obj.get(ax)
        score, why = None, ""
        if isinstance(node, dict) and "score" in node:
            score, why = _clamp(node["score"]), str(node.get("rationale") or "")
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            score = _clamp(node)
        if score is None:
            score = _axis_score_from_text(raw, ax)
            why = "[비JSON 응답에서 숫자만 추출]"
        if score is None:
            raise ValueError(f"루브릭에 '{ax}' 축이 없습니다: {(raw or '')[:120]!r}")
        out[ax] = (score, why)
    return out


def parse_same_score(raw):
    """어블레이션 비교 점수. 판사가 그냥 숫자만 답하는 경우가 잦아 폭넓게 받는다.

    끝까지 숫자가 없으면 0.5 로 둔다 — 비교 응답 하나가 망가졌다고 레코드를 버리면
    이미지 근거성만 못 재는 상황이 레코드 유실로 번진다.
    """
    obj = _json_object(raw)
    if "score" in obj:
        v = _clamp(obj["score"])
        if v is not None:
            return v
    m = re.search(r"[-+]?\d*\.?\d+", raw or "")
    return _clamp(m.group(0)) if m else 0.5


# ── 앵커 대조 ───────────────────────────────────────────────────────────────
def colreg_anchor_ok(advice, facts):
    """계산된 조우유형이나 조항이 조언에 실제로 등장하는가.

    둘 중 하나만 있어도 통과로 본다(프로토타입과 같은 판정) — 조항만 인용하고 유형을
    말로 안 쓰는 답도 규칙을 짚은 것은 맞다.
    """
    text = (advice or "").lower()
    enc_ok = any(kw.lower() in text for kw in ENCOUNTER_KW.get(facts.get("encounter"), []))
    articles = facts.get("articles") or []
    art_ok = (not articles) or any(
        re.search(rf"(?<!\d){a}(?!\d)", advice or "") for a in articles)
    return enc_ok or art_ok


# ── 서빙 호출 ───────────────────────────────────────────────────────────────
def call_vlm(url, prompt, image_b64, session_id):
    body = {"test_type": "question", "test_question": prompt, "session_id": session_id}
    if image_b64:
        body["images"] = [image_b64]
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"서빙 HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}") from e
    if isinstance(payload, list) and payload:
        return payload[0].get("output") or ""
    if isinstance(payload, dict):
        return payload.get("output") or ""
    raise RuntimeError(f"서빙 응답 형식을 모르겠습니다: {str(payload)[:160]}")


def _b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def score_one(url, rec, abs_path):
    """레코드 하나 채점. 판사 호출 3회. 반환: (scores, rationales)."""
    facts = rec.get("colreg") or {}
    ais = rec.get("ais_text_en") if rec.get("lang") == "en" else rec.get("ais_text_ko")
    describe, advice = rec.get("describe") or "", rec.get("advice") or ""
    key = rec.get("record_key") or rec.get("asset_id")

    # 1) 루브릭 3축 — 이미지와 함께 본다.
    raw = call_vlm(url, RUBRIC_P.format(ais=ais, describe=describe, advice=advice),
                   _b64(abs_path), f"dpjudge-{key}-rubric")
    rub = parse_rubric(raw)
    scores = {ax: rub[ax][0] for ax in RUBRIC_AXES}
    why = {ax: rub[ax][1] for ax in RUBRIC_AXES}

    # 2) 앵커 대조 — 모델 점수보다 이것이 우선한다.
    if not colreg_anchor_ok(advice, facts):
        scores["colreg_correctness"] = 0.0
        why["colreg_correctness"] = (why.get("colreg_correctness", "")
                                     + f" [앵커 불일치({facts.get('encounter')}"
                                       f"/{facts.get('articles')}) → 0 강등]").strip()

    # 3) 어블레이션 — 이미지 없이 만든 조언이 원본과 같은지.
    pred = None
    for attempt in (1, 2):
        raw_ab = call_vlm(url, ABLATE_P.format(ais=ais), None,
                          f"dpjudge-{key}-ablate-{attempt}")
        m = _ADVICE_RE.search(raw_ab or "")
        if m and m.group(1).strip():
            pred = m.group(1).strip()
            break
    if pred is None:
        # 조언을 못 받았으면 비교할 대상이 없다. 숫자를 지어내는 대신 **미측정**으로 둔다 —
        # 난수 같은 점수로 게이트를 굴리면 통과율이 의미를 잃는다.
        scores["image_grounding"] = None
        why["image_grounding"] = "미측정(이미지 없는 조언을 형식대로 받지 못했습니다)"
        return scores, why

    cmp_raw = call_vlm(url, ABLATE_CMP_P.format(pred=pred, advice=advice), None,
                       f"dpjudge-{key}-cmp")
    same = parse_same_score(cmp_raw)
    scores["image_grounding"] = round(1.0 - same, 3)
    why["image_grounding"] = f"이미지 없이 생성={pred[:80]!r}; 동일도={same:.2f}"
    return scores, why


# ── 실행 ────────────────────────────────────────────────────────────────────
def _thumb(src, dst):
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
    dry_run = bool(params.get("dry_run"))
    sample_size = int(params.get("sample_size", 10))
    run_id = str(params.get("run_id", "run"))
    cfg = params.get("config") or {}
    concurrency = max(int(params.get("concurrency") or DEFAULT_CONCURRENCY), 1)

    thresholds = {**DEFAULT_THRESHOLDS, **(cfg.get("thresholds") or {})}
    os.makedirs(os.path.join(out_dir, "assets"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "samples"), exist_ok=True)

    url = resolve_serving(params)
    items, src_dir = load_upstream(params.get("inputs"))
    if dry_run:
        items = items[:sample_size]
    log("phase", name="collect", count=len(items), dry_run=dry_run,
        concurrency=concurrency, thresholds=thresholds,
        model=((params.get("serving") or {}).get("judge") or {}).get("model_id"))

    funnel = [{"stage": "수집", "in": len(items), "out": len(items), "dropped": {}, "kind": "source"}]
    drops, by_reason = [], {}

    usable = []
    for it in items:
        abs_path = os.path.join(src_dir, it.get("path") or "")
        if not os.path.isfile(abs_path):
            drops.append({"record_key": it.get("record_key"), "reason": "image_missing",
                          "message": f"상류 이미지가 없습니다: {it.get('path')}"})
            by_reason["image_missing"] = by_reason.get("image_missing", 0) + 1
            continue
        usable.append((it, abs_path))

    t0 = time.time()

    def _work(pair):
        rec, abs_path = pair
        started = time.time()
        try:
            scores, why = score_one(url, rec, abs_path)
            return {"ok": True, "rec": rec, "path": abs_path, "scores": scores,
                    "why": why, "elapsed": round(time.time() - started, 2)}
        except Exception as e:  # noqa: BLE001 - 한 건이 나빠도 배치를 죽이지 않는다
            reason = "parse_failed" if isinstance(e, ValueError) else "serving_error"
            return {"ok": False, "rec": rec, "reason": reason,
                    "message": f"{type(e).__name__}: {e}"[:300]}

    # 제출 순서를 유지한다 — 두 실행을 나란히 비교할 때 줄 순서가 달라지면 diff 가 무의미하다.
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(_work, usable))

    scored = [r for r in results if r["ok"]]
    for r in results:
        if not r["ok"]:
            drops.append({"record_key": r["rec"].get("record_key"),
                          "reason": r["reason"], "message": r["message"]})
            by_reason[r["reason"]] = by_reason.get(r["reason"], 0) + 1
    funnel.append({"stage": "4축 채점", "in": len(usable), "out": len(scored),
                   "dropped": dict(by_reason), "kind": "transform"})

    # 게이트 — 미달은 버리지 않고 표시만 한다(재생성·검수 대상).
    n_sample, written, passed = 0, 0, 0
    fail_by_axis, unmeasured, copied = {}, {}, set()
    elapsed_all = []
    with open(os.path.join(out_dir, "records.jsonl"), "w", encoding="utf-8") as f:
        for r in scored:
            rec, scores = r["rec"], r["scores"]
            # 미측정(None) 축은 미달로 세지 않는다. 재지 못한 것과 기준 미달은 다르다.
            failed = [ax for ax in ALL_AXES
                      if scores.get(ax) is not None and scores[ax] < thresholds[ax]]
            for ax in ALL_AXES:
                if scores.get(ax) is None:
                    unmeasured[ax] = unmeasured.get(ax, 0) + 1
            for ax in failed:
                fail_by_axis[ax] = fail_by_axis.get(ax, 0) + 1
            asset_id = rec.get("asset_id") or f"j{written:06d}"
            rel = f"assets/{asset_id}.jpg"
            if asset_id not in copied:
                try:
                    shutil.copyfile(r["path"], os.path.join(out_dir, rel))
                except OSError as e:
                    drops.append({"record_key": rec.get("record_key"),
                                  "reason": "image_copy_failed", "message": str(e)[:160]})
                    by_reason["image_copy_failed"] = by_reason.get("image_copy_failed", 0) + 1
                    continue
                copied.add(asset_id)
                if n_sample < SAMPLE_LIMIT:
                    _thumb(os.path.join(out_dir, rel),
                           os.path.join(out_dir, "samples", f"{asset_id}.jpg"))
                    n_sample += 1
            _vals = [v for v in scores.values() if isinstance(v, (int, float))]
            row = {**rec, "path": rel, "scores": scores, "judge_rationale": r["why"],
                   "gate_passed": not failed, "failed_axes": failed,
                   "unmeasured_axes": [ax for ax in ALL_AXES if scores.get(ax) is None],
                   "worst_score": min(_vals) if _vals else None,
                   "judge_model": ((params.get("serving") or {}).get("judge") or {}).get("model_id")}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            elapsed_all.append(r["elapsed"])
            written += 1
            if not failed:
                passed += 1

    with open(os.path.join(out_dir, "drops.jsonl"), "w", encoding="utf-8") as f:
        for d in drops:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    funnel.append({"stage": "게이트", "in": written, "out": passed,
                   "dropped": fail_by_axis, "kind": "filter",
                   "note": "미달 레코드는 버리지 않고 재생성·검수 대상으로 남습니다"})

    pass_rate = round(passed / written, 3) if written else 0.0
    wall = round(time.time() - t0, 1)
    avg = round(sum(elapsed_all) / len(elapsed_all), 2) if elapsed_all else 0
    summary = {
        "node": "gate", "run_id": run_id, "node_index": params.get("node_index"),
        "dry_run": dry_run, "in": len(items), "out": written,
        "dropped_total": len(drops), "sample_count": n_sample,
        "passed": passed, "pass_rate": pass_rate, "fail_by_axis": fail_by_axis,
        "unmeasured_by_axis": unmeasured,
        "thresholds": thresholds,
        # 레코드당 판사 3회라 처리량이 이 노드의 운영 지표다.
        "throughput": {"wall_s": wall, "avg_record_s": avg, "concurrency": concurrency,
                       "calls_per_record": 3},
        "funnel": funnel,
    }
    with open(os.path.join(out_dir, "funnel.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"config": cfg, "thresholds": thresholds, "inputs": params.get("inputs"),
                   "serving": (params.get("serving") or {}).get("judge"),
                   "dry_run": dry_run, "sample_size": sample_size,
                   "concurrency": concurrency, "created_at": time.strftime(TS_FMT)},
                  f, ensure_ascii=False, indent=2)

    log("metric", name="gate/in", value=len(items))
    log("metric", name="gate/out", value=written)
    log("metric", name="gate/passed", value=passed)
    log("metric", name="gate/pass_rate", value=pass_rate)
    # 통과율이 너무 낮거나 너무 높으면 게이트가 제 역할을 못한다는 신호다.
    if written and pass_rate < 0.40:
        log("log", level="warn",
            message=f"통과율 {pass_rate:.0%} — 임계값이 이 모델에 과한지, 생성 프롬프트가 "
                    f"조우유형·조항을 명시하는지 확인하세요(축별 미달: {fail_by_axis})")
    elif written and pass_rate > 0.85:
        log("log", level="warn",
            message=f"통과율 {pass_rate:.0%} — 임계값이 낮아 걸러내지 못하고 있을 수 있습니다")
    print(f"[dp_judge] {len(items)} → {written} 채점 (통과 {passed}, {pass_rate:.0%}) "
          f"{wall}s avg {avg}s x{concurrency} → {out_dir}", flush=True)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="데이터 파이프라인 VLM 심사 노드")
    ap.add_argument("--params_path", required=True, help="노드 설정 JSON 경로")
    args = ap.parse_args(argv)
    with open(args.params_path, encoding="utf-8") as f:
        params = json.load(f)
    if not params.get("out_dir"):
        params["out_dir"] = os.path.dirname(os.path.abspath(args.params_path))
    try:
        run(params)
    except Exception as e:  # noqa: BLE001 - 사유를 남기고 비-0 으로 죽는다
        log("error", code="E_JUDGE_FAILED", message=f"{type(e).__name__}: {e}", fatal=True)
        raise


if __name__ == "__main__":
    main()
