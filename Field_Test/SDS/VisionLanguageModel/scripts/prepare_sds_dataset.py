#!/usr/bin/env python3
"""
scripts/prepare_sds_dataset.py — SDS 데이터셋을 LLaVA 형식 JSON으로 변환

두 가지 데이터셋 레이아웃을 지원한다.

[구 포맷 — 20260227] 샘플당 디렉토리 하나
  <root>/<sample>/input_data.csv, input_image.png,
                  output_describe_en.txt, output_advice_en.txt,
                  output_describe_kor.txt, output_advice_kor.txt,
                  output_advice_compact.txt

  3가지 학습 시나리오를 생성한다.
    sds_train_en.json         : 영문  — AIS(EN) + 해상상황묘사(EN) + 항해조력메시지(EN)
    sds_train_ko.json         : 한글  — AIS(KO) + 해상상황묘사(KO) + 항해조력메시지(KO)
    sds_train_ko_compact.json : 한글 간결 — AIS(KO) + 간결항해조력메시지(KO)

[평면 포맷 — 20260728] 출력 종류별 디렉토리
  <root>/csv/<stem>.csv
  <root>/png/<stem>.png
  <root>/describe_ko/<stem>.describe_ko.txt
  <root>/advice_ko/<stem>.advice_ko.txt

  국문 출력 2종만 있으므로 한글 시나리오 하나를 만들고, --valid_ratio 로
  학습/검증셋을 나눈다.
    sds_train_ko_<N>k.json
    sds_valid_ko_<N>k.json

Usage:
  python scripts/prepare_sds_dataset.py                       # 구 포맷 기본 경로
  python scripts/prepare_sds_dataset.py --dataset_dir ../dataset/20260728
  python scripts/prepare_sds_dataset.py --dataset_dir ../dataset/20260728 \
      --valid_ratio 0.1 --seed 42
"""
import os
import sys
import json
import random
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

# 평면 포맷 판별에 필요한 디렉토리 (demo/app.py FLAT_REQUIRED_DIRS 와 동일)
FLAT_REQUIRED_DIRS = ("csv", "png")

# 평면 포맷의 출력 파일 위치
FLAT_DESCRIBE = ("describe_ko", ".describe_ko.txt")
FLAT_ADVICE   = ("advice_ko",   ".advice_ko.txt")


# ── AIS 포맷 ──────────────────────────────────────────────────────────────────
# demo/app.py 의 _format_ais_df() 와 같은 문자열을 만든다. 학습 프롬프트와 추론
# 프롬프트가 한 글자라도 달라지면 모델이 학습한 입력 분포를 벗어나므로, 두 함수는
# 함께 수정해야 한다. include_bbox 도 그 대상이다.

