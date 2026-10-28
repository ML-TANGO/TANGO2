#!/usr/bin/env python3
"""빌트인 전처리 — SDS 시나리오 데이터셋 → LLaVA 학습 JSON (도메인 특화).

fb_preprocessing 빌트인(TYPE_BUILT_IN.SDS_LLAVA_CONVERT) 잡이 이미지 안에서
``python3 -u /built_in/sds_llava_convert.py <params> --input_data=/dataset/<name>`` 로 실행.

- 입력: SDS 데이터셋 **디렉터리**. 두 레이아웃을 자동 감지한다(A 우선, 없으면 B):

  A) 시나리오 subdir 레이아웃 — 각 subdir 안:
     input_data.csv, input_image.png,
     output_describe_en.txt / output_advice_en.txt,
     output_describe_kor.txt / output_advice_kor.txt, output_advice_compact.txt

  B) 타입별 디렉터리 레이아웃 (에이브노틱스 20260728 드롭 형식) — 같은 stem 으로 조인:
     png/<stem>.png, csv/<stem>.csv,
     describe_ko/<stem>.describe_ko.txt, advice_ko/<stem>.advice_ko.txt
     (en/compact 은 describe_en·advice_en·advice_compact 디렉터리가 있을 때만)

  B 를 재배치 없이 그대로 먹는 이유: 드롭이 10,000 샘플 × 4 파일이라 A 구조로
  옮기면 NFS 에서 40,000 파일을 1만 개 디렉터리로 이동해야 하고 원본이 훼손된다.
- 출력: **입력 디렉터리 안 sidecar** ``<input_data>/<result_file_name>_<variant>.json`` (LLaVA 대화 포맷).
  image 필드는 **상대경로** ``<scenario>/input_image.png`` — 학습 pod 이 IMAGE_DIR=/dataset/<name> 으로 마운트해 해석.
- Field_Test/SDS/.../prepare_sds_dataset.py 로직 포팅. 컬럼 매핑 없음(도메인 고정 포맷).
- **의존성 없음**: 표준 라이브러리(csv/json)만 사용 → 기본 잡 이미지(python3)에서 그대로 실행(pandas 불필요).

파라미터(스케줄러가 `--key value` 공백 형식 전달; --input_data 는 `=` 형식):
  --input_data       SDS 데이터셋 디렉터리 (필수, 스케줄러 주입)
  --sds_variant      en | ko | ko_compact | all   (기본 all)
  --result_file_name 출력 파일 베이스명            (기본 sds_train)
"""
import argparse
import csv
import json
import os
import sys

PROMPT_EN = (
    "Based on the camera image and AIS data provided, "
    "describe the current maritime situation and provide "
    "appropriate navigational advice in accordance with COLREG rules."
)
PROMPT_KO = (
    "사진과 AIS 데이터를 바탕으로 현재 해상상황을 묘사하고 "
    "COLREG 규칙에 따른 올바른 항해 조력 메시지를 생성해줘."
)
PROMPT_COMPACT = (
    "사진과 AIS 데이터를 바탕으로 간결한 항해 조력 메시지를 생성해줘. "
    "속도 조치, 방향 조치, 적용 근거(COLREG 조항)를 포함하시오."
)

_VARIANTS = ("en", "ko", "ko_compact")


def _f(row, key):
    """CSV 문자열 → float (빈값/오류 시 0.0)."""
    try:
        return float(row.get(key, "") or 0)
    except (ValueError, TypeError):
        return 0.0


def _i(row, key):
    """CSV 문자열 → int ('3.0' 같은 값도 허용)."""
    return int(_f(row, key))


def format_ais(rows, lang):
    """AIS row(dict) 리스트 → 텍스트 (demo/app.py format_ais_text() 동일 포맷)."""
    if lang == "en":
        lines = ["[Vessel AIS Information]"]
        for row in rows:
            sid = _i(row, "ship_id")
            spd, hdg = f"{_f(row,'knot'):.1f}kt", f"{_f(row,'heading'):.1f}°"
            lat, lon = f"{_f(row,'latitude'):.6f}", f"{_f(row,'longitude'):.6f}"
            lw = f"{_i(row,'length')}m x {_i(row,'width')}m"
            draft = f"{_i(row,'draft')}m"
            if _i(row, "my_ship") == 1:
                lines.append(f"- Own vessel (ID:{sid}) | Lat:{lat} Lon:{lon} | "
                             f"Speed:{spd} Heading:{hdg} | Size:{lw} Draft:{draft}")
            else:
                bbox = (f"x={_f(row,'bbox_x'):.0f} y={_f(row,'bbox_y'):.0f} "
                        f"w={_f(row,'bbox_width'):.0f} h={_f(row,'bbox_height'):.0f}")
                lines.append(f"- Nearby vessel (ID:{sid}) | Lat:{lat} Lon:{lon} | "
                             f"Speed:{spd} Heading:{hdg} | Size:{lw} Draft:{draft} | BoundingBox:[{bbox}]")
    else:
        lines = ["[선박 AIS 정보]"]
        for row in rows:
            sid = _i(row, "ship_id")
            spd, hdg = f"{_f(row,'knot'):.1f}kt", f"{_f(row,'heading'):.1f}°"
            lat, lon = f"{_f(row,'latitude'):.6f}", f"{_f(row,'longitude'):.6f}"
            lw = f"{_i(row,'length')}m × {_i(row,'width')}m"
            draft = f"{_i(row,'draft')}m"
            if _i(row, "my_ship") == 1:
                lines.append(f"- 자선 (ID:{sid}) | 위도:{lat} 경도:{lon} | "
                             f"속도:{spd} 방향:{hdg} | 선체:{lw} 흘수:{draft}")
            else:
                bbox = (f"x={_f(row,'bbox_x'):.0f} y={_f(row,'bbox_y'):.0f} "
                        f"w={_f(row,'bbox_width'):.0f} h={_f(row,'bbox_height'):.0f}")
                lines.append(f"- 주변선박 (ID:{sid}) | 위도:{lat} 경도:{lon} | "
                             f"속도:{spd} 방향:{hdg} | 선체:{lw} 흘수:{draft} | 바운딩박스:[{bbox}]")
    return "\n".join(lines)


