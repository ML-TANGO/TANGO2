#!/usr/bin/env python3
"""
scripts/prepare_sds_dataset.py — SDS 데이터셋을 LLaVA 형식 JSON으로 변환

3가지 학습 시나리오:
  sds_train_en.json         : 영문  — AIS(EN) + 해상상황묘사(EN) + 항해조력메시지(EN)
  sds_train_ko.json         : 한글  — AIS(KO) + 해상상황묘사(KO) + 항해조력메시지(KO)
  sds_train_ko_compact.json : 한글 간결 — AIS(KO) + 간결항해조력메시지(KO)

Usage:
  python scripts/prepare_sds_dataset.py
  python scripts/prepare_sds_dataset.py --dataset_dir /other/path --output_dir data/
"""
import os
import sys
import json
import argparse

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_DATASET_DIR = "/home/ywlee/dev/TANGO2_main/SDS/dataset/20260227"
DEFAULT_OUTPUT_DIR  = os.path.join(ROOT, "data")

# ── 프롬프트 (데모 PROMPT_MAP 과 동일 형식) ───────────────────────────────────
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


# ── AIS 포맷 (demo/app.py format_ais_text() 와 동일) ─────────────────────────

def format_ais(df: pd.DataFrame, lang: str) -> str:
    if lang == "en":
        lines = ["[Vessel AIS Information]"]
        for _, row in df.iterrows():
            sid   = int(row["ship_id"])
            spd   = f"{row['knot']:.1f}kt"
            hdg   = f"{row['heading']:.1f}°"
            lat   = f"{row['latitude']:.6f}"
            lon   = f"{row['longitude']:.6f}"
            lw    = f"{int(row['length'])}m x {int(row['width'])}m"
            draft = f"{int(row['draft'])}m"
            if int(row["my_ship"]) == 1:
                lines.append(
                    f"- Own vessel (ID:{sid}) | Lat:{lat} Lon:{lon} | "
                    f"Speed:{spd} Heading:{hdg} | Size:{lw} Draft:{draft}"
                )
            else:
                bbox = (f"x={row['bbox_x']:.0f} y={row['bbox_y']:.0f} "
                        f"w={row['bbox_width']:.0f} h={row['bbox_height']:.0f}")
                lines.append(
                    f"- Nearby vessel (ID:{sid}) | Lat:{lat} Lon:{lon} | "
                    f"Speed:{spd} Heading:{hdg} | Size:{lw} Draft:{draft} | "
                    f"BoundingBox:[{bbox}]"
                )
    else:
        lines = ["[선박 AIS 정보]"]
        for _, row in df.iterrows():
            sid   = int(row["ship_id"])
            spd   = f"{row['knot']:.1f}kt"
            hdg   = f"{row['heading']:.1f}°"
            lat   = f"{row['latitude']:.6f}"
            lon   = f"{row['longitude']:.6f}"
            lw    = f"{int(row['length'])}m × {int(row['width'])}m"
            draft = f"{int(row['draft'])}m"
            if int(row["my_ship"]) == 1:
                lines.append(
                    f"- 자선 (ID:{sid}) | 위도:{lat} 경도:{lon} | "
                    f"속도:{spd} 방향:{hdg} | 선체:{lw} 흘수:{draft}"
                )
            else:
                bbox = (f"x={row['bbox_x']:.0f} y={row['bbox_y']:.0f} "
                        f"w={row['bbox_width']:.0f} h={row['bbox_height']:.0f}")
                lines.append(
                    f"- 주변선박 (ID:{sid}) | 위도:{lat} 경도:{lon} | "
                    f"속도:{spd} 방향:{hdg} | 선체:{lw} 흘수:{draft} | "
                    f"바운딩박스:[{bbox}]"
                )
    return "\n".join(lines)


