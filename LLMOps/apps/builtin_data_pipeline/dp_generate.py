#!/usr/bin/env python3
"""데이터 파이프라인 — 생성 노드(kind=gen/synth, stage=generate).

스케줄러가 빌트인 잡 pod 안에서 아래로 실행한다.

    python3 -u /built_in/dp_generate.py --params_path=/dataset/_runs/<run_id>/<node_index>/params.json

COLREG 사실(결정론적 계산)과 AIS 텍스트를 앵커로 주고, 이미지와 함께 VLM 에 넣어
상황 서술(<describe>)과 항해 조언(<advice>)을 받는다.

**사실을 모델이 만들게 하지 않는다.** 조우 유형·적용 조항·CPA 는 앞 노드가 기하로
계산한 값을 프롬프트에 박아 넣고, 모델에는 그것을 문장으로 풀어내는 일만 시킨다.
모델이 조우 유형까지 판단하면 뒤의 심사가 모델의 답을 모델의 답으로 검증하게 되어
환각을 걸러 낼 수 없다. 심사 노드의 앵커 대조도 이 전제 위에서만 성립한다.

상류(BE 가 params.inputs 에 넣어 준다)

    inputs = {"records": "/dataset/_runs/<run>/<idx>"}   # dp_colreg 산출

서빙(BE 가 params.serving 에 넣어 준다) — 노드는 배포를 하지 않는다. 잡이 배포하면
잡이 죽는 순간 배포가 고아가 되어 GPU 가 영영 잠긴다.

    serving = {"generator": {"url": "http://...:18555/", "model_id": "...", "hf_id": "..."}}

산출(out_dir 아래)
  config.json    이 실행에 쓴 설정·모델 (비교의 기준)
  assets.jsonl   생성 성공 1건 = 1줄 (상류 레코드 + describe/advice)
  drops.jsonl    생성하지 못한 레코드: 왜
  funnel.json    [{stage, in, out, dropped{사유:건수}}]
  assets/        레코드 이미지(심사 노드의 입력 — 이미지 어블레이션에 필요하다)
  samples/       화면에 보여줄 썸네일 일부

범용(VQA) 프리셋은 아직 이 노드가 다루지 않는다 — 프롬프트 구성과 산출 형식이
완전히 다르다(템플릿별 Q·A 다중 생성). 해당 입력이 오면 조용히 이상한 것을 만들지 않고
사유를 남기고 멈춘다.
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

# 한 요청이 실패해도 배치를 죽이지 않되, 파싱 실패는 두 번까지 다시 물어본다.
# (프로토타입과 같은 횟수 — 형식을 안 지키는 것은 대개 한 번 더 물으면 잡힌다.)
GEN_RETRY = 2
# 서빙 호출 상한. 이미지 1장 + 수백 토큰이면 넉넉하다. 이보다 오래 걸리면 배포가
# 비정상이므로 배치 전체가 그것에 매달리지 않게 끊는다.
REQUEST_TIMEOUT_S = 300
# 동시 호출 수. vLLM 은 요청을 배치로 묶어 처리하므로 하나씩 보내면 GPU 가 논다.
# 레코드 100건 x 8초를 순차로 돌리면 13분인데, 그동안 GPU 는 대부분 대기 상태다.
DEFAULT_CONCURRENCY = 4

# 프롬프트 개정 번호. 프롬프트는 설정이 아니라 코드라, 이 값을 산출물에 남기지 않으면
# 두 실행을 나란히 놔도 차이가 설정 때문인지 프롬프트 때문인지 알 수 없다.
#   1 = 조우유형·조항·기상 명시
#   2 = + 조치를 수치로(변침각·목표 CPA·안전속력) — 심사의 actionability 축이 수치를 본다
PROMPT_REVISION = 2

ENCOUNTER_KO = {"head_on": "정면", "crossing": "교차", "overtaking": "추월", "safe": "안전"}
# 자선 역할도 번역한다 — 안 하면 "자선은 제17조에 따라 stand_on 선박으로" 처럼 내부 값이
# 한국어 조언에 그대로 새고, 그 문장이 그대로 학습 데이터가 된다.
ROLE_KO = {"give_way": "피항선(진로를 비켜야 하는 선박)", "stand_on": "유지선(침로·속력을 유지하는 선박)",
           "both_give_way": "쌍방 피항", "n/a": "해당 없음"}
ROLE_EN = {"give_way": "give-way vessel", "stand_on": "stand-on vessel",
           "both_give_way": "both give-way", "n/a": "n/a"}
ENCOUNTER_EN = {"head_on": "head-on", "crossing": "crossing",
                "overtaking": "overtaking", "safe": "safe"}

PROMPT_KO = ("사진과 AIS 데이터를 바탕으로 현재 해상상황을 묘사하고 "
             "COLREG 규칙에 따른 올바른 항해 조력 메시지를 생성해줘.")
PROMPT_EN = ("Based on the camera image and AIS data provided, "
             "describe the current maritime situation and provide "
             "appropriate navigational advice in accordance with COLREG rules.")

_DESC = re.compile(r"<describe>(.*?)</describe>", re.DOTALL | re.IGNORECASE)
_ADV = re.compile(r"<advice>(.*?)</advice>", re.DOTALL | re.IGNORECASE)


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
    """COLREG 계산 산출물. 없으면 어느 단계를 먼저 돌려야 하는지 말하고 죽는다."""
    src = (inputs or {}).get("records")
    if not src:
        raise RuntimeError("상류 노드 산출물 경로가 없습니다 — COLREG 계산 단계를 "
                           "먼저 실행하세요 (inputs.records)")
    path = os.path.join(src, "assets.jsonl")
    if not os.path.isfile(path):
        raise RuntimeError(f"상류 노드 산출물이 없습니다: {path}")
    return read_jsonl(path), src


def resolve_serving(params):
    """생성에 쓸 서빙 주소. BE 가 배포·회수를 책임지고 노드는 주소만 받는다."""
    url = ((params.get("serving") or {}).get("generator") or {}).get("url")
    if not url:
        raise RuntimeError("생성 모델 서빙 주소가 없습니다(params.serving.generator.url) — "
                           "모델 배포가 준비된 뒤에 실행됩니다")
    return url


# ── 프롬프트 ────────────────────────────────────────────────────────────────
def _facts_block(facts, lang):
    """계산된 사실을 프롬프트에 그대로 박는다 — 모델이 다시 판단하지 않게."""
    articles = facts.get("articles") or []
    if lang == "en":
        arts = ", ".join(f"Rule {a}" for a in articles)
        return (f"[Computed COLREG facts]\n"
                f"- encounter: {facts.get('encounter')}\n"
                f"- own role: {ROLE_EN.get(facts.get('own_role'), facts.get('own_role'))}\n"
                f"- articles: {arts}\n"
                f"- CPA: {facts.get('cpa_nm')}NM, TCPA: {facts.get('tcpa_min')}min\n"
                f"- recommended: {facts.get('maneuver')}")
    arts = ", ".join(f"제{a}조" for a in articles)
    return (f"[계산된 COLREG 사실]\n"
            f"- 조우유형: {facts.get('encounter')}\n"
            f"- 자선 역할: {ROLE_KO.get(facts.get('own_role'), facts.get('own_role'))}\n"
            f"- 적용조항: {arts}\n"
            f"- CPA: {facts.get('cpa_nm')}해리, TCPA: {facts.get('tcpa_min')}분\n"
            f"- 권고: {facts.get('maneuver')}")


def build_gen_prompt(ais_text, facts, lang, extra=""):
    """프로토타입 sds_pipeline.prompts.build_gen_prompt 와 같은 구성.

    조우 유형과 조항을 **문자열로 명시하라**고 요구하는 것이 핵심이다. 심사 노드가
    앵커 대조로 그 단어를 찾기 때문에, 여기서 요구하지 않으면 옳게 답해도 0점이 된다.
    """
    instr = PROMPT_EN if lang == "en" else PROMPT_KO
    articles = facts.get("articles") or []
    if lang == "en":
        enc = ENCOUNTER_EN.get(facts.get("encounter"), facts.get("encounter"))
        arts = ", ".join(f"Rule {a}" for a in articles)
        tag = ("Reply EXACTLY as <describe>...</describe><advice>...</advice>. "
               f'The <advice> MUST explicitly name the encounter type as "{enc}"'
               + (f', cite the applicable COLREG article(s) as "{arts}"' if arts else "")
               + ", briefly note any visible weather/visibility conditions in the "
                 "image (e.g., fog/rain/night) and their COLREG implication when present, "
                 # 심사의 actionability 축은 '구체적·안전한 조치(변침각·CPA·안전속력)'를 본다.
                 # 수치를 요구하지 않으면 모델은 방향만 말하고 그 축은 정확히 낮게 채점된다.
                 "and state the maneuver NUMERICALLY — give the course change in degrees "
                 "(e.g. 'starboard 20°'), the target CPA in nautical miles, and the safe "
                 "speed in knots, for whichever applies to this situation.")
    else:
        enc = ENCOUNTER_KO.get(facts.get("encounter"), facts.get("encounter"))
        arts = ", ".join(f"제{a}조" for a in articles)
        tag = ("반드시 <describe>...</describe><advice>...</advice> 형식으로만 답하라. "
               f'<advice>에는 조우유형을 "{enc}"이라는 단어로 명시하고'
               + (f', 해당 COLREG 조항을 "{arts}" 형태로 인용하고' if arts else "")
               + ", 이미지에서 보이는 기상/시정 상태(예: 안개/강우/야간)와 그로 인한 "
                 "COLREG상 함의를 있는 경우 짧게 언급하며, "
                 # 심사의 actionability 축은 '구체적·안전한 조치(변침각·CPA·안전속력)'를 본다.
                 # 수치를 요구하지 않으면 방향만 말하게 되고 그 축은 정확히 낮게 채점된다.
                 "조치를 반드시 **숫자로** 제시하라 — 변침 각도(예: 우현 20°), 확보할 "
                 "목표 CPA(해리), 필요한 안전속력(kt) 중 이 상황에 해당하는 것을 수치로 쓰라.")
    body = f"{ais_text}\n\n{_facts_block(facts, lang)}\n\n{instr}\n{tag}"
    return f"{body}\n{extra}".rstrip() if extra else body


def parse_action(raw):
    """<describe>/<advice> 추출. 형식을 안 지켰으면 실패로 올려 재시도하게 한다."""
    d, a = _DESC.search(raw or ""), _ADV.search(raw or "")
    if d and a:
        return d.group(1).strip(), a.group(1).strip()
    raise ValueError(f"<describe>/<advice> 구간이 없습니다: {(raw or '')[:120]!r}")


# ── 서빙 호출 ───────────────────────────────────────────────────────────────
def _b64_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def call_vlm(url, prompt, image_b64, session_id):
    """배포 래퍼 계약: POST / 에 test_question + images(base64). 응답은 [{output}] 형태."""
    body = {"test_type": "question", "test_question": prompt,
            "session_id": session_id, "images": [image_b64]}
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        # 401/402 는 래퍼가 "아직 준비 중 / 모델 오류" 로 쓰는 코드다. 사유를 그대로
        # 올려야 사용자가 배포 문제인지 데이터 문제인지 구분한다.
        raise RuntimeError(f"서빙 HTTP {e.code}: {detail}") from e
    if isinstance(payload, list) and payload:
        return payload[0].get("output") or ""
    if isinstance(payload, dict):
        return payload.get("output") or ""
    raise RuntimeError(f"서빙 응답 형식을 모르겠습니다: {str(payload)[:160]}")


def generate_one(url, rec, lang, extra_prompt, retry=GEN_RETRY):
    """레코드 하나 생성. 성공하면 (describe, advice, 시도횟수), 실패하면 예외."""
    facts = rec.get("colreg") or {}
    ais_text = rec.get("ais_text_en") if lang == "en" else rec.get("ais_text_ko")
    if not ais_text:
        raise ValueError(f"'{lang}' AIS 텍스트가 레코드에 없습니다")
    prompt = build_gen_prompt(ais_text, facts, lang, extra_prompt)
    image_b64 = _b64_image(rec["_abs_path"])
    last = None
    for attempt in range(1, retry + 1):
        raw = call_vlm(url, prompt, image_b64,
                       f"dpgen-{rec.get('asset_id')}-{lang}-{attempt}")
        try:
            describe, advice = parse_action(raw)
            return describe, advice, attempt, raw
        except ValueError as e:
            last = e
    raise ValueError(f"{retry}회 시도에도 형식을 지키지 않았습니다: {last}")


# ── 실행 ────────────────────────────────────────────────────────────────────
def _languages(cfg):
    """설정의 언어 → 생성할 언어 목록. 'ko + en' 은 레코드당 두 번 생성한다."""
    raw = (cfg.get("language") or "ko").strip().lower()
    if "ko" in raw and "en" in raw:
        return ["ko", "en"]
    return ["en"] if raw == "en" else ["ko"]


def _thumb(src, dst):
    """썸네일. 실패해도 생성 결과는 유효하므로 삼키고 넘어간다."""
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

    os.makedirs(os.path.join(out_dir, "assets"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "samples"), exist_ok=True)

    url = resolve_serving(params)
    items, src_dir = load_upstream(params.get("inputs"))
    if dry_run:
        items = items[:sample_size]
    log("phase", name="collect", count=len(items), dry_run=dry_run)

    # 이 노드는 COLREG 앵커가 있는 해양 레코드만 다룬다. 앵커가 없으면 프롬프트의
    # 사실 블록이 비어 모델이 조우 유형을 지어내고, 심사의 앵커 대조도 성립하지 않는다.
    if items and not isinstance(items[0].get("colreg"), dict):
        raise RuntimeError(
            "COLREG 사실이 없는 레코드입니다 — 이 생성 노드는 해양(SDS) 파이프라인 전용입니다. "
            "범용 VQA 생성은 아직 지원하지 않습니다")

    langs = _languages(cfg)
    extra_prompt = (cfg.get("prompt") or "").strip()
    if int(cfg.get("per_image") or 1) > 1:
        log("log", level="warn",
            message="'이미지당 생성 수' 는 해양 생성에서 쓰이지 않습니다 — "
                    "씬 하나당 상황 서술·조언 한 쌍을 만듭니다")

    funnel = [{"stage": "수집", "in": len(items), "out": len(items), "dropped": {}, "kind": "source"}]
    drops = []
    by_reason = {}

    # 이미지 경로를 미리 절대경로로 풀어 둔다(스레드에서 상대경로 조립을 반복하지 않게).
    usable = []
    for it in items:
        abs_path = os.path.join(src_dir, it.get("path") or "")
        if not os.path.isfile(abs_path):
            drops.append({"asset_id": it.get("asset_id"), "reason": "image_missing",
                          "message": f"상류 이미지가 없습니다: {it.get('path')}"})
            by_reason["image_missing"] = by_reason.get("image_missing", 0) + 1
            continue
        usable.append({**it, "_abs_path": abs_path})

    jobs = [(rec, lang) for rec in usable for lang in langs]
    log("phase", name="generate", count=len(jobs), concurrency=concurrency,
        languages=langs, model=((params.get("serving") or {}).get("generator") or {}).get("model_id"))

    t0 = time.time()

    def _work(job):
        rec, lang = job
        started = time.time()
        try:
            describe, advice, attempts, _raw = generate_one(url, rec, lang, extra_prompt)
            return {"ok": True, "rec": rec, "lang": lang, "describe": describe,
                    "advice": advice, "attempts": attempts,
                    "elapsed": round(time.time() - started, 2)}
        except Exception as e:  # noqa: BLE001 - 한 건이 나빠도 배치를 죽이지 않는다
            reason = "parse_failed" if isinstance(e, ValueError) else "serving_error"
            return {"ok": False, "rec": rec, "lang": lang, "reason": reason,
                    "message": f"{type(e).__name__}: {e}"[:300]}

    # 제출 순서대로 결과를 훑는다 — 동시에 돌리되 출력 순서는 입력과 같게 유지해,
    # 두 실행을 나란히 비교할 때 줄 순서가 달라 diff 가 무의미해지는 일을 막는다.
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(_work, jobs))

    n_sample = 0
    written = 0
    copied = set()
    elapsed_all = []
    with open(os.path.join(out_dir, "assets.jsonl"), "w", encoding="utf-8") as f:
        for res in results:
            rec, lang = res["rec"], res["lang"]
            asset_id = rec.get("asset_id") or f"g{written:06d}"
            if not res["ok"]:
                drops.append({"asset_id": asset_id, "lang": lang,
                              "timestamp": rec.get("timestamp"),
                              "reason": res["reason"], "message": res["message"]})
                by_reason[res["reason"]] = by_reason.get(res["reason"], 0) + 1
                continue

            rel = f"assets/{asset_id}.jpg"
            if asset_id not in copied:
                try:
                    shutil.copyfile(rec["_abs_path"], os.path.join(out_dir, rel))
                except OSError as e:
                    drops.append({"asset_id": asset_id, "lang": lang,
                                  "reason": "image_copy_failed", "message": str(e)[:160]})
                    by_reason["image_copy_failed"] = by_reason.get("image_copy_failed", 0) + 1
                    continue
                copied.add(asset_id)
                if n_sample < SAMPLE_LIMIT:
                    _thumb(os.path.join(out_dir, rel),
                           os.path.join(out_dir, "samples", f"{asset_id}.jpg"))
                    n_sample += 1

            row = {k: v for k, v in rec.items() if k != "_abs_path"}
            row.update({
                "path": rel,
                # 언어까지 넣어야 'ko + en' 실행에서 두 줄이 서로 다른 레코드로 구분된다.
                "record_key": f"{asset_id}:{lang}",
                "lang": lang,
                "describe": res["describe"],
                "advice": res["advice"],
                "gen_attempts": res["attempts"],
                "gen_model": ((params.get("serving") or {}).get("generator") or {}).get("model_id"),
            })
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            elapsed_all.append(res["elapsed"])
            written += 1

    with open(os.path.join(out_dir, "drops.jsonl"), "w", encoding="utf-8") as f:
        for d in drops:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    funnel.append({"stage": "생성", "in": len(jobs), "out": written,
                   "dropped": dict(by_reason), "kind": "transform"})

    wall = round(time.time() - t0, 1)
    avg = round(sum(elapsed_all) / len(elapsed_all), 2) if elapsed_all else 0
    summary = {
        "node": "generate", "run_id": run_id, "node_index": params.get("node_index"),
        "dry_run": dry_run, "in": len(jobs), "out": written,
        "dropped_total": len(drops), "sample_count": n_sample,
        "languages": langs, "prompt_revision": PROMPT_REVISION,
        # 처리량은 이 노드의 운영 지표다. 레코드가 늘면 여기가 병목이 되므로
        # 동시성을 얼마로 올릴지 판단할 근거를 남긴다.
        "throughput": {"wall_s": wall, "avg_call_s": avg, "concurrency": concurrency},
        "funnel": funnel,
    }
    with open(os.path.join(out_dir, "funnel.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    with open(os.path.join(out_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"config": cfg, "languages": langs, "prompt_revision": PROMPT_REVISION,
                   "inputs": params.get("inputs"),
                   "serving": (params.get("serving") or {}).get("generator"),
                   "dry_run": dry_run, "sample_size": sample_size,
                   "concurrency": concurrency, "retry": GEN_RETRY,
                   "created_at": time.strftime(TS_FMT)},
                  f, ensure_ascii=False, indent=2)

    log("metric", name="generate/in", value=len(jobs))
    log("metric", name="generate/out", value=written)
    log("metric", name="generate/dropped", value=len(drops))
    log("metric", name="generate/avg_call_s", value=avg)
    if by_reason.get("parse_failed"):
        log("log", level="warn",
            message=f"형식 미준수로 {by_reason['parse_failed']}건 실패 — 생성 모델이 "
                    "<describe>/<advice> 지시를 따르지 않습니다. 모델을 바꾸거나 "
                    "프롬프트를 조정하세요")
    print(f"[dp_generate] {len(jobs)} → {written} (제외 {len(drops)}) "
          f"{wall}s avg {avg}s x{concurrency} → {out_dir}", flush=True)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="데이터 파이프라인 생성 노드")
    ap.add_argument("--params_path", required=True, help="노드 설정 JSON 경로")
    args = ap.parse_args(argv)

    with open(args.params_path, encoding="utf-8") as f:
        params = json.load(f)
    if not params.get("out_dir"):
        params["out_dir"] = os.path.dirname(os.path.abspath(args.params_path))

    try:
        run(params)
    except Exception as e:  # noqa: BLE001 - 사유를 남기고 비-0 으로 죽는다
        log("error", code="E_GENERATE_FAILED", message=f"{type(e).__name__}: {e}", fatal=True)
        raise


if __name__ == "__main__":
    main()
