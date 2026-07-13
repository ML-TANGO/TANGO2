#!/usr/bin/env python3
"""빌트인 전처리 — SDS 시나리오 데이터셋 → LLaVA 학습 JSON (도메인 특화).

fb_preprocessing 빌트인(TYPE_BUILT_IN.SDS_LLAVA_CONVERT) 잡이 이미지 안에서
``python3 -u /built_in/sds_llava_convert.py <params> --input_data=/dataset/<name>`` 로 실행.

- 입력: SDS 데이터셋 **디렉터리**(시나리오 subdir 다수). 각 subdir 안:
    input_data.csv, input_image.png,
    output_describe_en.txt / output_advice_en.txt,
    output_describe_kor.txt / output_advice_kor.txt, output_advice_compact.txt
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


def build(input_dir):
    """시나리오 디렉터리들 → (en_data, ko_data, compact_data, stats)."""
    samples = sorted(
        d for d in os.listdir(input_dir)
        if os.path.isdir(os.path.join(input_dir, d))
    )
    en_data, ko_data, compact_data = [], [], []
    stats = {"ok": 0, "skipped": 0}

    for name in samples:
        sd = os.path.join(input_dir, name)
        csv_path = os.path.join(sd, "input_data.csv")
        img_path = os.path.join(sd, "input_image.png")
        img_rel = f"{name}/input_image.png"  # relative to input_dir (= IMAGE_DIR)

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

        desc_en = read_txt(os.path.join(sd, "output_describe_en.txt"))
        adv_en = read_txt(os.path.join(sd, "output_advice_en.txt"))
        desc_kor = read_txt(os.path.join(sd, "output_describe_kor.txt"))
        adv_kor = read_txt(os.path.join(sd, "output_advice_kor.txt"))
        compact = read_txt(os.path.join(sd, "output_advice_compact.txt"))

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
              "check dataset structure (scenario subdirs with input_data.csv + input_image.png + output_*.txt).",
              flush=True)
        sys.exit(1)

    written = []
    for v in targets:
        data = by_variant[v]
        out_path = os.path.join(input_dir, f"{safe_name}_{v}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        written.append(out_path)
        print(f"[sds_llava] {v}: {len(data)} samples → {out_path}", flush=True)

    print(f"[sds_llava] ok={stats['ok']} skipped={stats['skipped']} "
          f"total_records={total} files={len(written)}", flush=True)


if __name__ == "__main__":
    main()