def read_txt(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser("Prepare SDS dataset for VLM LoRA fine-tuning")
    p.add_argument("--dataset_dir", default=DEFAULT_DATASET_DIR,
                   help="Root dir containing sample sub-directories")
    p.add_argument("--output_dir",  default=DEFAULT_OUTPUT_DIR,
                   help="Directory to write JSON files")
    p.add_argument("--skip_missing", action="store_true",
                   help="Exclude samples where any output file is empty/missing")
    return p.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    samples = sorted([
        d for d in os.listdir(args.dataset_dir)
        if os.path.isdir(os.path.join(args.dataset_dir, d))
    ])
    print(f"총 샘플 수: {len(samples)}  ({args.dataset_dir})")

    en_data, ko_data, compact_data = [], [], []
    stats = {"ok": 0, "skipped": 0, "missing_files": []}

    for name in samples:
        sd = os.path.join(args.dataset_dir, name)

        csv_path = os.path.join(sd, "input_data.csv")
        img_path = os.path.join(sd, "input_image.png")
        img_rel  = f"{name}/input_image.png"   # relative to dataset_dir

        # 필수 파일 확인
        if not os.path.exists(csv_path) or not os.path.exists(img_path):
            stats["skipped"] += 1
            stats["missing_files"].append(name)
            continue

        df = pd.read_csv(csv_path)

        desc_en  = read_txt(os.path.join(sd, "output_describe_en.txt"))
        adv_en   = read_txt(os.path.join(sd, "output_advice_en.txt"))
        desc_kor = read_txt(os.path.join(sd, "output_describe_kor.txt"))
        adv_kor  = read_txt(os.path.join(sd, "output_advice_kor.txt"))
        compact  = read_txt(os.path.join(sd, "output_advice_compact.txt"))

        if args.skip_missing and not all([desc_en, adv_en, desc_kor, adv_kor, compact]):
            stats["skipped"] += 1
            stats["missing_files"].append(name)
            continue

        ais_en = format_ais(df, "en")
        ais_ko = format_ais(df, "ko")

        # ── 시나리오 1: 영문 ─────────────────────────────────────────────────
        if desc_en and adv_en:
            en_data.append({
                "id": f"{name}_en",
                "image": img_rel,
                "conversations": [
                    {
                        "from": "human",
                        "value": f"<image>\n{ais_en}\n\n{PROMPT_EN}",
                    },
                    {
                        "from": "gpt",
                        "value": f"{desc_en}\n\n{adv_en}",
                    },
                ],
            })

        # ── 시나리오 2: 한글 ─────────────────────────────────────────────────
        if desc_kor and adv_kor:
            ko_data.append({
                "id": f"{name}_ko",
                "image": img_rel,
                "conversations": [
                    {
                        "from": "human",
                        "value": f"<image>\n{ais_ko}\n\n{PROMPT_KO}",
                    },
                    {
                        "from": "gpt",
                        "value": f"{desc_kor}\n\n{adv_kor}",
                    },
                ],
            })

        # ── 시나리오 3: 한글 간결 ────────────────────────────────────────────
        if compact:
            compact_data.append({
                "id": f"{name}_ko_compact",
                "image": img_rel,
                "conversations": [
                    {
                        "from": "human",
                        "value": f"<image>\n{ais_ko}\n\n{PROMPT_COMPACT}",
                    },
                    {
                        "from": "gpt",
                        "value": compact,
                    },
                ],
            })

        stats["ok"] += 1

    # ── JSON 저장 ─────────────────────────────────────────────────────────────
    scenarios = [
        ("sds_train_en.json",         en_data,      "영문"),
        ("sds_train_ko.json",         ko_data,      "한글"),
        ("sds_train_ko_compact.json", compact_data, "한글 간결"),
    ]

    print()
    for fname, data, label in scenarios:
        out_path = os.path.join(args.output_dir, fname)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # 토큰 길이 추정 (rough: 4 chars ≈ 1 token)
        avg_chars = sum(
            len(s["conversations"][0]["value"]) + len(s["conversations"][1]["value"])
            for s in data
        ) / max(len(data), 1)
        print(f"  [{label:8s}] {fname}: {len(data)}개 샘플  "
              f"(평균 입출력 ~{avg_chars/4:.0f} 토큰)")

    if stats["skipped"]:
        print(f"\n스킵된 샘플: {stats['skipped']}개")
        for n in stats["missing_files"]:
            print(f"  - {n}")

    print(f"\nimage_dir (학습 스크립트에 지정): {args.dataset_dir}")


if __name__ == "__main__":
    main()
