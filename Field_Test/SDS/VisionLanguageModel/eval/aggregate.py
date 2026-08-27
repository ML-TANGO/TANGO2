#!/usr/bin/env python3
"""
eval/aggregate.py — 구성별 채점 결과를 하나의 표로 모은다.

출력은 셋이다.
  <out>.csv  구성 × 지표 전체 (기계 판독용)
  <out>.md   계열별 비교 표 (사람 판독용)
  <out>.json 원본 값 전부

사용:
  python eval/aggregate.py --dir results/eval_20260728 --out results/eval_20260728/summary
"""
import os
import json
import argparse
from collections import OrderedDict

# 표에 실을 순서. (표시 이름, 접근 경로, 소수 자리)
ROWS = [
    ("한글 출력 비율(%)",        ("content", "korean_output_pct"), 1),
    ("한글 문자 비율(%)",        ("content", "hangul_ratio_mean"), 1),
    ("SDS 형식 준수(%)",         ("content", "sds_format_pct"), 1),
    ("다단락 출력(%)",           ("content", "multi_paragraph_pct"), 1),
    ("빈 응답(%)",               ("content", "empty_pct"), 1),
    ("생성 길이 중앙값(자)",     ("content", "pred_len_median"), 0),

    ("BLEU",                     ("surface", "BLEU"), 2),
    ("BLEU-1",                   ("surface", "BLEU-1"), 2),
    ("BLEU-4",                   ("surface", "BLEU-4"), 2),
    ("chrF++",                   ("surface", "chrF++"), 2),
    ("ROUGE-1",                  ("surface", "ROUGE-1"), 2),
    ("ROUGE-2",                  ("surface", "ROUGE-2"), 2),
    ("ROUGE-L",                  ("surface", "ROUGE-L"), 2),
    ("METEOR",                   ("surface", "METEOR"), 2),
    ("CIDEr-D",                  ("surface", "CIDEr-D"), 2),
    ("TER(200표본, 낮을수록 근접)", ("surface", "TER"), 2),
    ("BERTScore-F1",             ("semantic", "BERTScore-F1"), 2),

    ("조우 유형 정확도(%)",      ("content", "encounter_acc"), 1),
    ("항법상 지위 정확도(%)",    ("content", "role_acc"), 1),
    ("변침 방향 정확도(%)",      ("content", "turn_dir_acc"), 1),
    ("육안 척수 일치(%)",        ("content", "vessel_count_vs_ref_acc"), 1),
    ("COLREG 조항 F1",           ("content", "colreg_f1"), 2),
    ("COLREG 조항 정밀도",       ("content", "colreg_precision"), 2),
    ("COLREG 조항 재현율",       ("content", "colreg_recall"), 2),
    ("조종 권고 비율(%)",        ("content", "advises_turn_pct"), 1),
    ("좌현변침 금지 위반(%)",    ("content", "port_turn_violation_pct"), 1),
]

NUMERIC_FIELDS = [
    ("CPA", "cpa"), ("TCPA", "tcpa"),
    ("자선 침로", "own_course"), ("자선 속력", "own_speed"),
    ("타선 침로", "tgt_course"), ("타선 속력", "tgt_speed"),
]

# Gemma 4 는 CLIP 계열과 계보가 다른 별도 기준선이므로 맨 뒤에 둔다.
ORDER = ["qwen3_clean", "qwen3_marine", "qwen3_sds9k",
         "llama31_clean", "llama31_marine", "llama31_sds9k",
         "gemma4_sds9k"]

LABEL = {
    "qwen3_clean":   "Qwen3 clean",
    "qwen3_marine":  "Qwen3 marine",
    "qwen3_sds9k":   "Qwen3 SDS-9k",
    "llama31_clean": "Llama3.1 clean",
    "llama31_marine": "Llama3.1 marine",
    "llama31_sds9k": "Llama3.1 SDS-9k",
    "gemma4_sds9k":  "Gemma4 SDS-9k",
}


def get(d, path):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def fmt(v, nd):
    if v is None:
        return "-"
    if isinstance(v, (int, float)):
        return f"{v:.{nd}f}"
    return str(v)


def md_table(names, rows):
    head = "| 지표 | " + " | ".join(LABEL.get(n, n) for n in names) + " |"
    sep = "|---" * (len(names) + 1) + "|"
    return "\n".join([head, sep] + rows)


def main():
    ap = argparse.ArgumentParser("채점 결과 집계")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    loaded = OrderedDict()
    for name in ORDER:
        p = os.path.join(args.dir, f"{name}.metrics.json")
        if os.path.exists(p):
            loaded[name] = json.load(open(p, encoding="utf-8"))
        else:
            print(f"  없음, 건너뜀: {p}")
    if not loaded:
        raise SystemExit("채점 결과가 하나도 없습니다.")

    names = list(loaded)

    # ── CSV ───────────────────────────────────────────────────────────────────
    csv_lines = ["metric," + ",".join(names)]
    for label, path, nd in ROWS:
        vals = [get(loaded[n], path) for n in names]
        csv_lines.append(label + "," + ",".join(
            "" if v is None else f"{v}" for v in vals))
    for disp, key in NUMERIC_FIELDS:
        for stat in ["within_tol", "median_ae", "coverage"]:
            vals = [get(loaded[n], ("content", "numeric", key, stat)) for n in names]
            csv_lines.append(f"{disp} {stat}," + ",".join(
                "" if v is None else f"{v}" for v in vals))
    with open(args.out + ".csv", "w", encoding="utf-8") as f:
        f.write("\n".join(csv_lines) + "\n")

    # ── Markdown ──────────────────────────────────────────────────────────────
    body = []
    for label, path, nd in ROWS:
        vals = [fmt(get(loaded[n], path), nd) for n in names]
        body.append(f"| {label} | " + " | ".join(vals) + " |")

    num_body = []
    for disp, key in NUMERIC_FIELDS:
        wt = [fmt(get(loaded[n], ("content", "numeric", key, "within_tol")), 1)
              for n in names]
        num_body.append(f"| {disp} 허용오차 내(%) | " + " | ".join(wt) + " |")
        ae = [fmt(get(loaded[n], ("content", "numeric", key, "median_ae")), 3)
              for n in names]
        num_body.append(f"| {disp} 절대오차 중앙값 | " + " | ".join(ae) + " |")

    md = [
        "# 20260728 검증셋 1,000건 평가",
        "",
        f"샘플 수: {loaded[names[0]]['n']:,}건. 생성은 greedy, `max_new_tokens=512` 고정.",
        "",
        "## 전체 지표",
        "",
        md_table(names, body),
        "",
        "## 수치 충실도 (정답은 CSV 원본)",
        "",
        md_table(names, num_body),
        "",
    ]
    with open(args.out + ".md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    with open(args.out + ".json", "w", encoding="utf-8") as f:
        json.dump(loaded, f, ensure_ascii=False, indent=2)

    print(f"→ {args.out}.csv")
    print(f"→ {args.out}.md")
    print(f"→ {args.out}.json")
    print()
    print("\n".join(md))


if __name__ == "__main__":
    main()