def read_csv_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_txt(path):
    if not os.path.exists(path):
        return ""
    # errors="replace": 깨진 UTF-8 한 개 때문에 전체 변환이 중단되지 않도록 방어.
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().strip()


def _scenario_samples(input_dir):
    """레이아웃 A — 시나리오 subdir 하나가 샘플 하나."""
    out = []
    for name in sorted(d for d in os.listdir(input_dir)
                       if os.path.isdir(os.path.join(input_dir, d))):
        sd = os.path.join(input_dir, name)
        out.append({
            "name": name,
            "csv": os.path.join(sd, "input_data.csv"),
            "img": os.path.join(sd, "input_image.png"),
            # image 는 input_dir(= IMAGE_DIR) 기준 상대경로여야 학습 pod 이 찾는다.
            "img_rel": f"{name}/input_image.png",
            "texts": {
                "desc_en": os.path.join(sd, "output_describe_en.txt"),
                "adv_en": os.path.join(sd, "output_advice_en.txt"),
                "desc_kor": os.path.join(sd, "output_describe_kor.txt"),
                "adv_kor": os.path.join(sd, "output_advice_kor.txt"),
                "compact": os.path.join(sd, "output_advice_compact.txt"),
            },
        })
    return out


def _type_dir_samples(input_dir):
    """레이아웃 B — png/·csv/·<kind>/ 를 stem 으로 조인해 샘플 구성.

    stem 은 png 파일명에서 뽑는다(이미지 없는 샘플은 학습에 못 쓰므로 기준으로
    적합). 텍스트는 `<kind>/<stem>.<kind>.txt` 규약 — 드롭이 파일명에 kind 를
    한 번 더 박아두는 형식이라 그대로 따른다. 없는 kind 디렉터리는 빈 경로를
    넘겨 read_txt 가 ""를 돌려주고, 해당 variant 만 자연히 0건이 된다.
    """
    img_dir = os.path.join(input_dir, "png")
    csv_dir = os.path.join(input_dir, "csv")
    if not (os.path.isdir(img_dir) and os.path.isdir(csv_dir)):
        return []

    def _txt(kind, stem):
        # 디렉터리가 없으면 존재하지 않는 경로를 그대로 반환 — read_txt 가 "" 처리.
        return os.path.join(input_dir, kind, f"{stem}.{kind}.txt")

    out = []
    for fname in sorted(f for f in os.listdir(img_dir) if f.endswith(".png")):
        stem = fname[: -len(".png")]
        out.append({
            "name": stem,
            "csv": os.path.join(csv_dir, f"{stem}.csv"),
            "img": os.path.join(img_dir, fname),
            "img_rel": f"png/{fname}",
            "texts": {
                "desc_en": _txt("describe_en", stem),
                "adv_en": _txt("advice_en", stem),
                "desc_kor": _txt("describe_ko", stem),
                "adv_kor": _txt("advice_ko", stem),
                "compact": _txt("advice_compact", stem),
            },
        })
    return out


