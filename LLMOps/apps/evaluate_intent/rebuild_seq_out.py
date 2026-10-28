#!/usr/bin/env python3
"""MixATIS 의 누락된 `seq.out`(BIO 태그)을 CoNLL 원본에서 복원한다.

`ugen_data.read_split()` 은 split 당 `seq.in`/`seq.out`/`label` 세 파일을 모두 요구하는데,
저장소의 `Evaluation/Intent_Detection/data/MixATIS_clean` 에는 **seq.out 이 없다** —
루트 `.gitignore` 4번째 줄 `*.out` 이 삼켰기 때문이다(train·dev·test 전부).

같은 디렉토리의 `<split>.txt` 가 CoNLL 형식으로 남아 있어 복원이 가능하다:

    토큰 태그      <- 한 줄에 하나
    ...
    의도#의도       <- 블록 끝 한 줄(공백 없는 단일 필드)
    (빈 줄)

이 스크립트는 그 블록을 읽어 seq.out 을 쓰고, 같은 블록에서 뽑은 토큰·의도가 기존
`seq.in`/`label` 과 **전부 일치하는지 대조**한다. 하나라도 어긋나면 쓰지 않고 실패한다 —
태그가 문장과 어긋난 채 평가에 들어가면 점수만 조용히 낮아진다.

빌드 시 build.sh 가 스테이징 디렉토리에 대고 실행한다(원본 저장소는 건드리지 않는다).
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional, Tuple


def parse_conll(path: str) -> Tuple[List[List[str]], List[List[str]], List[str]]:
    """CoNLL txt → (토큰 블록들, 태그 블록들, 의도 라벨들)."""
    tokens: List[List[str]] = []
    tags: List[List[str]] = []
    intents: List[str] = []
    cur_t: List[str] = []
    cur_g: List[str] = []
    pending_intent: Optional[str] = None

    def flush() -> None:
        nonlocal cur_t, cur_g, pending_intent
        if cur_t:
            tokens.append(cur_t)
            tags.append(cur_g)
            intents.append(pending_intent or "")
        cur_t, cur_g, pending_intent = [], [], None

    with open(path, encoding="utf-8") as fh:
        for line in fh:
            s = line.rstrip("\n")
            if not s.strip():
                flush()
                continue
            parts = s.split()
            if len(parts) >= 2:
                cur_t.append(parts[0])
                cur_g.append(parts[1])
            else:
                # 공백 없는 단일 필드 = 블록의 의도 라벨 줄
                pending_intent = parts[0]
    flush()
    return tokens, tags, intents


def read_lines(path: str) -> List[str]:
    with open(path, encoding="utf-8") as fh:
        return [ln.strip() for ln in fh if ln.strip()]


def rebuild_split(data_dir: str, split: str) -> int:
    """한 split 의 seq.out 을 복원하고 행 수를 돌려준다. 대조 실패 시 SystemExit."""
    txt = os.path.join(data_dir, f"{split}.txt")
    base = os.path.join(data_dir, split)
    seq_in, label = os.path.join(base, "seq.in"), os.path.join(base, "label")
    seq_out = os.path.join(base, "seq.out")

    for p in (txt, seq_in, label):
        if not os.path.isfile(p):
            raise SystemExit(f"[{split}] 필요한 파일이 없다: {p}")

    tokens, tags, intents = parse_conll(txt)
    ref_in, ref_lab = read_lines(seq_in), read_lines(label)

    if not (len(tokens) == len(ref_in) == len(ref_lab)):
        raise SystemExit(f"[{split}] 블록 수 불일치: txt={len(tokens)} "
                         f"seq.in={len(ref_in)} label={len(ref_lab)}")

    for i, (tok, tag, intent) in enumerate(zip(tokens, tags, intents)):
        if " ".join(tok) != ref_in[i]:
            raise SystemExit(f"[{split}] {i}번째 문장이 seq.in 과 다르다 — 복원 중단")
        if intent != ref_lab[i]:
            raise SystemExit(f"[{split}] {i}번째 의도가 label 과 다르다 — 복원 중단")
        if len(tok) != len(tag):
            raise SystemExit(f"[{split}] {i}번째 토큰/태그 길이 불일치 — 복원 중단")

    with open(seq_out, "w", encoding="utf-8") as fh:
        for tag in tags:
            fh.write(" ".join(tag) + "\n")
    return len(tags)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data_dir", help="MixATIS_clean 디렉토리")
    ap.add_argument("--splits", nargs="*", default=["train", "dev", "test"])
    args = ap.parse_args()

    total = 0
    for split in args.splits:
        n = rebuild_split(args.data_dir, split)
        total += n
        print(f"  {split}: seq.out {n}행 복원 (seq.in·label 과 전부 일치)")
    print(f"[ok] 총 {total}행")
    if total == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
