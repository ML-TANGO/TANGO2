"""MixATIS 평가 드라이버 — ETRI 원본 함수를 그대로 호출한다.

원본 `evaluate_qwen3_mixatis.py:main()` 은 argparse 로 인자를 받아 stdout 에 지표를
인쇄하고 끝난다. 플랫폼은 진행률 콜백과 `/output/metrics.json` 이 필요하므로 main() 을
쓰지 않고 **같은 함수들을 같은 순서로** 부르는 드라이버를 둔다. 모델 로드·프롬프트·생성·
파싱은 전부 원본 함수라 점수 정의가 갈라지지 않는다.

원본과 다른 점은 둘뿐이다.
  1) `adapter_dir` 는 선택이다. 플랫폼 체크포인트는 merged 라 그것만으로 평가가 되지만
     (원본의 zero-shot 경로), 같은 잡의 학습 단계가 LoRA 를 붙였으면 그 어댑터를 얹는다.
     비우면 종전과 완전히 같은 동작이다.
  2) 4bit 가 기본이 아니다. 원본은 A100 40G 급을 상정해 QLoRA 4bit 를 기본으로 켰지만
     우리 잡은 80GB 한 장을 통째로 받으므로 bf16 이 더 빠르고 bitsandbytes 의존도 없앤다.
     `use_4bit` 파라미터로 원본 동작을 복원할 수 있다.
"""
from __future__ import annotations

import csv
import os
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Tuple

import ugen_data
from evaluate_qwen3_mixatis import generate_batch, load_model_and_tokenizer

# 원본 run_experiment.sh 의 평가 기본값.
DEFAULT_BATCH_SIZE = 16
DEFAULT_MAX_NEW_TOKENS = 128
# 이미지에 baked 된 MixATIS(build.sh 가 seq.out 을 복원해 스테이징한다).
DATA_DIR = os.environ.get(
    "MIXATIS_DATA_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "MixATIS_clean"))

CSV_FIELDS = ("sentence", "gold_intents", "pred_intents",
              "gold_slots", "pred_slots", "intent_raw", "slot_raw")


def run_evaluate(model_path: str, output_dir: str, gpu_devices: str = "0",
                 split: str = "test", limit: int = 0,
                 batch_size: int = DEFAULT_BATCH_SIZE,
                 max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
                 use_4bit: bool = False, data_dir: str = DATA_DIR,
                 progress: Callable[[float, str], None] | None = None,
                 adapter_dir: str = "") -> Dict[str, Any]:
    """체크포인트로 MixATIS test 를 평가하고 예측 4종 리스트 + 통계를 돌려준다."""
    def tick(p: float, msg: str) -> None:
        if progress:
            progress(p, msg)

    # 플랫폼이 device 를 격리해 주므로 컨테이너 안에서는 0..n-1 이다.
    os.environ["CUDA_VISIBLE_DEVICES"] = gpu_devices

    examples = ugen_data.build_eval_examples(data_dir, split)
    if limit:
        examples = examples[:limit]
    if not examples:
        raise ValueError(f"평가할 발화가 없다: {data_dir}/{split}")
    tick(0.02, f"{len(examples)} 발화 로드")

    # 원본 loader 는 argparse Namespace 를 받는다 — 같은 필드만 채워 넘긴다.
    args = SimpleNamespace(model_name=model_path, adapter_dir=adapter_dir,
                           use_4bit=use_4bit)
    model, tokenizer = load_model_and_tokenizer(args)
    tick(0.10, "모델 로드 완료")

    pred_intents: List[List[str]] = []
    pred_slots: List[List[Tuple[str, str]]] = []
    gold_intents = [e["gold_intents"] for e in examples]
    gold_slots = [[tuple(s) for s in e["gold_slots"]] for e in examples]
    rows: List[Dict[str, str]] = []
    # 형식을 어긴 출력은 파싱에서 조용히 빈 예측이 된다 — 점수가 왜 낮은지 추적하려면
    # 개수를 세어 결과에 실어야 한다(LogicKor 의 unscored 와 같은 이유).
    empty_intent = empty_slot = 0

    for i in range(0, len(examples), batch_size):
        chunk = examples[i:i + batch_size]
        intent_out = generate_batch(model, tokenizer,
                                    [c["intent_messages"] for c in chunk], max_new_tokens)
        slot_out = generate_batch(model, tokenizer,
                                  [c["slot_messages"] for c in chunk], max_new_tokens)
        for c, io, so in zip(chunk, intent_out, slot_out):
            pi = ugen_data.parse_intent_answer(io)
            ps = ugen_data.parse_slot_answer(so)
            if not pi:
                empty_intent += 1
            if not ps:
                empty_slot += 1
            pred_intents.append(pi)
            pred_slots.append(ps)
            rows.append({
                "sentence": c["sentence"],
                "gold_intents": ";".join(c["gold_intents"]),
                "pred_intents": ";".join(pi),
                "gold_slots": ";".join(f"{v}={n}" for v, n in
                                       [tuple(x) for x in c["gold_slots"]]),
                "pred_slots": ";".join(f"{v}={n}" for v, n in ps),
                "intent_raw": io,
                "slot_raw": so,
            })
        done = min(i + batch_size, len(examples))
        tick(0.10 + 0.85 * done / len(examples), f"{done}/{len(examples)} 발화")

    # 발화별 예측 CSV — 형식 이탈을 사후에 눈으로 진단하는 유일한 수단이라 항상 남긴다.
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, "mixatis_eval.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(CSV_FIELDS))
        writer.writeheader()
        writer.writerows(rows)
    tick(0.97, "예측 CSV 저장")

    return {
        "pred_intents": pred_intents, "gold_intents": gold_intents,
        "pred_slots": pred_slots, "gold_slots": gold_slots,
        "stats": {
            "utterances": len(examples),
            "split": split,
            "batch_size": batch_size,
            "max_new_tokens": max_new_tokens,
            "use_4bit": bool(use_4bit),
            "adapter": bool(adapter_dir),
            "empty_intent_predictions": empty_intent,
            "empty_slot_predictions": empty_slot,
            "csv": os.path.basename(csv_path),
        },
    }