def build(input_dir):
    """SDS 데이터셋 디렉터리 → (en_data, ko_data, compact_data, stats).

    레이아웃 A(시나리오 subdir)를 먼저 보고, 쓸 수 있는 샘플이 하나도 없으면
    B(타입별 디렉터리)로 폴백한다. A 판정 기준을 "subdir 존재"가 아니라
    "input_data.csv 를 가진 subdir 존재"로 둔 이유: B 드롭도 png/·csv/ 라는
    subdir 를 갖고 있어서, 디렉터리 유무만 보면 A 로 오판해 전부 skip 된다.
    """
    samples = [s for s in _scenario_samples(input_dir) if os.path.exists(s["csv"])]
    layout = "scenario-dirs"
    if not samples:
        samples = _type_dir_samples(input_dir)
        layout = "type-dirs"
    print(f"[sds_llava] layout={layout} candidates={len(samples)}", flush=True)

    en_data, ko_data, compact_data = [], [], []
    stats = {"ok": 0, "skipped": 0}

    for sample in samples:
        name = sample["name"]
        csv_path, img_path, img_rel = sample["csv"], sample["img"], sample["img_rel"]

        if not os.path.exists(csv_path) or not os.path.exists(img_path):
            stats["skipped"] += 1
            continue
        try:
            rows = read_csv_rows(csv_path)
        except Exception as e:
            print(f"[sds_llava] read fail {name}: {e}", flush=True)
            stats["skipped"] += 1
            continue
        # 필수 AIS 컬럼 검증 — 헤더가 틀리면 조용히 0값 샘플을 만들지 않고 스킵.
        if not rows or "ship_id" not in rows[0] or "my_ship" not in rows[0]:
            print(f"[sds_llava] skip {name}: CSV missing required columns (ship_id/my_ship)", flush=True)
            stats["skipped"] += 1
            continue

        texts = sample["texts"]
        desc_en = read_txt(texts["desc_en"])
        adv_en = read_txt(texts["adv_en"])
        desc_kor = read_txt(texts["desc_kor"])
        adv_kor = read_txt(texts["adv_kor"])
        compact = read_txt(texts["compact"])

        ais_en = format_ais(rows, "en")
        ais_ko = format_ais(rows, "ko")

        if desc_en and adv_en:
            en_data.append({
                "id": f"{name}_en", "image": img_rel,
                "conversations": [
                    {"from": "human", "value": f"<image>\n{ais_en}\n\n{PROMPT_EN}"},
                    {"from": "gpt", "value": f"{desc_en}\n\n{adv_en}"},
                ],
            })
        if desc_kor and adv_kor:
            ko_data.append({
                "id": f"{name}_ko", "image": img_rel,
                "conversations": [
                    {"from": "human", "value": f"<image>\n{ais_ko}\n\n{PROMPT_KO}"},
                    {"from": "gpt", "value": f"{desc_kor}\n\n{adv_kor}"},
                ],
            })
        if compact:
            compact_data.append({
                "id": f"{name}_ko_compact", "image": img_rel,
                "conversations": [
                    {"from": "human", "value": f"<image>\n{ais_ko}\n\n{PROMPT_COMPACT}"},
                    {"from": "gpt", "value": compact},
                ],
            })
        stats["ok"] += 1

    return en_data, ko_data, compact_data, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_data", required=True)
    ap.add_argument("--sds_variant", default="all",
                    choices=["en", "ko", "ko_compact", "all"])
    ap.add_argument("--result_file_name", default="sds_train")
    args, _unknown = ap.parse_known_args()

    input_dir = os.path.realpath(args.input_data)
    if not os.path.isdir(input_dir):
        print(f"[sds_llava] input_data is not a directory: {input_dir!r}", flush=True)
        sys.exit(1)

    en_data, ko_data, compact_data, stats = build(input_dir)
    by_variant = {"en": en_data, "ko": ko_data, "ko_compact": compact_data}

    targets = _VARIANTS if args.sds_variant == "all" else (args.sds_variant,)
    # result_file_name 은 basename 으로 경로조작(`../`) 차단.
    safe_name = os.path.basename(args.result_file_name) or "sds_train"

    # 0건이면 파일을 쓰기 전에 실패 종료 — 실패 잡이 빈 [] sidecar 를 남기지 않도록.
    total = sum(len(by_variant[v]) for v in targets)
    if total == 0:
        print(f"[sds_llava] ok={stats['ok']} skipped={stats['skipped']} produced 0 records — "
              "check dataset structure — expected either scenario subdirs "
              "(input_data.csv + input_image.png + output_*.txt) or type dirs "
              "(png/ + csv/ + describe_ko/ + advice_ko/).",
              flush=True)
        sys.exit(1)

    written = []
    for v in targets:
        data = by_variant[v]
        # 0건 variant 는 파일을 만들지 않는다. variant=all 이 기본인데 드롭에
        # 따라(예: ko 라벨만 있는 데이터) 나머지가 늘 0건이고, 빈 [] 파일이
        # 남으면 그걸 학습 입력으로 지목했을 때 조용히 0 샘플로 학습된다.
        # total==0 을 실패로 끊는 위 가드와 같은 취지를 variant 단위로 적용.
        if not data:
            print(f"[sds_llava] {v}: 0 samples — skip writing", flush=True)
            continue
        out_path = os.path.join(input_dir, f"{safe_name}_{v}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        written.append(out_path)
        print(f"[sds_llava] {v}: {len(data)} samples → {out_path}", flush=True)

    print(f"[sds_llava] ok={stats['ok']} skipped={stats['skipped']} "
          f"total_records={total} files={len(written)}", flush=True)


if __name__ == "__main__":
    main()
