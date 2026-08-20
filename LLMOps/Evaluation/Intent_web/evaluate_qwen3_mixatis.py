# -*- coding: utf-8 -*-
"""
evaluate_qwen3_mixatis.py
-------------------------
학습한 Qwen3-8B(LoRA) 로 MixATIS test 셋을 추론하고 UGEN 메트릭으로 평가한다.

발화당 두 번 생성(UGEN 테스트 방식 그대로):
  1) intent QA -> intent 집합
  2) slot   QA -> (value, slot name) 쌍 집합

메트릭(UGEN utils/metric.py 의 Evaluator 와 동일 정의):
  - Intent Acc   : 문장별 intent 집합이 정확히 일치하는 비율(정렬 비교)
  - Intent F1    : intent 집합 멤버십 기반 micro F1
  - Slot F1      : (value, name) 쌍 기반 micro F1
  - Overall(Joint) Acc : slot 쌍 집합 AND intent 집합이 모두 일치하는 비율

사용 예:
  python evaluate_qwen3_mixatis.py \
      --model_name Qwen/Qwen3-8B \
      --adapter_dir ./out/qwen3-8b-mixatis-lora \
      --data_dir ./UGEN/data/MixATIS_clean \
      --out_csv ./out/mixatis_eval.csv --use_4bit

--adapter_dir 를 비우면 베이스 모델 zero-shot 평가가 된다.
"""

import os
import csv
import argparse
from typing import List, Tuple

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

from ugen_data import (
    build_eval_examples,
    parse_intent_answer,
    parse_slot_answer,
)


# ============================ 메트릭 (UGEN 재현) ==============================
def intent_acc(preds: List[List[str]], golds: List[List[str]]) -> float:
    correct = sum(1 for p, g in zip(preds, golds) if sorted(p) == sorted(g))
    return correct / len(golds) if golds else 0.0


def micro_f1(preds: List[list], golds: List[list]) -> Tuple[float, float, float]:
    """집합 멤버십 기반 micro precision/recall/F1 (intent·slot 공용)."""
    tp = fp = fn = 0.0
    for pred, gold in zip(preds, golds):
        gold_pool = list(gold)
        tp_i = 0
        for item in pred:
            if item in gold_pool:
                tp_i += 1
                gold_pool.remove(item)   # 중복 매칭 방지
            else:
                fp += 1
        fn += len(gold) - tp_i
        tp += tp_i
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f1


def overall_acc(pred_slots, gold_slots, pred_intents, gold_intents) -> float:
    correct = 0
    for ps, gs, pi, gi in zip(pred_slots, gold_slots, pred_intents, gold_intents):
        if sorted(ps) == sorted(gs) and sorted(pi) == sorted(gi):
            correct += 1
    return correct / len(gold_intents) if gold_intents else 0.0


# ============================ 생성 유틸 =====================================
def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--model_name", default="Qwen/Qwen3-8B")
    p.add_argument("--adapter_dir", default="", help="LoRA 어댑터 경로(없으면 zero-shot)")
    p.add_argument("--data_dir", default="./UGEN/data/MixATIS_clean")
    p.add_argument("--split", default="test")
    p.add_argument("--out_csv", default="./out/mixatis_eval.csv")
    p.add_argument("--max_new_tokens", type=int, default=128)
    p.add_argument("--batch_size", type=int, default=16)
    p.add_argument("--use_4bit", action="store_true")
    p.add_argument("--limit", type=int, default=0, help="앞 N개만 평가(디버그)")
    return p.parse_args()


def load_model_and_tokenizer(args):
    tokenizer = AutoTokenizer.from_pretrained(
        args.adapter_dir or args.model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"     # 생성은 left padding

    quant_config = None
    if args.use_4bit:
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        quantization_config=quant_config,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    if args.adapter_dir:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.adapter_dir)
    model.eval()
    return model, tokenizer


@torch.no_grad()
def generate_batch(model, tokenizer, list_of_messages, max_new_tokens):
    """chat 메시지 배치를 받아 assistant 응답 문자열 리스트를 반환."""
    prompts = [
        tokenizer.apply_chat_template(
            m, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        for m in list_of_messages
    ]
    enc = tokenizer(prompts, return_tensors="pt", padding=True,
                    truncation=True, max_length=1024).to(model.device)
    out = model.generate(
        **enc,
        max_new_tokens=max_new_tokens,
        do_sample=False,                 # 평가는 greedy 결정론적
        num_beams=1,
        pad_token_id=tokenizer.pad_token_id,
    )
    gen = out[:, enc["input_ids"].shape[1]:]   # 프롬프트 이후 토큰만
    texts = tokenizer.batch_decode(gen, skip_special_tokens=True)
    return [t.strip() for t in texts]


def main():
    args = parse_args()
    os.makedirs(os.path.dirname(args.out_csv) or ".", exist_ok=True)

    examples = build_eval_examples(args.data_dir, args.split)
    if args.limit:
        examples = examples[:args.limit]
    print(f"[eval] {len(examples)} 발화 평가 시작")

    model, tokenizer = load_model_and_tokenizer(args)

    pred_intents, pred_slots = [], []
    gold_intents = [e["gold_intents"] for e in examples]
    gold_slots = [[tuple(s) for s in e["gold_slots"]] for e in examples]
    raw_rows = []

    bs = args.batch_size
    for i in range(0, len(examples), bs):
        chunk = examples[i:i + bs]

        intent_out = generate_batch(
            model, tokenizer, [c["intent_messages"] for c in chunk],
            args.max_new_tokens)
        slot_out = generate_batch(
            model, tokenizer, [c["slot_messages"] for c in chunk],
            args.max_new_tokens)

        for c, io, so in zip(chunk, intent_out, slot_out):
            pi = parse_intent_answer(io)
            ps = parse_slot_answer(so)
            pred_intents.append(pi)
            pred_slots.append(ps)
            raw_rows.append({
                "sentence": c["sentence"],
                "gold_intents": ";".join(c["gold_intents"]),
                "pred_intents": ";".join(pi),
                "gold_slots": ";".join(f"{v}={n}" for v, n in
                                       [tuple(x) for x in c["gold_slots"]]),
                "pred_slots": ";".join(f"{v}={n}" for v, n in ps),
                "intent_raw": io,
                "slot_raw": so,
            })
        print(f"  ...{min(i + bs, len(examples))}/{len(examples)}")

    # --- 메트릭 ---
    i_acc = intent_acc(pred_intents, gold_intents)
    i_p, i_r, i_f1 = micro_f1(pred_intents, gold_intents)
    s_p, s_r, s_f1 = micro_f1(pred_slots, gold_slots)
    o_acc = overall_acc(pred_slots, gold_slots, pred_intents, gold_intents)

    # --- CSV 저장 ---
    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(raw_rows[0].keys()))
        w.writeheader()
        w.writerows(raw_rows)

    print("\n================ MixATIS 평가 결과 ================")
    print(f"  Intent Acc        : {i_acc:.4f}")
    print(f"  Intent F1 (P/R/F1): {i_p:.4f} / {i_r:.4f} / {i_f1:.4f}")
    print(f"  Slot   F1 (P/R/F1): {s_p:.4f} / {s_r:.4f} / {s_f1:.4f}")
    print(f"  Overall(Joint) Acc: {o_acc:.4f}")
    print(f"  per-sample CSV    : {args.out_csv}")
    print("==================================================")


if __name__ == "__main__":
    main()
