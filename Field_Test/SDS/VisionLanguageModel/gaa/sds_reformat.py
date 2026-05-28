"""
SDS Dataset → GAA chat.json 변환 스크립트

에피소드 디렉토리 구조:
  <dataset_root>/
    <episode_id>/
      input_data.csv       ← AIS 정보 + bbox 좌표 (픽셀)
      input_image.png      ← 카메라 이미지
      output_advice_kor.txt  ← 항법 조언 (한국어)
      output_advice_en.txt   ← 항법 조언 (영어)
      output_describe_kor.txt
      output_describe_en.txt

출력 JSON 형식 (LLaVA + GAA 확장):
  {
    "id": "<episode_id>",
    "image": "<episode_id>/input_image.png",
    "conversations": [
      {"from": "human", "value": "<image>\n[선박 AIS 정보]\n..."},
      {"from": "gpt",   "value": "..."}
    ],
    "bboxes": [[x1, y1, x2, y2], ...]   ← 정규화 좌표 [0, 1]
  }

Usage:
  python gaa/sds_reformat.py \\
      --dataset_root /home/ywlee/dev/TANGO2/SDS/dataset/20260227 \\
      --output      data/sds_gaa_ko.json \\
      --lang        ko
"""
import os
import sys
import json
import argparse
import pandas as pd
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def parse_args():
    p = argparse.ArgumentParser("SDS → GAA chat.json converter")
    p.add_argument("--dataset_root", required=True,
                   help="에피소드 디렉토리들이 있는 루트 경로")
    p.add_argument("--output", required=True,
                   help="출력 JSON 파일 경로")
    p.add_argument("--lang", default="kor", choices=["kor", "en"],
                   help="응답 언어 (kor=한국어, en=영어)")
    p.add_argument("--task", default="advice", choices=["advice", "describe"],
                   help="응답 타입 (advice=항법 조언, describe=상황 묘사)")
    return p.parse_args()


def build_human_message(df: pd.DataFrame, lang: str) -> str:
    """AIS 데이터프레임으로 human 메시지 생성."""
    if lang == "kor":
        lines = ["<image>", "[선박 AIS 정보]"]
        for _, row in df.iterrows():
            if row["my_ship"] == 1:
                lines.append(
                    f"- 자선 (ID:{int(row['ship_id'])}) | "
                    f"위도:{row['latitude']:.6f} 경도:{row['longitude']:.6f} | "
                    f"속도:{row['knot']:.1f}kt 방향:{row['heading']:.1f}° | "
                    f"선체:{int(row['length'])}m × {int(row['width'])}m 흘수:{row['draft']:.1f}m"
                )
            else:
                lines.append(
                    f"- 주변선박 (ID:{int(row['ship_id'])}) | "
                    f"위도:{row['latitude']:.6f} 경도:{row['longitude']:.6f} | "
                    f"속도:{row['knot']:.1f}kt 방향:{row['heading']:.1f}° | "
                    f"선체:{int(row['length'])}m × {int(row['width'])}m 흘수:{row['draft']:.1f}m"
                )
        lines.append("\n주변 선박과의 충돌 위험을 분석하고 항법 조치를 조언해줘.")
    else:
        lines = ["<image>", "[Vessel AIS Information]"]
        for _, row in df.iterrows():
            if row["my_ship"] == 1:
                lines.append(
                    f"- Own vessel (ID:{int(row['ship_id'])}) | "
                    f"Lat:{row['latitude']:.6f} Lon:{row['longitude']:.6f} | "
                    f"Speed:{row['knot']:.1f}kt Heading:{row['heading']:.1f}° | "
                    f"Size:{int(row['length'])}m × {int(row['width'])}m Draft:{row['draft']:.1f}m"
                )
            else:
                lines.append(
                    f"- Nearby vessel (ID:{int(row['ship_id'])}) | "
                    f"Lat:{row['latitude']:.6f} Lon:{row['longitude']:.6f} | "
                    f"Speed:{row['knot']:.1f}kt Heading:{row['heading']:.1f}° | "
                    f"Size:{int(row['length'])}m × {int(row['width'])}m Draft:{row['draft']:.1f}m"
                )
        lines.append("\nAnalyze collision risk with nearby vessels and advise on navigation actions.")
    return "\n".join(lines)