def format_ais(df: pd.DataFrame, lang: str, include_bbox: bool = True) -> str:
    """
    정규화된 DataFrame 으로 AIS 텍스트를 만든다.

    ship_type 컬럼이 있으면 포함한다. cpa/tcpa 컬럼(평면 포맷 20260728)이 있으면
    타선 항목에 함께 포함한다.

    include_bbox=False 이면 타선 항목에서 바운딩박스를 뺀다. 20260728 은 bbox_*
    좌표가 PNG 와 다른 카메라 기준으로 생성되어 이미지 위치와 일치하지 않으므로
    이 경로를 쓴다. 근거는 demo/app.py 의 FLAT_BBOX_NOTICE 주석에 있다.
    """
    has_type = "ship_type" in df.columns
    has_cpa  = "cpa" in df.columns and "tcpa" in df.columns

    def _cpa_str(row, en: bool) -> str:
        if not has_cpa:
            return ""
        if en:
            return f" | CPA:{float(row['cpa']):.4f}NM TCPA:{float(row['tcpa']):.2f}s"
        return f" | CPA:{float(row['cpa']):.4f}NM TCPA:{float(row['tcpa']):.2f}초"

    def _bbox_str(row, en: bool) -> str:
        if not include_bbox:
            return ""
        bbox = (f"x={row['bbox_x']:.0f} y={row['bbox_y']:.0f} "
                f"w={row['bbox_width']:.0f} h={row['bbox_height']:.0f}")
        label = "BoundingBox" if en else "바운딩박스"
        return f" | {label}:[{bbox}]"

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
            stype = f" Type:{row['ship_type']}" if has_type else ""
            if int(row["my_ship"]) == 1:
                lines.append(
                    f"- Own vessel (ID:{sid}{stype}) | Lat:{lat} Lon:{lon} | "
                    f"Speed:{spd} Heading:{hdg} | Size:{lw} Draft:{draft}"
                )
            else:
                lines.append(
                    f"- Nearby vessel (ID:{sid}{stype}) | Lat:{lat} Lon:{lon} | "
                    f"Speed:{spd} Heading:{hdg} | Size:{lw} Draft:{draft}"
                    f"{_bbox_str(row, True)}{_cpa_str(row, True)}"
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
            stype = f" 종류:{row['ship_type']}" if has_type else ""
            if int(row["my_ship"]) == 1:
                lines.append(
                    f"- 자선 (ID:{sid}{stype}) | 위도:{lat} 경도:{lon} | "
                    f"속도:{spd} 방향:{hdg} | 선체:{lw} 흘수:{draft}"
                )
            else:
                lines.append(
                    f"- 주변선박 (ID:{sid}{stype}) | 위도:{lat} 경도:{lon} | "
                    f"속도:{spd} 방향:{hdg} | 선체:{lw} 흘수:{draft}"
                    f"{_bbox_str(row, False)}{_cpa_str(row, False)}"
                )
    return "\n".join(lines)


def read_txt(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def load_csv_normalized(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = df.columns.str.lower()
    return df


def is_flat_dataset(dataset_dir: str) -> bool:
    """평면 포맷(20260728) 여부. csv/ 와 png/ 디렉토리가 모두 있으면 True."""
    return all(
        os.path.isdir(os.path.join(dataset_dir, d)) for d in FLAT_REQUIRED_DIRS
    )


def write_json(path: str, data: list, label: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # 토큰 길이 추정 (rough: 4 chars ≈ 1 token)
    avg_chars = sum(
        len(s["conversations"][0]["value"]) + len(s["conversations"][1]["value"])
        for s in data
    ) / max(len(data), 1)
    print(f"  [{label:10s}] {os.path.basename(path)}: {len(data):,}개 샘플  "
          f"(평균 입출력 ~{avg_chars / 4:.0f} 토큰)")


def count_label(n: int) -> str:
    """9000 → '9k', 1000 → '1k', 950 → '950'. 파일 이름에 쓴다."""
    if n >= 1000 and n % 1000 == 0:
        return f"{n // 1000}k"
    return str(n)


# ── 구 포맷 (20260227) ────────────────────────────────────────────────────────

def build_old_format(args) -> None:
    samples = sorted([
        d for d in os.listdir(args.dataset_dir)
        if os.path.isdir(os.path.join(args.dataset_dir, d))
    ])
    print(f"총 샘플 수: {len(samples)}  ({args.dataset_dir})  [구 포맷]")

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

        df = load_csv_normalized(csv_path)

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
                    {"from": "human", "value": f"<image>\n{ais_en}\n\n{PROMPT_EN}"},
                    {"from": "gpt",   "value": f"{desc_en}\n\n{adv_en}"},
                ],
            })

        # ── 시나리오 2: 한글 ─────────────────────────────────────────────────
        if desc_kor and adv_kor:
            ko_data.append({
                "id": f"{name}_ko",
                "image": img_rel,
                "conversations": [
                    {"from": "human", "value": f"<image>\n{ais_ko}\n\n{PROMPT_KO}"},
                    {"from": "gpt",   "value": f"{desc_kor}\n\n{adv_kor}"},
                ],
            })

        # ── 시나리오 3: 한글 간결 ────────────────────────────────────────────
        if compact:
            compact_data.append({
                "id": f"{name}_ko_compact",
                "image": img_rel,
                "conversations": [
                    {"from": "human", "value": f"<image>\n{ais_ko}\n\n{PROMPT_COMPACT}"},
                    {"from": "gpt",   "value": compact},
                ],
            })

        stats["ok"] += 1

    print()
    for fname, data, label in [
        ("sds_train_en.json",         en_data,      "영문"),
        ("sds_train_ko.json",         ko_data,      "한글"),
        ("sds_train_ko_compact.json", compact_data, "한글 간결"),
    ]:
        write_json(os.path.join(args.output_dir, fname), data, label)

    if stats["skipped"]:
        print(f"\n스킵된 샘플: {stats['skipped']}개")
        for n in stats["missing_files"]:
            print(f"  - {n}")


# ── 평면 포맷 (20260728) ──────────────────────────────────────────────────────

def build_flat_format(args) -> None:
    """
    평면 포맷에서 한글 시나리오 하나를 만들고 학습/검증으로 나눈다.

    타깃은 describe_ko 와 advice_ko 를 빈 줄로 이어 붙인 하나의 응답이며,
    프롬프트는 구 포맷의 한글 시나리오와 같은 PROMPT_KO 를 쓴다.

    바운딩박스는 넣지 않는다. 이 데이터셋의 bbox_* 좌표는 PNG 와 다른 카메라
    기준으로 생성되어 이미지 위의 선박 위치와 일치하지 않는다.
    """
    csv_dir = os.path.join(args.dataset_dir, "csv")
    png_dir = os.path.join(args.dataset_dir, "png")
    desc_dir, desc_suffix = (os.path.join(args.dataset_dir, FLAT_DESCRIBE[0]), FLAT_DESCRIBE[1])
    adv_dir,  adv_suffix  = (os.path.join(args.dataset_dir, FLAT_ADVICE[0]),   FLAT_ADVICE[1])

    for d in (desc_dir, adv_dir):
        if not os.path.isdir(d):
            raise SystemExit(f"[Prepare] {d} 가 없습니다. 평면 포맷의 국문 출력 "
                             f"디렉토리가 필요합니다.")

    stems = sorted(
        os.path.splitext(f)[0] for f in os.listdir(csv_dir) if f.endswith(".csv")
    )
    print(f"총 샘플 수: {len(stems):,}  ({args.dataset_dir})  [평면 포맷]")

    data = []
    skipped = {"png": 0, "describe": 0, "advice": 0}

    for stem in stems:
        if not os.path.exists(os.path.join(png_dir, f"{stem}.png")):
            skipped["png"] += 1
            continue

        desc = read_txt(os.path.join(desc_dir, f"{stem}{desc_suffix}"))
        if not desc:
            skipped["describe"] += 1
            continue

        adv = read_txt(os.path.join(adv_dir, f"{stem}{adv_suffix}"))
        if not adv:
            skipped["advice"] += 1
            continue

        df     = load_csv_normalized(os.path.join(csv_dir, f"{stem}.csv"))
        ais_ko = format_ais(df, "ko", include_bbox=False)

        data.append({
            "id": f"{stem}_ko",
            "image": f"png/{stem}.png",   # relative to dataset_dir
            "conversations": [
                {"from": "human", "value": f"<image>\n{ais_ko}\n\n{PROMPT_KO}"},
                {"from": "gpt",   "value": f"{desc}\n\n{adv}"},
            ],
        })

    total   = len(data)
    dropped = sum(skipped.values())
    if dropped:
        print(f"제외된 샘플: {dropped}개 "
              f"(png {skipped['png']}, describe_ko {skipped['describe']}, "
              f"advice_ko {skipped['advice']})")

    # ── 학습/검증 분할 ────────────────────────────────────────────────────────
    # 고정 시드로 섞는다. 같은 데이터셋과 같은 --seed 면 같은 분할이 재현된다.
    order = list(range(total))
    random.Random(args.seed).shuffle(order)

    n_valid = int(round(total * args.valid_ratio))
    valid   = [data[i] for i in order[:n_valid]]
    train   = [data[i] for i in order[n_valid:]]

    train_name = f"sds_train_ko_{count_label(len(train))}.json"
    valid_name = f"sds_valid_ko_{count_label(len(valid))}.json"

    print(f"\n분할: valid_ratio={args.valid_ratio}  seed={args.seed}")
    write_json(os.path.join(args.output_dir, train_name), train, "학습")
    write_json(os.path.join(args.output_dir, valid_name), valid, "검증")

    # 두 셋이 겹치지 않고 합이 전체와 같은지 확인한다. 분할 코드가 조용히 틀리면
    # 검증 손실이 학습 손실을 그대로 따라가는 것으로만 드러나서 알아채기 어렵다.
    train_ids = {s["id"] for s in train}
    valid_ids = {s["id"] for s in valid}
    assert not (train_ids & valid_ids), "학습셋과 검증셋에 같은 샘플이 있습니다"
    assert len(train_ids) + len(valid_ids) == total, "분할 후 샘플 수가 맞지 않습니다"
    print(f"  분할 확인: 중복 0개, 합계 {total:,}개")


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser("Prepare SDS dataset for VLM LoRA fine-tuning")
    p.add_argument("--dataset_dir", default=DEFAULT_DATASET_DIR,
                   help="Dataset root (구 포맷: 샘플 디렉토리들, "
                        "평면 포맷: csv/ png/ describe_ko/ advice_ko/)")
    p.add_argument("--output_dir",  default=DEFAULT_OUTPUT_DIR,
                   help="Directory to write JSON files")
    p.add_argument("--skip_missing", action="store_true",
                   help="구 포맷 전용. 출력 파일이 하나라도 비면 샘플을 제외한다")
    p.add_argument("--valid_ratio", type=float, default=0.1,
                   help="평면 포맷 전용. 검증셋 비율 (0 이면 분할하지 않는다)")
    p.add_argument("--seed", type=int, default=42,
                   help="평면 포맷 전용. 학습/검증 분할 셔플 시드")
    return p.parse_args()


def main():
    args = parse_args()
    args.dataset_dir = os.path.abspath(args.dataset_dir)
    os.makedirs(args.output_dir, exist_ok=True)

    if is_flat_dataset(args.dataset_dir):
        build_flat_format(args)
    else:
        build_old_format(args)

    print(f"\nimage_dir (학습 스크립트에 지정): {args.dataset_dir}")


if __name__ == "__main__":
    main()
