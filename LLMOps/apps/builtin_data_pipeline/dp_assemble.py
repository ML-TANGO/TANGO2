#!/usr/bin/env python3
"""데이터 파이프라인 — 조립·내보내기 노드(kind=out, stage=assemble).

스케줄러가 빌트인 잡 pod 안에서 아래로 실행한다.

    python3 -u /built_in/dp_assemble.py --params_path=/dataset/_runs/<run_id>/<node_index>/params.json

심사를 마친 레코드를 **학습이 그대로 읽는 형태**로 바꾼다. 모델을 쓰지 않는다.

이 노드는 상류(심사) 산출물을 읽는다. BE 가 params.inputs 에 넣어 준다.

    inputs = {"records": "/dataset/_runs/<run>/<idx>"}   # dp_judge 산출

두 포맷을 함께 낸다. 하나로 줄이지 않는 이유가 있다.
  * records.jsonl (평면) — 우리 플랫폼 학습기 `llm_model_vlm_fine_tuning.load_vlm_samples`
    가 읽는 형태다. 그 함수는 top-level 키(image|instruction|output 과 별칭)만 보므로
    LLaVA 의 중첩 conversations 구조는 **읽지 못한다**.
  * llava.json — 프로토타입과 외부 트레이너(LLaVA 계열)의 관례다.

이미지 경로 규약이 까다롭다: 학습기는 데이터셋 파일이 있는 디렉터리 기준 상대경로만
받고 `realpath`+`commonpath` 로 봉쇄한다. 그래서 **심볼릭 링크는 조용히 스킵된다** —
이미지는 실파일(하드링크, 안 되면 복사)로 out_dir 안에 둔다.

산출(out_dir 아래)
  config.json    이 실행에 쓴 설정 (비교의 기준)
  records.jsonl  학습 샘플 1건 = 1줄 (평면 스키마)
  llava.json     LLaVA conversations 배열
  drops.jsonl    담지 못한 레코드: 왜
  funnel.json    [{stage, in, out, dropped{사유:건수}}]
  assets/        학습이 읽을 이미지(상대경로 assets/…)
  samples/       화면에 보여줄 썸네일 일부
"""
import argparse
import json
import os
import shutil

# 학습기 콜레이터가 리터럴 이미지 토큰을 지우고 자기가 placeholder 를 넣는다. 평면
# 포맷에 토큰을 남기면 이미지 1장과 토큰 수가 어긋날 여지를 만들 뿐이라 지운다.
# LLaVA 포맷은 규약상 토큰이 있어야 하므로 거기서만 붙인다.
IMAGE_TOKEN = "<image>"
SAMPLE_LIMIT = 12
IMAGE_DIR = "assets"


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
    """심사 산출물. 없으면 어느 단계를 먼저 돌려야 하는지 말하고 죽는다."""
    src = (inputs or {}).get("records")
    if not src:
        raise RuntimeError("상류 노드 산출물 경로가 없습니다 — VLM 심사 단계를 먼저 "
                           "실행하세요 (inputs.records)")
    path = os.path.join(src, "records.jsonl")
    if not os.path.isfile(path):
        raise RuntimeError(f"심사 노드 산출물이 없습니다: {path}")
    return read_jsonl(path), src


def _thumb(src, dst, box=256):
    """썸네일. Pillow 가 없거나 이미지가 깨져도 조립을 멈추지 않는다."""
    try:
        from PIL import Image
        with Image.open(src) as im:
            im = im.convert("RGB")
            im.thumbnail((box, box))
            im.save(dst, "JPEG", quality=82)
        return True
    except Exception:  # noqa: BLE001 - 썸네일은 부가 산출물이다
        return False


def _link_or_copy(src, dst):
    """하드링크 우선, 안 되면 복사. 심볼릭 링크는 쓰지 않는다 — 학습기가 realpath 로
    봉쇄를 검사하므로 링크 대상이 데이터셋 디렉터리 밖이면 그 이미지는 스킵된다."""
    try:
        os.link(src, dst)
        return "linked"
    except OSError:
        shutil.copy2(src, dst)
        return "copied"


def instruction_of(rec):
    """학습 샘플의 질문. 노드가 question 을 주면 그것을, 아니면 AIS + 지시로 조립한다."""
    if rec.get("question"):
        return rec["question"].replace(IMAGE_TOKEN, " ").strip()
    lang = rec.get("lang") or "ko"
    ais = rec.get(f"ais_text_{lang}") or rec.get("ais_text_ko") or rec.get("ais_text") or ""
    tail = ("Describe the current maritime situation from the information and image above, "
            "and give navigational advice in accordance with COLREG."
            if lang == "en" else
            "위 정보와 이미지를 보고 현재 해상 상황을 서술하고 COLREG 에 따른 항해 조언을 제시하라.")
    return "\n".join(x for x in (ais, tail) if x).strip()


def answer_of(rec):
    if rec.get("answer"):
        return rec["answer"]
    return "\n\n".join(x for x in (rec.get("describe"), rec.get("advice")) if x)