def extract_bboxes(df: pd.DataFrame, img_w: int, img_h: int) -> list:
    """주변 선박(my_ship=0)의 bbox를 정규화 좌표로 추출."""
    bboxes = []
    for _, row in df.iterrows():
        if row["my_ship"] == 1:
            continue
        bx, by, bw, bh = row["bbox_x"], row["bbox_y"], row["bbox_width"], row["bbox_height"]
        if bw <= 0 or bh <= 0:
            continue
        x1 = max(0.0, bx / img_w)
        y1 = max(0.0, by / img_h)
        x2 = min(1.0, (bx + bw) / img_w)
        y2 = min(1.0, (by + bh) / img_h)
        if x2 > x1 and y2 > y1:
            bboxes.append([round(x1, 6), round(y1, 6), round(x2, 6), round(y2, 6)])
    return bboxes


def process_episode(ep_dir: str, ep_id: str, lang: str, task: str) -> dict | None:
    csv_path   = os.path.join(ep_dir, "input_data.csv")
    img_path   = os.path.join(ep_dir, "input_image.png")
    label_path = os.path.join(ep_dir, f"output_{task}_{lang}.txt")

    # 필수 파일 존재 확인
    for p in [csv_path, img_path, label_path]:
        if not os.path.exists(p):
            print(f"  [SKIP] {ep_id}: 파일 없음 — {os.path.basename(p)}")
            return None

    # 응답 텍스트
    with open(label_path, encoding="utf-8") as f:
        gpt_msg = f.read().strip()
    if not gpt_msg:
        print(f"  [SKIP] {ep_id}: 응답 텍스트 비어있음")
        return None

    # AIS 데이터
    df = pd.read_csv(csv_path)

    # 이미지 크기
    with Image.open(img_path) as img:
        img_w, img_h = img.size

    human_msg = build_human_message(df, lang)
    bboxes    = extract_bboxes(df, img_w, img_h)

    return {
        "id":    ep_id,
        "image": f"{ep_id}/input_image.png",
        "conversations": [
            {"from": "human", "value": human_msg},
            {"from": "gpt",   "value": gpt_msg},
        ],
        "bboxes": bboxes,
    }


def main():
    args = parse_args()

    episodes = sorted(
        d for d in os.listdir(args.dataset_root)
        if os.path.isdir(os.path.join(args.dataset_root, d))
    )
    print(f"발견된 에피소드: {len(episodes)}개")

    results = []
    skipped = 0
    for ep_id in episodes:
        ep_dir = os.path.join(args.dataset_root, ep_id)
        entry = process_episode(ep_dir, ep_id, args.lang, args.task)
        if entry is None:
            skipped += 1
        else:
            results.append(entry)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    bbox_count = sum(len(r["bboxes"]) for r in results)
    print(f"\n변환 완료:")
    print(f"  저장: {args.output}")
    print(f"  샘플: {len(results)}개 (스킵: {skipped}개)")
    print(f"  총 bbox: {bbox_count}개 "
          f"(평균 {bbox_count/len(results):.1f}개/샘플)")

    # 첫 번째 샘플 미리보기
    if results:
        print("\n--- 첫 번째 샘플 미리보기 ---")
        r = results[0]
        print(f"  id:     {r['id']}")
        print(f"  image:  {r['image']}")
        print(f"  bboxes: {r['bboxes']}")
        print(f"  human:  {r['conversations'][0]['value'][:200]}")
        print(f"  gpt:    {r['conversations'][1]['value'][:100]}")


if __name__ == "__main__":
    main()
