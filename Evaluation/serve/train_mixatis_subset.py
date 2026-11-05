#!/usr/bin/env python3
"""MixATIS SFT 를 예제 수만 제한해 짧게 돌리는 얇은 드라이버.

ETRI 원본(`train_qwen3_mixatis.py`)은 수정하지 않는다. `--debug` 플래그가 있지만
앞 200개로 고정이라 원하는 크기를 못 준다. 그래서 여기서
`build_training_examples` 만 감싸 부분집합을 돌려주고 원본 `main()` 을 그대로 호출한다.

부분집합은 **발화 단위**로 뽑는다. 원본은 발화당 (intent QA, slot QA) 2개를 이 순서로
연속 배치하므로, 앞에서 그냥 잘라내면 파일 순서 편향이 그대로 들어온다. 쌍을 유지한 채
고정 시드로 섞어 두 과제의 비율(1:1)을 보존한다.

사용:
  MIXATIS_LIMIT=3000 python train_mixatis_subset.py --model_name ... --epochs 1 ...

인자는 전부 원본 argparse 로 그대로 넘어간다. 예제 수만 env 로 받는다.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import train_qwen3_mixatis as T   # noqa: E402

LIMIT = int(os.environ.get("MIXATIS_LIMIT", "3000"))
SEED = int(os.environ.get("MIXATIS_SUBSET_SEED", "42"))
_orig = T.build_training_examples


def _subset(data_dir, split):
    examples = _orig(data_dir, split)
    if LIMIT <= 0 or LIMIT >= len(examples):
        print(f"[subset] 제한 없음 — 전체 {len(examples)}개 사용")
        return examples

    # (intent, slot) 쌍으로 묶는다. 원본이 이 순서로 append 하므로 2개씩 끊으면 된다.
    pairs = [examples[i:i + 2] for i in range(0, len(examples), 2)]
    for p in pairs:
        tasks = [e["task"] for e in p]
        if tasks != ["intent", "slot"]:
            raise SystemExit(f"[subset] 예상과 다른 예제 배치({tasks}) — 원본 변경 의심, 중단")

    random.Random(SEED).shuffle(pairs)
    n_pairs = LIMIT // 2
    picked = [e for p in pairs[:n_pairs] for e in p]
    print(f"[subset] 전체 {len(examples)}개 중 {len(picked)}개 사용 "
          f"(발화 {n_pairs}개 x 2문항, seed={SEED})")
    return picked


T.build_training_examples = _subset

if __name__ == "__main__":
    T.main()