def run(params):
    out_dir = params["out_dir"]
    steps = params.get("steps") or []
    dry_run = bool(params.get("dry_run"))
    sample_size = int(params.get("sample_size", 10))
    run_id = str(params.get("run_id", "run"))
    cfg = params.get("params") or {}
    # 게이트 미달을 학습에 넣으면 심사가 장식이 된다. 기본은 통과분만.
    only_passed = bool(cfg.get("only_passed", True))
    with_llava = bool(cfg.get("llava", True))

    os.makedirs(os.path.join(out_dir, IMAGE_DIR), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "samples"), exist_ok=True)

    items, src_dir = load_upstream(params.get("inputs"))
    if dry_run:
        items = items[:sample_size]
    log("phase", name="collect", count=len(items), dry_run=dry_run)

    funnel = [{"stage": "수집", "in": len(items), "out": len(items), "dropped": {},
               "kind": "source"}]
    drops, flat, llava = [], [], []
    by_reason, image_stat = {}, {"linked": 0, "copied": 0}
    n_sample = 0

    def _drop(rec, reason, message):
        drops.append({"record_key": rec.get("record_key") or rec.get("asset_id"),
                      "reason": reason, "message": message})
        by_reason[reason] = by_reason.get(reason, 0) + 1

    for rec in items:
        if only_passed and rec.get("gate_passed") is False:
            _drop(rec, "gate_failed",
                  f"게이트 미달 축: {', '.join(rec.get('failed_axes') or []) or '알 수 없음'}")
            continue
        key = rec.get("record_key") or rec.get("asset_id")
        if not key:
            _drop(rec, "no_key", "레코드 키가 없어 식별할 수 없습니다")
            continue
        rel_src = rec.get("path")
        if not rel_src:
            _drop(rec, "no_image", "이미지 경로가 없습니다 (VLM 학습은 이미지가 필수)")
            continue
        src = os.path.join(src_dir, rel_src)
        if not os.path.isfile(src):
            _drop(rec, "image_missing", f"이미지가 없습니다: {rel_src}")
            continue
        # 같은 프레임이 언어별로 여러 레코드가 되므로 원본 파일명만 쓰면 서로 덮어쓴다.
        base = f"{str(key).replace(':', '_').replace('/', '_')}" \
               f"{os.path.splitext(src)[1] or '.jpg'}"
        rel = f"{IMAGE_DIR}/{base}"
        try:
            image_stat[_link_or_copy(src, os.path.join(out_dir, rel))] += 1
        except OSError as e:
            _drop(rec, "image_copy_failed", str(e)[:120])
            continue
        if n_sample < SAMPLE_LIMIT and _thumb(os.path.join(out_dir, rel),
                                              os.path.join(out_dir, "samples", base)):
            n_sample += 1

        instruction, answer = instruction_of(rec), answer_of(rec)
        if not instruction or not answer:
            _drop(rec, "empty_text", "질문 또는 답이 비어 학습 샘플로 성립하지 않습니다")
            continue
        flat.append({
            "id": key, "image": rel, "instruction": instruction, "output": answer,
            "scores": rec.get("scores") or {}, "gate_passed": rec.get("gate_passed"),
            "lang": rec.get("lang"), "colreg": rec.get("colreg"),
        })
        if with_llava:
            llava.append({"id": key, "image": rel, "conversations": [
                {"from": "human", "value": f"{IMAGE_TOKEN}\n{instruction}"},
                {"from": "gpt", "value": answer},
            ]})

    funnel.append({"stage": "학습 포맷 조립", "in": len(items), "out": len(flat),
                   "dropped": dict(by_reason), "kind": "transform"})

    with open(os.path.join(out_dir, "records.jsonl"), "w", encoding="utf-8") as f:
        for row in flat:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    if with_llava:
        with open(os.path.join(out_dir, "llava.json"), "w", encoding="utf-8") as f:
            json.dump(llava, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "drops.jsonl"), "w", encoding="utf-8") as f:
        for d in drops:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    summary = {
        "node": "assemble", "run_id": run_id, "node_index": params.get("node_index"),
        "dry_run": dry_run, "in": len(items), "out": len(flat),
        "dropped_total": len(drops), "sample_count": n_sample,
        "images": image_stat,
        # 어느 포맷을 냈는지는 다음 사람이 무엇을 학습에 넣을지 고르는 근거다.
        "formats": ["records.jsonl(평면 · 우리 학습기)"] + (["llava.json"] if with_llava else []),
        "funnel": funnel,
    }
    with open(os.path.join(out_dir, "funnel.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    with open(os.path.join(out_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"steps": steps, "inputs": params.get("inputs"), "dry_run": dry_run,
                   "sample_size": sample_size,
                   "only_passed": only_passed, "llava": with_llava,
                   "trainer_contract": {
                       "reader": "llm_model_vlm_fine_tuning.load_vlm_samples",
                       "keys": ["image", "instruction", "output"],
                       "image_path": "산출 디렉터리 기준 상대경로(assets/…). 심볼릭 링크 불가",
                   }}, f, ensure_ascii=False, indent=2)

    log("done", **{k: summary[k] for k in ("in", "out", "dropped_total", "images")})


def main(argv=None):
    ap = argparse.ArgumentParser(description="데이터 파이프라인 조립·내보내기 노드")
    ap.add_argument("--params_path", required=True, help="노드 설정 JSON 경로")
    args = ap.parse_args(argv)

    with open(args.params_path, encoding="utf-8") as f:
        params = json.load(f)
    if not params.get("out_dir"):
        params["out_dir"] = os.path.dirname(os.path.abspath(args.params_path))

    try:
        run(params)
    except Exception as e:  # noqa: BLE001 - 사유를 남기고 비-0 으로 죽는다
        log("error", code="E_ASSEMBLE_FAILED", message=f"{type(e).__name__}: {e}", fatal=True)
        raise


if __name__ == "__main__":
    main()
